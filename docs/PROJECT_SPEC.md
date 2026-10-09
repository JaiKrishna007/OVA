# OVA — Clinical Fertility Treatment, Ingestion & Cross-Hospital Provenance Platform
**Kernel Prime'26 | SW-01 | Software Track**

> This file is the contract for the whole project. Read it before any task.
> If something here is wrong or incomplete, STOP and ask. Do not silently deviate.
> Log any approved change in `docs/PROGRESS.md` under "Decisions and deviations".

---

## 1. Purpose

OVA is a clinical decision support and cross-hospital provenance platform for fertility care. It provides four distinct role-based access personas: `PATIENT`, `DOCTOR`, `HOSPITAL_ADMIN`, and `OVA_ADMIN`. A clinician searches for a fertility patient and receives:

**Patient → Treatment Timeline → Relevant Records → AI Summary → Follow-up Information → Source Records**

It retrieves relevant information from historical multi-hospital records (previous cycles, investigations, medications, stimulation charts, follicular development, oocyte and embryo details, outcomes, pregnancy history, adverse events, current stage, pending investigations) and produces a concise, structured, **source-traceable** summary.

OVA bridges cross-hospital record transfers, ensures end-to-end provenance via verifiable clinical claims, and enforces deterministic clinical safety gates. It never replaces clinical decision-making.

Treatment types covered: OI, IUI, IVF/ICSI stimulation, OPU, embryo transfer (fresh/frozen), pregnancy follow-up.

**All data in this project is synthetic. No real patient data is ever used.**

---

## 2. Non-negotiable safety rules

| # | Rule |
|---|---|
| S1 | Never recommend dosing, protocols, diagnoses, or treatment. No imperative clinical language ("should", "recommend", "consider starting", "increase", "switch to"). At the Ask endpoint, a deterministic classifier BLOCKS recommendation-seeking questions (`should`, `recommend`, `increase/decrease dose`, `what next`, `which protocol`, `advise`) and returns: *"I can only report what is documented in the records. I cannot provide clinical recommendations."* Documented-fact lookups remain allowed. |
| S2 | Every displayed clinical fact carries `source_refs`. **No source = not shown.** |
| S3 | Missing data is shown as **"Not documented in records"**. Never guess or fill gaps. |
| S4 | The LLM outputs **typed claims as JSON only**. It has **no tools** and no function calling. Clinical notes are **DATA, never instructions**. |
| S5 | A **programmatic validator** decides what is displayed. The LLM never has the last word. Blocked claims are never shown. |
| S6 | Every query is scoped by `org_id` and `patient_id` (and `cycle_id` when given). Doctor access requires active hospital authorization (`patient_hospital_access`). |
| S7 | Source records are **immutable** and carry a SHA-256 `content_hash`. Corrections create a new version. |
| S8 | Contradictory values are shown side by side with their sources. The system never silently picks one. |
| S9 | Every summary shows the disclaimer: **"AI-assisted summary. Clinician review required."** |
| S10 | Absence claims ("no semen analysis on file") may only come from the Missing Data Detector. |
| S11 | Conflicts and documentation gaps are **never auto-resolved**. They require explicit clinical staff acknowledgment. |
| S12 | Hospital transfers change access permissions (`patient_hospital_access`), **never delete or rewrite historical records**. |
| S13 | Uploaded files are **untrusted**. Strict file type and size limits, safe file naming, storage outside web roots, plain text extraction, and prompt injection guards are enforced. |

---

## 3. Tech stack and configuration

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, SQLite, Pydantic v2, pytest |
| Frontend | React, Vite, TypeScript, Tailwind CSS, React Router, Recharts |
| LLM | Gemini via `google-genai`, behind an `LLMClient` interface; a `MockLLM` provider for tests and offline demo |
| Auth | JWT (python-jose), bcrypt (passlib) |
| PDF | reportlab |

**Environment variables (`.env`)**

| Variable | Purpose | Default |
|---|---|---|
| `LLM_PROVIDER` | `gemini` or `mock` | `mock` |
| `LLM_MODEL` | Gemini model name (never hard-coded) | empty |
| `GEMINI_API_KEY` | API key | empty |
| `JWT_SECRET` | JWT signing secret | `change-me` |
| `AS_OF_DATE` | Fixed "today" for demo (overdue logic) | `2025-03-14` |
| `DATABASE_URL` | SQLite path | `sqlite:///./app.db` |

