# AI Debugging & Root-Cause Analysis Platform — Product & Engineering Plan

This document is the **authoritative plan** for building an AI debugging and root-cause analysis product **designed to win in a crowded market**: sharp wedge, measurable customer outcomes, honest positioning, and architecture that supports **speed to proof** first—scale and platform breadth second.

---

## 1. Vision (one paragraph)

Build a **system of record for AI pipeline behavior**: ingest execution traces from diverse AI systems (RAG, agents, copilots, chat), normalize them into a **canonical execution graph**, and help teams move from “what happened” to **ranked, evidence-backed hypotheses** about why failures occurred—delivered through **debugging-first UX**, not generic observability dashboards.

**Success in one sentence**: Teams repeatedly choose this product **when something breaks** because it **shortens time-to-plausible-cause** with **trustworthy evidence**—not because it has the most charts.

---

## 2. Market context & success thesis

### 2.1 The market is crowded—strategy, not denial

LLM tracing, evals, and “LLM ops” are **actively served** by LangSmith, Langfuse, Arize, W&B, general APM (Datadog, etc.), and cloud-native stacks. **Crowding is a distribution and differentiation problem**, not proof that “why did this fail?” is solved everywhere.

**This plan assumes**: you win by **owning a narrow workflow** (post-incident debugging and diagnosis) and **proving ROI on that workflow** before expanding surface area—not by claiming “universal platform” on day one.

### 2.2 What “successful” means (non-hand-wavy)

| Stage | Signal |
|-------|--------|
| **Validation** | A small set of **design partners** ship **production** traces; they report **faster** understanding of real failures vs their prior process (logs + ad hoc). |
| **Traction** | Repeat **weekly** usage by **investigators** (not one-off demos); expansion of trace volume and teams inside the same account. |
| **Sustainability** | **Paid** use tied to value (seats, trace volume, or enterprise tier)—not endless free POCs. |

**Out of scope for “success” in year one**: beating incumbents on every observability feature; being the default for every framework globally.

### 2.3 Moat (realistic)

Long-term defensibility is **not** a JSON schema alone. It is the combination of:

- **Workflow lock-in**: Investigators **start here** when debugging AI failures (bookmarks, runbooks, integrations).
- **Trust artifacts**: Hypotheses **tied to evidence** (step IDs, rule IDs); auditability for postmortems.
- **Data compounding**: Historical failures + feedback on hypotheses improve rules and ranking (carefully, with privacy).
- **Distribution**: **Adapters and “works beside X”** beat “replace your entire stack.”

Assume **incumbents can copy UI**; sustained advantage comes from **depth of diagnosis + trust + integration path** executed over multiple quarters.

### 2.4 Go-to-market validation (bake in from Phase 0)

**Design partners (target: 3–10 for Phase 0–2)**

- **Criteria**: Production RAG or tool-using agents; real incident volume; a **named champion** with authority to spend time integrating.
- **Ask**: 30–60 min/week for **failure scenarios** + feedback on **hypothesis usefulness** (thumbs / short reason).

**90-day proof (per partner or cohort)**

- **Outcome metric**: Median **time from “open trace” to “first plausible cause the team agrees to investigate”** — down vs baseline (estimate pre/post if needed).
- **Instrument metric**: **Trace completeness** for failed runs (% with enough steps to run core rules).

**Kill / pivot gates (explicit)**

- If after **~90 days** with engaged partners, **hypotheses are not rated useful** and **time-to-cause does not improve**, **stop expanding features**; revisit ICP, schema coverage, or rule library—not “add more ML.”
- If **integration friction** blocks production traces, **pause net-new intelligence work** until one **blessed** path is trivial.

This is how the plan stays **directionally correct** under uncertainty: **measure the wedge**, don’t fantasize adoption.

---

## 3. Positioning & differentiation

### 3.1 What this is

| Dimension | This product | Typical observability / LLM ops |
|-----------|----------------|----------------------------------|
| Primary question | **Why** did this run fail or behave badly? | What was latency, cost, volume? |
| Core artifact | Canonical **execution graph** + diagnosis | Spans, metrics, scores |
| Output | **Hypotheses + evidence pointers** (trace steps, rules) | Dashboards, alerts, traces |
| Integration stance | **Schema-first**; adapters per ecosystem; **coexist** with existing tools | Often framework-native first |

### 3.2 Honest positioning: hypotheses, not oracles

Probabilistic systems rarely admit a single provable “root cause.” The product must **never** imply judicial certainty unless grounded in deterministic checks.

- **User-facing language**: “Primary hypothesis,” “likely causes,” “evidence,” “confidence.”
- **Internal engine**: May produce multiple candidates; the UI **collapses to a primary narrative** with a clear “see alternatives / evidence” path.
- **Enterprise narrative**: Reduces time-to-diagnosis and documents **why** the team believed X—audit-friendly when evidence links to trace steps and rule IDs.

This avoids a predictable enterprise objection: “Your RCA was wrong once, so we turned it off.”

### 3.3 Differentiation razor

**If a feature does not improve failure diagnosis or trust in diagnosis, it is secondary** until the core loop is proven.

### 3.4 Coexistence beats rip-and-replace

**Default posture**: Customers may keep LangSmith, Langfuse, Datadog, or cloud APM. This product **ingests canonical traces** (first-party SDK) and, over time, **optional bridges** (e.g. import or map from other trace formats)—**not** “migrate everything or get nothing.”

