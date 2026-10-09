import json
import os
import pytest
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.scope import Scope
from app.services.engines import (
    get_timeline,
    get_current_stage,
    get_followups,
    detect_conflicts,
    detect_missing_data,
    check_coverage,
    get_cycle_comparison,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")


def make_scope(user: User, patient_id: str) -> Scope:
    return Scope(user=user, patient_id=patient_id, cycle_id=None, org_id=user.org_id)


def test_timeline_engine(seeded_engine):
    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()
        scope = make_scope(user, "P-101")
        timeline = get_timeline(session, scope)

        assert timeline["patient_id"] == "P-101"
        assert len(timeline["cycles"]) == 1
        assert timeline["events_count"] > 0

        # Check cycle and event has source_refs
        for cycle in timeline["cycles"]:
            assert len(cycle["source_refs"]) > 0
            for event in cycle["events"]:
                assert len(event["source_refs"]) > 0
                assert event["source_refs"][0].startswith("REC-")

        # P-104 has 2 cycles
        scope_104 = make_scope(user, "P-104")
        timeline_104 = get_timeline(session, scope_104)
        assert len(timeline_104["cycles"]) == 2


def test_stage_engine(seeded_engine):
    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()

        # P-101: Cycle 1 completed (Ongoing clinical pregnancy)
        s_p101 = get_current_stage(session, make_scope(user, "P-101"))
        assert "Cycle 1 completed" in s_p101["stage"]
        assert "REC-0101" in s_p101["source_refs"]

        # P-102: Stage documented
        s_p102 = get_current_stage(session, make_scope(user, "P-102"))
        assert s_p102["stage"] is not None
        assert len(s_p102["source_refs"]) > 0

        # P-106: Cycle 1 inconclusive
        s_p106 = get_current_stage(session, make_scope(user, "P-106"))
        assert "Cycle 1 completed" in s_p106["stage"]
        assert s_p106["cycle_id"] == "CY-P106-1"


def test_followups_engine_overdue_and_pending(seeded_engine):
    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()

        # P-101 has overdue viability ultrasound scan
        fol_p101 = get_followups(session, make_scope(user, "P-101"))
        assert fol_p101["overdue_count"] >= 1
        overdue_names = [item["name"] for item in fol_p101["overdue"]]
        assert "Early Viability Ultrasound Scan" in overdue_names
        viab_item = next(i for i in fol_p101["overdue"] if i["name"] == "Early Viability Ultrasound Scan")
        assert viab_item["source_refs"] == ["REC-0104"]

        # P-102 has pending pre-stimulation check
        fol_p102 = get_followups(session, make_scope(user, "P-102"))
        assert fol_p102["pending_count"] >= 1
        pending_names = [item["name"] for item in fol_p102["pending"]]
        assert "Pre-stimulation Day 2 Estradiol & Progesterone Check" in pending_names


def test_conflicts_engine_matches_gold_with_zero_false_positives(seeded_engine):
    with open(os.path.join(GOLD_DIR, "conflicts.json"), "r", encoding="utf-8") as f:
        gold_conflicts = json.load(f)

    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()
        admin_user = session.query(User).filter_by(username="admin").first()

        all_detected = {}
        for pid in ["P-101", "P-102", "P-103", "P-104", "P-105"]:
            detected = detect_conflicts(session, make_scope(user, pid))
            all_detected[pid] = detected

        # P-102: Must detect AMH conflict across Hospital A and Hospital B
        assert len(all_detected["P-102"]) == 1
        conf_p102 = all_detected["P-102"][0]
        assert "AMH" in conf_p102["field"]
        assert set(conf_p102["source_refs"]) == {"REC-0201", "REC-0202"}
        assert set([conf_p102["hospital_a"], conf_p102["hospital_b"]]) == {"ORG-Y", "ORG-X"}

        # P-106 evaluated under admin: Must detect beta-hCG conflict across Hospital A and Hospital B
        conf_p106_list = detect_conflicts(session, make_scope(admin_user, "P-106"))
        assert len(conf_p106_list) == 1
        conf_p106 = conf_p106_list[0]
        assert "beta_hcg" in conf_p106["field"].lower() or "beta-hcg" in conf_p106["field"].lower()
        assert set(conf_p106["source_refs"]) == {"REC-0601", "REC-0603"}
        assert set([conf_p106["hospital_a"], conf_p106["hospital_b"]]) == {"ORG-Y", "ORG-B"}

        # Dr. Rao is unassigned to P-106 -> returns [] by RBAC
        assert len(detect_conflicts(session, make_scope(user, "P-106"))) == 0

        # Zero false positives on clean patients
        assert len(all_detected["P-101"]) == 0
        assert len(all_detected["P-103"]) == 0
        assert len(all_detected["P-104"]) == 0
        assert len(all_detected["P-105"]) == 0


def test_missing_data_engine_matches_gold_with_zero_false_positives(seeded_engine):
    with open(os.path.join(GOLD_DIR, "absences.json"), "r", encoding="utf-8") as f:
        gold_absences = json.load(f)

    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()
        admin_user = session.query(User).filter_by(username="admin").first()

        all_missing = {}
        for pid in ["P-101", "P-102", "P-103", "P-104", "P-105"]:
            missing = detect_missing_data(session, make_scope(user, pid))
            all_missing[pid] = missing

        # P-103: Must detect missing embryology report after OPU
        assert len(all_missing["P-103"]) == 1
        assert all_missing["P-103"][0]["rule_id"] == "RULE_GAP_OPU_EMBRYOLOGY"

        # P-106 evaluated under admin: Must detect missing partner semen analysis
        missing_106 = detect_missing_data(session, make_scope(admin_user, "P-106"))
        assert len(missing_106) == 1
        assert missing_106[0]["rule_id"] == "RULE_EXPECT_MALE_FACTOR_WORKUP"

        # Dr. Rao unassigned to P-106 -> [] by RBAC
        assert len(detect_missing_data(session, make_scope(user, "P-106"))) == 0

        # Zero false positives on clean patients!
        assert len(all_missing["P-101"]) == 0
        assert len(all_missing["P-102"]) == 0
        assert len(all_missing["P-104"]) == 0
        assert len(all_missing["P-105"]) == 0


def test_coverage_engine(seeded_engine):
    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()
        scope = make_scope(user, "P-101")

        # Empty claims -> coverage score 0
        empty_cov = check_coverage(session, scope, [])
        assert empty_cov["covered_count"] == 0
        assert empty_cov["omitted_count"] == empty_cov["total_must_mention"]
        assert empty_cov["coverage_score"] == 0.0

        # Partial claims
        mock_claims = [
            {"cycle_id": "CY-P101-1", "field_path": "cycles.CY-P101-1.outcome"},
        ]
        partial_cov = check_coverage(session, scope, mock_claims)
        assert partial_cov["covered_count"] >= 1
        assert partial_cov["coverage_score"] > 0.0


def test_comparison_engine(seeded_engine):
    with Session(seeded_engine) as session:
        user = session.query(User).filter_by(username="dr.rao").first()
        admin_user = session.query(User).filter_by(username="admin").first()

        # P-101 comparison
        comp_p101 = get_cycle_comparison(session, make_scope(user, "P-101"))
        assert comp_p101["cycles_count"] == 1
        assert len(comp_p101["matrix"]) == 1
        for c in comp_p101["matrix"]:
            assert len(c["source_refs"]) > 0

        # P-104 comparison (2 cycles)
        comp_p104 = get_cycle_comparison(session, make_scope(user, "P-104"))
        assert comp_p104["cycles_count"] == 2
        assert len(comp_p104["matrix"]) == 2

        # P-106 comparison under admin (1 cycle)
        comp_p106 = get_cycle_comparison(session, make_scope(admin_user, "P-106"))
        assert comp_p106["cycles_count"] == 1
        assert len(comp_p106["matrix"]) == 1