---

## 4. Architecture

```
A) INGESTION & PROVENANCE PIPELINE (Unstructured/Semi-structured Documents → Grounded Facts)
   Upload (PDF/TXT/JSON)
      │
      ▼
   SourceRecord (Immutable, SHA-256 content_hash, processing_status: UPLOADED)
      │
      ▼
   TextExtractor Interface (PdfText, Txt, Json, Mock; Scanned PDFs → NEEDS_OCR)
      │
      ▼
   ExtractionPipeline (LLMClient candidate claims, strict JSON schema, injection guard)
      │
      ▼
   ExtractionValidator (Programmatic grounding: source text exact check, spans, context)
      ├─ REJECTED/FLAGGED → audit log / review queue
      └─ VERIFIED → ClinicalClaim (extraction_method: seed|mock|gemini|nvidia)
            │
            ▼
         Normalizer (Canonical YAML dictionary: terms, test names, standardized units)
            │
            ▼
         Materializer (Commit VERIFIED claims into typed clinical tables & treatment_events)
            │  (materialized_table, materialized_row_id link back to claim)
            ▼
         Cycle Grouping Engine → Trigger Engine Recomputation (timeline, conflicts, gaps)
            │
            ▼
         Patient Summary marked stale (cache invalidation)

B) SUMMARY & CLINICAL REASONING PIPELINE (Verified Structured DB → Executive View)
   Context Pack Builder (Scoped per section from materialized tables & claims)
      │
      ▼
   Prompt-Injection Guard & Grounded LLM (Typed claims, JSON only)
      │
      ▼
   Summary Claim Validator (Programmatic check: summary claims verified against DB facts)
      ├─ VERIFIED → response display
      └─ BLOCKED  → remove / section degraded fallback (>50% blocked → retry once → fallback)
      │
      ▼
   Response Composer (Timeline + Summary + Persistent Conflicts + Gaps + Provenance Badges)
      │
      ▼
   Client UI (Role-scoped: PATIENT, DOCTOR, HOSPITAL_ADMIN, OVA_ADMIN)

NOTE: Two distinct validators exist and MUST NOT be merged:
1. ExtractionValidator: Verifies raw candidate claims directly against source document text.
2. Summary Validator: Verifies generated summary claims against materialized database facts.
```

**Design principles**
1. Facts first, language second. Summaries are built from verified structured facts, not raw chart text.
2. No fact without a `source_id` and verified `clinical_claim` provenance.
3. Scope before search: Role, hospital access (`patient_hospital_access`), and patient assignment.
4. Deterministic path works even if the LLM fails.
5. Validate after generating. Never trust generative model output.
6. Originals are immutable and cryptographically hashed (`content_hash`).

---

## 5. Data model

All clinical tables include: `source_id` (FK → `source_records.id`), `org_id` (the hospital that created/originated the row; immutable on transfer), `origin_org`, `trust_status`.

`trust_status` ∈ `internal_verified | external_unverified | external_reviewed | ocr_low_confidence`

