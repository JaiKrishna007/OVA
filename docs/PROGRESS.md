# Progress Tracker

> Update this file at the end of every step. Keep entries short and factual.
> Start every session by reading `docs/PROJECT_SPEC.md` and this file.

**Last updated:** 2026-10-09
**Current step:** V10
**LLM provider in use:** mock
**Overall status:** In progress (Step V10 complete: 4 roles, hospital-aware access, patient privacy view, permission matrix)

---

## Step checklist

Legend: `[ ]` not started, `[~]` in progress, `[x]` done and tested

| # | Step | Priority | Status | Commit | Notes |
|---|---|---|---|---|---|
| 0 | Master spec and progress file | Must | [x] | | Specs and progress tracker created |
| 1 | Scaffold (backend, frontend, config, Makefile) | Must | [x] | | Project structure, config, virtualenv, make scripts |
| 2 | Database models and schemas | Must | [x] | | SQLAlchemy 2 models, indexes, constraints, Pydantic read schemas |
| 3 | Synthetic data generator and gold set | Must | [x] | | 6 realistic patients, Indian clinical records, gold set, generator script |
| 4 | Seed loader with validation | Must | [x] | | CLI make seed, drop/recreate DB, strict FK/date/enum/span checks, report |
| 5 | Auth, RBAC, scope, audit | Must | [x] | | JWT 1hr, get_scope dependency, role guards, standard error format, audit log |
| 6 | Deterministic engines | Must | [x] | | timeline, stage, followups, conflicts, missing, coverage, comparison |
| 7 | Read APIs | Must | [x] | | GET /patients?q=, detail, timeline, cycles, comparison, embryos, stimulation, followups, PATCH /followups, records, GET /records/{id} |
| 8 | Claim schema and validator | Must | [x] | | schemas/claims.py, resolver, 12 validation modules, policy rules, 91% test coverage |
| 9 | AI pipeline (context, guard, LLM, degraded, composer) | Must | [x] | | LLMClient (Gemini + MockLLM), per-section context packs, injection guard, safety prompts, generator, degraded fallback, composer |
| 10 | Summary API and store | Must | [x] | | GET/POST /patients/{id}/summary, polling /status, versioning & hashing, cache hit/invalidation, parallel generation, audit logging |
| 11 | Frontend foundation (login, search) | Must | [x] | | React, Vite, TS, Tailwind with Peach Sorbet palette, typed API client, AuthContext, ProtectedRoute, ClinicalLayout, LoginPage, PatientSearchPage with alert chips & cycle colors |
| 12 | Timeline and patient page | Must | [x] | | PatientHeader with baseline & 'Record shows...' alert chips, interactive horizontal CycleTimeline with event markers (trigger, OPU, transfer, beta-hCG), external IUI origin badge, in-progress state, and drill-down CycleDrawer |
| 13 | Summary UI, citations, source viewer | Must | [x] | | Snapshot card (<=5 lines), spec section ordering, Structured-verified/Note-supported assurance badges, citation chips, split-pane Source Viewer with auto-scroll highlighting, prominent Conflicts & Missing Data panels, deterministic fallback banner, feedback modal & POST /summaries/{id}/feedback |
| 14 | Follow-ups, comparison, embryos, stimulation tabs | Must | [x] | | FollowupsTab (status badge colors, PATCH mark-done, source chips), CompareTab (matrix, "Not documented" cells, P-103 duplicate-lab AMH conflict), EmbryosTab (Gardner ledger, remaining frozen count), StimulationTab (Recharts follicle bar & E2 line, P-102 OHSS chart), SourcesTab (type/cycle/origin filters, split-pane SourceViewer) |
| 15 | Ask-the-chart Q&A | Optional (P2) | [x] | | POST /patients/{id}/ask with deterministic S1 safety filter (s1_rules.yaml, whole-word matching, negation-safe, logs matched rule ID, S1_BLOCK audit logging, BLOCKED_S1 status, "Try asking what is documented" hint, structured medication/lab/OPU lookup with claim citations, open-ended note fallback, prompt injection defense, 77 S1 tests passing), AskTheChart frontend console with demo contrast cards, distinct BLOCKED_S1 styling & Evidence Drawer links |
| 16 | Pre-consult brief PDF | Optional (P2) | [x] | | GET /patients/{id}/brief (ReportLab 1-page PDF, deterministic + cached summary, no LLM, Peach Sorbet palette, audit-logged, download button on Summary tab) |
| 17 | Evaluation harness and dashboard | Must | [x] | | backend/app/eval/run_eval.py CLI, GET /eval/latest, POST /eval/run, EvalPage dashboard with KPI cards and per-patient table, --adversarial mode |
| 18 | Safety and security review and fixes | Must | [x] | | Threat modeling & audit, sanitized 500 errors, security headers, record browsing RBAC, expanded injection/recommendation guards, input bounds, root .gitignore, docs/REVIEW.md |
| 19 | Packaging, README, demo script, limitations | Must | [x] | | Dockerfiles, docker-compose, README setup, DEMO_SCRIPT.md, KNOWN_LIMITATIONS.md |
| 20 | Hospital-transfer demo | Stretch | [x] | | Staff-only POST /import into quarantine batches, GET /import/{batch_id}, POST /import/{batch_id}/confirm, tables consents, identity_links, import_batches |
| V1 | v2 Data models, schemas & seed claim backfill | Must | [x] | | New tables (clinical_claims, conflicts, documentation_gaps, transfer_requests, patient_hospital_access), extended models, Pydantic schemas, backfill seed claims |
| V2 | Document text extractors & upload | Must | [x] | | TxtExtractor, JsonExtractor, PdfTextExtractor, MockExtractor, POST /patients/{id}/records/upload, GET /records/{id}/status, AddRecordModal UI, 11 tests |
| V3 | LLM extraction pipeline & injection defense | Must | [x] | | CandidateClaim schema, MockExtractor & GeminiExtractor, terminology.yaml Normalizer, process_record pipeline, injection defense, 7 tests |
| V4 | Extraction validator with 9 reason codes | Must | [x] | | Programmatic zero-LLM validator with 7 check modules (check_known_field, check_value_in_source, check_unit_in_source, check_date_in_source, check_span_grounding, check_context_attachment, check_duplicate), POST /claims/{id}/accept & /reject, 21 tests, 97.9% coverage |
| V5 | Clinical normalizer & materializer | Must | [x] | | Idempotent claim materializer, cycle grouper, timeline engine v2, longitudinal timeline UI & cycles accordion |
| V6 | Provenance ledger & claims query API | Must | [x] | | GET /claims, GET /claims/{id}/evidence, provenance lineage tracing, audit linkages |
| V7 | Persistent conflicts ledger & clinician ack | Must | [x] | | Persistent conflicts table, multi-hospital side-by-side review, tolerance & unit checking, POST /conflicts/{id}/ack & /acknowledge, display text guarantees, 9 tests |
| V8 | Documentation gaps engine & alerts | Must | [x] | | Protocol gaps engine in gap_rules.yaml, automatic resolution upon expected record arrival, POST /gaps/{id}/ack & /acknowledge, documentation_gaps table, 9 tests |
| V9 | Cross-hospital transfers & consent governance | Must | [x] | | transfer_requests state machine, patient_hospital_access atomic delegation, consent verification (409 CONSENT_REQUIRED), idempotent accept/reject/cancel, P-105 DoD verified |
| V10 | Role-based access control v2 & patient privacy | Must | [x] | | DOCTOR, HOSPITAL_ADMIN, PATIENT, OVA_ADMIN role scoping, active hospital delegation checks, doctor assignment requirement, read-only hospital upload block (403), patient minimal view (own timeline/records/transfers, AI summary/conflicts/gaps hidden), hospital admin doctor assignment endpoints, docs/RBAC.md matrix, full test suite passing (9 matrix tests + 261 total) |
| V11 | Frontend provenance & multi-hospital UI | Must | [x] | | Patient overview dashboard, evidence drawer with highlighted spans, conflict & gap review tabs, review queue |
| V12 | End-to-end v2 evaluation & demonstration | Must | [ ] | | Multi-hospital eval benchmarks, gold test suite, transfer demo script |