Rip-and-replace is a **late-stage enterprise motion**, not a validation motion.

---

## 4. Ideal customer profile (ICP) — initial wedge

Picking one wedge early prevents a “universal schema” that fits nobody. **Recommendation for v1:**

| Attribute | Recommendation |
|-----------|------------------|
| **Segment** | B2B teams shipping **RAG or tool-using agents** in production (internal or customer-facing) |
| **Pain** | High volume of “bad answers,” retrieval misses, tool errors; debugging is ad hoc (logs + intuition) |
| **Buyer / champion** | Platform / ML engineering, or senior backend + AI lead |
| **Why this wedge** | Trace structure (retrieval → LLM → tool) maps cleanly to rules; failures are frequent enough to prove value |

**Defer “support copilot only” or “pure chat”** as primary ICP until the graph and rules match those flows—unless you already have committed design partners in that shape.

**Document explicitly** (for sales and product): secondary ICPs and **which schema fields** each needs (e.g. human handoff for support bots later).

---

## 5. Non-goals (explicit)

- Replacing full **APM** for non-AI services (Kubernetes metrics, JVM deep dives, etc.).
- Being the **only** observability tool in the first 12–18 months—**coexistence** and **export** matter more than monopoly.
- **Guaranteed** root cause in all cases—only **evidence-backed hypotheses** with measurable confidence.
- **Universal out-of-the-box instrumentation for every framework** on day one—start with a **minimum viable instrumentation** path and expand adapters.
- **Winning on chart count** vs Datadog or cloud consoles—this is a **debugging** product first.

---

## 6. The three pillars (what must be excellent)

1. **Canonical trace model** — Strict enough to analyze; extensible via metadata; supports linear flows and DAGs where needed.
2. **Root-cause / diagnosis layer** — Rules-first, single surfaced narrative, LLM as **explainer** over structured evidence (not unconstrained guesswork).
3. **UX** — Graph + timeline + evidence drill-down; failure-first entry points; comparison when useful.

Everything else supports or monetizes these three.

---

## 7. Canonical execution model (foundation)

### 7.1 Purpose

- **Ingest**: Heterogeneous events → one internal representation.
- **Analyze**: Steps are addressable (for rules, anomalies, explanations).
- **Store**: Query by `trace_id`, time, type, error flags, tenant.

### 7.2 Execution graph (conceptual)

- **Trace**: One logical run (e.g. one user request through the pipeline).
- **Step**: Typed unit with semantic **input/output** and **metadata** (metrics, model name, etc.).
- **Graph**: Directed edges (parent/child or explicit edges) for **linear** and **DAG** (e.g. parallel tool calls, agent branches).

### 7.3 Design rules

| Rule | Rationale |
|------|-----------|
| **Strict step types** (enum, versioned) | Enables reliable rules and UI; “anything goes” JSON blocks analysis |
| **Separate semantic I/O from metadata** | Rules care about semantics; dashboards care about latency/tokens |
| **Version the schema** | Backward-compatible evolution; migrations for stored traces |
| **Optional partial traces** | Streaming / failures mid-run still yield value if schema allows incomplete steps |
| **Stable identifiers** | `trace_id`, `step_id`, optional `span_id` / `traceparent` for OTel alignment later |
| **External correlation** | Optional `correlation_id`, `session_id`, upstream `provider_trace_id` for linking to other systems |
| **Ingest owner / caller type** | Persist **whether the trace was produced in a human-driven context vs an automated service context** (see **§7.7**). Distinct from **this product’s** future user accounts and RBAC (§12)—this is **metadata about the client’s call path** at ingest time. |

### 7.4 Example shape (illustrative—not final JSON Schema)

```json
{
  "schema_version": "1.0",
  "trace_id": "uuid",
  "tenant_id": "org_...",
  "ingest_owner_type": "user | service",
  "ingest_owner_ref": "string | null",
  "started_at": "ISO-8601",
  "ended_at": "ISO-8601",
  "status": "success | error | partial",
  "correlation_ids": {
    "upstream_provider": "langsmith | langfuse | otel | null",
    "upstream_trace_id": "string | null"
  },
  "steps": [
    {
      "step_id": "s1",
      "type": "retrieval | llm_call | tool_call | transform | ...",
      "parent_step_id": null,
      "input": {},
      "output": {},
      "error": null,
      "metadata": {
        "latency_ms": 120,
        "tokens": { "input": 500, "output": 120 },
        "model": "gpt-4"
      }
    }
  ],
  "edges": []
}
```

**Implementation note**: Define **JSON Schema** (or Protobuf) + validation in ingestion; document **required vs optional** per step type. **`ingest_owner_*`** fields are part of the trace document once added to schema v1 (see **§7.7**).

### 7.5 “Universal” vs MVP instrumentation

- **North star**: Any AI system can emit compatible traces.
- **MVP reality**: Ship **one** blessed path (e.g. Python SDK with manual + a few wrappers, **or** OpenTelemetry exporter mapping to canonical steps) and **2–3 framework recipes** (e.g. LangChain / LlamaIndex patterns) documented as copy-paste.

Adapters are a **product surface**: each adapter is a milestone, not a vague promise.

### 7.6 Ingest frequency, partial traces, and tenant identity

**Default client contract (MVP)**

