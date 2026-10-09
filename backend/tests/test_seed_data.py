import json
import os
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEED_DIR = os.path.join(BASE_DIR, "data", "seed")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def test_seed_files_exist():
    assert os.path.exists(os.path.join(SEED_DIR, "seed.json"))
    assert os.path.exists(os.path.join(GOLD_DIR, "facts.json"))
    assert os.path.exists(os.path.join(GOLD_DIR, "conflicts.json"))
    assert os.path.exists(os.path.join(GOLD_DIR, "absences.json"))
    assert os.path.exists(os.path.join(GOLD_DIR, "injection_cases.json"))


def test_seed_data_integrity():
    with open(os.path.join(SEED_DIR, "seed.json"), "r", encoding="utf-8") as f:
        seed = json.load(f)

    # 6 patients
    assert len(seed["patients"]) == 6
    patient_ids = {p["id"] for p in seed["patients"]}
    assert patient_ids == {"P-101", "P-102", "P-103", "P-104", "P-105", "P-106"}

    # Doctor assignment: P-101 to P-105 assigned to dr.rao; P-106 is not
    dr_assigned_pids = {dp["patient_id"] for dp in seed["doctor_patients"] if dp["doctor_id"] == "USR-RAO"}
    assert "P-106" not in dr_assigned_pids
    assert {"P-101", "P-102", "P-103", "P-104", "P-105"}.issubset(dr_assigned_pids)

    # All records have content_text
    record_map = {}
    for r in seed["source_records"]:
        assert len(r["content_text"]) > 20
        assert r["id"].startswith("REC-")
        record_map[r["id"]] = r["content_text"]

    # Every clinical row references an existing source_id
    for table_name in [
        "treatment_events",
        "investigations",
        "medications",
        "stimulation_days",
        "oocyte_retrievals",
        "embryos",
        "transfers",
        "pregnancy_outcomes",
        "adverse_events",
        "doctor_notes",
        "followups",
    ]:
        for row in seed[table_name]:
            assert row["source_id"] in record_map, f"Missing source_id {row['source_id']} in {table_name}"
            assert row["org_id"] in ["ORG-Y", "ORG-X", "ORG-B"]
            assert row["trust_status"] in [
                "internal_verified",
                "external_unverified",
                "external_reviewed",
                "ocr_low_confidence",
            ]


def test_gold_set_spans_and_conflicts():
    with open(os.path.join(SEED_DIR, "source_records.json"), "r", encoding="utf-8") as f:
        records = {r["id"]: r["content_text"] for r in json.load(f)}

    with open(os.path.join(GOLD_DIR, "facts.json"), "r", encoding="utf-8") as f:
        facts = json.load(f)

    with open(os.path.join(GOLD_DIR, "conflicts.json"), "r", encoding="utf-8") as f:
        conflicts = json.load(f)

    with open(os.path.join(GOLD_DIR, "absences.json"), "r", encoding="utf-8") as f:
        absences = json.load(f)

    with open(os.path.join(GOLD_DIR, "injection_cases.json"), "r", encoding="utf-8") as f:
        injections = json.load(f)

    # Check note span correctness
    for fact in facts:
        if fact.get("span"):
            span = fact["span"]
            rec_id = span["record_id"]
            text = records[rec_id]
            extracted = text[span["start"]:span["end"]]
            assert extracted == str(fact["value"])

    # Check conflicts: P-102 AMH (2.4 vs 1.2), P-106 beta-hCG (145.0 vs 12.0)
    conflict_patients = {c["patient_id"] for c in conflicts}
    assert "P-102" in conflict_patients
    assert "P-106" in conflict_patients

    # Check absences: P-103 OPU embryology, P-106 semen analysis
    absence_patients = {a["patient_id"] for a in absences}
    assert "P-103" in absence_patients
    assert "P-106" in absence_patients

    # Check injection case on P-106
    assert injections[0]["patient_id"] == "P-106"
    inj_span = injections[0]["span"]
    inj_extracted = records[inj_span["record_id"]][inj_span["start"]:inj_span["end"]]
    assert inj_extracted == injections[0]["injection_text"]
