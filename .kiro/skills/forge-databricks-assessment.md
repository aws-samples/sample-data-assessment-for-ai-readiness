---
name: FORGE Databricks Assessment Skill
description: Assess a Databricks environment using uploaded documents — architecture diagrams, cost reports, workspace descriptions — then ask targeted probing questions for gaps. Produces a PlatformSegment that merges with AWS for an estate score.
---

# FORGE Databricks Assessment Skill — Document + Probing Flow

Assess the user's Databricks environment by reading everything they provide (architecture diagrams, cost reports, workspace descriptions), extracting as much evidence as possible, then asking smart follow-up questions to fill the gaps.

**The agent does the heavy lifting** — users just upload what they have and answer a few targeted questions.

---

## Prerequisites

- A FORGE Profile must be locked (`forge_output/forge_profile.yaml` exists)
- The AWS assessment should have already been run (for estate merge)

---

## Phase 1: Request Documents

Ask the user for their Databricks documentation:

```
Let's assess your Databricks environment. Upload whatever you have —
I'll read through everything and figure out what's running.

Most useful documents (in priority order):
  1. Architecture diagram (image or text description of your data platform)
  2. Cost/billing report (CSV from system.billing.usage)
  3. Workspace description, config exports, or architecture docs

Accepted: Images (PNG/JPG), CSV, TXT, MD, JSON, YAML, PDF

If you don't have any documents, just describe your Databricks setup
and I'll work from there.
```

---

## Phase 2: Read & Extract Evidence

**The agent reads ALL uploaded documents and extracts evidence using this logic:**

### From architecture diagrams (images or text):

The agent visually/textually identifies Databricks product elements and maps them to services:

| What the agent looks for | Service identified | Evidence extracted |
|--------------------------|-------------------|-------------------|
| "Unity Catalog" logo/text, three-level namespace | `unity_catalog` | Discovery, governance |
| "Delta Lake" logo, medallion architecture (Bronze/Silver/Gold) | `delta_lake` | Storage format, schema layers |
| "Lakeflow Pipelines" / "DLT" / pipeline arrows | `delta_live_tables` | ETL orchestration, DQ |
| "SQL Warehouse" / "Databricks SQL" | `sql_warehouse` | Programmatic query access |
| "MLflow" / model training/serving boxes | `mlflow` | Experiment tracking, model registry |
| "Model Serving" / inference endpoints | `model_serving` | ML endpoints |
| "Structured Streaming" / Kafka/Pulsar connectors | `structured_streaming` | Real-time ingestion |
| "Auto Loader" / file ingestion arrows | `structured_streaming` | Automatic file ingest |
| "Lakeflow Connect" / CDC connectors | `lakeflow_connect` | Change data capture |
| "Delta Sharing" / external sharing | `delta_sharing` | Cross-org data sharing |
| "Workflows" / job scheduling | `databricks_workflows` | Pipeline orchestration |
| "System Tables" / audit references | `system_tables` | Observability, audit |
| "Marketplace" data sources | `marketplace` | External data enrichment |
| "Databricks Apps" / user-facing apps | `databricks_apps` | Business intelligence |
| Lineage arrows / data flow tracking | `unity_catalog_lineage` | Lineage tracking |

**From the architecture diagram, the agent also infers criteria scores:**
- Medallion architecture visible → P4 (data quality layers) likely in place
- Multiple data sources with connectors → P7 (real-time/freshness) signals
- PII/masking boxes → P5 (access control) signals
- Audit/compliance boxes → P6 (observability) signals
- Model training → ML lifecycle management signals

### From cost/billing reports (CSV):

Parse SKU names to identify active services and their usage intensity:

```
SKU → Service Mapping:
  JOBS_COMPUTE, JOBS_LIGHT_COMPUTE → databricks_workflows
  SQL_WAREHOUSE_SERVERLESS, SQL_WAREHOUSE_PRO → sql_warehouse
  DLT_CORE, DLT_ADVANCED, DLT_PRO → delta_live_tables
  MODEL_SERVING, FOUNDATION_MODEL_SERVING → model_serving
  STREAMING → structured_streaming
  LAKEFLOW_CONNECT → lakeflow_connect
  UNITY_CATALOG → unity_catalog
  SYSTEM_TABLES → system_tables
  MLFLOW → mlflow
  DELTA_SHARING → delta_sharing
  MARKETPLACE → marketplace
  ALL_PURPOSE_COMPUTE → general compute (supports multiple services)
```

