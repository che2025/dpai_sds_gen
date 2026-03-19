# dpai_sds_gen

AI-driven SDS (Software Design Specification) generator for IEC 62304 medical device software.

Takes a GitHub repository URL as input, analyzes the codebase using Google Gemini (Vertex AI), and generates a fully structured `.docx` SDS document.

## How It Works

The pipeline runs in two phases:

**Phase 1 — Code Analysis (10 steps)**
Each step is one LLM call with Function Calling enabled, so the model can read and search the actual source files on demand. Steps cover: repo structure, build/deploy config, dependencies, API surface, data models, business features, error handling, security & privacy, test suite, and a final synthesis with gap assessment. Output: `analysis.md` cached at `~/.dpai_sds_gen/cache/`.

**Phase 2 — SDS Generation (12 sections)**
Each IEC 62304 section is generated as a structured JSON from the `analysis.md`. Function Calling is disabled here — all needed information is already in the analysis. Output: `sections/*.json`, then assembled into a `.docx`.

**Caching**: Phase 1 is skipped automatically if the repo's `HEAD` commit SHA hasn't changed. Only Phase 2 re-runs (much faster).

## Setup

### 1. Install dependencies

```bash
cd dpai_sds_gen
python -m venv venv && source venv/bin/activate
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true

# Gemini model to use
GEMINI_MODEL=gemini-2.5-pro

# Optional: required for private repos
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Cost / call guardrails
MAX_COST_USD=20.00
MAX_API_CALLS=200
```

### 3. Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

## Usage

### Full pipeline (recommended)

```bash
# Full repo
python -m src.cli.main run https://github.com/org/my-service \
  --sw-number SW14552 --sw-name "My Service"

# Subdirectory in a monorepo
python -m src.cli.main run https://github.com/org/monorepo/tree/main/apps/my-service \
  --sw-number SW14552 --sw-name "My Service"

# All options
python -m src.cli.main run https://github.com/org/repo/tree/main/apps/foo \
  --sw-number SW14552 \
  --sw-name "My Software" \
  --output SDS-SW14552.docx \
  --max-cost 30.00 \
  --verbose
```

### Re-assemble .docx without re-running LLM

If you only changed rendering/styling, you can skip both phases and just reassemble:

```python
from pathlib import Path
from src.docx_engine.assembler import assemble_docx

sections_dir = Path.home() / ".dpai_sds_gen/cache/<cache_key>/sections"
assemble_docx(sections_dir, Path("SDS-SW14552.docx"), sw_number="SW14552", sw_name="My Service")
```

## Project Configuration (.dpai_sds_gen.yaml)

Place in the target repo to persist project-specific settings:

```yaml
software:
  sw_number: "SW14552"
  sw_name: "Advanced Insights Services"
  system_name: "CGM System"

analysis:
  exclude_paths:
    - "vendor/"
    - "node_modules/"

references:
  - doc_number: "SRS-1000094"
    description: "Software Requirements Specification"
  - doc_number: "RA-1000086"
    description: "Software Risk and Hazard Analysis"

limits:
  max_cost_usd: 20.00
```

## Architecture

```
GitHub URL
    │
    ▼
git clone (shallow, depth=1)
    │
    ▼
Phase 1: Code Analysis (10 steps, serial)
    │  Each step = 1 LLM call + N function calls (read_file / search_code)
    │  LLM reads code on demand via Function Calling
    │
    ▼
analysis.md  ◄── cached, skipped if commit SHA unchanged
    │
    ▼
Phase 2: SDS Generation (12 sections, serial)
    │  Each section = 1 LLM call (no Function Calling — analysis.md is sufficient)
    │
    ▼
sections/*.json  ◄── cached per section
    │
    ▼
docx_engine: renderer.py + assembler.py
    │
    ▼
SDS-SW14552.docx
```

## Cache

Cached at `~/.dpai_sds_gen/cache/{org}_{repo}_{scope_hash}/`:

```
commit_sha.txt       ← cache invalidation key
cost.json            ← API call / token / cost log
analysis.md          ← Phase 1 output
sections/
  purpose_scope.json
  references.json
  definitions.json
  overview.json
  components.json
  integrations.json
  feature_6_3_1.json
  ...
  ai_principles.json
  security.json
  attachments.json
  quality_check.json
```

To force a full re-run, delete the cache directory:

```bash
rm -rf ~/.dpai_sds_gen/cache/<cache_key>/
```