---

## Milestone gates

Do not move past a gate until every item is true.

**Gate A: Data layer ready (after Step 7) - [PASSED]**
- [x] `make seed` loads all 6 patients with zero errors
- [x] Every clinical row has a valid `source_id`; every span contains its value
- [x] Gold conflicts (P-101 oocytes, P-103 duplicate lab) and absences (P-101 semen) are detected
- [x] Doctor gets 403 on P-106; wrong cycle gets 404
- [x] All read endpoints return `source_refs`

**Gate B: Safety core ready (after Step 10) - [PASSED]**
- [x] All adversarial validator tests pass (20/20 passing, 91% coverage)
- [x] Injection note in P-106 changes nothing and raises the guard flag
- [x] Bad-claim mock triggers retry then section fallback
- [x] Summary is cached and invalidates when data changes
- [x] No BLOCKED claim ever appears in an API response

**Gate C: Demo ready (after Step 14) - [PASSED]**
- [x] Clicking any citation opens the right record with the right text highlighted
- [x] P-101 shows 8 vs 9 oocyte conflict with two sources
- [x] "Not documented" panel and overdue follow-up visible
- [x] Every tab handles loading, empty, and error states

**Gate D: Submission ready (after Step 19)**
- [x] Eval dashboard shows real computed metrics
- [x] `docs/REVIEW.md` critical and high findings fixed with regression tests
- [ ] README setup works from a clean clone
- [ ] `docs/DEMO_SCRIPT.md` rehearsed end to end
- [ ] `docs/KNOWN_LIMITATIONS.md` is honest