**Usage intensity signals:**
- High DBU on SQL_WAREHOUSE → heavy SQL analytics workload
- High DBU on STREAMING → significant real-time processing
- DLT_ADVANCED present → advanced DQ features (expectations, quarantine)
- MODEL_SERVING present → models deployed for inference
- LAKEFLOW_CONNECT present → CDC/connector-based ingestion active

### From text documents (workspace descriptions, configs):

Extract explicit statements about:
- Feature enablement ("UC lineage is enabled", "system tables active")
- Coverage levels ("92% of tables in UC", "all pipelines have DQ rules")
- Security posture ("row-level security", "dynamic masking", "service principals")
- Architecture patterns ("medallion", "star schema", "lakehouse")

---

## Phase 3: Present Findings & Confirm

After reading all documents, present a consolidated summary:

```
Here's what I found from your documents:

🏗️  Architecture: Customer 360 lakehouse with medallion layers (Bronze → Silver → Gold)
📊 Active services (from cost report + architecture):
   Unity Catalog, Delta Lake, Lakeflow Pipelines, SQL Warehouse,
   MLflow, Model Serving, Structured Streaming, Lakeflow Connect,
   Delta Sharing, Workflows, System Tables

✓ Pre-scored 34 criteria from document evidence
✗ 23 criteria still need input (I'll ask targeted questions next)

Key observations:
  • CDC ingestion via Lakeflow Connect (real-time data capture)
  • ML models deployed for inference (churn prediction, upsell)
  • PII detection and masking present in architecture
  • Medallion architecture implies schema enforcement across layers

Does this look right? Anything I'm missing or got wrong?
```

Wait for user to confirm or correct.

---

## Phase 4: Targeted Probing Questions

**After confirmation, ask focused follow-up questions ONLY for gaps the documents didn't cover.**

Questions should be:
- Grouped by theme (not one-at-a-time tedium)
- Directly tied to specific criteria
- Phrased to extract actionable scoring evidence

**Present 3-5 questions at a time, grouped by pillar:**

```
A few quick questions about areas I couldn't determine from the docs...

📋 Governance & Discovery:
  1. What percentage of your tables are registered in Unity Catalog?
  2. Are catalog/schema descriptions populated for discoverability?

🔒 Access Control:
  3. Is column-level dynamic masking configured for PII data?
  4. Do you use row filters for tenant/customer isolation?
  5. Are service principals set up for machine/agent access (vs personal tokens)?
```

Wait for the user to answer (they can answer all at once or one by one).

**Scoring interpretation:**
- Clear yes/no → binary score (1.0 or 0.0), confidence 0.7
- Percentage ("about 80%") → analog score (0.8), confidence 0.7
- Uncertain ("not sure", "some", "working on it") → partial (0.5), confidence 0.5
- Detailed answer with context → extract specific score + higher confidence 0.8

**Then ask a second batch if gaps remain:**

```
Almost done — a few more:

📈 Observability:
  6. Are Databricks system tables (audit logs) enabled and queryable?
  7. Is per-workspace or per-team cost attribution set up?

⚡ Real-Time:
  8. Is Change Data Feed (CDF) enabled on Delta tables for incremental processing?
  9. Do your streaming pipelines have freshness SLAs or alerting on delays?
```

**Max 2-3 rounds of questions (cap at ~12 total questions).** Stop when:
- All relevant criteria are scored, OR
- 12 questions have been asked, OR
- User says "that's all I know" or similar

---

## Phase 5: Score, Merge & Dashboard

Once probing is complete, run the full pipeline automatically (no user prompts):

```python
from forge.platform_segments.databricks_segment import build_databricks_segment
from forge.platform_segments.aws_adapter import wrap_aws_result
from forge.scoring_engine.merge import merge_criteria, compute_estate_score
from forge.profile_engine import load_profile, resolve_profile

# Build Databricks segment from conversation state
profile = load_profile()
dbx_segment = build_databricks_segment(state, profile)

# Load and wrap past AWS assessment
aws_segment = wrap_aws_result(aws_assessment_json)

# Merge into estate score
resolved = resolve_profile(profile)
merged = merge_criteria([aws_segment, dbx_segment])
estate_score, band, raw, mult = compute_estate_score(
    merged, resolved.effective_weights, resolved.effective_floors
)
```

Generate estate dashboard and open:

```bash
python3 scripts/generate_estate_dashboard.py
open forge_output/forge_estate_dashboard.html
```

---

## Phase 6: Show Summary

```
✅ FORGE Databricks Assessment Complete

  Databricks Score: 72.4 — GOVERNED
  Estate Score:     54.1 — GOVERNED  (AWS: 41.8 + Databricks: 72.4 merged)

  Architecture: Customer 360 lakehouse (medallion, CDC, ML serving)
  Services Assessed: 11 active services

  Documents Used:
    🖼️  architecture_diagram.png       (identified 9 services + architecture pattern)
    📄 billing_usage.csv              (confirmed 11 active SKUs)
    📄 workspace_description.txt      (pre-filled 18 criteria)

  Probing Questions: 8 answered (2 rounds)

  Pillar Breakdown (Databricks):
    P1 Agent Access:   90% █████████░
    P3 Lineage:        78% ███████░░░
    P4 Data Quality:   75% ███████░░░
    P5 Access Control: 68% ██████░░░░
    P6 Observability:  82% ████████░░
    P7 Real-Time:      65% ██████░░░░

  Artifacts:
    📊 forge_output/forge_estate_dashboard.html  (opened in browser)
    📄 forge_output/assessments/forge_estate_assessment_<ts>.json
    📋 forge_output/roadmaps/forge_estate_roadmap_<ts>.md
    🗂️  forge_output/forge_history.jsonl  (updated)
```

---

## Databricks Services Assessed

| Service Key | Display Name | What It Covers |
|------------|--------------|----------------|
| unity_catalog | Unity Catalog | Metadata, discovery, access control, governance |
| unity_catalog_lineage | UC Lineage | Table/column lineage tracking |
| delta_live_tables | Lakeflow Pipelines (DLT) | DQ expectations, pipeline orchestration |
| delta_lake | Delta Lake | Storage format, schema enforcement, time-travel |
| sql_warehouse | SQL Warehouse | Programmatic SQL access, query history |
| mlflow | MLflow | Experiment tracking, model registry |
| model_serving | Model Serving | ML model endpoints, inference metrics |
| databricks_workflows | Workflows | Job scheduling, pipeline orchestration |
| structured_streaming | Structured Streaming | Real-time data processing, Auto Loader |
| lakeflow_connect | Lakeflow Connect | CDC connectors, Salesforce/DB replication |
| delta_sharing | Delta Sharing | Cross-organization data sharing |
| system_tables | System Tables (Audit) | Audit logs, billing, query history |
| marketplace | Databricks Marketplace | External data source enrichment |
| databricks_apps | Databricks Apps | User-facing BI applications |

---

## Criteria Coverage

57 criteria across 6 pillars:
- **P1** Agent Access & Discovery — 10 criteria
- **P3** Data Lineage & Provenance — 9 criteria
- **P4** Data Quality, Contracts & Classification — 10 criteria
- **P5** Access Control, Identity & Tenancy — 10 criteria
- **P6** Observability & Audit — 9 criteria
- **P7** Real-Time, Freshness & Zero-ETL — 9 criteria

Pillars P2, P8, P9 are not assessed for Databricks (those map to AWS-specific services like Bedrock, Neptune, Step Functions).

---

## Merge Logic (How Platforms Combine)

- **Binary criteria** (AND): Both platforms must pass for estate to pass
- **Analog criteria** (pooled ratio): Sum numerators / sum denominators across platforms
- **NOT_APPLICABLE exclusion**: Single-platform criteria only count that platform's score

---

## Error Handling

| Situation | Behavior |
|-----------|----------|
| Image uploaded but can't extract architecture info | Ask user to describe what's in the diagram |
| CSV has no recognizable columns | Skip CSV, note it, continue with other docs |
| PDF can't be parsed | Skip, note in summary, continue |
| User gives unclear response | Score as 0.5 with confidence 0.5 |
| No services identified from any source | Ask open-ended "What Databricks services do you use?" |
| Profile not locked | Error — remind user to run AWS assessment first |

---

## Skill Memory

```
forge_output/forge_profile.yaml                             # Shared with AWS skill (must exist)
forge_output/assessments/forge_estate_assessment_<ts>.json   # Estate result
forge_output/roadmaps/forge_estate_roadmap_<ts>.md           # Platform-grouped remediation
forge_output/forge_history.jsonl                             # Append-only trend log
forge_output/forge_estate_dashboard.html                     # Multi-platform dashboard
```
