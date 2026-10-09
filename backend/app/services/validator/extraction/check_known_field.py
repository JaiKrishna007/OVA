from typing import Set
from app.services.extraction.schemas import CandidateClaim
from app.services.extraction.normalizer import get_normalizer
from app.services.validator.extraction.models import CheckDetail

# Comprehensive known canonical fields
KNOWN_CANONICAL_FIELDS: Set[str] = {
    # Hormones & Labs
    "amh",
    "fsh",
    "lh",
    "estradiol",
    "progesterone",
    "tsh",
    "prolactin",
    "beta_hcg",
    # Follicles & Anatomy
    "endometrial_thickness",
    "antral_follicle_count",
    "right_ovary_follicles",
    "left_ovary_follicles",
    # Embryology Counts
    "oocytes_retrieved",
    "mature_oocytes_mii",
    "fertilized_2pn",
    "blastocysts_count",
    "embryos_created",
    "embryos_frozen",
    "embryos_transferred",
    # Semen Analysis
    "sperm_concentration",
    "progressive_motility",
    "normal_morphology",
    "semen_volume",
    "total_motile_count",
    # Procedures & Treatments
    "procedure",
    "opu",
    "embryo_transfer",
    "fet",
    "iui",
    "oi",
    "trigger",
    "stimulation",
    "medication",
    # Clinical Outcomes
    "pregnancy_test",
    "clinical_pregnancy",
    "fetal_heart_rate",
    "diagnosis",
}


def check_known_field(candidate: CandidateClaim) -> CheckDetail:
    """
    Check 1: Field is a known canonical field or registered synonym.
    Hard check: Failure produces REJECTED with reason FIELD_UNKNOWN.
    """
    normalizer = get_normalizer()
    field_lower = candidate.field.strip().lower()

    from app.services.validator.extraction.check_context_attachment import FIELD_SYNONYMS

    all_synonyms = {syn.lower() for syns in FIELD_SYNONYMS.values() for syn in syns}
    # Check known set or normalizer synonym dictionary
    is_known = (
        field_lower in KNOWN_CANONICAL_FIELDS
        or field_lower in FIELD_SYNONYMS
        or field_lower in all_synonyms
        or field_lower in normalizer._synonym_map
        or candidate.field in normalizer.config.get("fields", {})
        or candidate.field in normalizer.config.get("terms", {})
    )

    if not is_known:
        return CheckDetail(
            name="check_known_field",
            passed=False,
            detail=f"Field '{candidate.field}' is not recognized in canonical clinical terminology dictionary.",
            reason_code="FIELD_UNKNOWN",
            is_hard_check=True,
        )

    return CheckDetail(
        name="check_known_field",
        passed=True,
        detail=f"Field '{candidate.field}' is recognized.",
        reason_code=None,
        is_hard_check=True,
    )