- **One `POST` per logical pipeline run** when the run **completes** (success or failure): send the **full execution graph** in one payload when possible.
- If the pipeline **stops early** (crash, timeout, kill), send a **partial trace** as soon as it is useful: whatever steps exist so far, with `status: "partial"` or `"error"` as appropriate, plus error context on the last step. This is **recommended** for debugging; it is not mandatory for every failure (e.g. ultra-low-level crashes may send nothing).
- Include an `environment` dimension per trace (`prod` / `staging` / `dev` / `critical`; default `prod`) so the same tenant can isolate investigation views and retention policy by environment without separate API surfaces.

**Why not one POST per step (for now)?**

- Higher volume and server complexity (ordering, idempotency per step). Defer until near–real-time streaming is a proven need.

**`tenant_id` is not “any string the client invents” in production**

- In **MVP/dev**, `X-Tenant-ID` may be a plain string for speed.
- In **production**, treat tenant as **server-issued**: map **API keys**, **JWT**, or **mTLS** to a tenant record customers cannot spoof. Clients should not pick arbitrary tenant names for real data.

### 7.7 Ingest owner type (human vs service caller)

Traces can be emitted when **an end user** drives a run (e.g. chat UI, support console) or when **automation** drives it (batch job, worker, cron, backend-to-backend pipeline). Both are valid; they answer different questions in the UI and in analytics (“sessions humans saw” vs “overnight reprocessing”). **Store this distinction on the trace** so we do not infer it from heuristics alone.

| Field | Purpose |
|-------|---------|
| **`ingest_owner_type`** (enum) | **`user`** — run is tied to a **human-driven** client flow (interactive product surface). **`service`** — run is produced by **non-interactive automation** (scheduled job, internal worker, API integration without a human in the loop for that execution). |
| **`ingest_owner_ref`** (optional string) | Opaque identifier from the **customer’s** systems: e.g. their user id, service account id, or job id. **Not** a substitute for `trace_id`; used for display, correlation, and future RBAC joins when the customer maps identities. **Never required** for correctness of storage. |

**Semantics**

- This is **caller classification at the tenant’s edge**, not **our product’s** logged-in investigator (that remains **§12 RBAC**). A **`service`**-owned trace may still be viewed by a human analyst in our UI later.
- **SDK / API contract**: default may be **`service`** if unspecified (safe for headless integrations); interactive SDK paths should set **`user`** when the run corresponds to an end-user request.
- **Storage**: persist at **trace** row level first; propagate to steps only if a future rule needs it (unlikely for v1).

**Why not overload `tenant_id` or API keys?** API keys often identify **automation** only; JWTs may identify **either** a human or a workload. Explicit **`ingest_owner_type`** avoids ambiguity and keeps analytics honest.

---

## 8. Reference architecture (logical)

This section is the **directionally correct** system shape for success: **clear boundaries**, **async write path**, **fast read path**, **diagnosis as its own concern**. Implementation may swap technologies (Postgres vs ClickHouse, SQS vs Kafka) without changing these boundaries.

### 8.1 Bounded contexts (services / modules)

| Context | Responsibility |
|---------|------------------|
| **Ingest API** | Authenticate tenant; accept batches; validate; persist **`ingest_owner_type`** (and optional **`ingest_owner_ref`**) per **§7.7**; enqueue; **return quickly** (202 + idempotency key). |
| **Normalization worker** | Schema version handling; fill defaults; DAG linking; write to stores; emit “trace ready” events. |
| **Query API** | List/filter traces; trace detail; support UI and automation. |
| **Diagnosis engine** | Rules + scoring → **primary hypothesis** + evidence; optional LLM **explanation** from structured bundle only. |
| **Control plane** (can start minimal) | Tenants, API keys, RBAC, retention policies, redaction rules. |
| **Web UI** | Graph, timeline, failure-first home; client of Query + Diagnosis APIs. |

**Rule**: **Diagnosis** reads normalized traces from storage/API—it does not mutate canonical truth except for **derived artifacts** (hypothesis records, user feedback), stored separately or as append-only metadata.

### 8.2 Write path vs read path

| Path | Flow | Goal |
|------|------|------|
| **Write (ingest)** | Client → Ingest API → **queue** → Normalization → **OLTP/index** + **object blob** | Durability, backpressure, retries; **never** block client on heavy work. |
| **Read (query)** | UI / API → Query API → **OLTP** (and blob fetch for full payload when needed) | Low latency for lists and detail views. |

At higher scale: **materialized summaries** (per trace rollups) in OLTP or columnar store; **read replicas** or caching for hot lists. **Do not** premature-optimize with Kafka until ingest volume justifies it.

### 8.3 Storage (dual strategy, unchanged in intent)

| Store | Use case | Contents |
|-------|----------|----------|
| **OLTP / analytics DB** | Fast filters, dashboards, trace lists | Normalized **summary rows** + step index / hot fields |
| **Object storage** | Cheap full payload, replay, audit | Raw or normalized **full** trace blobs |

**Index**: `trace_id`, `tenant_id`, `environment`, time range, `status`, `step_types`, error flags, optional `model`, latency aggregates, **severity / hypothesis flags** (once diagnosis exists).

### 8.4 Integration & export (success enablers)

| Mechanism | Purpose |
|-----------|---------|
| **First-party SDK + HTTP** | Primary adoption path; full schema control. |
| **Correlation fields** | Link rows to upstream tools without owning them. |
| **Webhook / export** (phase after MVP core) | Push “failed trace + hypothesis” to Slack, ticketing, SOAR—**workflow embedding**. |
| **OTel mapping** (later) | Meet buyers where they instrument today. |

### 8.5 Diagnosis pipeline (single user-visible story)

