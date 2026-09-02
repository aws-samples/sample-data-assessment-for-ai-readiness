---
name: FORGE Customization
description: Customize FORGE assessment weights, recommendations, and partner solutions without editing Python code.
---

# FORGE Customization Skill

Help partners customize the FORGE assessment framework by editing YAML configuration files in `forge_config/`.

## What Can Be Customized

### 1. IAM Role Permissions
**File:** `forge/role_provisioner/cfn_template.yaml`

The FORGE assessment role uses a **least-privilege** model — each API action is explicitly granted. When you add new criteria, assessors, or probes that call additional AWS APIs, the CFN template must be updated to include those actions.

### 2. Weights & Shift Vectors
**File:** `forge_config/weights.yaml`

Partners can adjust:
- **Base pillar weights** (must sum to 100) — controls how much each pillar contributes to the overall FORGE score
- **Per-dimension shift vectors** (must be zero-sum per entry) — adjusts weights based on architecture, workload, industry, and agent maturity
- **Floor override thresholds** — minimum pillar scores before coverage penalty kicks in

### 2. Remediation Recommendations
**File:** `forge_config/recommendations.yaml`

Partners can:
- Update suggested remediation actions for each criterion
- Add their own product-specific recommendations
- Set effort estimates (low/medium/high) and timeline (estimated_days)
- Reference partner solution IDs from the partner catalog

### 3. Partner Solutions
**File:** `forge_config/partner_solutions.yaml`

Partners can:
- Register their products with a unique ID
- Map products to applicable FORGE criteria (P1.1 through P9.12)
- Provide specific integration notes for AWS environments
- Categorize solutions for easy reference

## Commands

### Update IAM Role After Adding New API Calls

When you add new criteria or modify assessors that call AWS APIs not already in the CFN template, follow this workflow:

#### 1. Identify New Actions Needed

Check the pillar assessor or probe code for new boto3 API calls:

```bash
# Find all boto3 API calls in a pillar assessor (e.g., p4.py)
grep -n "safe_call\|client\." forge/pillar_assessors/p4.py
```

#### 2. Map boto3 Methods to IAM Actions

| boto3 Method | IAM Action |
|-------------|------------|
| `client.list_*()` | `service:List*` (use exact name, e.g. `glue:ListCrawlers`) |
| `client.get_*()` | `service:Get*` (use exact name, e.g. `glue:GetDatabase`) |
| `client.describe_*()` | `service:Describe*` (use exact name, e.g. `rds:DescribeDBInstances`) |

Common pattern: CamelCase method → CamelCase action. E.g., `glue.get_databases()` → `glue:GetDatabases`.

#### 3. Add to the CFN Template

Edit `forge/role_provisioner/cfn_template.yaml`. Add the action to the appropriate pillar statement, or create a new statement if it's a new service:

```yaml
              # Add to existing pillar statement:
              - Sid: P4DataQualityRead
                Effect: Allow
                Action:
                  - "macie2:GetMacieSession"
                  - "macie2:ListClassificationJobs"
                  - "macie2:ListFindings"
                  - "macie2:GetFindingsStatistics"   # ← new action
                Resource: "*"
```

Or for a brand new service:

```yaml
              - Sid: P4NewServiceRead
                Effect: Allow
                Action:
                  - "newservice:ListResources"
                  - "newservice:DescribeResource"
                Resource: "*"
```

#### 4. Validate the Template

```bash
python3 << 'EOF'
import yaml

for tag in ['!Ref', '!Sub', '!GetAtt', '!Join', '!Select']:
    yaml.SafeLoader.add_constructor(tag, lambda loader, node: loader.construct_scalar(node))

with open('forge/role_provisioner/cfn_template.yaml') as f:
    doc = yaml.safe_load(f)

stmts = doc['Resources']['ForgeAssessmentRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
print(f'Total statements: {len(stmts)}')

# Verify no wildcards
for stmt in stmts:
    for action in stmt.get('Action', []):
        if action.endswith('*'):
            print(f'ERROR: wildcard action "{action}" in {stmt["Sid"]}')
            break
    else:
        continue
    break
else:
    print('✓ All actions are specific (no wildcards)')

# Verify no Deny statements
deny = [s for s in stmts if s['Effect'] == 'Deny']
if deny:
    print(f'ERROR: {len(deny)} Deny statements found — use least-privilege Allow only')
else:
    print('✓ No Deny statements (least-privilege model)')
EOF
```

#### 5. Deploy the Updated Role

