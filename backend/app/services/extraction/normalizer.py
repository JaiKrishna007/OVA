import os
import re
import yaml
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from pydantic import BaseModel

from app.services.extraction.schemas import CandidateClaim

logger = logging.getLogger(__name__)

TERMINOLOGY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "terminology.yaml"


class NormalizedClaimResult(BaseModel):
    """Result of normalizing a candidate claim."""
    canonical_field: str
    canonical_value: Any
    numeric_value: Optional[float] = None
    canonical_unit: Optional[str] = None
    canonical_date: Optional[date] = None
    reason_codes: List[str] = []
    is_valid: bool = True


class Normalizer:
    """
    Config-driven clinical terminology and unit normalizer.
    Guarantees:
    - Normalizes synonyms to canonical terms (e.g. Ovum Pickup -> OPU).
    - Normalizes drug and procedure names.
    - Standardizes unit casing and aliases.
    - NEVER converts values between different units silently. If unit differs
      from canonical allowed units, preserves original value and emits UNIT_AMBIGUOUS.
    - Normalizes diverse date formats (DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY, ISO).
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or TERMINOLOGY_PATH
        self.config: Dict[str, Any] = self._load_config()
        self._synonym_map: Dict[str, str] = {}
        self._build_lookup_tables()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load terminology config from {self.config_path}: {e}")
        return {}

    def _build_lookup_tables(self):
        # Build synonym lookup: lowercase synonym -> canonical term
        terms = self.config.get("terms", {})
        for term_key, term_info in terms.items():
            canonical = term_info.get("canonical", term_key)
            synonyms = term_info.get("synonyms", [])
            for syn in synonyms:
                self._synonym_map[syn.strip().lower()] = canonical
            self._synonym_map[canonical.strip().lower()] = canonical

    def normalize_term(self, term: str) -> str:
        """Translates term or procedure synonym to canonical form."""
        if not term:
            return term
        cleaned = term.strip().lower()
        return self._synonym_map.get(cleaned, term)

    def normalize_drug(self, drug_name: str) -> str:
        """Maps drug variations to canonical capitalization."""
        if not drug_name:
            return drug_name
        cleaned = drug_name.strip().lower()
        drugs_map = self.config.get("drugs", {})
        return drugs_map.get(cleaned, drug_name)

    def normalize_date(self, date_str: Optional[str]) -> Tuple[Optional[date], Optional[str]]:
        """
        Parses dates from various clinical formats into datetime.date and ISO string:
        - DD/MM/YYYY (e.g. 14/06/2026)
        - DD-MM-YYYY (e.g. 14-06-2026)
        - DD Month YYYY (e.g. 15 June 2026, 15 Jun 2026)
        - Month DD, YYYY (e.g. June 15, 2026)
        - YYYY-MM-DD (ISO)
        """
        if not date_str or not isinstance(date_str, str):
            return None, None

        cleaned = date_str.strip()
        # Common clinical date formats
        formats = [
            "%Y-%m-%d",          # 2026-06-14
            "%d/%m/%Y",          # 14/06/2026
            "%d-%m-%Y",          # 14-06-2026
            "%d %B %Y",          # 15 June 2026
            "%d %b %Y",          # 15 Jun 2026
            "%B %d, %Y",         # June 15, 2026
            "%b %d, %Y",         # Jun 15, 2026
            "%d.%m.%Y",          # 14.06.2026
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(cleaned, fmt).date()
                return parsed, parsed.isoformat()
            except ValueError:
                continue

        # Regex fallback for embedded dates e.g. "on 14/06/2026"
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", cleaned)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                parsed = date(year, month, day)
                return parsed, parsed.isoformat()
            except ValueError:
                pass

        return None, None

    def normalize_unit(self, field_name: str, raw_unit: Optional[str]) -> Tuple[Optional[str], List[str]]:
        """
        Normalizes unit casing and validates against field-specific canonical requirements.
        NEVER silently converts values between disparate units.
        If raw_unit differs from canonical or allowed units, returns original unit and emits UNIT_AMBIGUOUS.
        """
        reason_codes: List[str] = []
        if not raw_unit:
            return None, reason_codes

        cleaned_unit = raw_unit.strip()
        lower_unit = cleaned_unit.lower()

        # Check standard casing dictionary
        unit_casing_map = self.config.get("unit_casing", {})
        standardized_unit = unit_casing_map.get(lower_unit, cleaned_unit)

        # Retrieve field config
        field_key = field_name.strip().lower()
        fields_config = self.config.get("fields", {})
        field_meta = fields_config.get(field_key)

        if field_meta:
            canonical_unit = field_meta.get("canonical_unit")
            allowed_units = [u.lower() for u in field_meta.get("allowed_units", [])]

            if canonical_unit:
                # Check if unit is among allowed units
                if lower_unit in allowed_units or standardized_unit.lower() == canonical_unit.lower():
                    return canonical_unit, reason_codes
                else:
                    # Incompatible unit for this clinical field (e.g. pmol/L for AMH, nmol/L for P4)
                    # KEEP original and emit UNIT_AMBIGUOUS
                    reason_codes.append("UNIT_AMBIGUOUS")
                    return cleaned_unit, reason_codes

        return standardized_unit, reason_codes

    def normalize_claim(self, claim: CandidateClaim) -> NormalizedClaimResult:
        """
        Executes end-to-end normalization of a candidate claim.
        """
        reason_codes: List[str] = []

        # 1. Canonicalize field name and term
        raw_field = claim.field.strip().lower()
        # Aliases
        field_alias_map = {
            "serum amh": "amh",
            "anti mullerian hormone": "amh",
            "serum estradiol": "estradiol",
            "e2": "estradiol",
            "serum progesterone": "progesterone",
            "p4": "progesterone",
            "beta hcg": "beta_hcg",
            "b-hcg": "beta_hcg",
            "betahcg": "beta_hcg",
            "oocytes": "oocytes_retrieved",
            "eggs": "oocytes_retrieved",
            "total oocytes": "oocytes_retrieved",
            "mii": "mature_oocytes_mii",
            "2pn": "fertilized_2pn",
            "blastocysts": "blastocysts_count",
            "sperm count": "sperm_concentration",
            "pr motility": "progressive_motility",
            "morphology": "normal_morphology",
            "endometrium": "endometrial_thickness",
        }
        canonical_field = field_alias_map.get(raw_field, raw_field)

        # 2. Canonicalize value (for procedures or categorical values)
        raw_val = claim.value
        canonical_val = raw_val
        numeric_val: Optional[float] = None

        if isinstance(raw_val, str):
            # Try procedure canonicalization
            canonical_val = self.normalize_term(raw_val)
            # Try drug canonicalization
            canonical_val = self.normalize_drug(canonical_val)

            # Try numeric parsing
            try:
                # Remove commata
                clean_num_str = re.sub(r"[^\d.]", "", raw_val)
                if clean_num_str:
                    numeric_val = float(clean_num_str)
            except (ValueError, TypeError):
                pass
        elif isinstance(raw_val, (int, float)):
            numeric_val = float(raw_val)

        # 3. Canonicalize unit
        canonical_unit, unit_reasons = self.normalize_unit(canonical_field, claim.unit)
        if unit_reasons:
            reason_codes.extend(unit_reasons)

        # 4. Canonicalize date
        parsed_date, _ = self.normalize_date(claim.date)

        return NormalizedClaimResult(
            canonical_field=canonical_field,
            canonical_value=canonical_val,
            numeric_value=numeric_val,
            canonical_unit=canonical_unit,
            canonical_date=parsed_date,
            reason_codes=reason_codes,
            is_valid=("UNIT_AMBIGUOUS" not in reason_codes),
        )


_normalizer_instance: Optional[Normalizer] = None


def get_normalizer() -> Normalizer:
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = Normalizer()
    return _normalizer_instance