```
Normalized trace
    → Rule evaluators (deterministic signals)
    → Scorer / ranker → primary + secondary hypotheses + evidence list
    → Optional LLM explainer (input = structured bundle only; cite step_ids)
    → Persist DiagnosisRecord (versioned; feedback-capable)
```

**Anti-pattern**: Three separate “verdicts” (rules vs anomaly vs LLM) shown as equals—**one primary hypothesis**, everything else is **detail**.

**Write-heavy optimization rule**:
- Keep ingest path **cheap and deterministic** (validation + lightweight rule diagnosis).
- Move expensive analysis (LLM narratives, deep anomaly, embeddings, cross-trace mining) to **read-time on demand** or **scheduled batch jobs**.
- Never block core ingest acceptance on optional heavy inference.

### 8.6 Security & tenancy (architectural)

- **Tenant ID** on every row and blob prefix; **no cross-tenant queries** at the application layer (defense in depth with infra isolation as you grow).
- **Secrets**: Short-lived API keys; rotate; audit admin actions.
- **PII**: Redaction as a **pipeline stage** (ingest or read-time) per policy—not an afterthought in the UI only.

---

## 9. Layered build (ordered delivery)

Below is the **recommended build order**. Later phases may start in parallel once interfaces are stable.

### Phase A — Ingestion & normalization

| Item | Problem | Inputs | Outputs | Notes |
|------|-----------|--------|---------|--------|
| **Ingestion API** | Clients must send data reliably at high volume | SDK / HTTP (single + batch) | Validated events | **Non-blocking** client side; server **async** processing |
| **Validation** | Garbage in → garbage out | Raw payloads | Accepted / rejected with reason | Strict schema; quotas per tenant |
| **Normalization** | Heterogeneous shapes | Raw events | Canonical graph | Fill defaults, normalize timestamps, token fields, link DAG |

**Critical engineering**: Queue between accept and heavy work; **batch ingest endpoint**; retries; **idempotency keys** for step upserts; rate limits/quotas.
Batch ingest should return SDK-friendly per-item results and use **partial success semantics** (`207 Multi-Status`) when outcomes are mixed.

### Phase B — Storage

As in §8.3; implement **blob + index** before fancy query features.

### Phase C — Query & API

- Filter/list traces (failure-first presets; **optional time range** on trace **`started_at`** / run time for “Kibana-style” windows).
- Get trace detail (full graph for UI).
- Pagination, sorting by time / severity.

**Public API first**: UI is a client; enables **automation and integrations** early.

### Phase D — Visualization

- **Timeline** and **graph** views; expand step I/O (with redaction—see §12).
- **Failure-first** landing: “open worst traces this week,” not empty search.

**Diff between two traces** ships **after** single-trace clarity.

### Phase E — Detection & diagnosis (core intelligence)

| Layer | Role | MVP depth |
|-------|------|-----------|
| **Rule-based detection** | Deterministic signals | **Ship first**: thresholds, empty retrieval, tool errors, truncation flags |
| **Scoring / ranking** | Combine rules into **primary hypothesis** | Simple weighted score; avoid opaque ML stack early |
| **LLM-assisted explanation** | Natural language over **structured** evidence | **On-demand or batched**; template- or schema-guided; cite step IDs |
| **Statistical anomaly** | “Unusual trace” | **Defer** or light z-score on metrics only |

### Phase F — Trust & enterprise

- **Multi-tenant isolation**, RBAC (who can view traces / admin).
- **PII / secret handling**: redaction at ingest or UI; configurable retention.
- Encryption in transit and at rest (standard cloud posture).
- **Audit log** for access and exports (needed for mid-market+).

### Phase G — Growth features (after core loop validated)

| Feature | Value | Risk if too early |
|---------|--------|-------------------|
| **Replay / experimentation** | High for proving fixes | Heavy eng; needs stable capture + sandbox |
| **Semantic search** | Find similar failures | Needs embedding pipeline + quality eval |
| **Custom rules** | Enterprise stickiness | Needs safe execution model (no arbitrary code in v1) |
| **Alerting** | Proactive | Needs low false-positive rate from rules |
| **Streaming / Kafka** | Scale | Only when single-region throughput demands it |
| **Webhooks / export** | Workflow lock-in | Ship once hypothesis quality is credible |

---

## 10. MVP definition (ship this first)

**Goal**: A team can **integrate quickly**, see **execution graphs** for failed runs, get **ranked hypotheses with evidence**, and **trust** the system with production data—while **measuring** time-to-plausible-cause with design partners.

### 10.1 MVP includes

1. **Canonical schema v1** + validation, including **`ingest_owner_type`** / optional **`ingest_owner_ref`** per **§7.7**.
2. **Ingestion**: HTTP API + minimal SDK (language TBD in implementation phase); **queue-backed** processing with **single + batch ingest** support.
3. **Normalization pipeline** + **dual storage** (operational DB + object store for blobs).
4. **Query APIs** + **UI**: graph + timeline, failure filters.
5. **Rule engine v1**: small **library of built-in rules** (retrieval quality, tool empty/error, latency spike, truncation).
6. **Hypothesis baseline**: persist primary hypothesis + evidence at write time; keep this deterministic and cheap.
7. **Optional explanation**: LLM-generated narrative runs on-demand (read path) or in batch, always **bounded** by structured evidence.
8. **DiagnosisRecord** persistence (hypothesis, confidence, evidence pointers, schema version)—enables feedback and iteration.
9. **Tenant model + basic RBAC** + **retention** + **redaction hooks**.

