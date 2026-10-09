from typing import Dict, Any

CLAIMS_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "type": {"type": "string", "enum": ["FACT", "ABSENCE", "CONFLICT"]},
                    "section": {"type": "string"},
                    "entity": {"type": "string"},
                    "cycle_id": {"type": ["string", "null"]},
                    "field_path": {"type": ["string", "null"]},
                    "conflict_id": {"type": ["string", "null"]},
                    "absence_rule_id": {"type": ["string", "null"]},
                    "value": {},
                    "unit": {"type": ["string", "null"]},
                    "date": {"type": ["string", "null"]},
                    "polarity": {"type": "string", "enum": ["present", "absent"]},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "span": {
                        "type": ["object", "null"],
                        "properties": {
                            "record_id": {"type": "string"},
                            "start": {"type": "integer"},
                            "end": {"type": "integer"},
                        },
                    },
                    "display_text": {"type": "string"},
                },
                "required": ["claim_id", "type", "section", "entity", "display_text"],
            },
        }
    },
    "required": ["claims"],
}


SECTION_PROMPT_DESCRIPTIONS: Dict[str, str] = {
    "profile_diagnosis": "Summarize patient baseline demographics, blood group, BMI, and baseline investigations. For unrecorded baseline tests present in missing_items, emit typed ABSENCE claims.",
    "prior_cycles": "Summarize prior treatment cycles (OI, IUI, IVF, FET) including cycle types, start dates, and outcomes.",
    "protocols_medications": "Summarize medications, stimulation protocols, doses, and routes prescribed during cycles.",
    "follicular_development": "Summarize follicular tracking, endometrial thickness measurements, and hormonal levels (E2, LH, P4).",
    "oocyte_retrieval": "Summarize oocyte retrieval procedures (OPU), total oocytes retrieved, and maturity counts (MII, MI, GV). If an active conflict is listed in conflicts, emit a CONFLICT claim citing both sources.",
    "embryo_details": "Summarize embryos created, morphology grades (Gardner), PGT results, and fate (transferred, frozen, discarded).",
    "outcomes_pregnancy": "Summarize embryo transfers, beta-hCG values, dates, and clinical pregnancy outcomes.",
    "adverse_events": "Summarize recorded adverse events (e.g. OHSS, bleeding), severity, and management.",
    "current_stage": "Summarize the patient's current treatment stage derived from the latest cycle milestone.",
}


def build_system_prompt(section: str) -> str:
    """
    Constructs a rigid, safety-focused system prompt for clinical claim generation.
    """
    desc = SECTION_PROMPT_DESCRIPTIONS.get(section, "Summarize relevant clinical facts.")

    return f"""You are a specialized clinical data extraction assistant generating structured summary claims for the section: '{section}'.

MANDATORY SAFETY AND COMPLIANCE RULES:
1. OUTPUT FORMAT: Output ONLY valid JSON adhering strictly to the provided claims schema: {{"claims": [...]}}. No conversational text, no markdown codeblocks, no tool calls.
2. STRICT DATA GROUNDING: Use ONLY data explicitly provided in the context pack. Do not infer, assume, or extrapolate facts.
3. CITATIONS & FIELD PATHS: Every FACT claim must cite its valid 'source_ids' and 'field_path'.
4. NO CLINICAL RECOMMENDATIONS: NEVER recommend dosing, medications, protocols, next steps, or diagnoses. Do NOT use imperative clinical verbs (e.g., 'should', 'recommend', 'increase', 'administer', 'consider').
5. ABSENCE HANDLING: Use type 'ABSENCE' ONLY for items explicitly enumerated in 'missing_items'. If an item is not in the data and not in 'missing_items', emit NOTHING for it.
6. CONFLICT HANDLING: Use type 'CONFLICT' ONLY for items explicitly provided in 'conflicts'. Report both figures and cite both sources. Never pick one side.
7. DISPLAY TEXT INTEGRITY: Every numeral and date mentioned in 'display_text' must appear verbatim in the claim's 'value', 'date', 'cycle_id', or 'unit'. Never hallucinate numbers.
8. SECTION SCOPE: {desc}
"""