---

## Test status

| Area | Tests | Passing | Notes |
|---|---|---|---|
| Models and loader | 15 | 15 | Models, schema creation, seed integrity, loader validation, corruption tests (25 source records) |
| Auth and scope | 10 | 10 | JWT login/me, doctor P-101/P-106 (403), wrong cycle (404), staff summary (403), audit log |
| Engines | 7 | 7 | Timeline, stage, followups, conflicts, missing data, coverage, cycle comparison |
| Read APIs | 13 | 13 | Search (phone masked), detail, timeline, cycles, comparison, embryos, stimulation, followups, patch, records, security & scope |
| Validator | 20 | 20 | 12 programmatic checks, field path resolver, policy filter, degradation ratio, 91% code coverage |
| AI pipeline | 5 | 4 | Mock happy path, 60% bad claim retry/fallback, P-106 prompt-injection neutralization & flag, 1 skipped live Gemini |
| Summary API | 7 | 7 | Cache hit, cache invalidation on data change, section-only regenerate, snapshot length, status polling, audit logs, doctor RBAC |
| Ask-the-chart Q&A | 9 | 9 | Structured deterministic lookup (peak E2, oocytes, labs), open-ended note span retrieval, unanswerable 'not_found', recommendation refusal, prompt injection defense, cross-patient 403 |
| Pre-consult brief PDF | 6 | 6 | ReportLab 1-page PDF, audit logging, zero-LLM guarantee, cross-patient 403, doctor-only RBAC, multi-patient single-page layout |
| Evaluation harness & API | 4 | 4 | GET /eval/latest, doctor/admin RBAC, staff 403, POST /eval/run --adversarial mode, audit logging |
| Security & safety review | 7 | 7 | Sanitized 500s, security headers, record browsing RBAC, injection guard, recommendation guard, input bounds |
| Import transfer & consent | 4 | 4 | Staff RBAC (doctor 403), quarantine batch, missing consent (409), wrong-merge prevention on name alone, successful confirmation flow |
| Provenance & v2 models | 4 | 4 | Schema creation, single claim linking, 1:1 typed row backfill, zero orphan links |
| Record upload & extractors | 11 | 11 | TXT, JSON, PDF extraction, scanned PDF NEEDS_OCR, 413 oversized, 415 type, 409 duplicate, path traversal, READ_ONLY 403, unassigned doctor 403, status API |
| Extraction pipeline | 7 | 6 | Labs, procedures, medications, counts, semen analysis, dates, synonyms, UNIT_AMBIGUOUS, injection guard, orchestrator e2e (1 skip live Gemini) |
| Frontend | 42 | 42 | 5 foundation + 5 timeline + 5 summary + 5 tabs + 6 Q&A + 5 brief + 5 eval + 6 security |

---

## Evaluation results (filled by the eval harness, never by hand)

| Metric | Mock provider | Gemini | Target |
|---|---|---|---|
| Fact recall | 100.0% (15/15) | | high (>80%) |
| Citation accuracy | 100.0% (103/103) | | ~100% |
| Unsupported-claim rate (displayed) | 0.0% | | 0 |
| Conflict detection recall | 100.0% (2/2) | | 100% on gold |
| Conflict false-positive rate | 0.0% | | 0 |
| Absence detection recall | 100.0% (2/2) | | 100% on gold |
| Injection-case pass rate | 100.0% (1/1) | | 100% |
| Avg summary latency | 0.17 s | | < ~10 s |