| Table | Key columns |
|---|---|
| `organizations` | id, name, type (`hospital`) |
| `users` | id, username, password_hash, role (`PATIENT`/`DOCTOR`/`HOSPITAL_ADMIN`/`OVA_ADMIN`), org_id, hospital_id, patient_id (nullable, for PATIENT) |
| `doctor_patients` | doctor_id, patient_id |
| `patients` | id, name, dob, sex, org_id, diagnosis (JSON), partner_id (nullable), blood_group, bmi, phone |
| `cycles` | id, patient_id, cycle_no, type (`OI`/`IUI`/`IVF`/`ICSI`/`FET`), start_date, end_date, outcome, origin_org, external_cycle_no |
| `treatment_events` | id, cycle_id, kind (`trigger`/`opu`/`fertilization_check`/`transfer`/`beta_hcg`/`scan`/`loss`/`delivery`/`cancel`), date, detail, source_id |
| `investigations` | id, patient_id, cycle_id (nullable), category (`lab`/`imaging`/`semen`/`genetic`), name, value, unit, ref_range, date, status (`resulted`/`pending`), ordered_date, source_id |
| `medications` | id, cycle_id, name, dose, route, start_date, end_date, purpose, source_id |
| `stimulation_days` | id, cycle_id, day_no, date, follicles (JSON), e2, lh, p4, endometrium_mm, dose_note, source_id |
| `oocyte_retrievals` | id, cycle_id, date, oocytes_retrieved, mii, mi, gv, source_id |
| `embryos` | id, cycle_id, embryo_label, day, grade, pgt_status, fate (`transferred`/`frozen`/`discarded`/`fresh`), storage_location, source_id |
| `transfers` | id, cycle_id, date, kind (`fresh`/`frozen`), embryo_ids (JSON), endometrium_mm, source_id |
| `pregnancy_outcomes` | id, cycle_id, beta_hcg_value, beta_hcg_date, result (`negative`/`biochemical`/`clinical`/`ongoing`/`loss`/`ectopic`/`live_birth`), gestation_note, source_id |
| `adverse_events` | id, cycle_id, kind, severity, date, management_note, source_id |
| `doctor_notes` | id, patient_id, cycle_id (nullable), date, author, text, source_id |
| `followups` | id, patient_id, cycle_id (nullable), kind, name, status (`pending`/`scheduled`/`done`/`overdue`), due_date, source_id |
| `source_records` | id (`REC-####`), patient_id, cycle_id (nullable), type, date, author, origin_org, trust_status, content_text, version, uploaded_by, mime_type, file_path, processing_status (`UPLOADED`/`EXTRACTING`/`VALIDATED`/`NEEDS_OCR`/`FAILED`), content_hash |
| `clinical_claims` | id (`CLM-####`), patient_id, hospital_id, source_record_id, cycle_id (nullable), field, value_text, value_num, unit, event_date, span_start, span_end, evidence_text, extraction_method (`seed`/`mock`/`gemini`/`nvidia`), validation_status (`VERIFIED`/`REJECTED`/`FLAGGED`), validation_checks (JSON), reason_codes (JSON), uploaded_by, created_at, materialized_table, materialized_row_id |
| `conflicts` | id (`CONF-####`), patient_id, field, claim_ids (JSON), status (`OPEN`/`ACKNOWLEDGED`), acknowledged_by, note, at |
| `documentation_gaps` | id (`GAP-####`), patient_id, cycle_id (nullable), rule_id, trigger_claim_id, expected_item, status (`OPEN`/`ACKNOWLEDGED`/`RESOLVED`), detected_at |
| `consents` | id (`CNS-####`), patient_id, granted_to_hospital_id, purpose, scope, status (`ACTIVE`/`REVOKED`/`EXPIRED`), granted_at, expires_at, revoked_at |
| `transfer_requests` | id (`TRF-####`), patient_id, from_hospital_id, to_hospital_id, requested_by, status (`REQUESTED`/`ACCEPTED`/`REJECTED`/`COMPLETED`/`CANCELLED`), consent_id, decided_by, decided_at, reason |
| `patient_hospital_access` | id (`PHA-####`), patient_id, hospital_id, access_level (`READ_ONLY`/`READ_WRITE`), status (`ACTIVE`/`REVOKED`), source_transfer_id, since |
| `summaries` | id, patient_id, version, data_version, generated_at, content_json, validator_report_json |
| `summary_feedback` | id, summary_id, statement_ref, type, comment, user_id, at |
| `eval_runs` | id, run_at, provider, metrics_json |
| `audit_log` | id, user_id, hospital_id, action, patient_id, event_type, details (JSON), outcome, at |
| `identity_links`, `import_batches` | Cross-clinic identity and quarantine staging stores |

**ID conventions:** `P-101`, `CY-P101-2`, `REC-0142`, `OPU-P101-2`.

**`field_path` format:** `<table>.<row_id>.<column>`
Example: `oocyte_retrievals.OPU-P101-2.oocytes_retrieved`

---

## 6. Claim schema (the only thing the LLM may output)

```json
{
  "claim_id": "c12",
  "type": "FACT",
  "section": "oocyte_retrieval",
  "entity": "oocyte_retrieval",
  "cycle_id": "CY-P101-2",
  "field_path": "oocyte_retrievals.OPU-P101-2.oocytes_retrieved",
  "value": 9,
  "unit": null,
  "date": "2024-06-12",
  "polarity": "present",
  "source_ids": ["REC-0051"],
  "span": null,
  "display_text": "Cycle 2 retrieved 9 oocytes."
}
```

