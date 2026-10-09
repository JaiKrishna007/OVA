"""
Ask-The-Chart Clinical Q&A Service (Kernel Prime'26, SW-01).

Router:
1. Rejection / Refusal: Clinical recommendations (dosing, next steps) or prompt injection overrides.
2. Structured queries: Deterministic database lookup (e.g. E2, oocytes, labs, embryos, baseline)
   rendered as typed verified claims.
3. Open-ended queries: Keyword retrieval over patient notes only (no vector DB needed),
   grounded sentence extraction with exact character span, validated via zero-LLM claim validator.
4. Fallback: If nothing verifiable is found, returns "Not found in records."
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from app.core.scope import Scope
from app.models.patient import Patient
from app.models.cycle import Cycle
from app.models.clinical import (
    StimulationDay,
    TreatmentEvent,
    OocyteRetrieval,
    Embryo,
    Investigation,
    DoctorNote,
    Medication,
)
from app.models.provenance import ClinicalClaim
from app.models.source_record import SourceRecord
from app.models.enums import TreatmentEventKind, EmbryoFate
from app.services.engines.conflicts import detect_conflicts
from app.core.audit import record_audit
from app.services.safety.s1_filter import evaluate_s1_safety, S1Decision
from app.schemas.claims import (
    Claim,
    ClaimType,
    Polarity,
    TextSpan,
    ValidationStatus,
)
from app.services.ai.injection_guard import INJECTION_PATTERNS
from app.services.validator.validator import validate_claim

logger = logging.getLogger(__name__)

FIXED_REFUSAL_MESSAGE = (
    "I can only report what is documented in the patient's records. "
    "I cannot provide clinical recommendations, treatment plans, or dosage decisions."
)

INJECTION_REFUSAL_MESSAGE = (
    "Unable to process question containing instruction override directives. "
    "I can only report factual information documented in the patient's medical records."
)

# Recommendation / prescribing / clinical next-step regex patterns
RECOMMENDATION_PATTERNS = [
    re.compile(r"(?i)\b(?:recommend|recommendation|recommending)\b"),
    re.compile(r"(?i)\b(?:should\s+(?:we|i|she|the\s+doctor|the\s+patient|be\s+done))\b"),
    re.compile(r"(?i)\b(?:what\s+(?:should|ought|next\s+step|would\s+you\s+(?:do|give|suggest|recommend)))\b"),
    re.compile(r"(?i)\b(?:what\s+(?:dose|dosage|medication|protocol)\s+(?:should|to\s+give|to\s+prescribe))\b"),
    re.compile(r"(?i)\b(?:how\s+much\s+(?:dose|dosage|medication|menopur|gonal|rec-fsh)\s+(?:should|to\s+give))\b"),
    re.compile(r"(?i)\b(?:prescribe|prescription|treatment\s+plan\s+(?:advice|suggestion))\b"),
    re.compile(r"(?i)\b(?:suggest|suggestion|advise|advice)\b"),
    re.compile(r"(?i)\b(?:can\s+(?:i|we|she)\s+(?:start|increase|decrease|take|prescribe))\b"),
    re.compile(r"(?i)\b(?:best\s+treatment\s+(?:option|plan|protocol))\b"),
    re.compile(r"(?i)\b(?:propose|proposal|plan\s+of\s+action)\b"),
    re.compile(r"(?i)\b(?:next\s+treatment\s+step)\b"),
]

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "cannot", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "she'd", "she'll", "she's", "should", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "would", "you", "your", "yours",
    "patient", "record", "records", "chart", "notes", "tell", "show", "find", "get", "give",
    # Header metadata words
    "kernel", "prime", "fertility", "clinic", "hospital", "pid", "date", "doctor", "dr", "opd",
    "consultation", "department", "women", "womens",
}


def check_recommendation_request(question: str) -> bool:
    """Detects if question asks for medical advice, dosing changes, or recommendations."""
    for pat in RECOMMENDATION_PATTERNS:
        if pat.search(question):
            return True
    return False


def check_injection_attempt(question: str) -> bool:
    """Detects prompt injection or system instruction override attempts."""
    for pat in INJECTION_PATTERNS:
        if pat.search(question):
            return True
    return False


def extract_cycle_number(question: str) -> Optional[int]:
    """Extracts cycle number from question text like 'Cycle 2', 'cycle #3', 'in cycle 1'."""
    m = re.search(r"(?i)\bcycle\s*(?:#|no\.?|number)?\s*(\d+)\b", question)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def lookup_structured_field(
    db: Session,
    scope: Scope,
    question: str,
) -> Optional[Claim]:
    """
    Performs deterministic database lookup for structured clinical inquiries.
    Returns a verified Claim if found, otherwise None.
    """
    q_lower = question.lower()
    patient_id = scope.patient_id
    cycle_no = extract_cycle_number(question)

    patient_cycles = db.query(Cycle).filter(Cycle.patient_id == patient_id).order_by(Cycle.cycle_no.asc()).all()
    patient_cycle_ids = [c.id for c in patient_cycles]

    target_cycle = None
    if cycle_no:
        target_cycle = next((c for c in patient_cycles if c.cycle_no == cycle_no), None)
        target_cycle_ids = [target_cycle.id] if target_cycle else []
    else:
        target_cycle_ids = patient_cycle_ids

    # 1. Estradiol / E2
    if any(k in q_lower for k in ["e2", "estradiol"]):
        if target_cycle_ids:
            stim_days = (
                db.query(StimulationDay)
                .filter(StimulationDay.cycle_id.in_(target_cycle_ids))
                .order_by(StimulationDay.day_no.desc())
                .all()
            )
            if stim_days:
                target_day = None
                if "trigger" in q_lower:
                    target_day = stim_days[0]  # Latest day of stim
                elif any(k in q_lower for k in ["peak", "highest", "max"]):
                    target_day = max(stim_days, key=lambda d: d.e2 or 0)
                else:
                    target_day = stim_days[0]

                if target_day and target_day.e2 is not None:
                    val = float(target_day.e2)
                    src = target_day.source_id or "REC-UNKNOWN"
                    date_str = target_day.date.isoformat()
                    c_obj = next((c for c in patient_cycles if c.id == target_day.cycle_id), None)
                    c_label = f" in Cycle {c_obj.cycle_no}" if c_obj else ""
                    disp = f"Serum Estradiol (E2){c_label} was {val:.1f} pg/mL on {date_str}."

                    return Claim(
                        claim_id="clm-ask-e2",
                        type=ClaimType.FACT,
                        section="follicular_development",
                        entity="estradiol",
                        cycle_id=target_day.cycle_id,
                        field_path=f"stimulation_days.{target_day.id}.e2",
                        value=val,
                        unit="pg/mL",
                        date=date_str,
                        polarity=Polarity.PRESENT,
                        source_ids=[src],
                        display_text=disp,
                    )

    # 2. Oocytes retrieved / OPU
    if any(k in q_lower for k in ["oocyte", "oocytes", "egg", "eggs", "retrieval", "retrieved", "opu"]):
        if target_cycle_ids:
            opu = (
                db.query(OocyteRetrieval)
                .filter(OocyteRetrieval.cycle_id.in_(target_cycle_ids))
                .order_by(OocyteRetrieval.date.desc())
                .first()
            )
            if opu and opu.oocytes_retrieved is not None:
                val = opu.oocytes_retrieved
                src = opu.source_id or "REC-UNKNOWN"
                date_str = opu.date.isoformat()
                c_obj = next((c for c in patient_cycles if c.id == opu.cycle_id), None)
                c_label = f"Cycle {c_obj.cycle_no} " if c_obj else ""
                field_path = f"oocyte_retrievals.{opu.id}.oocytes_retrieved"

                # Check if this field has an active conflict
                confs = detect_conflicts(db, scope)
                active_conf = next((c for c in confs if c.get("field_path") == field_path or c.get("field") == "oocytes_retrieved" or "OPU" in str(c.get("conflict_id", ""))), None)

                if active_conf:
                    c_num = c_obj.cycle_no if c_obj else 2
                    disp = f"Records show conflicting oocyte counts for Cycle {c_num}: {active_conf.get('value_a')} oocytes in OPU report vs {active_conf.get('value_b')} in discharge summary."
                    return Claim(
                        claim_id="clm-ask-opu-conflict",
                        type=ClaimType.CONFLICT,
                        conflict_id=active_conf["conflict_id"],
                        section="oocyte_retrieval",
                        entity="oocyte_retrieval",
                        cycle_id=opu.cycle_id,
                        field_path=field_path,
                        value=active_conf.get("value_a") or val,
                        polarity=Polarity.PRESENT,
                        source_ids=active_conf.get("source_refs", [src]),
                        display_text=disp,
                    )

                disp = f"{c_label}Oocyte retrieval yielded {val} oocytes on {date_str}."
                return Claim(
                    claim_id="clm-ask-opu",
                    type=ClaimType.FACT,
                    section="oocyte_retrieval",
                    entity="oocyte_retrieval",
                    cycle_id=opu.cycle_id,
                    field_path=field_path,
                    value=val,
                    date=date_str,
                    polarity=Polarity.PRESENT,
                    source_ids=[src],
                    display_text=disp,
                )

    # 3. Lab Investigations (AMH, TSH, Prolactin, FSH, LH, beta-hCG)
    lab_keywords = {
        "amh": ["amh", "anti-mullerian", "anti-müllerian"],
        "tsh": ["tsh", "thyroid"],
        "fsh": ["fsh", "follicle stimulating"],
        "lh": ["lh", "luteinizing"],
        "beta_hcg": ["hcg", "beta-hcg", "beta hcg"],
        "prolactin": ["prolactin"],
    }
    for lab_code, synonyms in lab_keywords.items():
        if any(s in q_lower for s in synonyms):
            invs = (
                db.query(Investigation)
                .filter(Investigation.patient_id == patient_id)
                .order_by(Investigation.date.desc(), Investigation.ordered_date.desc())
                .all()
            )
            matched_inv = None
            for inv in invs:
                inv_name_lower = inv.name.lower()
                if any(s in inv_name_lower for s in synonyms):
                    matched_inv = inv
                    break

            if matched_inv and matched_inv.value is not None:
                raw_val = matched_inv.value
                val: Any = float(raw_val) if raw_val.replace(".", "", 1).isdigit() else raw_val
                unit = matched_inv.unit or ""
                inv_date = matched_inv.date or matched_inv.ordered_date
                date_str = inv_date.isoformat() if inv_date else None
                src = matched_inv.source_id or "REC-UNKNOWN"
                disp = f"{matched_inv.name} was {raw_val} {unit}".strip()
                if date_str:
                    disp += f" on {date_str}."
                else:
                    disp += "."

                return Claim(
                    claim_id=f"clm-ask-{lab_code}",
                    type=ClaimType.FACT,
                    section="profile_diagnosis",
                    entity=lab_code,
                    cycle_id=matched_inv.cycle_id,
                    field_path=f"investigations.{matched_inv.id}.value",
                    value=val,
                    unit=unit if unit else None,
                    date=date_str,
                    polarity=Polarity.PRESENT,
                    source_ids=[src],
                    display_text=disp,
                )

    # 4. Embryos / Cryostorage
    if any(k in q_lower for k in ["embryo", "embryos", "blastocyst", "blastocysts", "frozen", "cryo"]):
        if any(k in q_lower for k in ["frozen", "remaining", "storage", "tank"]):
            frozen_embryos = (
                db.query(Embryo)
                .filter(Embryo.patient_id == patient_id, Embryo.fate == EmbryoFate.FROZEN)
                .all()
            )
            count = len(frozen_embryos)
            src = frozen_embryos[0].source_id if frozen_embryos else "REC-UNKNOWN"
            disp = f"The patient has {count} frozen embryos remaining in cryostorage."
            target_id = frozen_embryos[0].id if frozen_embryos else "none"

            return Claim(
                claim_id="clm-ask-embryos-frozen",
                type=ClaimType.FACT,
                section="embryo_details",
                entity="embryos",
                cycle_id=frozen_embryos[0].cycle_id if frozen_embryos else None,
                field_path=f"embryos.{target_id}.fate" if frozen_embryos else None,
                value="frozen",
                polarity=Polarity.PRESENT,
                source_ids=[src] if frozen_embryos else [],
                display_text=disp,
            )

    # 5. Baseline Demographics (Blood group, BMI, DOB)
    patient = db.get(Patient, patient_id)
    if patient:
        if any(k in q_lower for k in ["blood group", "blood type"]):
            if patient.blood_group:
                src = patient.source_records[0].id if patient.source_records else "REC-UNKNOWN"
                disp = f"Patient blood group is {patient.blood_group}."
                return Claim(
                    claim_id="clm-ask-blood-group",
                    type=ClaimType.FACT,
                    section="profile_diagnosis",
                    entity="blood_group",
                    field_path=f"patients.{patient.id}.blood_group",
                    value=patient.blood_group,
                    polarity=Polarity.PRESENT,
                    source_ids=[src],
                    display_text=disp,
                )

        if "bmi" in q_lower or "body mass index" in q_lower:
            if patient.bmi is not None:
                src = patient.source_records[0].id if patient.source_records else "REC-UNKNOWN"
                disp = f"Patient BMI is {patient.bmi:.1f} kg/m²."
                return Claim(
                    claim_id="clm-ask-bmi",
                    type=ClaimType.FACT,
                    section="profile_diagnosis",
                    entity="bmi",
                    field_path=f"patients.{patient.id}.bmi",
                    value=patient.bmi,
                    unit="kg/m²",
                    polarity=Polarity.PRESENT,
                    source_ids=[src],
                    display_text=disp,
                )

    # 6. Medications / Prescribed Doses (e.g. Gonal-F, Menopur, Cetrorelix, Letrozole, etc.)
    # If the question explicitly asks about notes or consultation, allow it to fall through to note lookup
    is_note_query = any(k in q_lower for k in ["noted", "note", "consultation", "opd", "history"])
    if not is_note_query:
        med_targets = ["gonal", "rec-fsh", "menopur", "cetrorelix", "letrozole", "progesterone", "decapeptyl"]
        has_med_target = any(k in q_lower for k in med_targets)
        is_generic_dose = any(k in q_lower for k in ["dose", "dosage", "medication", "medicine"]) and not any(
            k in q_lower for k in ["eltroxin", "aspirin", "thyroid", "blood"]
        )

        if has_med_target or is_generic_dose:
            query = db.query(Medication)
            if target_cycle_ids:
                query = query.filter(Medication.cycle_id.in_(target_cycle_ids))
            else:
                query = query.join(Cycle, Cycle.id == Medication.cycle_id).filter(Cycle.patient_id == patient_id)

            patient_meds = query.order_by(Medication.start_date.desc()).all()

            matched_med = None
            for med in patient_meds:
                med_name_lower = med.name.lower()
                for target in med_targets:
                    if target in q_lower and target in med_name_lower:
                        matched_med = med
                        break
                if matched_med:
                    break

            if not matched_med and any(k in q_lower for k in ["gonal", "rec-fsh", "fsh"]):
                for med in patient_meds:
                    med_name_lower = med.name.lower()
                    if any(k in med_name_lower for k in ["gonal", "rec-fsh"]):
                        matched_med = med
                        break

            if not matched_med and is_generic_dose and patient_meds:
                matched_med = patient_meds[0]

            if matched_med:
                # Look up corresponding clinical claim id
                c_claim = (
                    db.query(ClinicalClaim)
                    .filter(
                        ClinicalClaim.patient_id == patient_id,
                        ClinicalClaim.materialized_row_id == matched_med.id,
                    )
                    .first()
                )
                claim_id_to_use = c_claim.id if c_claim else f"CLM-MED-{matched_med.id}"
                src = matched_med.source_id or (c_claim.source_record_id if c_claim else "REC-UNKNOWN")

                disp = f"{matched_med.name} dose was {matched_med.dose}."

                return Claim(
                    claim_id=claim_id_to_use,
                    type=ClaimType.FACT,
                    section="stimulation_medications",
                    entity="medication",
                    cycle_id=matched_med.cycle_id,
                    field_path=f"medications.{matched_med.id}.dose",
                    value=matched_med.dose,
                    unit="IU" if "IU" in matched_med.dose else None,
                    polarity=Polarity.PRESENT,
                    source_ids=[src],
                    display_text=disp,
                )

    return None


def extract_keywords(text: str) -> List[str]:
    """Extracts non-stop-word search tokens of length >= 3."""
    words = re.findall(r"[a-zA-Z0-9\-]+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in STOP_WORDS]


def lookup_open_ended_notes(
    db: Session,
    scope: Scope,
    question: str,
) -> Optional[Claim]:
    """
    Performs keyword retrieval over the patient's notes only.
    Extracts the highest-scoring sentence with character span offset,
    and returns a validated Claim.
    """
    patient_id = scope.patient_id
    keywords = extract_keywords(question)
    if not keywords:
        return None

    # Retrieve all clinical source records strictly for this patient
    records = (
        db.query(SourceRecord)
        .filter(SourceRecord.patient_id == patient_id)
        .order_by(SourceRecord.date.desc())
        .all()
    )

    if not records:
        return None

    best_record: Optional[SourceRecord] = None
    best_sentence: Optional[str] = None
    best_span: Optional[Tuple[int, int]] = None
    best_score = 0

    for rec in records:
        content = rec.content_text
        if not content:
            continue

        # Split content by line or period
        for m in re.finditer(r"[^\n\r]+", content):
            line = m.group(0).strip()
            if not line or len(line) < 15:
                continue

            # Split line into sentences if it contains periods
            line_start = m.start()
            sub_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]

            for sub_s in sub_sentences:
                sub_lower = sub_s.lower()
                matched_kw_count = sum(1 for kw in keywords if kw in sub_lower)

                if matched_kw_count > best_score:
                    # Find exact substring span within content
                    s_pos = content.find(sub_s, line_start)
                    if s_pos != -1:
                        best_score = matched_kw_count
                        best_record = rec
                        best_sentence = sub_s
                        best_span = (s_pos, s_pos + len(sub_s))

    if best_score > 0 and best_record and best_sentence and best_span:
        clean_display = " ".join(best_sentence.split())

        # Extract numeric tokens and units if present
        nums = re.findall(r"\b\d+(?:\.\d+)?\b", clean_display)
        num_val: Any = None
        unit_val: Optional[str] = None
        if nums:
            num_val = float(nums[0]) if "." in nums[0] else int(nums[0])
            for u in ["mcg", "mg", "IU", "mm", "pg/mL", "mIU/mL", "uIU/mL", "ng/mL"]:
                if u.lower() in clean_display.lower():
                    unit_val = u
                    break

        # Check if a clinical claim exists for this record
        c_claim = (
            db.query(ClinicalClaim)
            .filter(
                ClinicalClaim.patient_id == patient_id,
                ClinicalClaim.source_record_id == best_record.id,
            )
            .first()
        )
        claim_id_to_use = c_claim.id if c_claim else "clm-ask-note"

        claim = Claim(
            claim_id=claim_id_to_use,
            type=ClaimType.FACT,
            section="notes",
            entity="clinical_note",
            cycle_id=best_record.cycle_id,
            polarity=Polarity.PRESENT,
            source_ids=[best_record.id],
            value=num_val,
            unit=unit_val,
            span=TextSpan(
                record_id=best_record.id,
                start=best_span[0],
                end=best_span[1],
            ),
            display_text=clean_display,
        )

        return claim

    return None


def ask_patient_chart(
    db: Session,
    scope: Scope,
    question: str,
) -> Dict[str, Any]:
    """
    Main Ask-The-Chart entrypoint:
    1. Deterministic S1 safety filter runs BEFORE any retrieval or LLM call.
    2. Structured claims / tables lookup.
    3. Grounded note retrieval over patient notes only.
    """
    q_clean = question.strip()
    patient_id = scope.patient_id

    # 1. Deterministic S1 Safety Filter: Run BEFORE any retrieval or LLM call
    s1_res = evaluate_s1_safety(q_clean)
    if s1_res.decision in (S1Decision.BLOCK, S1Decision.AMBIGUOUS):
        # Create persistent audit entry with event_type S1_BLOCK
        record_audit(
            db,
            user_id=scope.user.id,
            action="ask_question_s1_blocked",
            patient_id=scope.patient_id,
            event_type="S1_BLOCK",
            details={
                "question": q_clean,
                "rule_id": s1_res.rule_id,
                "reason": s1_res.reason,
                "hint": s1_res.hint,
            },
            outcome="blocked",
        )
        return {
            "patient_id": patient_id,
            "question": q_clean,
            "classification": "refusal",
            "status": "BLOCKED_S1",
            "answer": s1_res.message,
            "matched_rule_id": s1_res.rule_id,
            "hint": s1_res.hint,
            "claims": [],
            "citations": [],
            "source_refs": [],
        }

    # Prompt injection boundary defense
    if check_injection_attempt(q_clean):
        record_audit(
            db,
            user_id=scope.user.id,
            action="ask_question_s1_blocked",
            patient_id=scope.patient_id,
            event_type="S1_BLOCK",
            details={"question": q_clean, "rule_id": "S1_BLOCK_PROMPT_INJECTION"},
            outcome="blocked",
        )
        return {
            "patient_id": patient_id,
            "question": q_clean,
            "classification": "refusal",
            "status": "BLOCKED_S1",
            "answer": INJECTION_REFUSAL_MESSAGE,
            "matched_rule_id": "S1_BLOCK_PROMPT_INJECTION",
            "hint": None,
            "claims": [],
            "citations": [],
            "source_refs": [],
        }

    active_conflicts = detect_conflicts(db, scope)

    # 2. Structured question classification and deterministic lookup
    structured_claim = lookup_structured_field(db, scope, q_clean)
    if structured_claim:
        # Run programmatic validator
        validation_res = validate_claim(db, patient_id, structured_claim, active_conflicts=active_conflicts)
        if validation_res.status == ValidationStatus.VERIFIED:
            citations = []
            for sid in structured_claim.source_ids:
                # Find matching clinical claim id if available
                cid = structured_claim.claim_id
                if not cid or cid.startswith("clm-ask-"):
                    real_c = (
                        db.query(ClinicalClaim)
                        .filter(
                            ClinicalClaim.patient_id == patient_id,
                            ClinicalClaim.source_record_id == sid,
                        )
                        .first()
                    )
                    if real_c:
                        cid = real_c.id
                citations.append({
                    "source_id": sid,
                    "type": "record",
                    "claim_id": cid,
                    "field_path": structured_claim.field_path,
                })

            return {
                "patient_id": patient_id,
                "question": q_clean,
                "classification": "structured",
                "status": "answered",
                "answer": structured_claim.display_text,
                "matched_rule_id": s1_res.rule_id,
                "claims": [structured_claim.model_dump()],
                "citations": citations,
                "source_refs": structured_claim.source_ids,
            }
        else:
            logger.info(f"Structured claim blocked by validator: {validation_res.reason_codes}")

    # 3. Open-ended / note content lookup
    note_claim = lookup_open_ended_notes(db, scope, q_clean)
    if note_claim:
        validation_res = validate_claim(db, patient_id, note_claim, active_conflicts=active_conflicts)
        if validation_res.status == ValidationStatus.VERIFIED:
            citations = []
            for sid in note_claim.source_ids:
                cid = note_claim.claim_id
                if not cid or cid.startswith("clm-ask-"):
                    real_c = (
                        db.query(ClinicalClaim)
                        .filter(
                            ClinicalClaim.patient_id == patient_id,
                            ClinicalClaim.source_record_id == sid,
                        )
                        .first()
                    )
                    if real_c:
                        cid = real_c.id
                citations.append({
                    "source_id": sid,
                    "type": "record",
                    "claim_id": cid,
                    "span": (
                        {
                            "start": note_claim.span.start,
                            "end": note_claim.span.end,
                        }
                        if note_claim.span
                        else None
                    ),
                })

            return {
                "patient_id": patient_id,
                "question": q_clean,
                "classification": "open_ended",
                "status": "answered",
                "answer": note_claim.display_text,
                "matched_rule_id": s1_res.rule_id,
                "claims": [note_claim.model_dump()],
                "citations": citations,
                "source_refs": note_claim.source_ids,
            }
        else:
            logger.info(f"Note claim blocked by validator: {validation_res.reason_codes}")

    # 4. Nothing verifiable found
    return {
        "patient_id": patient_id,
        "question": q_clean,
        "classification": "open_ended" if not structured_claim else "structured",
        "status": "not_found",
        "answer": "Not found in records.",
        "matched_rule_id": s1_res.rule_id,
        "claims": [],
        "citations": [],
        "source_refs": [],
    }
