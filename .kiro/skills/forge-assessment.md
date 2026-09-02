---
name: FORGE Assessment Skill
description: Run a FORGE 2.3 assessment — deploy the IAM role, probe the account, declare a FORGE Profile, collect 142 criteria, score, and generate the dashboard. Supports multi-platform estate assessments (AWS + Databricks).
---

# FORGE 2.3 Assessment Skill — From IAM Setup to Score Memory

Guide the user through the complete FORGE 2.3 assessment workflow. The skill has two pause points where it waits for user input:

1. **Profile confirmation** (Step 4) — User confirms or adjusts the proposed FORGE Profile
2. **Multi-platform question** (Step 6) — User says whether they have additional platforms

Everything else runs automatically.

**Flow overview:**

```
Pre-Flight → Probe → Profile (confirm) → Collect/Assess →
  → "Additional platforms?" →
      → No  → Dashboard + Summary (AWS-only)
      → Yes → Databricks skill → Merge → Estate Dashboard + Summary
```

---

## Phase A: Pre-Flight Gate (Runs Every Session)

The skill starts with an automated pre-flight check. No user prompts unless something fails.

### 1. Check AWS Credentials

Run silently:

```bash
aws sts get-caller-identity
```

**If it fails** (no credentials, expired token):

```
❌ No AWS credentials found in this terminal.

Please log in to AWS in this terminal, then tell me when you're ready:

  • aws sso login --profile <profile-name>
  • export AWS_PROFILE=<profile-name>
  • export AWS_ACCESS_KEY_ID=... / AWS_SECRET_ACCESS_KEY=... / AWS_SESSION_TOKEN=...

I'll re-check once you're set.
```

**STOP and wait.** Do NOT proceed until `get-caller-identity` succeeds. Re-run the check after the user says they've authenticated.

**If it succeeds** — extract the Account ID and display:

```
✅ AWS credentials active
   Account: 123456789012
   Identity: arn:aws:iam::123456789012:user/engineer
```

Ask the user: "Is this the account you want to assess?" If they say a different account ID, tell them to switch profiles and re-check.

### 2. Check FORGE-Assessment-Role (Deploy if Missing)

Once credentials are confirmed, check if the read-only assessment role exists:

```bash
aws iam get-role --role-name FORGE-Assessment-Role 2>&1
```

**If the role exists** — try to assume it to confirm it's functional:

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::<account-id>:role/FORGE-Assessment-Role \
  --role-session-name forge-preflight-check \
  --tags Key=forge-skill,Value=preflight \
  --duration-seconds 900 2>&1
```

- If assume succeeds → ✅ Pre-flight complete. Proceed to Step 3 (Probe).
- If assume fails (permission denied, tag policy, etc.) → show the error and help debug.

**If the role does NOT exist** (`NoSuchEntity`) — deploy it automatically:

```
The FORGE-Assessment-Role doesn't exist yet in this account. I'll deploy it now.

This creates a least-privilege read-only role — no data access, no mutations,
session-tagged, 1-hour TTL. All 9 API permission sets are scoped to specific
actions only (no wildcards).
```

Then deploy:

```bash
aws cloudformation deploy \
  --template-file forge/role_provisioner/cfn_template.yaml \
  --stack-name forge-assessment-role \
  --capabilities CAPABILITY_IAM
```

Wait for the stack to complete, then re-check with `get-role` and `assume-role` to confirm.

**Pre-flight is complete when:**
1. ✅ Valid AWS credentials in the terminal
2. ✅ Correct account confirmed
3. ✅ FORGE-Assessment-Role exists and is assumable

Only then proceed to the assessment.

---

## Phase B: Skill Runner (Per Assessment Session)

### 3. Probe the Account

Run the probes directly to discover what services are present. **Do NOT run `python3 -m forge assess` here** — that command requires a declared profile which doesn't exist yet. Instead, call the probe engine directly:

```python
python3 -c "
from forge.relevance_engine.probes import run_probes

results = run_probes('<aws-region>')
results.sort(key=lambda r: (r.classification.value, r.service_name))