- `type` ∈ `FACT | ABSENCE | CONFLICT`. **There is no inference type.**
- `ABSENCE` must reference a Missing Data Detector item.
- `CONFLICT` must reference a Conflict Detector item.
- `span` is `{record_id, start, end}` for note-derived facts, else `null`.
- `polarity` ∈ `present | absent`.

**Sections (fixed order)**
1. `profile_diagnosis`
2. `prior_cycles`
3. `protocols_medications`
4. `follicular_development`
5. `oocyte_retrieval`
6. `embryo_details`
7. `outcomes_pregnancy`
8. `adverse_events`
9. `current_stage`

**Assurance tiers**
| Tier | Meaning |
|---|---|
| `STRUCTURED_VERIFIED` | Claim equals a DB field exactly |
| `NOTE_SUPPO## 7. Dual validators and reason codes

OVA employs **two separate, non-overlapping validators**. They must never be merged.

### 7.1 Extraction Validator (Source Text → Candidate Claims)
Verifies raw candidate claims generated by the LLM ingestion pipeline against the source document text:

| Check | Reason code on failure | Behavior |
|---|---|---|
| Field recognized in schema | `FIELD_UNKNOWN` | REJECT claim |
| Extracted value found verbatim in source | `VALUE_NOT_IN_SOURCE` | REJECT claim |
| Extracted unit matches source text | `UNIT_NOT_IN_SOURCE` | REJECT claim |
| Event date grounded in source text | `DATE_NOT_IN_SOURCE` | REJECT claim |
| Character offset span substring matches value | `SPAN_MISMATCH` | REJECT claim |
| Character offset span within bounds of document | `SPAN_OUT_OF_RANGE` | REJECT claim |
| Value appears in text but attached to another entity | `CONTEXT_MISMATCH` | REJECT claim |
| Exact duplicate of already validated claim | `DUPLICATE_CLAIM` | REJECT claim |
| Unit in source has multiple clinical interpretations | `UNIT_AMBIGUOUS` | **FLAG** claim (not rejected) |

### 7.2 Summary Claim Validator (Materialized DB Facts → Executive Summary)
Verifies generated clinical summary claims against materialized database facts:

| Check | Reason code on failure |
|---|---|
| Source exists in DB | `SOURCE_NOT_FOUND` |
| Patient scope matches DB | `PATIENT_SCOPE` |
| Cycle scope matches DB | `CYCLE_SCOPE` |
| Date matches DB field | `DATE_MISMATCH` |
| Value matches DB field exactly | `VALUE_MISMATCH` |
| Numbers/dates inside `display_text` match typed fields | `TEXT_NUMBER_MISMATCH` |
| Medication match | `MEDICATION_MISMATCH` |
| Polarity matches | `POLARITY_MISMATCH` |
| Severity / grade matches | `SEVERITY_MISMATCH` |
| Field path resolves to DB column | `FIELD_PATH_INVALID` |
| Span exists and contains value | `SPAN_INVALID` |
| Active conflict on field | `ACTIVE_CONFLICT` |
| Absence has detector reference | `ABSENCE_UNSUPPORTED` |
| Policy filter (advice, dosing, diagnosis, imperative language) | `POLICY_VIOLATION` |
| Coverage (important facts omitted) | Reported by Coverage Checker, not a block |

The validator contains **no LLM calls**. The policy rules live in a config file and are unit-tested.

**Degraded mode (per section):** if more than 50% of a section's claims are blocked, retry the LLM once. If it still fails, or the LLM errors or times out, replace that section with a deterministic rendering from the engines and set `mode = "deterministic_fallback"`.

---

## 8. Deterministic engines

| Engine | Responsibility |
|---|---|
| Timeline | Ordered cycles and events, outcome badges, origin and trust tags |
| Stage | Current stage relative to `AS_OF_DATE`, or "Stage not documented" |
| Follow-up | Pending, scheduled, overdue (`due_date < AS_OF_DATE`) |
| Conflict Detector | Different values for the same fact across sources, including OPU vs discharge-note counts and outcome mismatches. Shows both, picks neither |
| Missing Data Detector | Rule-based expected items per patient profile (config file), output `{item, reason, rule_id}` |
| Coverage Checker | Must-mention facts not covered by claims (each cycle outcome, adverse events, active conflicts, frozen embryo count) |
| Comparison | Cycle comparison matrix, null where undocumented |

Every engine output includes `source_refs`.

---

## 9. API (base `/api/v1`, `Authorization: Bearer <JWT>`)

| Method | Path | Roles |
|---|---|---|
| POST | `/auth/login` | public |
| GET | `/auth/me` | all |
| GET | `/patients?q=` | DOCTOR, HOSPITAL_ADMIN |
| GET | `/patients/{id}` | DOCTOR, HOSPITAL_ADMIN, PATIENT (own record only) |
| GET | `/patients/{id}/timeline` | DOCTOR, HOSPITAL_ADMIN, PATIENT |
| GET | `/patients/{id}/cycles/{cycle_id}` | DOCTOR, HOSPITAL_ADMIN, PATIENT |
| GET | `/patients/{id}/cycle-comparison` | DOCTOR, HOSPITAL_ADMIN |
| GET | `/patients/{id}/embryos` | DOCTOR, HOSPITAL_ADMIN, PATIENT |
| GET | `/patients/{id}/stimulation/{cycle_id}` | DOCTOR, HOSPITAL_ADMIN, PATIENT |
| GET | `/patients/{id}/followups` | DOCTOR, HOSPITAL_ADMIN |
| PATCH | `/followups/{id}` | DOCTOR, HOSPITAL_ADMIN |
| GET | `/patients/{id}/summary?length=snapshot\|detailed` | DOCTOR, HOSPITAL_ADMIN (PATIENT hidden unless `PATIENT_SEES_AI_SUMMARY=true`) |
| GET | `/patients/{id}/summary/status` | DOCTOR, HOSPITAL_ADMIN |
| POST | `/patients/{id}/summary/regenerate` | DOCTOR |
| POST | `/summaries/{id}/feedback` | DOCTOR |
| POST | `/patients/{id}/ask` | DOCTOR (S1 classifier blocks clinical recommendations) |
| GET | `/records/{source_id}` | DOCTOR, HOSPITAL_ADMIN |
| GET | `/patients/{id}/records` | DOCTOR, HOSPITAL_ADMIN |
| GET | `/patients/{id}/brief` | DOCTOR |
| GET | `/eval/latest` | OVA_ADMIN, DOCTOR |
| GET | `/audit` | OVA_ADMIN |
| GET | `/health` | public |
| POST | `/sources/upload` | HOSPITAL_ADMIN, OVA_ADMIN |
| GET | `/claims` | DOCTOR, HOSPITAL_ADMIN, OVA_ADMIN |
| POST | `/conflicts/{id}/ack` | DOCTOR, HOSPITAL_ADMIN |
| POST | `/gaps/{id}/ack` | DOCTOR, HOSPITAL_ADMIN |
| POST/GET | `/transfers`, `/transfers/{id}/decide` | HOSPITAL_ADMIN, OVA_ADMIN |
| POST/GET | `/consents` | HOSPITAL_ADMIN, PATIENT, OVA_ADMIN |

**Error format (all errors):**
```json
{ "error": { "code": "NOT_FOUND", "message": "Record not found", "request_id": "r-91f" } }
```

**Citation object (used everywhere a fact is shown):**
```json
{ "source_id": "REC-0142", "type": "lab", "date": "2025-03-12",
  "origin": "Hospital X", "trust": "external_unverified",
  "span": { "page": null, "start": 120, "end": 168 } }
