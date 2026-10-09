"""
Pre-Consult Clinical Brief Service: Generates a one-page PDF clinical summary
using ReportLab. Strictly consumes cached validated summaries and deterministic
engine data; NEVER triggers a fresh LLM call.
"""

import io
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.core.config import settings
from app.core.scope import Scope
from app.models.patient import Patient
from app.models.organization import Organization
from app.models.summary import Summary
from app.models.source_record import SourceRecord
from app.services.engines.timeline import get_timeline
from app.services.engines.stage import get_current_stage
from app.services.engines.conflicts import detect_conflicts
from app.services.engines.missing import detect_missing_data
from app.services.engines.followups import get_followups
from app.services.ai.composer import build_snapshot_lines


def generate_patient_brief_pdf(db: Session, scope: Scope) -> bytes:
    """
    Renders a concise, professional, single-page A4 PDF pre-consult brief.
    Adheres strictly to the Peach Sorbet clinical design palette.
    """
    patient_id = scope.patient_id
    patient = db.get(Patient, patient_id)
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    org = db.get(Organization, patient.org_id) if patient.org_id else None
    org_name = org.name if org else "Fertility Care Network"

    # Reference earliest record for baseline demographics source
    earliest_rec = db.scalars(
        select(SourceRecord)
        .where(SourceRecord.patient_id == patient_id)
        .order_by(SourceRecord.date.asc())
    ).first()
    demo_source_ref = f"[{earliest_rec.id}]" if earliest_rec else ""

    # 1. Deterministic Engines
    stage_data = get_current_stage(db, scope)
    current_stage = stage_data.get("current_stage", "Under evaluation")
    stage_sources = " ".join([f"[{s}]" for s in stage_data.get("source_refs", [])[:2]])

    all_conflicts = detect_conflicts(db, scope)
    missing_items = detect_missing_data(db, scope)

    followups_data = get_followups(db, scope)
    overdue_followups = followups_data.get("overdue", [])
    pending_followups = followups_data.get("pending", [])
    scheduled_followups = followups_data.get("scheduled", [])

    timeline_data = get_timeline(db, scope)
    cycles = timeline_data.get("cycles", [])

    # 2. Cached validated summary (STRICTLY NO fresh LLM call)
    latest_summary = db.scalars(
        select(Summary)
        .where(Summary.patient_id == patient_id)
        .order_by(desc(Summary.version))
    ).first()

    if latest_summary and latest_summary.content_json and latest_summary.content_json.get("snapshot"):
        snapshot_lines = latest_summary.content_json.get("snapshot", [])
    else:
        # Fallback to pure deterministic rule-based snapshot without LLM
        snapshot_lines = build_snapshot_lines(
            patient=patient,
            current_stage=current_stage,
            verified_claims_by_section={},
            all_conflicts=all_conflicts,
            overdue_followups=overdue_followups,
            missing_items=missing_items,
        )

    # 3. ReportLab Document Assembly
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=24,
        rightMargin=24,
        topMargin=20,
        bottomMargin=20,
    )

    # Peach Sorbet palette styling tokens
    c_brand = colors.HexColor("#8C3A3A")      # Dark Coral / Header
    c_primary = colors.HexColor("#F08080")    # Peach Sorbet Primary
    c_accent = colors.HexColor("#F4978E")     # Accent Pink
    c_tint = colors.HexColor("#FFF5F3")       # Light peach background
    c_border = colors.HexColor("#F8AD9D")     # Soft border
    c_th_bg = colors.HexColor("#FBC4AB")      # Table Header background
    c_text = colors.HexColor("#1A202C")       # Dark Charcoal body text
    c_muted = colors.HexColor("#4A5568")      # Muted gray
    c_alert = colors.HexColor("#C53030")      # Red Alert

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=c_brand,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=c_muted,
    )
    sec_heading_style = ParagraphStyle(
        "SecHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=c_brand,
    )
    body_style = ParagraphStyle(
        "BodyTxt",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=c_text,
    )
    bold_style = ParagraphStyle(
        "BoldTxt",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=c_text,
    )
    meta_style = ParagraphStyle(
        "MetaTxt",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=c_muted,
    )
    footer_style = ParagraphStyle(
        "FooterTxt",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        alignment=TA_CENTER,
        textColor=c_muted,
    )

    story = []

    # --- TOP HEADER ---
    header_data = [
        [
            Paragraph(f"<b>OVA &nbsp;|&nbsp; {org_name.upper()}</b> &nbsp;|&nbsp; PRE-CONSULT CLINICAL BRIEF", title_style),
            Paragraph(
                f"<b>CONFIDENTIAL MEDICAL SUMMARY</b><br/>"
                f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                ParagraphStyle("RightSub", parent=subtitle_style, alignment=TA_RIGHT),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[380, 167])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=4, spaceBefore=0))

    # --- PATIENT DEMOGRAPHICS HEADER BOX ---
    age_str = f"{datetime.now().year - patient.dob.year}y" if patient.dob else "N/A"
    dob_str = str(patient.dob) if patient.dob else "N/A"
    diag_str = "None documented"
    if patient.diagnosis:
        if isinstance(patient.diagnosis, dict):
            pri = patient.diagnosis.get("primary", "")
            sec = patient.diagnosis.get("secondary", "")
            diag_str = f"{pri}; {sec}".strip("; ")
        elif isinstance(patient.diagnosis, list):
            diag_str = ", ".join(patient.diagnosis)

    patient_grid = [
        [
            Paragraph(f"<b>Patient:</b> {patient.name} (<b>{patient.id}</b>)", body_style),
            Paragraph(f"<b>DOB / Age:</b> {dob_str} ({age_str})", body_style),
            Paragraph(f"<b>Blood Group:</b> {patient.blood_group or 'N/A'}", body_style),
            Paragraph(f"<b>BMI:</b> {patient.bmi or 'N/A'} kg/m²", body_style),
        ],
        [
            Paragraph(f"<b>Partner ID:</b> {patient.partner_id or 'None on record'}", body_style),
            Paragraph(f"<b>Current Stage:</b> {current_stage} {stage_sources}", bold_style),
            Paragraph(f"<b>Diagnosis:</b> {diag_str}", body_style),
            Paragraph(f"<b>Baseline Source:</b> {demo_source_ref or '[-]'} ", body_style),
        ]
    ]
    pat_table = Table(patient_grid, colWidths=[145, 120, 110, 172])
    pat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_tint),
        ("BOX", (0, 0), (-1, -1), 0.5, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#FDE2D9")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pat_table)
    story.append(Spacer(1, 4))

    # --- 5-LINE EXECUTIVE SNAPSHOT ---
    story.append(Paragraph("<b>EXECUTIVE SUMMARY (VALIDATED 5-LINE SNAPSHOT)</b>", sec_heading_style))
    story.append(Spacer(1, 2))
    snap_rows = []
    for i, line in enumerate(snapshot_lines[:5], 1):
        if isinstance(line, dict):
            clean_line = line.get("text", "").strip()
            sources = line.get("source_refs", [])
            if sources:
                clean_line += f" [{', '.join(sources)}]"
        else:
            clean_line = str(line).strip()
        snap_rows.append([
            Paragraph(f"<b>{i}.</b>", ParagraphStyle("Num", parent=bold_style, textColor=c_brand)),
            Paragraph(clean_line, body_style),
        ])
    snap_table = Table(snap_rows, colWidths=[14, 533])
    snap_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(snap_table)
    story.append(Spacer(1, 4))

    # --- CYCLE & TREATMENT TIMELINE ---
    story.append(Paragraph("<b>CYCLE & TREATMENT TIMELINE</b>", sec_heading_style))
    story.append(Spacer(1, 2))
    timeline_rows = [
        [
            Paragraph("<b>Cycle</b>", bold_style),
            Paragraph("<b>Type</b>", bold_style),
            Paragraph("<b>Dates</b>", bold_style),
            Paragraph("<b>Protocol & Outcomes</b>", bold_style),
            Paragraph("<b>Origin & Trust</b>", bold_style),
            Paragraph("<b>Sources</b>", bold_style),
        ]
    ]
    if cycles:
        for c in cycles[:4]:
            sources_str = " ".join([f"[{s}]" for s in c.get("source_refs", [])[:2]]) or "[-]"
            dates_str = f"{c.get('start_date') or ''} to {c.get('end_date') or 'Ongoing'}"
            origin_str = f"{c.get('origin_org', 'Internal')} ({c.get('trust_status', 'verified')})"
            outcome_badge = c.get("outcome") or ("In Progress" if not c.get("end_date") else "Completed")
            timeline_rows.append([
                Paragraph(f"Cycle {c.get('cycle_no', '?')}", body_style),
                Paragraph(str(c.get("type", "")), body_style),
                Paragraph(dates_str, meta_style),
                Paragraph(f"<b>{outcome_badge}</b>", body_style),
                Paragraph(origin_str, meta_style),
                Paragraph(sources_str, meta_style),
            ])
    else:
        timeline_rows.append([
            Paragraph("No treatment cycles recorded.", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph("[-]", meta_style),
        ])

    timeline_table = Table(timeline_rows, colWidths=[42, 48, 100, 142, 145, 70])
    timeline_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_th_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(timeline_table)
    story.append(Spacer(1, 4))

    # --- CONFLICTS & MISSING DATA (SIDE BY SIDE 2-COLUMN TABLE) ---
    conf_cell = []
    conf_cell.append(Paragraph("<b>DOCUMENTED RECORD CONFLICTS</b>", sec_heading_style))
    if all_conflicts:
        for conf in all_conflicts[:2]:
            desc_txt = conf.get("description", "Discrepancy noted")
            srcs = " ".join([f"[{s}]" for s in conf.get("source_refs", [])])
            conf_cell.append(
                Paragraph(f'• <font color="{c_alert}"><b>Conflict:</b></font> {desc_txt} {srcs}', body_style)
            )
    else:
        conf_cell.append(Paragraph("No contradictory records or discrepancies found.", meta_style))

    miss_cell = []
    miss_cell.append(Paragraph("<b>NOT-DOCUMENTED (CLINICAL GAPS)</b>", sec_heading_style))
    if missing_items:
        for m in missing_items[:2]:
            item_name = m.get("item", "Item")
            reason = m.get("reason", "")
            miss_cell.append(Paragraph(f"• <b>{item_name}:</b> {reason}", body_style))
    else:
        miss_cell.append(Paragraph("All protocol-standard workup items documented.", meta_style))

    two_col_table = Table([[conf_cell, miss_cell]], colWidths=[270, 277])
    two_col_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FFF9F8")),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F8FAFC")),
    ]))
    story.append(two_col_table)
    story.append(Spacer(1, 4))

    # --- PENDING FOLLOW-UPS & ACTION ITEMS ---
    story.append(Paragraph("<b>PENDING & OVERDUE CLINICAL FOLLOW-UPS</b>", sec_heading_style))
    story.append(Spacer(1, 1.5))
    fol_rows = []
    action_items = overdue_followups + pending_followups + scheduled_followups
    if action_items:
        for f in action_items[:3]:
            st = f.get("status", "pending").upper()
            st_color = "#C53030" if st == "OVERDUE" else "#D69E2E" if st == "PENDING" else "#3182CE"
            srcs = " ".join([f"[{s}]" for s in f.get("source_refs", [])])
            fol_rows.append([
                Paragraph(f'<font color="{st_color}"><b>[{st}]</b></font>', bold_style),
                Paragraph(f"{f.get('name', 'Action item')} (Due: {f.get('due_date', 'N/A')})", body_style),
                Paragraph(srcs or "[-]", meta_style),
            ])
    else:
        fol_rows.append([
            Paragraph("NONE", meta_style),
            Paragraph("No overdue or pending clinical follow-ups recorded.", body_style),
            Paragraph("[-]", meta_style),
        ])

    fol_table = Table(fol_rows, colWidths=[70, 410, 67])
    fol_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(fol_table)
    story.append(Spacer(1, 5))

    # --- DISCLAIMER FOOTER ---
    disclaimer_text = (
        "<b>AI-assisted. Clinician review required.</b> "
        "This pre-consult brief summarizes verified records using deterministic clinical engines and cached summaries. "
        "It does not replace clinical judgment or primary record inspection. All treatment decisions remain the responsibility of the treating clinician."
    )
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor("#CBD5E0"), spaceAfter=3, spaceBefore=0))
    story.append(Paragraph(disclaimer_text, footer_style))

    # Render document to memory
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
