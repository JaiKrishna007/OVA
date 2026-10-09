import re
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings
from app.services.ai.injection_guard import sanitize_string, guard_note_text
from app.services.ai.llm.base import LLMClient
from app.services.ai.llm import get_llm_client
from app.services.extraction.schemas import (
    CandidateClaim,
    CandidateClaimsResponse,
    ExtractionResult,
    Span,
    CANDIDATE_CLAIMS_JSON_SCHEMA,
)

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """Abstract interface for extracting candidate clinical claims from document text."""

    name: str = "base"

    @abstractmethod
    def extract(self, record_id: str, text: str) -> ExtractionResult:
        """
        Extracts candidate claims from raw text.
        Must enforce temperature=0, JSON schema, and prompt injection defense.
        """
        pass


class MockExtractor(BaseExtractor):
    """
    Deterministic regex and rule-based extractor for high-precision clinical entity extraction.
    Covers:
    - Labs: AMH, FSH, LH, E2, P4, TSH, PRL, beta-hCG
    - Procedures: OPU, embryo transfer (ET/FET), IUI, stimulation, trigger
    - Medications with doses (e.g. Gonal-F, Menopur, Cetrotide, Ovitrelle)
    - Embryology counts (oocytes, MII, 2PN, blastocysts)
    - Semen parameters (concentration, motility, morphology, volume)
    - Diverse date formats (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY, ISO)
    - Strict span grounding: text[span.start:span.end] == evidence_text
    """

    name: str = "mock"

    def __init__(self):
        # Comprehensive date pattern matching (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY, Month DD YYYY, ISO)
        self.date_regex = re.compile(
            r"\b(?:"
            r"(?:\d{4}-\d{2}-\d{2})"
            r"|(?:\d{1,2}[/-]\d{1,2}[/-]\d{4})"
            r"|(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})"
            r"|(?:\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})"
            r")\b",
            re.IGNORECASE,
        )

    def _find_nearest_date(self, text: str, pos: int) -> Optional[str]:
        """Finds date mentioned closest to the match offset in the same line or section."""
        # Find all dates in text
        matches = list(self.date_regex.finditer(text))
        if not matches:
            return None

        # Return the date closest to match position
        closest = min(matches, key=lambda m: abs(m.start() - pos))
        # Ensure within reasonable proximity (e.g. 300 chars)
        if abs(closest.start() - pos) < 400:
            return closest.group(0)
        return None

    def extract(self, record_id: str, text: str) -> ExtractionResult:
        if not text:
            return ExtractionResult(record_id=record_id, raw_text="")

        # 1. Reuse existing prompt injection guard
        sanitized_text, has_injection, guard_events = sanitize_string(
            text, context_label=f"record:{record_id}"
        )
        if has_injection:
            logger.warning(f"MockExtractor: prompt injection pattern detected in record {record_id}. Emitting 0 claims.")
            return ExtractionResult(
                record_id=record_id,
                claims=[],
                has_injection=True,
                guard_events=guard_events,
                raw_text=text,
            )

        claims: List[CandidateClaim] = []

        # 2. Lab extractions
        # AMH
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?AMH\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(ng\/m[lL]|pmol\/[lL]|pg\/m[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "ng/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="amh",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # FSH
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?FSH\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(mIU\/m[lL]|IU\/[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "mIU/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="fsh",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # LH
        for m in re.finditer(
            r"(?i)\bLH\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(mIU\/m[lL]|IU\/[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "mIU/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="lh",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # Estradiol / E2
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?(?:Estradiol|E2)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(pg\/m[lL]|pmol\/[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "pg/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="estradiol",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # Progesterone / P4
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?(?:Progesterone|P4)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(ng\/m[lL]|nmol\/[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "ng/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="progesterone",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # TSH
        for m in re.finditer(
            r"(?i)\bTSH\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(mIU\/[lL]|uIU\/m[lL]|mIU\/m[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "mIU/L"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="tsh",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # Prolactin / PRL
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?(?:Prolactin|PRL)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(ng\/m[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "ng/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="prolactin",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # beta-hCG
        for m in re.finditer(
            r"(?i)\b(?:Serum\s+)?(?:Beta[- ]?hCG|b-hCG)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(mIU\/m[lL]|IU\/[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "mIU/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="beta_hcg",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.98,
                )
            )

        # Endometrial thickness
        for m in re.finditer(
            r"(?i)\b(?:Endometrium|Endometrial\s+thickness|ET)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(mm)\b",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="endometrial_thickness",
                    value=val,
                    unit="mm",
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.95,
                )
            )

        # 3. Procedures
        # OPU / Ovum Pickup / Oocyte Retrieval / Egg Retrieval
        for m in re.finditer(
            r"(?i)\b(OPU|Ovum\s+Pickup|Ovum\s+Pick\s+Up|Oocyte\s+Retrieval|Egg\s+Retrieval)\b",
            text,
        ):
            evidence = m.group(0)
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="procedure",
                    value=evidence,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.99,
                )
            )

        # Embryo Transfer / ET / FET
        for m in re.finditer(
            r"(?i)\b(Embryo\s+Transfer|Fresh\s+Embryo\s+Transfer|Frozen\s+Embryo\s+Transfer|FET|\bET\b)\b",
            text,
        ):
            # Avoid matching ET if it was endometrial thickness
            start_idx = max(0, m.start() - 20)
            context_window = text[start_idx:m.end() + 20].lower()
            if "thickness" in context_window or " mm" in context_window:
                continue

            evidence = m.group(0)
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="procedure",
                    value=evidence,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.99,
                )
            )

        # IUI
        for m in re.finditer(
            r"(?i)\b(Intrauterine\s+Insemination|IUI)\b",
            text,
        ):
            evidence = m.group(0)
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="procedure",
                    value=evidence,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.99,
                )
            )

        # Trigger
        for m in re.finditer(
            r"(?i)\b(Trigger\s+Injection|Ovulation\s+Trigger|hCG\s+Trigger|Lupron\s+Trigger|Dual\s+Trigger|\bTrigger\b)\b",
            text,
        ):
            evidence = m.group(0)
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="procedure",
                    value=evidence,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.95,
                )
            )

        # 4. Medications with doses
        for m in re.finditer(
            r"(?i)\b(Gonal[- ]?F|Menopur|Cetrotide|Ovitrelle|Duphaston|Progynova|Lupron|Decapeptyl)\b(?:\s+([0-9]+(?:\.[0-9]+)?)\s*(IU|mg|mcg))?",
            text,
        ):
            evidence = m.group(0)
            drug = m.group(1)
            dose_val = float(m.group(2)) if m.group(2) else None
            dose_unit = m.group(3) if m.group(3) else None
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="medication",
                    value=drug if dose_val is None else f"{drug} {dose_val}",
                    unit=dose_unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.95,
                )
            )

        # 5. Embryology Counts
        # Oocytes retrieved
        for m in re.finditer(
            r"(?i)\b([0-9]+)\s*(?:oocytes|eggs)\s*(?:retrieved|collected|obtained)?\b",
            text,
        ):
            evidence = m.group(0)
            count = int(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="oocytes_retrieved",
                    value=count,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.96,
                )
            )

        # MII mature oocytes
        for m in re.finditer(
            r"(?i)\b([0-9]+)\s*(?:MII|mature\s+oocytes)\b",
            text,
        ):
            evidence = m.group(0)
            count = int(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="mature_oocytes_mii",
                    value=count,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.96,
                )
            )

        # Fertilized 2PN
        for m in re.finditer(
            r"(?i)\b([0-9]+)\s*(?:fertilized|2PN|two\s+pronuclei)\b",
            text,
        ):
            evidence = m.group(0)
            count = int(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="fertilized_2pn",
                    value=count,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.96,
                )
            )

        # Blastocysts count
        for m in re.finditer(
            r"(?i)\b([0-9]+)\s*(?:blastocysts?|Day\s*5\s*embryos?)\b",
            text,
        ):
            evidence = m.group(0)
            count = int(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="blastocysts_count",
                    value=count,
                    unit=None,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.96,
                )
            )

        # 6. Semen Parameters
        # Concentration
        for m in re.finditer(
            r"(?i)\b(?:Sperm\s+concentration|Sperm\s+count)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(M\/m[lL]|million\/m[lL]|10\^6\/m[lL])?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            unit = m.group(2) or "M/mL"
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="sperm_concentration",
                    value=val,
                    unit=unit,
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.97,
                )
            )

        # Progressive motility
        for m in re.finditer(
            r"(?i)\b(?:Progressive\s+motility|PR\s+motility|Motility)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(%)?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="progressive_motility",
                    value=val,
                    unit="%",
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.97,
                )
            )

        # Normal morphology
        for m in re.finditer(
            r"(?i)\b(?:Normal\s+morphology|Morphology)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(%)?",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="normal_morphology",
                    value=val,
                    unit="%",
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.97,
                )
            )

        # Semen volume
        for m in re.finditer(
            r"(?i)\b(?:Semen\s+volume|Volume)\b(?:\s*[:=-]|\s+is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(m[lL])\b",
            text,
        ):
            evidence = m.group(0)
            val = float(m.group(1))
            dt = self._find_nearest_date(text, m.start())
            claims.append(
                CandidateClaim(
                    field="semen_volume",
                    value=val,
                    unit="mL",
                    date=dt,
                    evidence_text=evidence,
                    span=Span(start=m.start(), end=m.end()),
                    confidence=0.97,
                )
            )

        return ExtractionResult(
            record_id=record_id,
            claims=claims,
            has_injection=False,
            raw_text=text,
        )