### 10.2 MVP explicitly excludes (or stub only)

- Full causal graph reasoning across arbitrary domains.
- Heavy embedding-based anomaly detection.
- Full replay with arbitrary model swapping (unless a thin “re-run prompt” stub is trivial).
- Custom user-defined code rules (start with **configurable thresholds** if needed).

---

## 11. Phased roadmap (suggested)

| Phase | Name | Focus | Exit criteria |
|-------|------|--------|----------------|
| **0** | Design lock + partners | JSON Schema; ICP; **5–10 failure scenarios** from partners; **baseline time-to-cause** (even estimated) | Schema v1 frozen; **3+** committed partners; demo script |
| **1** | Ingest + store + UI + **SDK v0** | End-to-end trace visible in UI; **thin Python SDK** (ingest, retries, **`trace_id` returned**, logging hooks per §16.3) | Partner debugs **one real production failure** from graph alone |
| **2** | Rules + hypothesis | Built-in rules + primary hypothesis + evidence | **Measured** reduction in time-to-plausible-cause vs Phase 0 baseline |
| **3** | LLM explanation | Template-guided explanations; **thumbs feedback** on hypotheses | Users prefer explanation vs raw JSON; feedback loop feeding rule weights |
| **4** | Enterprise hardening | SSO, stronger RBAC, audit logs, SLAs | Pass security review for one mid-market customer |
| **5** | Scale & integrations | OTel, frameworks, streaming **if needed**; webhooks/export | SLOs met at target load; workflow integrations live |
| **6** | Advanced | Replay, semantic search, custom rules, alerting | Revenue-driven prioritization |

Phases can overlap (e.g. security items start in Phase 2), but **Phase 1–3** should not balloon with Phase 6 features.

### 11.1 SDK roadmap (complements §11)

SDK ships **after** the HTTP contract is stable enough to wrap; it is **not** a blocker for UI on the public API.

| Horizon | Scope |
|---------|--------|
| **Phase 1** | **Python SDK v0**: single + batch ingest, retries/backoff, **`trace_id` in responses**, optional **callback / hook** for structured logging (see §16.3); thin, dependency-light. |
| **Phase 2** | Redaction hooks, OpenTelemetry baggage / context helpers, **2–3 copy-paste framework recipes** (plan §7.5). |
| **Phase 3+** | Additional language SDKs only when **design partners or revenue** justify; core remains **schema + HTTP**. |

---

## 12. Trust, security, and data governance

Elevate these alongside the graph—they are **buying criteria**, not footnotes.

| Area | Requirement |
|------|-------------|
| **Tenant isolation** | Hard boundaries; no cross-tenant queries |
| **RBAC** | Roles: viewer, analyst, admin; optional project-scoped |
| **PII / secrets** | Redact prompts, headers, tool payloads; configurable patterns |
| **Retention** | Per-tenant TTL; legal hold considerations |
| **Audit** | Who exported / viewed sensitive traces (enterprise) |
| **Compliance path** | Roadmap for SOC 2–style controls when revenue justifies |

---

## 13. Success metrics

### 13.1 North Star

| North Star | Definition |
|------------|------------|
| **Time to plausible cause (TTPC)** | Wall-clock or session time from **opening a failed trace** to **first hypothesis** the team treats as worth investigating (validated by lightweight user signal: thumbs, or runbook checkpoint). |

Everything in the product roadmap should eventually **move TTPC down** or **confidence up** without eroding trust.

### 13.2 Product (MVP → v1)

| Metric | Definition | Why |
|--------|------------|-----|
| **TTPC** | As above | Core value |
| **Trace completeness** | % of failed runs with enough steps to run rules | Integration health |
| **Hypothesis acceptance** | Thumbs-up rate or analyst marking “useful” | Quality of rules + ranking |
| **Weekly active investigators** | Users who open traces weekly | Stickiness |

### 13.3 Engineering

| Metric | Definition |
|--------|------------|
| Ingest latency (p95/p99) | Time to **accept** (before async processing) |
| Processing lag | Queue → normalized + queryable |
| Query latency | Trace detail load time |
| Error rate | Ingestion failures, validation rejects |

### 13.4 Business (leading indicators)

- Number of **production** integrations (not POCs).
- Expansion: more teams / higher trace volume within same account.
- **Paid** expansion tied to seats, volume, or enterprise tier.

---

## 14. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| **Crowded market** | **Narrow ICP** + **TTPC** proof + **coexistence** with existing tools |
| **Commoditization** (incumbents copy UX) | **Diagnosis depth + evidence + workflow** (export, runbooks); data/feedback loop on hypotheses |
| **False RCA** | Hypothesis framing; confidence; evidence; user feedback |
| **Integration friction** | One blessed SDK path + recipes; **Phase 0 partner commitment** |
| **Scope creep** | MVP list is sacred; Phase 6 stays backlog until Phase 3 wins |
| **Privacy / enterprise blockers** | Redaction + retention from Phase 1; audit in Phase 4 |

---

## 15. End-to-end flow (reference)

```
[Client app] → SDK / HTTP → [Ingest API] → [Queue]
       → [Normalize] → [OLTP + index] + [Object blob]
       → [Query API] → [UI: graph / timeline]
       → [Diagnosis: rules + rank] → [DiagnosisRecord]
       → [LLM explainer (optional)] → [UI]
       → [Webhooks / export / alerts — later]
```

