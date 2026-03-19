# dpai_sds_gen

AI-driven SDS (Software Design Specification) generator for IEC 62304 medical device software.

Takes a GitHub repository URL as input, analyzes the codebase using Google Gemini (Vertex AI), and generates a .docx SDS report.

## Setup

### 1. Install dependencies

```bash
cd dpai_sds_gen
pip install -e .
```

Or install dependencies directly:

```bash
pip install typer rich python-dotenv google-genai python-docx pyyaml
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
GOOGLE_CLOUD_PROJECT=dp-experimental
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_MODEL=gemini-2.5-pro
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
MAX_COST_USD=20.00
```

### 3. Authenticate with Google Cloud

Make sure you are authenticated:

```bash
gcloud auth application-default login
```

Or if using a virtual environment:

```bash
source venv_1/bin/activate
export GOOGLE_CLOUD_PROJECT=dp-experimental
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=true
```

## Usage

### Full pipeline (recommended)

```bash
# Analyze a full repo
dpai_sds_gen run https://github.com/org/my-service --sw-number SW14552 --sw-name "My Service"

# Analyze a subdirectory in a monorepo
dpai_sds_gen run https://github.com/org/horizon-adk/tree/main/apps/health-coach \
  --sw-number SW14552 --sw-name "Health Coach"

# With all options
dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo \
  --sw-number SW14552 \
  --sw-name "My Software" \
  --output SDS-SW14552.docx \
  --max-cost 30.00 \
  --verbose
```

### Separate phases

```bash
# Phase 1 only
dpai_sds_gen analyze https://github.com/org/repo

# Phase 2 only (requires prior Phase 1)
dpai_sds_gen generate https://github.com/org/repo --output report.docx

# Regenerate a specific section
dpai_sds_gen regenerate https://github.com/org/repo --section integrations

# Validate the generated SDS
dpai_sds_gen validate https://github.com/org/repo
```

### Running directly with Python

```bash
source venv_1/bin/activate
export GOOGLE_CLOUD_PROJECT=dp-experimental
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_GENAI_USE_VERTEXAI=true

python -m src.cli.main run https://github.com/org/repo --sw-number SW14552 --sw-name "My Service"
```

## Project Configuration (.dpai_sds_gen.yaml)

Place in the target repo (or its subdirectory) to persist project-specific settings:

```yaml
software:
  sw_number: "SW14552"
  sw_name: "Advanced Insights Services"
  system_name: "CGM System"

analysis:
  exclude_paths:
    - "vendor/"
    - "node_modules/"
  entry_points:
    - "src/main.py"

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
GitHub URL → git clone → Phase 1 (Analyze) → Phase 2 (Generate) → .docx
                              ↓                    ↓
                         Code Reader          Code Reader
                         (file access)     (Function Calling)
                              ↓                    ↓
                         Gemini API           Gemini API
                         (multi-turn)      (+ code verification)
                                                   ↓
                                             docx Engine
                                            (python-docx)
```

## Cache

Results are cached in `~/.dpai_sds_gen/cache/`. Re-running the same URL skips completed steps. Use `--reanalyze` to force a full re-run.