class GeminiExtractor(BaseExtractor):
    """
    LLM-driven extractor utilizing Google Gemini via LLMClient.
    Wraps document text in untrusted data boundaries, defends against prompt injections,
    enforces temperature=0, and uses strict JSON schema.
    """

    name: str = "gemini"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()

    def extract(self, record_id: str, text: str) -> ExtractionResult:
        if not text:
            return ExtractionResult(record_id=record_id, raw_text="")

        # 1. Reuse existing prompt injection guard
        sanitized_text, has_injection, guard_events = sanitize_string(
            text, context_label=f"record:{record_id}"
        )
        if has_injection:
            logger.warning(f"GeminiExtractor: prompt injection pattern detected in record {record_id}.")
            return ExtractionResult(
                record_id=record_id,
                claims=[],
                has_injection=True,
                guard_events=guard_events,
                raw_text=text,
            )

        system_prompt = (
            "You are an expert clinical data extraction system for fertility EMR documents.\n"
            "Your task is to extract candidate clinical claims from the provided document text.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output ONLY a valid JSON object matching the provided schema with a 'claims' array.\n"
            "2. For each claim, you MUST provide:\n"
            "   - 'field': The clinical entity (e.g. amh, fsh, lh, estradiol, progesterone, tsh, beta_hcg, opu, embryo_transfer, medication, oocytes_retrieved, sperm_concentration, progressive_motility).\n"
            "   - 'value': The exact extracted value or entity name.\n"
            "   - 'unit': The extracted unit (e.g. ng/mL, pg/mL, mIU/mL, IU, mg) or null.\n"
            "   - 'date': The relevant date mentioned for this finding in ISO YYYY-MM-DD or original format, or null.\n"
            "   - 'evidence_text': The EXACT substring from the document supporting this claim.\n"
            "   - 'span': An object with 'start' and 'end' character offsets where 'evidence_text' is located in the raw document.\n"
            "3. NO hallucinations. Every claim must have an exact evidence span in the document.\n"
            "4. NEVER output explanations, markdown formatting, or tool calls."
        )

        guarded_payload = (
            f'<untrusted_clinical_data record_id="{record_id}">\n'
            f'{sanitized_text}\n'
            f'</untrusted_clinical_data>'
        )

        try:
            res_dict = self.llm_client.generate_json(
                system=system_prompt,
                user=guarded_payload,
                schema=CANDIDATE_CLAIMS_JSON_SCHEMA,
            )
        except Exception as e:
            logger.error(f"GeminiExtractor failed for record {record_id}: {e}")
            return ExtractionResult(
                record_id=record_id,
                claims=[],
                warnings=[f"LLM extraction error: {e}"],
                raw_text=text,
            )

        raw_claims = res_dict.get("claims", [])
        validated_claims: List[CandidateClaim] = []

        for item in raw_claims:
            try:
                candidate = CandidateClaim.model_validate(item)
                # Verify that span matches text; if slightly misaligned, attempt to ground in text
                expected_sub = text[candidate.span.start:candidate.span.end]
                if expected_sub != candidate.evidence_text:
                    # Attempt exact substring locate
                    found_idx = text.find(candidate.evidence_text)
                    if found_idx != -1:
                        candidate.span = Span(start=found_idx, end=found_idx + len(candidate.evidence_text))

                validated_claims.append(candidate)
            except Exception as e:
                logger.debug(f"Invalid candidate claim item skipped: {e}")

        return ExtractionResult(
            record_id=record_id,
            claims=validated_claims,
            has_injection=False,
            raw_text=text,
        )


def get_extractor() -> BaseExtractor:
    """Factory selecting extractor based on configured LLM_PROVIDER."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        try:
            return GeminiExtractor()
        except Exception as e:
            logger.warning(f"Failed to instantiate GeminiExtractor ({e}), falling back to MockExtractor.")
            return MockExtractor()
    return MockExtractor()