Optional: **upstream trace IDs** correlated for “open related trace in LangSmith” style links—does not require owning their storage.

---

## 16. Technology stack (default)

Single **coherent** stack for Phase 1–3 (speed to proof, one primary language for API + workers + diagnosis). Swap pieces when **measured** need (see §8 and tradeoffs below).

### 16.1 Recommended stack

| Piece | Default choice | Role |
|-------|----------------|------|
| **SDK** | Python | Lowest friction for RAG/agent teams; thin client (batch, retry, idempotency, redaction). |
| **Ingest + Query APIs + workers** | Python (e.g. FastAPI) + worker processes | Same codebase as SDK ecosystem; iterate fast with design partners. |
| **Primary database (OLTP)** | **PostgreSQL** | Trace metadata, lists, RBAC, `DiagnosisRecord`, multi-tenant queries. |
| **Blob store** | **S3-compatible** (S3, GCS, MinIO) | Full trace payloads, cheap retention, replay artifacts later. |
| **Queue** | Managed queue (**SQS**, **GCP Pub/Sub**, or **Redis Streams** self-hosted) | Backpressure between ingest accept and normalization—**not** Kafka until volume justifies it. |
| **Web UI** | **React + TypeScript** | Graph/timeline; hireable; consumes public Query + Diagnosis APIs only. |
| **External LLM** | **OpenAI / Anthropic (or Azure-hosted equivalents)** via API, behind an abstraction | **Only** for the bounded **explainer** path (§16.2)—not for core hypothesis discovery. |
| **Infra** | Docker; **Terraform** or **Pulumi**; **ECS / Cloud Run / Fly** before mandatory K8s | Ship; add orchestration when ops complexity warrants it. |

**Tradeoffs (when to deviate)**

- **Go (or similar) for ingest only**: If **measured** p99/CPU on the hot ingest path is the bottleneck—not by default.
- **ClickHouse / warehouse**: When **analytics at very large volume** outgrows Postgres + partitioning; defer for MVP.
- **Self-hosted LLM**: Enterprise air-gap or policy—**later**; keep the **same explainer interface** so the app stays provider-agnostic.

### 16.1.1 PostgreSQL scale (post-MVP): partitioning by tenant

**Not required for MVP.** Introduce when **table size**, **vacuum/IO**, or **retention drops** justify operational complexity.

**Recommendation:** use **`PARTITION BY HASH (tenant_id)`** with a **fixed modulus** (e.g. **32 or 64** partitions)—not **`LIST (tenant_id)`** per customer. **Why:** tenant count can grow very large; **one partition per tenant** becomes unmanageable. **HASH** keeps a **bounded** partition count, still aligns with **tenant-scoped queries**, and combines with **B-tree indexes** such as `(tenant_id, environment, started_at DESC)` for list/time-window patterns.

**Optional later:** **subpartition by time** (e.g. monthly `RANGE` on `started_at` or `ingested_at`) under each hash bucket for TTL-style drops—only when measured.

### 16.1.2 S3-compatible blob storage — where to store access keys

**Principle:** `s3_access_key_id` and `s3_secret_access_key` (or the standard `AWS_*` equivalents) are **secrets**. They must **never** be committed to the repository, checked into tickets, or baked into container images as literals.

**Options (prefer top to bottom for production):**

| Approach | When to use | Notes |
|----------|-------------|--------|
| **IAM role for the workload** (ECS task role, Lambda execution role, EC2 instance profile, EKS/IRSA, etc.) | Production on AWS | **Preferred:** no long-lived access keys in config; boto3 uses the role automatically. Rotate by IAM policy, not by redeploying secrets. |
| **GCP / Azure workload identity** (GKE workload identity, Azure managed identity, etc.) | Production on those clouds | Same idea as IAM: **prefer** identity attached to the service over static keys; wire credentials the platform provides into the process or use provider-specific SDK integration if not using S3 API with keys. |
| **Environment variables** set by the platform | Containers, systemd, PaaS (Fly, Railway, etc.) | Inject `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (or app-specific `RCA_S3_*` if the stack maps them) from the host’s secret store. Values exist only at runtime. |
| **Secret manager → env at startup** | AWS Secrets Manager, SSM Parameter Store (SecureString), Vault, Doppler, etc. | Platform or sidecar resolves secrets into env vars before the process starts; app still reads env only. |
| **Local `.env` file** (gitignored) | Developer laptop, one-off staging | Acceptable for **local** MinIO/S3 testing; ensure **`.env` is in `.gitignore`** and only **`.env.example`** (placeholders) is committed. |

**Implementation alignment (reference backend):**

- If **`RCA_S3_BUCKET`** is unset, the app does **not** call object storage—no keys required.
- When blob mode is on, credentials may be supplied as **app-prefixed** (`RCA_S3_ACCESS_KEY_ID`, `RCA_S3_SECRET_ACCESS_KEY`) or omitted so **boto3’s default credential chain** applies (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `~/.aws/credentials`, then IAM role).
- **MinIO / local S3-compatible:** set **`RCA_S3_ENDPOINT_URL`** (e.g. `http://127.0.0.1:9000`) and bucket; keys are often **dev-only** credentials—still treat as secrets and keep them out of git.

**Do not:** paste keys into `plan.md`, README examples, or Terraform state without encryption; treat any example as **placeholder only**.

### 16.2 External LLM calls — why, where, and what we do *not* use them for