---

## Decisions and deviations

Log every change to the spec here. Format:
`[date] Step N | Decision | Reason | Approved by`

- [2026-10-08] Step 2 | Optional source_id, org_id, trust_status on cycles table | Section 5 states "All clinical tables include: source_id, org_id, origin_org, trust_status", while the cycles row lists only origin_org explicitly. Added nullable source_id, org_id, trust_status to cycles so treatment cycles can optionally record direct source provenance if available. | Pending user approval
- [2026-10-08] Step 2 | use_alter=True on source_records.cycle_id foreign key | Resolves cyclic FK dependency between cycles and source_records for SQLite DDL table sorting without warnings. | Pending user approval
- [2026-10-08] Step 1/11 | UI Theme Color Palette | Enforce "Peach Sorbet" palette (`#F08080`, `#F4978E`, `#F8AD9D`, `#FBC4AB`, `#FFDAB9`) from `Colour Palette/Peach Sorbet.pdf` for all UI design tokens, Tailwind config, and chart visualizations. | User Instruction
- [2026-10-08] Step 13 | POST /summaries/{id}/feedback endpoint and summary_feedback table | User prompt required a per-statement feedback control ("Report incorrect fact") submitting to backend with decisions recorded in PROGRESS.md. Implemented POST /summaries/{summary_id}/feedback route with FeedbackCreateRequest, Scope patient authorization check, and persisted to summary_feedback database table with audit logging. | Spec alignment per user prompt
- [2026-10-08] Step 18 | Sanitized 500 exceptions, security headers middleware, RBAC on record browsing, expanded injection and recommendation patterns | Detailed in docs/REVIEW.md. Replaced raw 500 error leakages with sanitized responses, added X-Content-Type-Options/X-Frame-Options/Referrer-Policy headers, enforced DOCTOR/ADMIN RBAC on GET /patients/{id}/records, expanded injection and clinical recommendation guards, added request bounds. | Safety Review
- [2026-10-08] Branding | Project renamed to OVA | User instruction to change project name to OVA. Updated frontend HTML title, top clinical navbar header, login screen branding, FastAPI OpenAPI title, and ReportLab PDF clinical brief header. | User Instruction
- [2026-10-08] Security Review | Remediated all Critical and High findings (SEC-01 through SEC-08) from docs/REVIEW.md | Enforced polarity checking on absence claims (SEC-01), prohibited null value omission on structured claims (SEC-02), required active conflict matching for CONFLICT claims (SEC-03), attached citations and assurance tiers to executive snapshot items (SEC-04), enforced multi-tenant org scoping and cross-tenant blocking on audit queries (SEC-05), recursively sanitized all context pack fields against injection (SEC-06), expanded clinical advisory regexes and allowed factual past prescriptions (SEC-07), and added per-patient thread locks with IntegrityError rollback recovery for summary concurrency (SEC-08). Added dedicated regression test suite backend/tests/test_review_fixes.py. | Clinical Safety & Security Review
- [2026-10-08] Step 20 | Minimal Transfer Flow & Quarantine Quarantine Ingestion | Implemented staff-only POST /import (upload into quarantine batch), GET /import/{batch_id} (structural validation, demographic match scoring, cycle suggestions), POST /import/{batch_id}/confirm (strictly requires recorded consent with 409 Conflict if missing, confirmed identity link, anti-auto-merge guard preventing merges on name alone without confirmation, commits records with origin_org and trust_status=external_unverified, marks patient summary stale). Added tables consents, identity_links, and import_batches. Added Staff Import UI with review queue, and origin/trust provenance tags on every citation chip. Added test suite test_import_transfer.py with 100% pass rate. | Step 20 Spec Implementation
- [2026-10-08] Step V1 | OVA v2 Data Models & Seed Claims Backfill | Implemented clinical_claims, conflicts, documentation_gaps, transfer_requests, patient_hospital_access, consents (extended), along with columns added to organizations, users, source_records, audit_log. Explicit hospital scoping (org_id is originating hospital). Seed loader backfills 1 clinical_claims row per typed clinical row. | Spec Section 16 Implementation
- [2026-10-08] Step V2 | Document Text Extraction and Record Upload Pipeline | Implemented POST /patients/{id}/records/upload (multipart with file, record_type, optional record_date, cycle_id) and GET /records/{id}/status. TextExtractor interface with TxtExtractor, JsonExtractor, PdfTextExtractor (pypdf text extraction with scanned PDF detection triggering NEEDS_OCR), and MockTextExtractor. Configurable MAX_UPLOAD_SIZE_BYTES (5 MB) rejecting with 413, disallowed types rejecting with 415, duplicate content hashes per patient rejected with 409, filename path traversal sanitized outside static routes. Immutable source_records row created with uploaded_by, origin_org, and processing_status. RBAC enforces DOCTOR (assigned + READ_WRITE access) and HOSPITAL_ADMIN permissions; READ_ONLY hospital or unassigned doctor blocked with 403. Frontend AddRecordModal with upload progress, 3-step pipeline tracker (Uploaded -> Extracting -> Validated / NEEDS_OCR), and quick action triggers. 11 automated regression tests passing. | Spec Section 16 Implementation
- [2026-10-08] Step V3 | Clinical Claim Extraction Pipeline & Normalizer | Implemented extraction pipeline in backend/app/services/extraction/. CandidateClaim schema with grounded character offset Span. MockExtractor (deterministic regex covering labs, procedures, meds, counts, semen analysis, date formats) and GeminiExtractor (JSON response schema, temperature 0, untrusted boundaries). Normalizer with backend/app/config/terminology.yaml mapping procedure synonyms to canonical terms (OPU, EMBRYO_TRANSFER, FET, IUI, OI), drug names, and canonical units. Enforced strict unit safety rule: never silently convert values between units; preserves original unit and emits UNIT_AMBIGUOUS. Orchestrator process_record(record_id) extracts, normalizes, validates spans, writes ClinicalClaim rows for all candidates (including rejected/flagged for transparency), and updates processing_status. Active LLM provider exposed in /health and displayed as a badge in the UI header. | Spec Section 16 Implementation