```

---

## 10. Users and access (seed)

Four distinct roles are supported:
- **`PATIENT`**: Own information only, read-only. AI summary and conflict flags are hidden unless `PATIENT_SEES_AI_SUMMARY=true`.
- **`DOCTOR`**: Records of patients the doctor is assigned to (`doctor_patients`) **AND** whose hospital has active access (`patient_hospital_access`).
- **`HOSPITAL_ADMIN`** (mapped from old `staff`): Manage records, doctor assignments, and transfer requests for their own hospital.
- **`OVA_ADMIN`** (mapped from old `admin`): Platform configuration and audit logging. No clinical record edits.

| User | Role | Notes |
|---|---|---|
| `dr.rao` | DOCTOR | Hospital `ORG-Y`. Assigned to P-101 to P-105 with active hospital access |
| `dr.sharma` | DOCTOR | Hospital `ORG-Z`. Assigned to Hospital B patients; receives 403 on Hospital A patients |
| `nurse.devi` | HOSPITAL_ADMIN | Hospital `ORG-Y`. Manages uploads and transfer requests for Hospital A |
| `admin` | OVA_ADMIN | Platform-wide config, audit, and evaluation |
| `patient.priya` | PATIENT | Bound to P-101. Read-only view of own timeline and records |

---

## 11. Synthetic data (v2 dataset)

| ID | Profile | Deliberate test content |
|---|---|---|
| **P-101** Priya S., 33 | Clean record | Diminished ovarian reserve. Clean baseline, verified IVF cycle with 8 oocytes, all claims cleanly grounded |
| **P-102** Anitha R., 29 | Cross-hospital conflict (Main demo patient) | Records across Hospital A (`ORG-Y`) and Hospital B (`ORG-Z`). Conflicting lab values (AMH 4.2 vs 2.1 ng/mL). Demonstration of multi-hospital provenance tags and persistent conflict flagging |
| **P-103** Meena K., 38 | Missing documentation | OPU conducted with 12 oocytes retrieved, but embryology report missing from records. Triggers `documentation_gaps` alert |
| **P-104** Sunita D., 31 | Multiple cycles | Complex multi-cycle history (Cycle 1 OI, Cycle 2 IVF, Cycle 3 FET). Tests cross-cycle timeline grouping and comparative progression |
| **P-105** Kavya M., 35 | Hospital transfer | Patient transferring from Hospital B to Hospital A. Valid recorded consent on file with a pending `transfer_requests` row awaiting hospital admin decision |
| **P-106** Lakshmi V., 27 | Multiple conflicts and gaps | Complex chart with conflicting beta-hCG values, overdue repeat semen analysis gap, and unassigned doctor access (403 test) |

**Extra test fixtures:**
- `prompt_injection_note.txt`: Separate uploadable document containing prompt injection phrases, testing injection guard during ingestion.
- `dr.sharma`: Second clinician at Hospital B who receives 403 Forbidden when requesting patients at Hospital A.
- `p102_transfer_update.json`: Uploadable transfer document for P-102 introducing a value conflict and documentation gap.

---

## 12. Repository layout

```
backend/
  app/
    main.py
    core/            # config, security, errors
    db/              # session, base
    models/          # clinical, transfer, provenance (claims, conflicts, gaps)
    schemas/         # Pydantic schemas (claims, transfer, clinical)
    routers/         # auth, patients, records, summaries, import_transfer, transfers, conflicts, gaps
    services/
      engines/       # timeline, stage, followups, conflicts, missing, coverage, comparison
      ai/            # llm/{base,gemini,nvidia,mock}, context_pack, injection_guard, prompts, generator, degraded, composer
      ingestion/     # text_extractor, extraction_pipeline, normalizer, materializer, seed_loader
      validator/     # extraction_validator.py + summary claim validator modules
    eval/            # run_eval.py
  data/{seed,gold}/  # seed fixtures, gold set, generator script
  tests/
