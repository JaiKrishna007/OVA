import re
from typing import List, Dict, Optional, Set
from app.services.extraction.schemas import CandidateClaim
from app.services.extraction.normalizer import get_normalizer
from app.services.validator.extraction.models import CheckDetail

# Competitor fields in the hormonal lab group
LAB_COMPETITOR_GROUPS = {
    "amh": ["fsh", "lh", "estradiol", "progesterone", "tsh", "prolactin", "beta_hcg"],
    "fsh": ["amh", "lh", "estradiol", "progesterone", "tsh", "prolactin", "beta_hcg"],
    "lh": ["amh", "fsh", "estradiol", "progesterone", "tsh", "prolactin", "beta_hcg"],
    "estradiol": ["amh", "fsh", "lh", "progesterone", "tsh", "prolactin", "beta_hcg"],
    "progesterone": ["amh", "fsh", "lh", "estradiol", "tsh", "prolactin", "beta_hcg"],
    "tsh": ["amh", "fsh", "lh", "estradiol", "progesterone", "prolactin", "beta_hcg"],
    "prolactin": ["amh", "fsh", "lh", "estradiol", "progesterone", "tsh", "beta_hcg"],
    "beta_hcg": ["amh", "fsh", "lh", "estradiol", "progesterone", "tsh", "prolactin"],
}

# Synonyms for context matching
FIELD_SYNONYMS: Dict[str, List[str]] = {
    "amh": ["amh", "anti-mullerian", "anti mullerian", "anti-mullerian hormone", "anti mullerian hormone", "serum amh"],
    "fsh": ["fsh", "follicle stimulating hormone", "serum fsh"],
    "lh": ["lh", "luteinizing hormone", "serum lh"],
    "estradiol": ["estradiol", "e2", "serum estradiol", "oestradiol"],
    "progesterone": ["progesterone", "p4", "serum progesterone"],
    "tsh": ["tsh", "thyroid stimulating hormone"],
    "prolactin": ["prolactin", "prl", "serum prolactin"],
    "beta_hcg": ["beta-hcg", "beta hcg", "b-hcg", "bhcg", "hcg"],
    "oocytes_retrieved": ["oocytes", "eggs", "retrieved", "collected", "oocyte"],
    "mature_oocytes_mii": ["mii", "mature oocytes", "mature eggs", "metaphase ii"],
    "fertilized_2pn": ["2pn", "fertilized", "fertilised", "two pronuclei"],
    "blastocysts_count": ["blastocysts", "blastocyst", "day 5", "blast"],
    "sperm_concentration": ["concentration", "count", "sperm", "sperm count"],
    "progressive_motility": ["progressive motility", "motility", "pr motility", "pr"],
    "normal_morphology": ["normal morphology", "morphology"],
    "semen_volume": ["volume", "semen volume"],
    "endometrial_thickness": ["endometrium", "endometrial thickness", "thickness", "et"],
    "opu": ["opu", "ovum pickup", "ovum pick up", "oocyte retrieval", "egg retrieval"],
    "embryo_transfer": ["embryo transfer", "et", "fresh transfer", "transfer"],
    "fet": ["fet", "frozen embryo transfer", "frozen transfer"],
    "iui": ["iui", "intrauterine insemination"],
    "oi": ["oi", "ovulation induction"],
    "trigger": ["trigger", "hCG trigger", "lupron trigger", "dual trigger"],
}


def check_context_attachment(
    candidate: CandidateClaim,
    source_text: str,
    window_chars: int = 100,
) -> CheckDetail:
    """
    Check 6: The claimed value is attached to the claimed field in surrounding context.
    - Inspects the window preceding the value/span in the source text.
    - Verifies that the field name or a known synonym appears before the value.
    - Rejects if a competing field appears closer to the value than the claimed field (CONTEXT_MISMATCH).
    Hard check: Failure produces REJECTED.
    """
    field_key = candidate.field.strip().lower()

    # Determine window preceding span
    span_start = candidate.span.start
    win_start = max(0, span_start - window_chars)
    # The context window includes text preceding the span plus the start of evidence
    context_window = source_text[win_start:candidate.span.end].lower()

    # 1. Get synonyms for the claimed field
    normalizer = get_normalizer()
    synonyms = list(FIELD_SYNONYMS.get(field_key, [field_key]))
    # Add terms from terminology.yaml
    term_cfg = normalizer.config.get("terms", {}).get(field_key.upper())
    if term_cfg:
        synonyms.extend([s.lower() for s in term_cfg.get("synonyms", [])])

    # Check if claimed field or synonym appears in the context window
    field_matched = False
    field_pos = -1
    for syn in synonyms:
        idx = context_window.rfind(syn.lower())
        if idx != -1 and idx > field_pos:
            field_matched = True
            field_pos = idx

    # If field or synonym is completely absent in preceding context and evidence
    if not field_matched:
        return CheckDetail(
            name="check_context_attachment",
            passed=False,
            detail=f"Claimed field '{candidate.field}' or its synonyms do not appear in the context preceding value '{candidate.value}'.",
            reason_code="CONTEXT_MISMATCH",
            is_hard_check=True,
        )

    # 2. Competitor check: Does a competitor field appear CLOSER to the value?
    competitors = LAB_COMPETITOR_GROUPS.get(field_key, [])
    for comp in competitors:
        comp_synonyms = FIELD_SYNONYMS.get(comp, [comp])
        for csyn in comp_synonyms:
            comp_idx = context_window.rfind(csyn.lower())
            if comp_idx != -1 and comp_idx > field_pos:
                # Competitor appears closer to the value than the claimed field!
                # e.g. "AMH was 4.2 ng/mL, FSH was 2.4 mIU/mL" -> value 2.4 is attached to FSH, not AMH
                return CheckDetail(
                    name="check_context_attachment",
                    passed=False,
                    detail=f"Context mismatch: competing field '{comp}' ('{csyn}') appears closer to value '{candidate.value}' than claimed field '{candidate.field}'.",
                    reason_code="CONTEXT_MISMATCH",
                    is_hard_check=True,
                )

    return CheckDetail(
        name="check_context_attachment",
        passed=True,
        detail=f"Field '{candidate.field}' correctly attached in preceding context window.",
        reason_code=None,
        is_hard_check=True,
    )