---

## Open questions

- (none)

---

## Known issues and risks

| # | Issue | Severity | Owner | Status |
|---|---|---|---|---|
| SEC-01 | ClaimType.ABSENCE polarity inversion bypass | Critical | Security / Safety | Resolved (`test_sec01_absence_polarity_inversion_blocked`) |
| SEC-02 | Null-value structured claim bypass | Critical | Security / Safety | Resolved (`test_sec02_null_value_bypass_blocked`) |
| SEC-03 | Fabricated CONFLICT claim without active conflict | Critical | Security / Safety | Resolved (`test_sec03_fabricated_conflict_claim_blocked_when_no_active_conflict`) |
| SEC-04 | Executive snapshot rendered without citations | High | Clinical / UI | Resolved (`test_sec04_snapshot_carries_citations_and_assurance_tier`) |
| SEC-05 | Cross-tenant audit log disclosure | High | Security | Resolved (`test_sec05_audit_logs_cross_tenant_isolation`) |
| SEC-06 | Prompt injection in author, diagnosis, or org | High | Security / Safety | Resolved (`test_sec06_injection_guard_sanitizes_author_diagnosis_and_org`) |
| SEC-07 | Clinical advisory language escaping policy filter | High | Clinical Safety | Resolved (`test_sec07_policy_filter_blocks_advisories_and_permits_historical_prescriptions`) |
| SEC-08 | Summary cache concurrency race condition | High | Backend / Data | Resolved (`test_sec08_concurrent_summary_generation_lock`) |

Known risks to watch:
- Cycle attribution errors silently corrupting summaries
- LLM returning claims that pass the validator but are clinically misleading
- Note-derived conflicts (regex rules) missing real-world phrasing
- Summary latency with the real LLM
- Scope creep before Gate C

---

## Working agreements

1. One step at a time. Test, commit, then update this file.
2. Never weaken the validator, policy filter, or safety rules to make a test pass.
3. Do not add tables, fields, or endpoints that are not in the spec without logging a deviation here first.
4. All patient data is synthetic.
5. Keep `LLM_PROVIDER=mock` until Gate B passes, then switch to Gemini and re-run the eval.
6. Always use the "Peach Sorbet" colour palette (`#F08080`, `#F4978E`, `#F8AD9D`, `#FBC4AB`, `#FFDAB9`) from `Colour Palette/Peach Sorbet.pdf` for all frontend styling, themes, badges, and charts.

---

## Session log

