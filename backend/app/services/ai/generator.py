import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.scope import Scope
from app.schemas.claims import Claim, SectionValidationResult
from app.services.validator.validator import validate_claims
from app.services.ai.context_pack import build_section_context_pack
from app.services.ai.injection_guard import guard_context_pack
from app.services.ai.prompts import build_system_prompt, CLAIMS_JSON_SCHEMA
from app.services.ai.llm.base import LLMClient
from app.services.ai.llm import get_llm_client

logger = logging.getLogger(__name__)


class SectionGenerationResult:
    def __init__(
        self,
        section: str,
        claims: List[Claim],
        validation_result: SectionValidationResult,
        guard_flag: bool = False,
        guard_events: Optional[List[Dict[str, Any]]] = None,
        context_pack: Optional[Dict[str, Any]] = None,
    ):
        self.section = section
        self.claims = claims
        self.validation_result = validation_result
        self.guard_flag = guard_flag
        self.guard_events = guard_events or []
        self.context_pack = context_pack or {}


def generate_and_validate_section(
    db: Session,
    scope: Scope,
    section: str,
    llm_client: Optional[LLMClient] = None,
    all_conflicts: Optional[List[Dict[str, Any]]] = None,
    all_missing: Optional[List[Dict[str, Any]]] = None,
) -> SectionGenerationResult:
    """
    Executes the generation and validation lifecycle for a single section:
    1. Builds scoped context pack.
    2. Applies prompt injection defenses.
    3. Calls LLM with strict JSON schema.
    4. Parses claims and validates deterministically via Programmatic Validator.
    """
    if llm_client is None:
        llm_client = get_llm_client()

    raw_pack = build_section_context_pack(
        db,
        scope,
        section,
        all_conflicts=all_conflicts,
        all_missing=all_missing,
    )

    guarded_pack, guard_flag, guard_events = guard_context_pack(raw_pack)

    system_prompt = build_system_prompt(section)
    user_payload = json.dumps(guarded_pack, default=str)

    try:
        response_dict = llm_client.generate_json(
            system=system_prompt,
            user=user_payload,
            schema=CLAIMS_JSON_SCHEMA,
        )
    except Exception as e:
        logger.error(f"LLM call failed for section '{section}': {e}")
        # Return empty claims to trigger retry or fallback
        empty_val = SectionValidationResult(
            section=section,
            total_claims=0,
            verified_claims=0,
            blocked_claims=0,
            blocked_ratio=0.0,
            results=[],
        )
        return SectionGenerationResult(
            section=section,
            claims=[],
            validation_result=empty_val,
            guard_flag=guard_flag,
            guard_events=guard_events,
            context_pack=guarded_pack,
        )

    raw_claims = response_dict.get("claims", [])
    claims: List[Claim] = []
    for item in raw_claims:
        try:
            # Ensure section field matches target section
            item["section"] = section
            claim = Claim.model_validate(item)
            claims.append(claim)
        except Exception as ve:
            logger.warning(f"Discarding invalid claim schema in section '{section}': {ve}")

    val_report = validate_claims(
        db,
        scope.patient_id,  # type: ignore
        claims,
        scope=scope,
    )
    val_result = val_report.sections.get(
        section,
        SectionValidationResult(
            section=section,
            total_claims=len(claims),
            verified_claims=0,
            blocked_claims=len(claims),
            blocked_ratio=1.0 if claims else 0.0,
            results=[],
        ),
    )

    return SectionGenerationResult(
        section=section,
        claims=claims,
        validation_result=val_result,
        guard_flag=guard_flag,
        guard_events=guard_events,
        context_pack=guarded_pack,
    )
