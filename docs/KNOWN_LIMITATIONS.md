# OVA — Known Limitations & Out-of-Scope Architecture

In accordance with clinical safety principles and engineering transparency, this document articulates what is mocked, current architectural trade-offs, and what is intentionally out of scope for the OVA platform prototype.

---

## 1. What is Mocked vs. What is Real

### 1.1 Synthetic Patient Cohort
* **Current State:** All patient data (P-101 through P-106), hospital documents (REC-0101 through REC-0601), cycle records, embryology logs, and lab results are **100% synthetic**. They were engineered based on real-world Assisted Reproductive Technology (ART) clinical workflows, ESHRE/ASRM guidelines, and common cross-clinic documentation discrepancies.
* **Production Path:** Transition to real clinical deployments requires HIPAA / GDPR / Indian Digital Personal Data Protection (DPDP) Act compliance, Business Associate Agreements (BAA), and Institutional Review Board (IRB) ethics approval.

### 1.2 LLM Providers (Mock, NVIDIA NIM, and Gemini)
* **Default Mode:** By default, the application runs with `LLM_PROVIDER=mock`. The mock provider acts as a deterministic generative emulator that parses section contexts and generates candidate JSON claims to test validator pipelines instantaneously without external network calls or API costs.
* **NVIDIA NIM Integration:** Fully implemented and verified `NvidiaClient` (`backend/app/services/ai/llm/nvidia.py`) running on the high-performance **`meta/llama-3.2-11b-vision-instruct`** model hosted on NVIDIA NIM API catalog. Tested and verified for low latency, zero hallucination, and strictly constrained clinical JSON schema generation. Set `LLM_PROVIDER=nvidia` with `NVIDIA_API_KEY` to run with real live inference.
* **Google Gemini Client:** An integrated `GeminiClient` (`backend/app/services/ai/llm/gemini.py`) using Google GenAI SDK (`google-genai`). Setting `LLM_PROVIDER=gemini` with a valid `GEMINI_API_KEY` activates Gemini generative extraction.
* **Trade-off:** Real cloud LLM calls introduce external network latency (1.5 to 10 seconds depending on provider traffic), which is why OVA's dual-engine deterministic fallback pipeline (`degraded.py`) was engineered to guarantee zero downtime.

### 1.3 Optical Character Recognition (OCR) Preprocessing
* **Current State:** Hospital records (`SourceRecord`) are stored as pre-extracted, UTF-8 clinical text documents with pre-computed character offsets (`span: {start, end}`).
* **Out of Scope:** Native computer-vision OCR on raw scanned TIFF/JPEG faxed lab reports, handwriting transcription, or image skew correction is out of scope for this prototype. In a hospital EHR environment, an enterprise OCR pipeline (e.g. Google Cloud Document AI) would precede OVA ingestion.

---

## 2. Ingestion & Connectivity Scope

### 2.1 Static Seed Ingestion vs. Live EHR Integration
* **Current State:** Ingestion is executed via `seed_loader.py` loading validated JSON fixtures into SQLite.
* **Out of Scope:** Direct bi-directional integration with hospital EHR protocols (HL7 v2 ADT/ORU feeds, FHIR R4 Resources, or DICOM imaging archives from ultrasound machines) is currently out of scope. In production, OVA would act as an event-driven microservice consuming FHIR `Observation`, `DiagnosticReport`, and `Procedure` streams.

### 2.2 Vector Databases & Semantic Embeddings
* **Architectural Decision:** OVA intentionally **does not use a Vector Database (RAG)** for clinical information extraction.
* **Rationale:** Vector similarity searches suffer from semantic drift, hallucinated nearest neighbors, and silent retrieval failures in numerical lab values (e.g., retrieving an AMH of 1.2 instead of 2.4 because the texts are semantically identical). OVA relies on deterministic database indexing and literal keyword extraction with strict character-span validation.

---

## 3. Clinical & Regulatory Boundaries (Rule S1)

### 3.1 Non-Prescription & Non-Advisory Principle
* **Strict Constraint:** Under **Safety Rule S1**, OVA is strictly a **decision-support and audit verification platform**.
* **Hard Limitations:**
  * OVA **never** recommends drug dosages (e.g. *"Increase Gonal-F to 300 IU"*).
  * OVA **never** proposes treatment protocols or diagnostic conclusions.
  * OVA **never** calculates prognostic pregnancy success probabilities.
* Any user query attempting to solicit treatment recommendations is rejected with a polite fixed message:
  > *"I can only report what is documented in the patient's records. I cannot provide clinical recommendations, treatment plans, or dosage decisions."*

---

## 4. Infrastructure & Database Limitations

### 4.1 SQLite Single-Node Concurrency
* **Current State:** Database storage uses SQLite with WAL mode (`check_same_thread=False`). Per-patient threading locks (`threading.Lock`) prevent race conditions during summary generation.
* **Limitation:** While well-suited for single-container local deployments, SQLite does not support horizontal multi-node scaling.
* **Production Path:** PostgreSQL 16+ with row-level security (RLS), connection pooling via PgBouncer, and distributed locks (Redis Redlock).

### 4.2 Language & Terminology
* **Current State:** The clinical terminology lexicons, regex engines, and policy filters are optimized for **English-language** reproductive endocrinology records and international IVF abbreviations (OPU, ET, FET, ICSI, PGT-A, AMH, E2, OHSS).
* **Limitation:** Multilingual clinical records (e.g., Hindi, Kannada, Spanish) or non-fertility medical subspecialties (cardiology, oncology) are not supported in this version.