The product’s **core diagnosis** is **deterministic**: rules over the **normalized execution graph**, scoring, and a **primary hypothesis** with **evidence** (`step_id`s, rule IDs). **That path does not require** calling OpenAI or Anthropic.

**Where external LLMs *do* add value** (optional layer on top of structured output):

| Use | Purpose |
|-----|---------|
| **Narrative explainer** | Turn the **already computed** `DiagnosisRecord` + evidence bundle into a short, readable summary for humans (e.g. “Retrieval returned low-similarity chunks; the model then answered without grounding—see steps `s2`, `s4`”). |
| **Suggested next checks** | Propose **non-binding** investigation steps grounded in the same evidence (still cite step/rule IDs). |
| **Multi-step summarization** | When many steps fired signals, compress **without** inventing new “causes” not present in the rule output. |

**Contract for trust**

- **Input to the model** is **structured**: hypothesis, confidence, evidence list, redacted step snippets—not “here are raw logs, guess the bug.”
- **Output** should be **schema-constrained** (JSON with required citations) so the UI can reject or flag **uncited** claims.
- **Primary hypothesis** remains **owned by rules + ranker**; the LLM **does not** override scores without an explicit product decision.

**When you can skip vendor LLMs entirely**

- Early MVP can ship **hypothesis + bullet evidence** only (no prose).
- On-prem or strict data policies: **template-only** explanations (“Rule X fired because …”) until a **customer-approved** model endpoint is wired to the same interface.

**Why OpenAI / Anthropic (or Azure) specifically**

- They are **API-complete** for structured chat/completions with tool/schema-style constraints; **not** because the product is “built on ChatGPT”—only the **explainer** (and future optional features like semantic search embeddings) may call out; **embeddings** can use the same or a dedicated embedding API.

### 16.3 Client SDK — `trace_id`, async ingest, and logging (division of responsibility)

**Principle:** The **application** owns **what** gets logged (business context, PII policy). The **SDK** owns **making correlation easy and consistent**.

| Concern | Preferred owner |
|--------|------------------|
| Emitting `trace_id` into app logs / log pipeline | **Application**, with **SDK helpers** (e.g. one-line hook, OTel baggage) so callsites do not diverge. |
| Ensuring `trace_id` is **known** after ingest | **SDK** returns **`trace_id`** (and per-item outcomes) from **`POST` responses**, including **202 Accepted** when the server has **accepted** the payload but processing continues asynchronously. |
| Fire-and-forget / background flush | SDK should still expose **completion** (future, callback, or batch result) so **`trace_id` is not dropped**; “flush with no completion path” is discouraged for production observability. |
| Creating the id | **Best practice:** generate or accept **`trace_id` at the start of the user-facing request** and propagate through logs **before** ingest completes; ingest **confirms** the same id to the product. Server-issued ids are fine if documented—then the **first** reliable log line may be **after** the HTTP response unless the app pre-allocates. |

**Summary:** Ship SDK hooks so customers *can* centralize logging; do not silently log full prompts from the SDK without redaction policy alignment (Phase 2 hooks).

---

## 17. Document maintenance

- **Owner**: Product + engineering lead (name when assigned).
- **Update trigger**: Schema version bump, ICP change, phase completion review, or **failed kill/pivot gate** (document learnings).
- **Related artifacts** (to add as you create them): `schema/`, ADRs for storage and diagnosis engine, API OpenAPI spec, **design partner brief** (1-pager).

---

## 18. Summary checklist (what “good” looks like)

- [ ] Schema v1 documented and versioned; strict step types; **correlation** fields for coexistence; **ingest owner type** (user vs service) + optional **owner ref** per **§7.7**.
- [ ] One ICP; **failure scenarios** and **design partners** documented.
- [ ] **TTPC** defined and measured; **90-day proof** and **kill gates** understood by the team.
- [ ] Reference architecture: **write vs read path**, **diagnosis boundary**, **dual storage**.
- [ ] MVP shipped: ingest → queue → normalize → store → UI → rules → **DiagnosisRecord** → bounded explanation.
- [ ] Hypotheses framed honestly; evidence linkable to trace steps; **single primary narrative** in UI.
- [ ] Trust: tenants, RBAC, redaction, retention from early phases; audit on roadmap.
- [ ] Advanced features (replay, semantic search, heavy ML, Kafka) **explicitly phased** after proof.
- [ ] **Coexistence** and **export** treated as success enablers, not late extras.
- [ ] **Default technology stack** (§16) agreed; **LLM usage** limited to bounded explainer (§16.2) unless product explicitly expands scope.
- [ ] Ingest remains write-light; expensive diagnosis paths run on-demand or batch unless metrics justify moving them earlier.
- [ ] **Tenant binding** is server-issued for production (API key / JWT → tenant), not free-form client strings; **ingest contract** documented: one POST per completed run, partial trace on early failure when debugging matters.

---

## 19. Next implementation steps (prioritized — engineer handoff)

Use this section when continuing work in a new session. Order is **suggested**; adjust with measured need.

### Already in repo (baseline)

