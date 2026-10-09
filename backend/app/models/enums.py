from enum import Enum


class UserRole(str, Enum):
    DOCTOR = "doctor"
    STAFF = "staff"
    ADMIN = "admin"
    PATIENT = "patient"
    HOSPITAL_ADMIN = "hospital_admin"
    OVA_ADMIN = "ova_admin"


class ClaimValidationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class ExtractionMethod(str, Enum):
    SEED = "seed"
    MOCK = "mock"
    GEMINI = "gemini"
    NVIDIA = "nvidia"


class ConflictStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class GapStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class TransferRequestStatus(str, Enum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HospitalAccessLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    READ_WRITE = "READ_WRITE"


class HospitalAccessStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class SourceProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    VALIDATED = "VALIDATED"
    NEEDS_OCR = "NEEDS_OCR"
    FAILED = "FAILED"


class ConsentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class TrustStatus(str, Enum):
    INTERNAL_VERIFIED = "internal_verified"
    EXTERNAL_UNVERIFIED = "external_unverified"
    EXTERNAL_REVIEWED = "external_reviewed"
    OCR_LOW_CONFIDENCE = "ocr_low_confidence"


class CycleType(str, Enum):
    OI = "OI"
    IUI = "IUI"
    IVF = "IVF"
    ICSI = "ICSI"
    FET = "FET"


class TreatmentEventKind(str, Enum):
    TRIGGER = "trigger"
    OPU = "opu"
    FERTILIZATION_CHECK = "fertilization_check"
    TRANSFER = "transfer"
    BETA_HCG = "beta_hcg"
    SCAN = "scan"
    LOSS = "loss"
    DELIVERY = "delivery"
    CANCEL = "cancel"


class InvestigationCategory(str, Enum):
    LAB = "lab"
    IMAGING = "imaging"
    SEMEN = "semen"
    GENETIC = "genetic"


class InvestigationStatus(str, Enum):
    RESULTED = "resulted"
    PENDING = "pending"


class EmbryoFate(str, Enum):
    TRANSFERRED = "transferred"
    FROZEN = "frozen"
    DISCARDED = "discarded"
    FRESH = "fresh"


class TransferKind(str, Enum):
    FRESH = "fresh"
    FROZEN = "frozen"


class PregnancyResult(str, Enum):
    NEGATIVE = "negative"
    BIOCHEMICAL = "biochemical"
    CLINICAL = "clinical"
    ONGOING = "ongoing"
    LOSS = "loss"
    ECTOPIC = "ectopic"
    LIVE_BIRTH = "live_birth"


class FollowupStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    DONE = "done"
    OVERDUE = "overdue"