print(f\"{'Service':<20} {'Status':<20} {'Resources'}\")
print('-' * 60)
for r in results:
    status = r.classification.value
    count = r.resource_count if r.resource_count else 0
    print(f'{r.service_name:<20} {status:<20} {count}')
"
```

This runs the lightweight probe phase only (list/describe calls) without requiring a profile.

Display the probe results to the user:

| Service | Status | Resources |
|---------|--------|-----------|
| glue | provisioned | 14 databases |
| lakeformation | provisioned | tag policies active |
| bedrock | provisioned | 2 agents |
| kinesis | not_provisioned | 0 |
| neptune | not_provisioned | 0 |
| ... | ... | ... |

### 4. Profile Wizard — Agent Proposes, User Confirms

**If no `forge_output/forge_profile.yaml` exists**, the agent analyzes probe results to PROPOSE a FORGE Profile, then asks the user to confirm.

**How the agent determines the proposal:**

- **Architecture**: 
  - `open_lakehouse` if Iceberg tables, S3 Tables, Glue Data Catalog, Lake Formation detected
  - `saas_native` if API Gateway, Cognito, multi-tenant DynamoDB patterns dominate
  - `hybrid` if both data platform and SaaS delivery signals are strong

- **Workload**:
  - `rag_retrieval` if Bedrock Knowledge Bases, OpenSearch vector collections detected
  - `single_tool` if single Bedrock agent with limited tool use
  - `multi_tool_agents` if multiple agents, Step Functions orchestration, complex tool chains

- **Industry**:
  - `financial_services` if Macie PII detection active, strict access controls, cost attribution heavy
  - `healthcare` if HIPAA-aligned patterns (PHI tagging, audit manager active)
  - `public_sector` if GovCloud or FedRAMP-aligned patterns detected
  - `general` otherwise

- **Agent Maturity**:
  - `pilot` if Bedrock agents exist but no guardrails or production patterns
  - `single_agent_prod` if 1 active agent with guardrails configured
  - `multi_agent_prod` if multiple agents with orchestration (Step Functions + guardrails)

**Present the proposal to the user:**

```
Based on your account probe, I recommend this FORGE Profile:

  Architecture:   open_lakehouse  (detected: Glue catalog, Lake Formation, Iceberg tables)
  Workload:       multi_tool_agents  (detected: 2 Bedrock agents, Step Functions)
  Industry:       financial_services  (detected: Macie active, strict IAM, cost tags)
  Agent Maturity: single_agent_prod  (detected: 1 agent with guardrails)

Does this look right? You can confirm or adjust any dimension.
```

**If the user confirms**, lock the profile:

```bash
python3 -m forge profile declare \
  --architecture <selection> \
  --workload <selection> \
  --industry <selection> \
  --agent-maturity <selection>
```

**If the user adjusts**, use their overrides instead.

This writes `forge_output/forge_profile.yaml` and locks it for the engagement. Subsequent runs skip the profile wizard and use the locked profile automatically.

### 5. Collect & Assess (Automatic — No User Prompts)

**After profile is locked, run the AWS assessment pipeline automatically:**

```bash
python3 -m forge assess --account-id <account-id> --region <region> --show-delta
```

The pipeline runs without stopping:

1. **COLLECT** → 142 criteria (89 auto 🤖 + 53 manual 🔧)
2. **ASSESS** → Apply FORGE Profile → effective weights/floors → score → recommendations
3. **OUTPUT** → JSON manifest + markdown roadmap + history append

**DO NOT** ask the user anything during this step. The only pause point in the entire flow is Step 4 (profile confirmation).

---

### 6. Ask About Additional Platforms

**After the AWS assessment pipeline completes, ALWAYS ask:**

```
AWS assessment complete. Before I generate the final dashboard —

Is this a multi-platform environment? Do you also use any of these data platforms
alongside AWS?

  • Databricks  (Unity Catalog, Delta Live Tables, SQL Warehouse, etc.)
  • (More platforms coming soon: Azure Synapse, Snowflake, Google BigQuery)

If yes, I'll assess your other platform(s) and produce a combined Estate Score.
If no, I'll generate the AWS-only dashboard now.
```

**If the user says no** → proceed to Step 7 (AWS-only dashboard & summary).

**If the user selects Databricks** → proceed to Step 8 (Databricks assessment, then estate dashboard & summary).

---

### 7. Generate Dashboard & Show Summary (AWS-Only Path)

**This step runs only if the user has no additional platforms.**

Generate and open the dashboard automatically:

```bash
python3 forge_dashboard_generator.py forge_output/assessments/forge_assessment_results.json
open forge_output/forge_dashboard.html
```

Print a concise summary:

```
✅ FORGE 2.3 Assessment Complete

  Score:   38.6 — FOUNDATIONAL
  Profile: open_lakehouse / multi_tool_agents / general / single_agent_prod
  Account: 123456789012 (us-east-1)

  Delta vs last run: +38.6 pts  (7 pillars improved, 0 regressed)
  Band: UNREADY → FOUNDATIONAL ↑

  Top Score-Lift Opportunities:
    P4 Data Quality & Classification  — +8.2 pts potential
    P2 Semantic Context & Retrieval   — +6.1 pts potential
    P8 Agent Controllability          — +4.3 pts potential

  Artifacts:
    📄 forge_output/assessments/forge_assessment_<ts>.json   (full manifest)
    📋 forge_output/roadmaps/forge_roadmap_<ts>.md           (remediation plan)
    📊 forge_output/forge_dashboard.html                     (opened in browser)
    🗂️  forge_output/forge_history.jsonl                     (trend log updated)
```

**Assessment is complete.**

---

## Phase C: Multi-Platform Assessment (Databricks)

### 8. Run Databricks Assessment (Document + Probing)

Trigger the Databricks assessment flow. This runs entirely within the same session using the same locked FORGE Profile.

```python
from forge.skill_support.databricks_skill import get_initial_prompt, advance_skill_phase
from forge.platform_segments.databricks_segment import SkillConversationState, build_databricks_segment
from forge.platform_segments.aws_adapter import wrap_aws_result
from forge.scoring_engine.merge import merge_criteria, compute_estate_score
from forge.profile_engine import load_profile, resolve_profile
```

**Step 8a: Request documents**

```
Let's assess your Databricks environment. Upload whatever you have —
I'll read through everything and figure out what's running.

Most useful (in priority order):
  1. Architecture diagram (image or text description)
  2. Cost/billing report (CSV from system.billing.usage)
  3. Workspace description, config exports, or architecture docs

Accepted: Images (PNG/JPG), CSV, TXT, MD, JSON, YAML, PDF

If you don't have documents, just describe your setup and I'll work from there.
```

**Step 8b: Read all documents → Extract evidence → Present findings**

The agent reads ALL uploaded documents (images, CSVs, text), identifies services from architecture elements and SKU names, extracts criteria evidence, and presents a consolidated summary for user confirmation.

**Step 8c: Probing questions (2-3 rounds, max ~12 questions)**

Ask targeted follow-up questions grouped by theme for criteria not covered by documents. Stop when all relevant criteria are scored or 12 questions answered.

**Step 8d: Score, merge, and build estate (automatic — no prompts)**

```python
profile = load_profile()
dbx_segment = build_databricks_segment(state, profile)
aws_segment = wrap_aws_result(aws_assessment_result)

resolved = resolve_profile(profile)
merged = merge_criteria([aws_segment, dbx_segment])
estate_score, estate_band, raw_score, coverage_mult = compute_estate_score(
    merged, resolved.effective_weights, resolved.effective_floors
)
```

See the **forge-databricks-assessment** skill for full phase details.

### 9. Generate Estate Dashboard & Show Summary

Generate the estate dashboard and open it automatically — **DO NOT** ask the user:

```bash
python3 scripts/generate_estate_dashboard.py
open forge_output/forge_estate_dashboard.html
```

Print the combined summary:

```
✅ FORGE Estate Assessment Complete (Multi-Platform)

  AWS Score:        44.8 — FOUNDATIONAL
  Databricks Score: 65.2 — GOVERNED
  ─────────────────────────────────
  Estate Score:     52.8 — GOVERNED

  Platforms: AWS (api_discovery) + Databricks (document + conversational)
  Profile:   open_lakehouse / multi_tool_agents / financial_services / multi_agent_prod

  Merge Logic Applied:
    Binary criteria:  AND across platforms (both must pass)
    Analog criteria:  Pooled ratio (sum numerators / sum denominators)

  Top Estate-Level Score-Lift Opportunities:
    P4 Data Quality   — +6.8 pts (AWS: 3 gaps, Databricks: 2 gaps)
    P7 Real-Time      — +4.2 pts (AWS: 2 gaps, Databricks: 4 gaps)
    P5 Access Control — +3.9 pts (Databricks: 3 gaps)

  Artifacts:
    📊 forge_output/forge_estate_dashboard.html              (opened in browser)
    📄 forge_output/assessments/forge_estate_assessment_<ts>.json
    📋 forge_output/roadmaps/forge_estate_roadmap_<ts>.md    (grouped by platform)
    🗂️  forge_output/forge_history.jsonl                     (estate record appended)
```

The estate dashboard shows:
- **Estate Score** as the primary gauge with platform badges below
- **Radar chart toggle**: Combined | AWS | Databricks
- **Criteria drill-down** with platform badges and per-platform failure attribution
- **Remediation roadmap** grouped by platform (AWS actions vs Databricks actions)

**Assessment is complete.**

---

## Scoring Model: FORGE 2.3 Profiles

**Formula:** `FORGE Score = Raw Score(effective_weights) × Coverage Multiplier(effective_floors)`

- **No Track Adjustment** — replaced by FORGE Profiles
- **9 Pillars, 142 Criteria** — same framework, new weighting
- **Base Weights**: P1=17%, P2=17%, P3=8%, P4=12%, P5=11%, P6=9%, P7=7%, P8=10%, P9=9%
- **Profile Shifts**: ±8pp cap per pillar, 2% floor, normalized to 100%
- **Coverage Multiplier**: Penalty rates P1-P3=8%, P4-P8=5%, P9=3%, capped at 40%
- **Bands**: UNREADY (<26), FOUNDATIONAL (26-50), GOVERNED (51-75), AGENT-READY (76-90), FORGE-NATIVE (91+)

---

## CloudTrail Audit Trail

Every API call made during the assessment is recorded in CloudTrail with:
- **Session name**: `forge-skill-<timestamp>` (filterable in `userIdentity.arn`)
- **Session tags**: `forge-skill`, `forge-version=2.3.0`, `forge-run-id`

Filter command: `aws cloudtrail lookup-events --lookup-attributes AttributeKey=Username,AttributeValue=forge-skill-*`

---

## Skill Memory

```
forge_output/forge_profile.yaml                              # Locked profile (never overwrite)
forge_output/assessments/forge_assessment_<ts>.json           # AWS-only timestamped manifest
forge_output/assessments/forge_estate_assessment_<ts>.json    # Multi-platform estate manifest
forge_output/roadmaps/forge_roadmap_<ts>.md                  # AWS remediation priorities
forge_output/roadmaps/forge_estate_roadmap_<ts>.md           # Platform-grouped remediation
forge_output/forge_history.jsonl                             # Append-only (supports estate + per-platform)
forge_output/forge_dashboard.html                            # AWS-only dashboard
forge_output/forge_estate_dashboard.html                     # Multi-platform estate dashboard
```

### Assessment Results JSON Structure

**Important:** In `forge_assessment_results.json`, `pillars` is a **list** of pillar objects (not a dict keyed by pillar name). Each pillar object has the shape:

```json
{
  "code": "P1",
  "name": "Agent Access & Discovery",
  "total": 21,
  "raw_score": 80.95,
  "relevant_count": 21,
  "not_applicable_count": 0,
  "undetermined_count": 0,
  "criteria": [ { "index": 1, "name": "...", "score": 1.0, "met": true, ... } ]
}
```

Iterate with `for pillar in data["pillars"]` — do NOT use `.items()` or assume dict keys.

---

## Validation Rules

- **Account ID**: Must be exactly 12 numeric digits (`^\d{12}$`)
- **Region**: Must be a valid AWS region identifier (e.g., `us-east-1`)
- **Profile dimensions**: Must match enum values exactly (see options above)
- **Profile lock**: Once declared, cannot be modified for the engagement

## Error Handling

- If CloudFormation deploy fails → Check IAM permissions (need `iam:CreateRole` and `cloudformation:CreateStack`)
- If STS AssumeRole fails → Verify the role exists and session tag is included
- If no profile declared → Prompt user to run `forge profile declare` first
- If `--track` is used → Display migration message: "Use `forge profile declare` instead"