frontend/src/{pages,components,api,types}/
docs/{PROJECT_SPEC.md,PROGRESS.md,REVIEW.md,DEMO_SCRIPT.md,KNOWN_LIMITATIONS.md}
```

---

## 13. Coding conventions

- Type hints everywhere. Small modules. Docstrings on every engine and validator check.
- Every service function takes `(db, scope)` and **never queries without `patient_id`**.
- No secrets in code. No hard-coded model names. No hard-coded eval numbers.
- Every new endpoint gets a test, including a scope-failure test.
- Frontend: never render record text as raw HTML (no `dangerouslySetInnerHTML`).
- Do not add tables, fields, or endpoints that are not in this spec without asking.
- Do not weaken the validator, the policy filter, or the safety rules to make a test pass.

---

## 14. Out of scope

Live hospital EHR feeds (HL7 v2 / FHIR R4), DICOM ultrasound image archives, enterprise computer-vision OCR, handwriting transcription, multilingual extraction, Postgres production deployment, horizontal scaling, real patient data, and native mobile apps.

---

## 16. OVA v2: Ingestion, provenance, cross-hospital features

### 16.1 Unified Ingestion & Provenance Data Flow
1. **Upload**: Clinical document (`.pdf`, `.txt`, `.json`) is received at `POST /sources/upload`.
2. **SourceRecord Persistence**: Stored with immutable metadata, `uploaded_by`, `mime_type`, `file_path`, `content_hash` (SHA-256), and `processing_status = UPLOADED`.
3. **Text Extraction**: The `TextExtractor` interface extracts raw UTF-8 text using modular adapters (`TxtExtractor`, `JsonExtractor`, `PdfTextExtractor`, `MockExtractor`). If a PDF lacks an embedded text layer (scanned image), `processing_status` is transitioned to `NEEDS_OCR` and extraction halts gracefully.
4. **Extraction Pipeline**: Text is processed by `ExtractionPipeline`, wrapping the text in `PromptInjectionGuard`. The `LLMClient` generates candidate claims adhering strictly to the JSON claim schema.
5. **Extraction Validator**: Evaluates candidate claims against raw source text using programmatic checks (exact substring grounding, span bounds, date/unit validation, context matching).
6. **ClinicalClaim Ledger**: Verified claims are written to `clinical_claims` with `validation_status = VERIFIED` and `extraction_method` (`seed`, `mock`, `gemini`, `nvidia`). Failed claims are logged with reason codes.
7. **Normalizer**: Standardizes extracted entity terms and units using a versioned YAML terminology dictionary (e.g. `OPU` = `Ovum Pickup` = `Oocyte Retrieval` = `Egg Retrieval`; `EMBRYO_TRANSFER` = `ET`).
8. **Materializer**: Converts verified claims into rows in existing typed clinical tables (`investigations`, `treatment_events`, `oocyte_retrievals`, `embryos`, etc.), populating `materialized_table` and `materialized_row_id` on the claim.
9. **Seed Provenance Backfill**: All seed data rows are backfilled into `clinical_claims` with `extraction_method = 'seed'` and `validation_status = 'VERIFIED'` so both seed data and uploaded documents share an identical provenance chain.
10. **Engine Trigger & Summary Invalidation**: Deterministic engines recompute timeline, stage, follow-ups, conflicts, and gaps. Any cached patient summary is marked `is_stale = true`.

### 16.2 Cross-Hospital Governance & Role Scoping
- **Hospital Scope**: Every clinical row retains its originating hospital (`org_id`). This origin is immutable and never changes upon transfer.
- **Access Delegation**: Hospitals access patient records only when an active entry exists in `patient_hospital_access` (`access_level`: `READ_ONLY` or `READ_WRITE`, `status`: `ACTIVE`).
- **Transfer Requests**: Initiated by hospital admins via `transfer_requests` (`from_hospital_id`, `to_hospital_id`, `consent_id`). Decided by the sending hospital admin. Approving a transfer creates an active grant in `patient_hospital_access`.
- **Consent Governance**: Patient consents in `consents` govern the legal basis for transfer requests (`granted_to_hospital_id`, `purpose`, `scope`, `status`: `ACTIVE`, `REVOKED`, `EXPIRED`).
- **Patient Privacy**: Patient users have read-only access strictly scoped to their own `patient_id`. Clinical notes, AI summaries, and conflict alerts remain invisible to patients unless `PATIENT_SEES_AI_SUMMARY = true`.

### 16.3 Persistent Conflicts and Documentation Gaps
- **Conflicts**: Persistent records in `conflicts` (`patient_id`, `field`, `claim_ids`, status `OPEN | ACKNOWLEDGED`). Conflicting values from different sources/hospitals are preserved side-by-side. Clinicians acknowledge conflicts with an explanatory note; they are never auto-resolved.
- **Documentation Gaps**: Persistent records in `documentation_gaps` (`patient_id`, `cycle_id`, `rule_id`, `trigger_claim_id`, `expected_item`, status `OPEN | ACKNOWLEDGED | RESOLVED`). Triggered when clinical protocol rules (e.g. OPU without subsequent embryology report) detect missing records.

### 16.4 Q&A Clinical Recommendation Refusal
- The `POST /patients/{id}/ask` endpoint enforces Safety Rule S1 through a deterministic classifier before reaching the generative layer.
- If a query solicits clinical recommendations or imperative guidance (`should`, `recommend`, `increase dose`, `decrease dose`, `what next`, `which protocol`, `advise`), the request is blocked with:
  *"I can only report what is documented in the records. I cannot provide clinical recommendations."*
- Factual lookups of documented data ("what dose was administered on day 5?") proceed through verified retrieval.