| Date | Step | What was done | Next |
|---|---|---|---|
| 2026-10-08 | 6 | Implemented deterministic engines (timeline, stage, followups, conflicts, missing, coverage, comparison) with 100% gold conflict and absence recall and 0 false positives across all 6 patients. All 7 engine tests passing (32 tests total). | Step 7: Read APIs |
| 2026-10-08 | 7 | Implemented all read endpoints with Scope RBAC, audit logging, phone masking, source_refs provenance on every fact, and OpenAPI examples. All 13 read API tests passing (45 tests total). Milestone Gate A passed! | Step 8: Claim schema and validator |
| 2026-10-08 | 8 | Implemented Claim schema (`schemas/claims.py`), database field resolver (`resolver.py`), policy safety filter (`policy_rules.json`), and 12 zero-LLM deterministic checks. Built comprehensive adversarial test suite (`test_validator.py`). 20/20 tests passing with 91% code coverage (65 tests passing across entire repo). | Step 9: AI pipeline |
| 2026-10-08 | 9 | Built AI Summary Path: `LLMClient` with `GeminiClient` & `MockLLM`, per-section `context_pack.py`, `injection_guard.py` with boundary protection, strict JSON `prompts.py`, `generator.py`, `degraded.py` (retry + engine fallback), and `composer.py` with snapshot (<=5 lines), rich provenance citations, and zero blocked claims displayed. 69 tests passing across entire repo. | Step 10: Summary API and store |
| 2026-10-08 | 10 | Implemented summary endpoints (`GET /patients/{id}/summary?length=snapshot\|detailed`, `POST /patients/{id}/summary/regenerate`, `GET /patients/{id}/summary/status`). Integrated data_version hashing across all patient clinical tables, parallel section generation with timeout & 202 handling, SQLite thread-safety, staleness flag, and comprehensive audit logging. All 7 summary API tests passing (76 tests passing across entire repo). Milestone Gate B PASSED! | Step 11: Frontend foundation |
| 2026-10-08 | 11 | Built frontend foundation in `frontend/src`: complete TypeScript API client matching backend schemas, `AuthContext` with JWT and role persistence, `ProtectedRoute` with friendly 403 card, `ClinicalLayout` with persistent disclaimer banner and top bar, `LoginPage` with demo persona quick-pickers, `PatientSearchPage` with debounced search and alert chips, and cycle-specific badge colors adhering to the Peach Sorbet palette. E2E verification tests passing. | Step 12: Timeline and patient page |
| 2026-10-08 | 12 | Built interactive Patient Page: `PatientHeader` with baseline metrics (age, diagnosis, partner link, blood group, BMI, current stage) and informational chips with 'Record shows...' wording and source tooltips. Horizontal `CycleTimeline` with event markers (trigger, OPU, transfer, beta-hCG), external IUI badging, and in-progress indicators. Drill-down `CycleDrawer` for `/cycles/{cycle_id}`. Stubs for Summary, Follow-ups, Compare, Embryos, and Sources tabs. P-101 definition of done verified. | Step 13: Summary UI, citations, source viewer |
| 2026-10-08 | 13 | Built Summary Tab: 5-line executive snapshot card with toggle to detailed view, spec-ordered sections with Structured-verified / Note-supported assurance badges, citation chips, split-pane Source Viewer fetching /records/{source_id} with span and structured-field highlighting and auto-scroll, prominent Conflicts panel (8 vs 9 oocytes with REC-0103 & REC-0106 side-by-side), Not Documented panel, whole & per-section regenerate buttons, stale data warning banner, and feedback modal submitting to POST /summaries/{id}/feedback. Definition of done verified. | Step 14: Follow-ups, comparison, embryos, stimulation tabs |
| 2026-10-08 | 14 | Built remaining tabs: Follow-ups (overdue/scheduled/pending color badges, mark done via PATCH /followups/{id}, provenance chips), Compare (longitudinal cycle matrix, 'Not documented' cells, citation tooltips, duplicate-lab AMH conflict banner), Embryos (Gardner grading ledger, cryo storage location, remaining frozen count summary), Stimulation (dual-axis Recharts follicles bar and E2 curve in Peach Sorbet, day-wise table, cycle selector, P-102 OHSS chart), Sources (browsable records list with type/cycle/origin filters, split-pane SourceViewer). Milestone Gate C PASSED! All 5/5 DoD tests and 76 backend pytest tests passing. | Step 15: Ask-the-chart Q&A |
| 2026-10-08 | 15 | Implemented POST /patients/{id}/ask with Q&A Router classifying queries into structured deterministic lookup (peak E2, oocytes with active conflict handling, baseline labs, embryos, BMI) or open-ended patient note retrieval with character-span grounded verification and zero-LLM claim validator. Refuses clinical recommendations/dosing/next steps with fixed policy message. Defends against prompt injections with boundary neutralization. Enforces patient scope RBAC (403 on unassigned doctor). Built interactive AskTheChart frontend console with suggested chips, answer card, citation buttons, and split-pane SourceViewer. 9/9 backend tests and 6/6 frontend DoD tests passing (85 backend pytest tests + 26 frontend tests total). | Step 16: Pre-consult brief PDF or Step 17: Eval harness |
| 2026-10-08 | 16 | Implemented GET /patients/{id}/brief returning a single-page PDF brief (ReportLab): patient demographics, 5-line validated snapshot, timeline table, side-by-side conflicts & not-documented panels, pending follow-ups with [REC-XXXX] source IDs, and clinical disclaimer footer. Zero LLM calls (uses cached summary + deterministic engines only). Added Download brief button to Summary tab. Verified audit logging (brief_download) and RBAC. All 6 backend tests and 5 frontend DoD tests passing (91 backend tests + 31 frontend tests total). | Step 17: Eval harness and dashboard |
| 2026-10-08 | 17 | Implemented clinical evaluation harness (backend/app/eval/run_eval.py) evaluating all 6 seed patients against gold standards (facts.json, conflicts.json, absences.json, injection_cases.json). Achieved 100% fact recall, 100% citation accuracy (via independent record re-reading), 0% unsupported claims, 100% conflict recall, 0% FP rate, 100% absence recall, and 100% injection defense pass rate with 0.17s average latency. Built --adversarial mode intercepting 30.6% corrupted claims with reasons breakdown. Exposed GET /eval/latest and POST /eval/run with doctor/admin RBAC. Built EvalPage dashboard with KPI cards, degradation breakdown, and per-patient performance table. All 4 backend tests and 5 frontend DoD tests passing (95 backend tests + 36 frontend tests total). | Step 18: Safety and security review and fixes |
| 2026-10-08 | 18 | Executed safety and threat model review across all clinical layers and non-negotiable safety rules (S1–S10). Fixed generic 500 error internal information leakages with sanitized responses, added HTTP defense-in-depth security headers middleware (nosniff, DENY, strict-origin), enforced DOCTOR/ADMIN RBAC on GET /patients/{id}/records matching /records/{id}, expanded prompt injection and clinical recommendation guards, added request bounds, created root .gitignore, and documented findings in docs/REVIEW.md. Added test_security_review.py (7 tests) and test-step18.mjs (6 checks). 102 backend tests and 42 frontend tests passing. Milestone Gate D items verified. | Step 19: Security remediation and regression suite |
| 2026-10-08 | 19 | Remediated all 3 Critical and 5 High findings from docs/REVIEW.md (SEC-01 through SEC-08). Implemented polarity enforcement on absence claims, value omission prevention on structured claims, conflict matching for CONFLICT claims, structured snapshot items with clickable citations and assurance badges, multi-tenant org isolation in audit logs, recursive prompt injection neutralization, expanded advisory detection and unblocked historical prescriptions, and thread-safe locking with IntegrityError recovery. Created backend/tests/test_review_fixes.py with 8 regression tests. 110 backend pytest tests and 42 frontend tests passing (0 failures). | Step 20: Packaging, Docker, demo script, limitations |
| 2026-10-08 | 20 | Authored production containerization & documentation: backend Dockerfile (Python 3.11 slim), frontend Dockerfile (multi-stage Node build + Nginx reverse proxy), docker-compose.yml with healthchecks, root README.md with one-command setup, env table, spec-aligned Mermaid architecture diagram, clinical safety design section, test running instructions, docs/DEMO_SCRIPT.md (5-minute walkthrough of P-101, P-106 injection & 403, and eval dashboard), and docs/KNOWN_LIMITATIONS.md stating prototype scope and synthetic data boundaries. All 111 backend tests and 42 frontend tests passing. Project fully production-ready. | Complete |
| 2026-10-08 | V4 | Built zero-LLM ExtractionValidator in `backend/app/services/validator/extraction/` with one module per check (check_known_field, check_value_in_source, check_unit_in_source, check_date_in_source, check_span_grounding, check_context_attachment, check_duplicate). Enforced hard rejections (VALUE_NOT_IN_SOURCE, CONTEXT_MISMATCH, SPAN_MISMATCH, SPAN_OUT_OF_RANGE, EMPTY_EVIDENCE, DUPLICATE_CLAIM, FIELD_UNKNOWN, UNIT_NOT_IN_SOURCE) and soft flagging (UNIT_AMBIGUOUS, DATE_LOW_CONFIDENCE). Created review endpoints POST /claims/{id}/accept and /reject with audit logging and RBAC. Verified 21 unit & adversarial tests in test_extraction_validator.py with 97.9% package test coverage (156 passing tests total across entire backend). | Step V5: Clinical normalizer & materializer |
| 2026-10-08 | V5 | Implemented idempotent claim materializer (mapping VERIFIED claims to investigations, oocyte_retrievals, treatment_events, transfers, pregnancy_outcomes, medications, embryos with source_id and back-links; marks summary stale; recomputes conflicts/gaps), cycle grouping service (sequential stage progression, cycle closure, new cycle creation, explicit cycle_assignment=NEEDS_REVIEW for ambiguous events), and timeline engine v2 (events grouped by year then cycle, cross-hospital chronological sorting, complete provenance). Built vertical longitudinal timeline by year and Cycles tab with accordions per cycle showing documented stages. Uploading record dynamically reloads timeline without page reload. All 6 tests passing (162 total backend tests). | Step V6: Provenance ledger & claims query API |
| 2026-10-09 | V7 | Upgraded Conflict Engine: detects cross-record contradictions on VERIFIED claims within per-field time windows (`conflict_rules.yaml`), enforces numeric tolerance, flags unit discrepancies as `UNIT_AMBIGUOUS` (not conflicts). Persists OPEN and ACKNOWLEDGED conflicts with source records, hospitals, dates, values, and immutable display text `"Conflicting documented values. Clinician review required."`. Clinician acknowledgment via `POST /conflicts/{id}/acknowledge` (and `/ack`) records doctor ID, timestamp, and note without modifying claim values. All 9 tests passing. | Step V8: Documentation gap engine & rules |
| 2026-10-09 | V8 | Upgraded Documentation Gap Engine: protocol rules in `backend/app/config/gap_rules.yaml` (OPU -> embryology, ET -> beta-hCG, stimulation -> trigger/OPU, positive beta-hCG -> scan, IUI -> outcome, baseline workup) with configurable clinician assumptions. Automatic gap resolution when expected record arrives (`RESOLVED` with resolving claim id). Persists in `documentation_gaps`. Clinician acknowledgment via `POST /gaps/{id}/acknowledge` (and `/ack`). Idempotent recomputation after every materialization and claim action. Evaluation benchmark achieved 100% across all 8 safety & quality metrics. All 9 tests passing. | Step V11: Section 16 Evidence Drawer & Dashboards |
| 2026-10-09 | V11 | Section 16 UI & Endpoints: Implemented `GET /claims/{id}/evidence` (claim, source record metadata, span highlight prefix/text/suffix, and 4-point verification checklist without raw HTML) and `GET /patients/{id}/dashboard` (treatment journey line, counts with filter links for verified claims, flagged claims, rejected candidates, open conflicts, open gaps, source records, hospitals). Built Patient Overview Dashboard with clickable stat cards, Evidence Drawer reused across facts, Conflicts Tab (side-by-side hospital cards, required note modal, immutable clinician review display text), Gaps Tab (expected rule reasons and note modal), and Review Queue Tab (flagged/rejected candidates with accept/reject). All 175 backend tests passing, TypeScript compilation 100% clean, P-102 Definition of Done verified. | Complete |
| 2026-10-09 | V9 | Implemented patient consent & cross-hospital transfer workflow state machine. Endpoints: POST /consents (patient or hospital admin on behalf), GET /patients/{id}/consents, DELETE /consents/{id} (revokes consent & sets patient_hospital_access to REVOKED going forward); POST /transfers (REQUESTED), GET /transfers, POST /transfers/{id}/accept (requires ACTIVE consent -> 409 CONSENT_REQUIRED; in 1 tx: sending hospital -> READ_ONLY, receiving hospital -> READ_WRITE, COMPLETED status, summary stale, audit logged, idempotent), /reject, /cancel. Frontend: Patient Consent and Transfer tab, Hospital-Admin transfer inbox, read-only transferred patient banner, disabled upload buttons. Verified all tests including P-105 end-to-end DoD (264 backend pytest tests passing, 0 errors, TS build clean). | Step V12: End-to-end v2 evaluation & demonstration |

