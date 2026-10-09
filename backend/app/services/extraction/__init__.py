from app.services.extraction.schemas import (
    Span,
    CandidateClaim,
    CandidateClaimsResponse,
    ExtractionResult,
    CANDIDATE_CLAIMS_JSON_SCHEMA,
)
from app.services.extraction.normalizer import (
    Normalizer,
    NormalizedClaimResult,
    get_normalizer,
)
from app.services.extraction.extractors import (
    BaseExtractor,
    MockExtractor,
    GeminiExtractor,
    get_extractor,
)
from app.services.extraction.pipeline import (
    process_record,
    validate_candidate_claim,
)

__all__ = [
    "Span",
    "CandidateClaim",
    "CandidateClaimsResponse",
    "ExtractionResult",
    "CANDIDATE_CLAIMS_JSON_SCHEMA",
    "Normalizer",
    "NormalizedClaimResult",
    "get_normalizer",
    "BaseExtractor",
    "MockExtractor",
    "GeminiExtractor",
    "get_extractor",
    "process_record",
    "validate_candidate_claim",
]