- Python FastAPI backend: `POST /v1/traces`, `POST /v1/traces/batch`, `GET` list (optional **`environment`** + **`started_at_from` / `started_at_to`** on run time) / detail / diagnosis, **PostgreSQL** + `ingest_jobs` durable backlog, rule-based `DiagnosisRecord`, example `scripts/`. Local dev: **`backend/docker-compose.postgres.yml`** (port **5433**) and **`backend/run_api.sh`** (starts Docker, migrates, runs the API); tests use DB **`rca_test`** (see **`backend/README.md`**).
- **Tenant auth (production path):** optional **`RCA_API_KEYS`** JSON map → `tenant_id`, plus **JWT bearer auth** (`RCA_JWT_*`: secret, algorithm, tenant claim, optional issuer/audience); clients use **`Authorization: Bearer`** or **`X-API-Key`**; with keys/JWT unset, dev uses **`X-Tenant-ID`** only.
- **Composite uniqueness:** **`UNIQUE (tenant_id, trace_id)`** on **`traces`**, **`diagnoses`**, **`ingest_jobs`** (and **`UNIQUE (tenant_id, trace_id, step_id)`** on **`trace_steps`**). The same `trace_id` UUID may exist for **different** tenants; duplicates **within** the same tenant (regardless of `environment` field) return **409**. `environment` remains a column for filtering and display.
- **Rate limits & quotas (initial):** per-tenant ingest request-rate and daily trace quota with **429 + Retry-After** on `POST /v1/traces` and `/v1/traces/batch` (current implementation is in-process; distributed limiter backend remains a scale task).
- **Tenant limit management (initial):** admin-only APIs (`/v1/admin/tenants/{tenant_id}/limits`) persist per-tenant policies in `tenant_limits`; ingest enforcement resolves tenant override first, then global defaults.
- **Migrations (initial):** Alembic is wired with a baseline revision; startup runs `upgrade head` instead of relying only on `create_all`.
- **Object storage (implemented, optional):** when `RCA_S3_BUCKET` is set, full trace payload is written to S3-compatible storage at `{urlencoded_tenant_id}/{trace_id}/trace.json`; DB stores metadata/index fields (`blob_key`, `blob_etag`, `step_count`) and keeps read compatibility. Blob `put/get` now includes bounded retry/backoff and timing logs for transient failure visibility.
- **Web UI (current):** React app supports auth mode switching, ingest single/batch, trace list with infinite scroll + filters, trace detail with execution graph + timeline + step drill-down, step query table with infinite scroll and row-to-trace deep-linking, admin limits, and test-data generation.

### Near-term (product + trust)

1. **S3 hardening + ops guardrails (remaining)** — lifecycle/retention rules (infra policy), DB↔blob reconciliation tooling, and admin repair path (`re-upload` / `re-link` / retry commands). **Where to put access keys (and when to avoid keys):** **§16.1.2**.

### Data & scale

2. **Distributed ingest queue + workers** — move background ingest from DB-backed polling to a distributed queue/consumer model (SQS / Redis Streams / Pub/Sub) for multi-instance safety, retry/DLQ semantics, and cross-region scale.
3. **Distributed rate limits / quotas (Redis)** — use Redis as the shared backend for rate limits and daily quotas so 429 behavior stays correct across multiple API instances.
4. **PostgreSQL scale hardening** — tenant hash partitioning and operational tuning once measured load justifies it; local/tests already run against Postgres (Docker/`rca_test`), so behavior stays aligned with prod.

### Product surface

5. **Python SDK** — batching, flush, retries, idempotency, **`trace_id` return + logging hooks** (see **§16.3**); redaction hooks; thin wrappers for common frameworks (see **§11.1**).
6. **LLM explainer (on-demand)** — `POST /v1/traces/{id}/explain` or similar; structured input only; cite `step_id`s.
7. **Ingest owner metadata** — add **`ingest_owner_type`** (`user` \| `service`) and optional **`ingest_owner_ref`** to the HTTP + stored trace model per **§7.7** (DB columns + list/filter in UI when ready).
8. **Step/trace outcome semantics (defer until user signal)** — decide whether to introduce a non-binary failure model (for example **`soft_fail`** vs **`hard_fail`** at step level) and derived trace-level outcome (for example **`degraded`** when there are soft failures but no hard failures). Keep current behavior for now; revisit after real user evidence that this distinction improves triage, alert quality, or reporting.

#### 8.1 Decision gate (when to implement)

- Confirm at least a few design-partner users explicitly need to distinguish **recoverable/expected** failures from **action-required** failures.
- Validate the distinction changes behavior (dashboard filters, alert routing, or incident response), not just label preference.
- Lock vocabulary before schema work (`soft_fail` / `hard_fail` / `degraded` vs alternatives like `warning` / `partial_success`) so SDK/UI/docs stay consistent.

#### 8.2 Proposed implementation shape (future)

- **Phase A (low-risk):** accept optional step-level failure severity in ingest payload; keep trace status aggregation unchanged until semantics stabilize.
- **Phase B (schema + UX):** add indexed storage/filtering for the chosen outcome model and expose it in list/query/UI.
- **Aggregation rule (candidate):** any hard failure => trace `error`; no hard failures and >=1 soft failure => trace `degraded`; no failures => trace `success`.

### Ops & enterprise

9. **Observability** — OpenTelemetry on our own API/workers.
10. **SSO / RBAC / audit** — Phase 4 hardening per roadmap.
11. **Webhooks / export** — after hypothesis quality is credible.

### GTM

12. **Design partner brief** + **90-day TTPC** measurement loop.
13. **JSON Schema** artifact published for `Trace` v1; OpenAPI kept as source of truth for HTTP.

---

This plan ties **product strategy**, **GTM validation**, **architecture**, and **implementation defaults** (§16) so technology choices map to **interfaces and outcomes**—maximizing the odds of building something **directionally right** in a crowded market.
