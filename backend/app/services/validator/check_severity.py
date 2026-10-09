from typing import List, Optional
from app.schemas.claims import Claim, ReasonCode
from app.services.validator.resolver import ResolvedField


def check_severity_grade(claim: Claim, resolved_field: Optional[ResolvedField] = None) -> List[ReasonCode]:
    """
    Validates clinical severity levels and embryo morphological grades.
    """
    if not resolved_field or not resolved_field.row:
        return []

    # Adverse events severity check
    if resolved_field.table == "adverse_events":
        actual_severity = getattr(resolved_field.row, "severity", None)
        if actual_severity:
            actual_str = str(actual_severity).strip().lower()
            if resolved_field.column == "severity" and claim.value:
                if str(claim.value).strip().lower() != actual_str:
                    return [ReasonCode.SEVERITY_MISMATCH]
            # Check display_text for contradicting severity keywords
            severities = ["mild", "moderate", "severe"]
            for s in severities:
                if s in claim.display_text.lower() and s != actual_str:
                    return [ReasonCode.SEVERITY_MISMATCH]

    # Embryo grade check
    if resolved_field.table == "embryos" and resolved_field.column == "grade":
        actual_grade = getattr(resolved_field.row, "grade", None)
        if actual_grade and claim.value:
            if str(claim.value).strip().upper() != str(actual_grade).strip().upper():
                return [ReasonCode.SEVERITY_MISMATCH]

    return []
