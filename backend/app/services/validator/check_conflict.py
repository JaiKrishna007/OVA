from typing import List, Dict, Any
from app.schemas.claims import Claim, ReasonCode, ClaimType


def check_active_conflict(claim: Claim, active_conflicts: List[Dict[str, Any]]) -> List[ReasonCode]:
    """
    Validates active conflict handling:
    - If a claim is of type CONFLICT, it MUST reference and match an active detected conflict item.
    - If a field or entity is involved in an active conflict, a regular FACT claim on that field is BLOCKED (ACTIVE_CONFLICT).
    - Only a CONFLICT claim that explicitly references the detector conflict item may cite conflicting data.
    """
    if claim.type == ClaimType.CONFLICT:
        if not active_conflicts:
            return [ReasonCode.ACTIVE_CONFLICT]
        
        matching_conflict = None
        for conf in active_conflicts:
            if claim.conflict_id and conf.get("conflict_id") == claim.conflict_id:
                matching_conflict = conf
                break
            if claim.field_path and conf.get("field_path") == claim.field_path:
                matching_conflict = conf
                break
            if claim.cycle_id and conf.get("cycle_id") == claim.cycle_id:
                if "oocyte" in claim.entity.lower() and "OPU" in conf.get("conflict_id", ""):
                    matching_conflict = conf
                    break
        
        if not matching_conflict:
            return [ReasonCode.ACTIVE_CONFLICT]
        
        if claim.conflict_id and claim.conflict_id != matching_conflict.get("conflict_id"):
            return [ReasonCode.ACTIVE_CONFLICT]

        return []

    if not active_conflicts:
        return []

    # Check if a regular (non-CONFLICT) claim's field_path or cycle+entity matches an active conflict
    matching_conflict = None
    for conf in active_conflicts:
        conf_field = conf.get("field", "")
        conf_id = conf.get("conflict_id", "")
        if claim.field_path:
            if conf.get("field_path") == claim.field_path:
                matching_conflict = conf
                break
            if conf_field and (conf_field in claim.field_path or claim.field_path.endswith(f".{conf_field}")):
                matching_conflict = conf
                break


    if matching_conflict:
        # A non-CONFLICT claim on an active conflict field is blocked
        return [ReasonCode.ACTIVE_CONFLICT]

    return []

