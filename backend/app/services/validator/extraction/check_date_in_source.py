import re
from datetime import date
from typing import List, Set
from app.services.extraction.schemas import CandidateClaim
from app.services.extraction.normalizer import get_normalizer
from app.services.validator.extraction.models import CheckDetail

# Regex extracting all potential date strings in source documents
SOURCE_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),                                       # 2026-06-14
    re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b"),                             # 14/06/2026, 14-06-2026
    re.compile(r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b", re.IGNORECASE),
    re.compile(r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b"),                                 # 14.06.2026
]


def _extract_all_dates_from_source(source_text: str) -> Set[date]:
    """Finds and parses all date instances present in the raw source text."""
    normalizer = get_normalizer()
    found_dates: Set[date] = set()

    for pattern in SOURCE_DATE_PATTERNS:
        for match in pattern.finditer(source_text):
            parsed, _ = normalizer.normalize_date(match.group(1))
            if parsed:
                found_dates.add(parsed)

    return found_dates


def check_date_in_source(candidate: CandidateClaim, source_text: str) -> CheckDetail:
    """
    Check 4: The claimed date occurs in the source text (compared as parsed dates).
    - If date claimed but does not match any date in source text: hard failure -> REJECTED (DATE_NOT_IN_SOURCE).
    - If date is poorly anchored or has low confidence: soft failure -> FLAGGED (DATE_LOW_CONFIDENCE).
    """
    if not candidate.date:
        return CheckDetail(
            name="check_date_in_source",
            passed=True,
            detail="No specific date attached to candidate claim.",
            reason_code=None,
            is_hard_check=True,
        )

    normalizer = get_normalizer()
    candidate_date, _ = normalizer.normalize_date(candidate.date)
    if not candidate_date:
        return CheckDetail(
            name="check_date_in_source",
            passed=False,
            detail=f"Candidate date '{candidate.date}' could not be parsed into a valid calendar date.",
            reason_code="DATE_INVALID_FORMAT",
            is_hard_check=True,
        )

    # Extract all calendar dates from the source document
    source_dates = _extract_all_dates_from_source(source_text)
    if not source_dates:
        return CheckDetail(
            name="check_date_in_source",
            passed=False,
            detail=f"Source document contains no dates, but claim asserts '{candidate.date}'.",
            reason_code="DATE_NOT_IN_SOURCE",
            is_hard_check=True,
        )

    if candidate_date not in source_dates:
        return CheckDetail(
            name="check_date_in_source",
            passed=False,
            detail=f"Claimed date '{candidate_date.isoformat()}' does not match any date found in source document.",
            reason_code="DATE_NOT_IN_SOURCE",
            is_hard_check=True,
        )

    # Check for low-confidence flag
    if candidate.confidence is not None and candidate.confidence < 0.6:
        return CheckDetail(
            name="check_date_in_source",
            passed=False,
            detail=f"Date '{candidate_date.isoformat()}' confirmed in text but extraction confidence is low ({candidate.confidence}).",
            reason_code="DATE_LOW_CONFIDENCE",
            is_hard_check=False,  # Soft check: triggers FLAGGED
        )

    return CheckDetail(
        name="check_date_in_source",
        passed=True,
        detail=f"Date '{candidate_date.isoformat()}' verified against dates in source document.",
        reason_code=None,
        is_hard_check=True,
    )
