import json
from typing import Dict, Any, Optional, List
from app.services.ai.llm.base import LLMClient
from app.schemas.claims import ClaimType, Polarity


class MockLLM(LLMClient):
    """
    Deterministic LLM provider that generates valid typed claims directly
    from the provided context pack without requiring an external API key.
    Configurable to emit bad claims to simulate failures and test degraded fallback.
    """

    def __init__(self, bad_claim_ratio: float = 0.0, simulate_error: bool = False):
        self.bad_claim_ratio = bad_claim_ratio
        self.simulate_error = simulate_error

    def generate_json(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.simulate_error:
            raise RuntimeError("Simulated LLM service timeout / network failure")

        try:
            pack = json.loads(user)
        except Exception:
            pack = {}

        section = pack.get("section", "general")
        patient_id = pack.get("patient_id", "")
        structured_rows = pack.get("structured_rows", [])
        notes = pack.get("notes", [])
        conflicts = pack.get("conflicts", [])
        missing_items = pack.get("missing_items", [])
        spans = pack.get("spans", [])

        # Map conflict field paths
        conflict_map = {c.get("field_path"): c for c in conflicts if c.get("field_path")}

        claims: List[Dict[str, Any]] = []

        # 1. Generate claims from structured rows
        for i, row in enumerate(structured_rows):
            fpath = row.get("field_path")
            cid = f"c_{section}_{i+1}"
            cycle_id = row.get("cycle_id")
            source_id = row.get("source_id")
            sources = [source_id] if source_id else []

            # Check if this field has an active conflict
            if fpath and fpath in conflict_map:
                conf = conflict_map[fpath]
                claims.append({
                    "claim_id": cid,
                    "type": ClaimType.CONFLICT.value,
                    "section": section,
                    "entity": row.get("table", "clinical"),
                    "cycle_id": cycle_id,
                    "field_path": fpath,
                    "conflict_id": conf.get("id"),
                    "value": str(conf.get("value_a", row.get("value"))),
                    "unit": row.get("unit"),
                    "date": row.get("date"),
                    "polarity": Polarity.PRESENT.value,
                    "source_ids": conf.get("source_ids", sources),
                    "span": None,
                    "display_text": conf.get("description", f"Conflict noted on {row.get('column')}."),
                })
            else:
                col_name = str(row.get("column", "item")).replace("_", " ")
                val = row.get("value")
                unit_str = f" {row.get('unit')}" if row.get("unit") else ""
                claims.append({
                    "claim_id": cid,
                    "type": ClaimType.FACT.value,
                    "section": section,
                    "entity": row.get("table", "clinical"),
                    "cycle_id": cycle_id,
                    "field_path": fpath,
                    "conflict_id": None,
                    "value": val,
                    "unit": row.get("unit"),
                    "date": row.get("date"),
                    "polarity": Polarity.PRESENT.value,
                    "source_ids": sources,
                    "span": None,
                    "display_text": f"{col_name.capitalize()} was {val}{unit_str}.",
                })

        # 2. Generate ABSENCE claims from missing items
        for j, miss in enumerate(missing_items):
            item_name = miss.get("item", "item")
            rule_id = miss.get("rule_id", "RULE_UNKNOWN")
            claims.append({
                "claim_id": f"c_{section}_abs_{j+1}",
                "type": ClaimType.ABSENCE.value,
                "section": section,
                "entity": "clinical_investigation",
                "cycle_id": None,
                "field_path": None,
                "absence_rule_id": rule_id,
                "conflict_id": None,
                "value": item_name,
                "unit": None,
                "date": None,
                "polarity": Polarity.ABSENT.value,
                "source_ids": [],
                "span": None,
                "display_text": f"{item_name} is not documented in records.",
            })

        # 3. Generate note-derived claims if spans are provided
        for k, sp in enumerate(spans):
            claims.append({
                "claim_id": f"c_{section}_span_{k+1}",
                "type": ClaimType.FACT.value,
                "section": section,
                "entity": "doctor_note",
                "cycle_id": sp.get("cycle_id"),
                "field_path": None,
                "conflict_id": None,
                "value": sp.get("text"),
                "unit": None,
                "date": sp.get("date"),
                "polarity": Polarity.PRESENT.value,
                "source_ids": [sp.get("record_id")],
                "span": {
                    "record_id": sp.get("record_id"),
                    "start": sp.get("start"),
                    "end": sp.get("end"),
                },
                "display_text": f"Note documents {sp.get('text')}.",
            })

        # 4. If configured, corrupt claims based on bad_claim_ratio
        if self.bad_claim_ratio > 0.0 and claims:
            num_to_corrupt = int(round(len(claims) * self.bad_claim_ratio))
            if num_to_corrupt == 0:
                num_to_corrupt = 1
            for idx in range(min(num_to_corrupt, len(claims))):
                c = claims[idx]
                # Corrupt by introducing hallucinated numbers and bad cycle scope
                c["display_text"] = "Patient dosage was 9999 mg on day 888."
                c["cycle_id"] = "CY-CORRUPT-999"

        return {"claims": claims}