```bash
aws cloudformation deploy \
  --template-file forge/role_provisioner/cfn_template.yaml \
  --stack-name forge-assessment-role \
  --capabilities CAPABILITY_IAM
```

CloudFormation will update the inline policy in-place. No downtime — the role ARN stays the same.

#### 6. Update the Role Scope Display (Optional)

If you added a notable new action, update `_ROLE_SCOPE_ENTRIES` in `forge/collector.py` so the runtime permission summary stays accurate:

```python
_ROLE_SCOPE_ENTRIES = [
    ("P1 Agent Access & Discovery", "glue:GetDatabases, glue:GetTables, ..."),
    # ... update the relevant pillar line
]
```

### IAM Role Design Principles

| Principle | Rule |
|-----------|------|
| **No wildcards** | Every action must be fully spelled out (e.g., `glue:GetDatabases` not `glue:Get*`) |
| **No Deny statements** | If you don't grant it, it's denied implicitly — no explicit Deny needed |
| **No data-plane access** | Never add `s3:GetObject`, `dynamodb:GetItem`, `athena:StartQueryExecution`, or `bedrock:InvokeModel` |
| **No mutations** | Never add any Create/Delete/Put/Update/Attach/Detach action |
| **Resource: "*"** | Acceptable because all actions are read-only metadata. Scoping to specific ARNs is optional but adds maintenance cost |
| **Group by pillar** | Each `Sid` maps to a pillar or shared concern for auditability |

### Audit: List All Granted Actions

```bash
python3 << 'EOF'
import yaml

for tag in ['!Ref', '!Sub', '!GetAtt', '!Join', '!Select']:
    yaml.SafeLoader.add_constructor(tag, lambda loader, node: loader.construct_scalar(node))

with open('forge/role_provisioner/cfn_template.yaml') as f:
    doc = yaml.safe_load(f)

stmts = doc['Resources']['ForgeAssessmentRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
all_actions = []
for stmt in stmts:
    sid = stmt.get('Sid', 'unnamed')
    for action in stmt.get('Action', []):
        all_actions.append((sid, action))

print(f'Total granted actions: {len(all_actions)}')
print()
for sid, action in sorted(all_actions, key=lambda x: x[1]):
    print(f'  {action:45s} ({sid})')
EOF
```

---

### View Current Weights

```bash
python3 -c "from forge.profile_engine.dimensions import BASE_WEIGHTS; print(BASE_WEIGHTS); print(f'Sum: {sum(BASE_WEIGHTS.values())}')"
```

### Validate Weight Sum

After editing `forge_config/weights.yaml`, always verify the sum:

```bash
python3 -c "
import yaml
with open('forge_config/weights.yaml') as f:
    config = yaml.safe_load(f)
weights = config['base_weights']
total = sum(weights.values())
print(f'Weights: {weights}')
print(f'Sum: {total}')
assert total == 100, f'ERROR: Weights sum to {total}, must be 100!'
print('✓ Valid: weights sum to 100')
"
```

### Validate Shift Vectors Are Zero-Sum

```bash
python3 -c "
import yaml
with open('forge_config/weights.yaml') as f:
    config = yaml.safe_load(f)
for dim_name, dim_shifts in config.get('shifts', {}).items():
    for variant, pillars in dim_shifts.items():
        total = sum(pillars.values())
        status = '✓' if total == 0 else '✗ ERROR'
        print(f'{status} shifts.{dim_name}.{variant}: sum={total}')
"
```

### Preview Score Impact With Different Weights

```bash
python3 -c "
from forge.profile_engine.dimensions import BASE_WEIGHTS
from forge.scoring_engine.formula import compute_raw_score

# Example: simulated pillar scores (replace with your actuals)
pillar_scores = {'P1': 65, 'P2': 45, 'P3': 30, 'P4': 55, 'P5': 70, 'P6': 50, 'P7': 25, 'P8': 40, 'P9': 35}

# Current weights
current_raw = compute_raw_score(pillar_scores, {k: float(v) for k, v in BASE_WEIGHTS.items()})

# Modified weights (example: boost P1 to 20, reduce P9 to 6)
modified = dict(BASE_WEIGHTS)
modified['P1'] = 20
modified['P9'] = 6
modified_raw = compute_raw_score(pillar_scores, {k: float(v) for k, v in modified.items()})

print(f'Current raw score: {current_raw:.2f}')
print(f'Modified raw score: {modified_raw:.2f}')
print(f'Delta: {modified_raw - current_raw:+.2f}')
"
```

### Add a Partner Solution

1. Edit `forge_config/partner_solutions.yaml` and add an entry:

```yaml
  - id: my-product
    name: "My Product Name"
    vendor: "My Company"
    category: "Data Quality"
    applicable_criteria: ["P4.1", "P4.7", "P4.10"]
    description: "Brief description of what it does"
    integration_notes: "How it integrates with AWS services"
```

2. Reference it in `forge_config/recommendations.yaml` under the relevant criteria:

```yaml
P4.1:
  # ... existing fields ...
  partner_solutions:
    - my-product
```

### List All Criteria a Partner Can Address

```bash
python3 -c "
import yaml
with open('forge_config/partner_solutions.yaml') as f:
    catalog = yaml.safe_load(f)
for sol in catalog['solutions']:
    print(f\"{sol['id']}: {sol['name']} ({sol['category']})\")
    for c in sol['applicable_criteria']:
        print(f'  - {c}')
    print()
"
```

### Run Assessment With Custom Config

No special flags needed. The assessment automatically picks up `forge_config/` files:

```bash
python3 -m forge --region us-east-1
```

The roadmap output will include recommendations and partner solutions for each unmet criterion.

## Workflow: Adding a New Pillar Assessor API Call

1. **Write the assessor code** that calls a new AWS API (e.g., `glue.get_security_configurations()`)
2. **Map the method** to its IAM action: `glue:GetSecurityConfigurations`
3. **Add to CFN template** under the correct pillar Sid in `forge/role_provisioner/cfn_template.yaml`
4. **Validate** with the validation script above (no wildcards, no Deny)
5. **Deploy** with `aws cloudformation deploy`
6. **Update display** in `forge/collector.py` `_ROLE_SCOPE_ENTRIES` if desired
7. **Test** by running the assessment — the new API call should succeed with the updated role

## Workflow: Adjusting a Weight

1. **View current state:** Run the view weights command above
2. **Edit YAML:** Modify `forge_config/weights.yaml` — change the pillar you want to boost, and reduce another to keep sum=100
3. **Validate:** Run the validate weight sum command
4. **Preview impact:** Use the preview command with your actual pillar scores
5. **Commit:** If satisfied, the change takes effect on next assessment run

## Workflow: Adding Partner Recommendations

1. **Register product** in `forge_config/partner_solutions.yaml`
2. **Map criteria:** List all FORGE criteria IDs your product addresses in `applicable_criteria`
3. **Add to roadmap:** Reference your product ID in `forge_config/recommendations.yaml` under each relevant criterion's `partner_solutions` list
4. **Run assessment:** Your product will appear in the roadmap output alongside AWS-native solutions

## File Relationships

```
forge/role_provisioner/
└── cfn_template.yaml       ← IAM role (least-privilege, update when adding new API calls)
         │
         ▼
forge/pillar_assessors/     ← Assessor code calls AWS APIs that must be granted in the template
forge/relevance_engine/probes.py  ← Probe API calls must also be granted

forge_config/
├── weights.yaml            ← Scoring parameters (weights, shifts, floors)
├── recommendations.yaml    ← Per-criterion remediation guidance
└── partner_solutions.yaml  ← Partner product registry
         │                            │
         │                            ▼
         │                   recommendations.yaml references
         │                   partner IDs from this file
         ▼
forge/profile_engine/dimensions.py reads weights.yaml
forge/collector.py reads recommendations.yaml + partner_solutions.yaml
forge/collector.py displays role scope from _ROLE_SCOPE_ENTRIES
```

## Validation Rules

| File | Rule | Check |
|------|------|-------|
| cfn_template.yaml | No wildcard actions (no `Get*`, `List*`, `Describe*`) | Action suffix check |
| cfn_template.yaml | No Deny statements | Effect check |
| cfn_template.yaml | No data-plane or mutation actions | Action blocklist |
| weights.yaml | `base_weights` values sum to 100 | Sum check |
| weights.yaml | Each shift vector sums to 0 | Zero-sum check |
| weights.yaml | All 9 pillars (P1-P9) present in base_weights | Key completeness |
| partner_solutions.yaml | Each `id` is unique | Uniqueness |
| partner_solutions.yaml | `applicable_criteria` use valid format (P#.#) | Format check |
| recommendations.yaml | Keys match valid criteria IDs | Registry lookup |

## Notes

- If `forge_config/weights.yaml` is missing, the system uses hardcoded defaults in `dimensions.py`
- If `forge_config/recommendations.yaml` is missing, the roadmap still generates but without solution guidance
- PyYAML (`pip install pyyaml`) is required for YAML loading; without it, defaults are used silently
- Changes take effect on the next assessment run — no restart needed
