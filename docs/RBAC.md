# Role-Based Access Control (RBAC) & Hospital-Aware Access

This document specifies the four core roles and hospital-aware access delegation rules for OVA v2, in accordance with `docs/PROJECT_SPEC.md` (Section 16).

---

## 1. System Roles

| Role | Scope | Description |
|---|---|---|
| **`DOCTOR`** | Facility & Assigned Patients | Physician providing clinical care. Can view patient charts, request summaries, and ask Q&A only for patients assigned to them where their hospital has active access. Can perform clinical writes (upload records, accept/reject claims, acknowledge conflicts/gaps) only if their hospital has `READ_WRITE` access. |
| **`HOSPITAL_ADMIN`** | Facility-wide | Hospital administrator. Can view all charts accessible to their hospital, assign/unassign facility doctors to patients, view facility audit logs, and manage hospital transfers. Cannot access records of hospitals without an active delegation. |
| **`PATIENT`** | Self Only | Patient accessing their personal chart. Read-only view limited strictly to their own `patient_id`. Sees own timeline, personal records list, consents, and transfer requests. Clinical AI summary, persistent conflicts, documentation gaps, and validation flags are hidden by default unless `PATIENT_SEES_AI_SUMMARY=true`. Cannot perform any clinical writes. |
| **`OVA_ADMIN`** | Platform-wide (Non-clinical) | Central platform administrator. Has zero access to clinical patient charts, timelines, records, notes, or claims. Has full access to system audit logs, evaluation benchmarks, and platform configuration. |

---

## 2. Hospital Delegation & Write Permissions

1. **Active Hospital Access Rule:**
   - Any patient-scoped clinical endpoint requires that the user's hospital (`user.hospital_id` or `user.org_id`) possesses an **`ACTIVE`** record in `patient_hospital_access` for that `patient_id`.
   - Access levels:
     - `READ_WRITE`: Authorized for both retrieval and clinical modifications.
     - `READ_ONLY`: Authorized for viewing patient data, but strictly forbidden (403) from modifications.
     - `NO_ACCESS`: Missing or revoked delegation grant results in deterministic **403 Forbidden**.

2. **Doctor Assignment Rule:**
   - In addition to active hospital access, a `DOCTOR` must have an explicit assignment in `doctor_patients` (`doctor_id == user.id` and `patient_id == patient_id`).
   - Unassigned doctors receive **403 Forbidden**.

3. **Clinical Write Rule:**
   - Operations that write or alter patient data (`POST /patients/{id}/records/upload`, `POST /claims/{id}/accept`, `POST /claims/{id}/reject`, `POST /conflicts/{id}/ack`, `POST /gaps/{id}/ack`, `PATCH /followups/{id}`) require **`READ_WRITE`** access level.
   - Hospitals with `READ_ONLY` access receive **403 Forbidden** on write attempts.

4. **Patient Privacy Rule:**
   - Patients can only request their own patient ID (`user.patient_id == patient_id`). Cross-patient requests receive **403 Forbidden**.
   - `GET /patients/{id}/summary` returns **403 Forbidden** for patients unless `PATIENT_SEES_AI_SUMMARY=true`.
   - Conflicts and documentation gaps are clinical governance tools and remain strictly forbidden to patients.

5. **OVA Admin Privacy Rule:**
   - Platform administrators cannot access any patient-specific clinical endpoints (**403 Forbidden**).

---

## 3. Comprehensive Permission Matrix Table

| Endpoint / Action | DOCTOR (Assigned, RW Hospital) | DOCTOR (Assigned, RO Hospital) | DOCTOR (Unassigned, RW Hospital) | DOCTOR (Hospital with No Access) | HOSPITAL_ADMIN (RW Hospital) | HOSPITAL_ADMIN (RO Hospital) | HOSPITAL_ADMIN (No Access) | PATIENT (Own Chart) | PATIENT (Other Chart) | OVA_ADMIN |
|---|---|---|---|---|---|---|---|---|---|---|
| **Search / List Patients** (`GET /patients`) | 200 (Assigned) | 200 (Assigned) | 200 (Assigned) | 200 (Assigned) | 200 (Facility) | 200 (Facility) | 200 (Facility) | 200 (Own) | 200 (Own) | 403 |
| **Patient Profile** (`GET /patients/{id}`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 403 |
| **Timeline** (`GET /patients/{id}/timeline`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 403 |
| **Records List** (`GET /patients/{id}/records`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 403 |
| **View Record Detail** (`GET /records/{id}`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 403 |
| **AI Summary** (`GET /patients/{id}/summary`, default) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 403 | 403 | 403 |
| **AI Summary** (`GET /patients/{id}/summary`, flag enabled) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 403 |
| **Ask The Chart** (`POST /patients/{id}/ask`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 403 | 403 | 403 |
| **Pre-consult Brief PDF** (`GET /patients/{id}/brief`) | 200 | 200 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| **Upload Record** (`POST /patients/{id}/records/upload`) | 200 | 403 (RO) | 403 | 403 | 200 | 403 (RO) | 403 | 403 | 403 | 403 |
| **View Conflicts** (`GET /patients/{id}/conflicts`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 403 | 403 | 403 |
| **Acknowledge Conflict** (`POST /conflicts/{id}/ack`) | 200 | 403 (RO) | 403 | 403 | 200 | 403 (RO) | 403 | 403 | 403 | 403 |
| **View Gaps** (`GET /patients/{id}/gaps`) | 200 | 200 | 403 | 403 | 200 | 200 | 403 | 403 | 403 | 403 |
| **Acknowledge Gap** (`POST /gaps/{id}/ack`) | 200 | 403 (RO) | 403 | 403 | 200 | 403 (RO) | 403 | 403 | 403 | 403 |
| **Accept Claim** (`POST /claims/{id}/accept`) | 200 | 403 (RO) | 403 | 403 | 200 | 403 (RO) | 403 | 403 | 403 | 403 |
| **Reject Claim** (`POST /claims/{id}/reject`) | 200 | 403 (RO) | 403 | 403 | 200 | 403 (RO) | 403 | 403 | 403 | 403 |
| **Assign Doctor** (`POST /hospital-admin/doctor-assignments`) | 403 | 403 | 403 | 403 | 200 | 200 | 403 | 403 | 403 | 403 |
| **View Facility Audit** (`GET /audit`) | 403 | 403 | 403 | 403 | 200 | 200 | 200 | 403 | 403 | 200 (All) |
| **View Consents** (`GET /consents`) | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 (Own) | 403 | 403 |
| **View Transfers** (`GET /transfer-requests`) | 200 | 200 | 200 | 200 | 200 | 200 | 200 | 200 (Own) | 403 | 200 (All) |

---

## 4. Test Verification

Every combination in this matrix is programmatically verified by test fixtures in `backend/tests/test_rbac_matrix.py`, guaranteeing zero regression on clinical governance boundaries.
