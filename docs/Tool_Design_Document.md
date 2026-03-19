# SDS Generator Tool — Technical Design Document

## Tool Name: `dpai_sds_gen`

## 1. PRODUCT OVERVIEW

`dpai_sds_gen` is a CLI tool that takes a **GitHub repository URL** as input and generates an IEC 62304-compliant Software Design Specification (SDS) in .docx format. It operates in two phases: Phase 1 deeply analyzes the codebase; Phase 2 generates the SDS document. The final .docx is handed off to QA for review and editing.

The URL can point to a full repo or a **subdirectory within a monorepo** — the tool parses the URL to determine the SDS scope automatically. For example:

```
# Full repo → SDS covers the entire repository
dpai_sds_gen run https://github.com/org/my-service

# Subdirectory → SDS covers apps/health-coach, with shared code accessible
dpai_sds_gen run https://github.com/org/horizon-adk/tree/main/apps/health-coach
```

The tool clones the repo locally (authenticating via GitHub token for private repos), performs analysis, generates the .docx, and cleans up the clone automatically.

The tool calls Google Gemini API for AI reasoning and produces a .docx file that conforms to the company's SDS template (CORPFT-010522).

---

## 2. ARCHITECTURE OVERVIEW

```
             GitHub URL (required input)
             "https://github.com/org/repo/tree/main/apps/foo"
                           │
                           ▼
                    ┌─────────────┐
                    │  URL Parser  │─── repo: org/repo
                    │              │─── branch: main
                    └──────┬──────┘─── scope_path: apps/foo
                           │
                           ▼
                    ┌─────────────┐
                    │  git clone   │─── auth: GitHub token
                    │  (depth=1)   │─── dest: ~/.dpai_sds_gen/clones/{hash}/
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                                 ▼
   ┌─────────────┐                  ┌──────────────┐
   │   Phase 1    │                 │  Code Reader   │
   │   Analyze    │────────────────▶│               │
   └──────┬──────┘   Function       │  scope: apps/foo (primary)
          │          Calling        │  context: full repo (imports,
          ▼          (FC enabled)   │           shared libs)
   ┌─────────────┐                  └──────────────┘
   │ analysis.md  │
   │ (cached)     │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐    analysis.md   ┌──────────────┐
   │   Phase 2    │─── only, no ───▶│  Gemini LLM   │
   │   Generate   │    FC           │  (no code     │
   └──────┬──────┘                  │   access)     │
          │                         └──────────────┘
          ▼
   ┌─────────────┐
   │  sections/   │
   │  *.json      │
   └──────┬──────┘
          │
          ▼
   ┌─────────────┐
   │ docx Engine  │───▶  SDS-SW14552.docx
   │ (python-docx)│
   └─────────────┘
          │
          ▼
   Auto-delete clone
```

### Core Design Principles

1. **GitHub URL is the only required input.** The tool parses the URL to determine repo, branch, and analysis scope. Everything else is auto-detected or optional configuration.
2. **Scope-aware analysis.** When the URL points to a subdirectory, that directory is the primary analysis target. But the Code Reader has access to the full cloned repo, so the AI can follow imports upward into shared libraries, common packages, or repo-root configs when needed.
3. **Clone, analyze, clean up.** The repo is cloned to a local temp directory, analyzed, and the clone is deleted after completion. Cached analysis results persist so re-runs don't require re-cloning.
4. **Function Calling in Phase 1 only.** Phase 1 uses Gemini Function Calling so the LLM can read and search code on demand. Phase 2 has FC disabled — by the time Phase 2 runs, all needed information is in `analysis.md`. This avoids wasted API calls and keeps Phase 2 fast.
5. **LLM is decoupled.** The Gemini API Adapter is a clean interface. Model selection (`gemini-2.5-pro` vs `gemini-2.5-flash`) is controlled via the `GEMINI_MODEL` env var.

---

## 3. URL PARSING AND REPO ACCESS

### 3.1 URL Format Support

The tool accepts GitHub URLs in these formats:

```
# Full repo (default branch)
https://github.com/org/repo

# Full repo (specific branch)
https://github.com/org/repo/tree/develop

# Subdirectory (specific branch)
https://github.com/org/repo/tree/main/apps/my-service

# Subdirectory (nested path)
https://github.com/org/repo/tree/release-2.0/services/api/insights
```

**Parsing logic:**

```python
def parse_github_url(url: str) -> RepoTarget:
    """
    Returns:
      - org: "org"
      - repo: "repo"
      - branch: "main" (or detected default)
      - scope_path: "apps/my-service" (or "" for full repo)
      - clone_url: "https://github.com/org/repo.git"
    """
```

If the URL contains `/tree/{branch}/{path}`, the `scope_path` is extracted. If it's just `https://github.com/org/repo`, the `scope_path` is empty (meaning: analyze the whole repo).

### 3.2 Authentication

Private repos require a GitHub Personal Access Token (PAT) or GitHub App token.

**Token resolution order:**

1. `--token` CLI flag (highest priority, for one-off use)
2. `GITHUB_TOKEN` environment variable (standard CI/CD pattern)
3. `~/.dpai_sds_gen/credentials.yaml` (persisted config)
4. `gh auth token` — attempt to read from GitHub CLI if installed

```yaml
# ~/.dpai_sds_gen/credentials.yaml
github:
  token: "ghp_xxxxxxxxxxxxxxxxxxxx"
```

The token is passed to `git clone` via the URL:
```
https://{token}@github.com/org/repo.git
```

The token is **never** sent to Gemini or logged.

### 3.3 Clone Strategy

```python
def clone_repo(target: RepoTarget, token: str) -> Path:
    clone_dir = Path.home() / ".dpai_sds_gen" / "clones" / f"{target.org}_{target.repo}_{hash}"

    # Clone with depth=1 for speed (we don't need full history)
    # We DO need the full repo tree, even when scope_path is set,
    # because the AI needs access to shared code outside scope_path.
    run(["git", "clone", "--depth=1", "--branch", target.branch,
         target.clone_url, str(clone_dir)])

    return clone_dir
```

**Key decisions:**
- **Shallow clone (`--depth=1`)**: We only need the current state of the code, not commit history. This makes cloning fast even for large repos.
- **Full repo clone, not sparse**: Even when the URL points to a subdirectory, we clone the entire repo. This is critical because `apps/foo` likely imports from `libs/shared/`, `packages/common/`, or reads config from the repo root. The AI needs access to these to understand the software fully.
- **Auto-cleanup**: After the pipeline completes (success or failure), the clone directory is deleted. A `--keep-clone` flag is available for debugging.

### 3.4 Cache Strategy

Analysis results and generated sections are cached outside the clone (since the clone gets deleted):

```
~/.dpai_sds_gen/
├── credentials.yaml                # GitHub token
├── clones/                         # Temporary clone directories (auto-cleaned)
│   └── org_repo_abc123/            # Active clone (deleted after run)
└── cache/
    └── {org}_{repo}_{branch}_{scope_hash}/
        ├── analysis.md             # Phase 1 output
        ├── sections/               # Phase 2 section JSONs
        │   ├── sec_01_purpose.json
        │   └── ...
        └── cost.json               # Token/cost tracking
```

The cache key includes the scope_path hash so that running the tool against different subdirectories of the same monorepo produces separate caches.

**Cache invalidation**: The cache is invalidated if the repo's HEAD commit SHA changes since the last analysis. The tool stores the commit SHA at analysis time and checks it on re-run.

```bash
$ dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo
# First run: clones, analyzes, generates, cleans clone. Cache saved.

$ dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo
# Second run: clones (shallow, fast), checks HEAD SHA.
# SHA matches cache → skips Phase 1, runs Phase 2 from cache.
# SHA differs → re-runs Phase 1.
```

---

## 4. CLI INTERFACE DESIGN

### 4.1 Commands

```bash
# Full pipeline: clone → analyze → generate → clean up
python -m src.cli.main run <github-url> [options]
```

The following subcommands are not yet implemented: `analyze`, `generate`, `regenerate`, `validate`, `auth`.

### 4.2 Key Flags

```bash
--sw-number SW14552            # Software identifier
--sw-name "My Software"        # Software name
--output report.docx           # Output path (default: SDS-{sw-number}.docx in cwd)
--token ghp_xxxxx              # GitHub token (overrides GITHUB_TOKEN env var)
--verbose / -v                 # Show detailed progress and API calls
--max-cost 20.00               # Abort if estimated cost exceeds this (USD)
```

### 4.3 Project Configuration File (`.dpai_sds_gen.yaml`)

Can live in the target repo (auto-detected at `{scope_path}/.dpai_sds_gen.yaml` or repo root) or passed via `--config`.

```yaml
# .dpai_sds_gen.yaml
software:
  sw_number: "SW14552"
  sw_name: "Advanced Insights Services"
  system_name: "CGM System"                  # Parent system, if any

analysis:
  exclude_paths:                              # Directories to skip within scope
    - "vendor/"
    - "node_modules/"
    - "test/fixtures/large_data/"
  entry_points:                               # Hint: main entry points to prioritize
    - "src/main.py"
    - "cmd/server/main.go"

references:                                   # Known document references to include
  - doc_number: "SRS-1000094"
    description: "Software Requirements Specification"
  - doc_number: "RA-1000086"
    description: "Software Risk and Hazard Analysis"

output:
  template: "default"                         # or path to custom .docx template

limits:
  max_cost_usd: 20.00
  max_api_calls: 200
```

**Config resolution order**: CLI flags → `.dpai_sds_gen.yaml` in scope_path → `.dpai_sds_gen.yaml` in repo root → built-in defaults.

---

## 5. PHASE 1: CODE ANALYSIS

### 5.1 Scope-Aware Analysis

The Code Reader operates with two access levels:

- **Scope (primary)**: The directory the URL points to (e.g., `apps/health-coach/`). Phase 1 steps systematically analyze every file in this directory. This is the SDS target.
- **Context (secondary)**: The rest of the repo. The AI can access files outside the scope when it encounters imports, shared libraries, or config files that live at the repo root. Context files are pulled on-demand, not pre-analyzed.

**How it works in practice:**

```
Phase 1, Step 3 (Dependencies):
  → Reads apps/health-coach/requirements.txt      (scope — automatic)
  → Finds: "from shared.auth import JWTValidator"  (scope file imports from outside)
  → AI requests: read_file("shared/auth/jwt.py")   (context — on demand)
  → Understands the shared auth module
  → Records: "Depends on shared/auth for JWT validation"
```

This means the AI naturally follows the code's own import graph outward when needed, but doesn't waste time analyzing unrelated services in the monorepo.

### 5.2 Pipeline

```
Step 1: File Inventory & Structural Map
         ↓  [carry_over_files: passes FILES_NEEDED files to next step]
Step 2: Build/Deploy/Config Analysis
         ↓  [carry_over_files]
Step 3: Dependency & Integration Extraction
         ↓  [carry_over_files]
Step 4: API Surface Extraction
         ↓  [carry_over_files]
Step 5: Data Model Extraction
         ↓  [carry_over_files]
Step 6: Feature & Business Logic Deep Dive  ← heaviest step
         ↓  [carry_over_files]
Step 7: Safety & Error Handling Analysis
         ↓  [carry_over_files]
Step 8: Security Analysis
         ↓  [carry_over_files]
Step 9: Test Suite Analysis
         ↓  [carry_over_files]
Step 10: Synthesis & Gap Assessment
         ↓
Output: ~/.dpai_sds_gen/cache/{key}/analysis.md
```

**carry_over_files mechanism**: After each step completes, the pipeline parses any `## FILES NEEDED` section in the LLM output to identify files the LLM flagged as important but didn't read yet. These files are pre-fetched and injected at the top of the next step's context, ensuring critical files (e.g., `parameters.py`, `constants/`) are never missed.

**Full context accumulation**: All completed step outputs are concatenated and passed as context to each subsequent step, so later steps benefit from earlier findings.

Step 1 is slightly different in scope-aware mode: it maps the scope directory in full detail (all levels), and also does a shallow scan of the repo root to identify shared libraries, common packages, and root-level configuration that the scope might depend on.

### 5.3 Code Reader

```python
class CodeReader:
    def __init__(self, clone_dir: Path, scope_path: str):
        self.clone_dir = clone_dir        # Full repo root
        self.scope_dir = clone_dir / scope_path  # Primary analysis target
        self.scope_path = scope_path

    def tree(self, depth=3) -> str:
        """Directory tree of the scope directory."""

    def tree_root(self, depth=2) -> str:
        """Shallow tree of the full repo root (for context orientation)."""

    def read_file(self, path: str) -> str:
        """Read a file. Path can be relative to scope OR repo root.
        Scope files: direct path (e.g., 'src/main.py')
        Context files: prefix with '~/' (e.g., '~/shared/auth/jwt.py')
        Files > 500 lines return a summary; use read_file_full for complete content."""

    def read_file_full(self, path: str) -> str:
        """Full file content regardless of size."""

    def search(self, pattern: str, file_glob: str = "*", scope_only: bool = True) -> list:
        """Search for pattern. scope_only=True limits to scope directory;
        scope_only=False searches entire repo."""

    def files_by_extension(self, ext: str) -> list[str]:
        """List files in scope matching extension."""

    def dependency_manifests(self) -> dict:
        """Parsed dependency files from scope directory.
        Also checks repo root for root-level manifests (e.g., monorepo root package.json)."""

    def config_files(self) -> dict[str, str]:
        """Config files from scope + repo root."""

    def test_files(self) -> list[str]:
        """Test file paths in scope."""

    def is_in_scope(self, path: str) -> bool:
        """Whether a file is inside the primary scope directory."""
```

**Path convention for Function Calling**:
- Paths without prefix are relative to scope: `read_file("src/main.py")` → `{clone}/apps/foo/src/main.py`
- Paths prefixed with `~/` are relative to repo root: `read_file("~/shared/auth/jwt.py")` → `{clone}/shared/auth/jwt.py`
- This convention is explained to Gemini in the tool descriptions so it can access both scope and context files.

### 5.4 Context Window Strategy

Same tiered approach as before, with scope awareness:

**Tier 1 — Always in context**:
- Phase 1 guidance prompt
- Structural map of scope directory
- Shallow map of repo root (for context orientation)
- Accumulated analysis so far

**Tier 2 — Step-specific**: Files within scope relevant to the current step.

**Tier 3 — On-demand**: Files outside scope (shared libraries, root configs) pulled via multi-turn when the LLM encounters cross-scope imports.

### 5.5 LLM Interaction Pattern

Same as before. Each step uses a structured prompt with an additional scope-awareness instruction:

```
[SYSTEM]
Phase 1 guidance document

[CONTEXT]
Analysis scope: apps/health-coach/ (this is the SDS target)
Full repo structure (shallow): {repo root tree}
Scope structure (detailed): {scope tree}
Analysis so far: {...}

[FILES]
{scope files relevant to this step}

[TASK]
"Analyze the software within the scope directory. If you encounter
 imports from outside the scope (e.g., shared libraries), use the
 read_file tool with ~/ prefix to examine those files. Record
 external dependencies as integrations in your analysis."
```

---

## 6. PHASE 2: SDS GENERATION

### 6.1 Pipeline

Phase 2 reads `analysis.md` and generates section JSONs. **Function Calling is disabled** — all needed information is already in `analysis.md`. This avoids wasted API calls and keeps Phase 2 fast and predictable.

```
Step 1:  Generate Section 1 (Purpose) + Section 2 (Scope)
          ↓
Step 2:  Generate Section 3 (References)
          ↓
Step 3:  Generate Section 4 (Definitions) — initial pass
          ↓
Step 4:  Generate Section 5 (Overview)
          ↓
Step 5:  Generate Section 6.1 (Software Components)
          ↓
Step 6:  Generate Section 6.2 (Software Integrations)
          ↓
Step 7:  Generate Section 6.3 (Key Features) — one JSON per feature, auto-detected count
          ↓
Step 8:  Generate Section 6.4 (AI/ML Principles) — if applicable
          ↓
Step 9:  Generate Section 6.5 (Security and Privacy)
          ↓
Step 10: Generate Section 7 (Attachments) + TBC Summary Table
          ↓
Step 11: Update Section 4 (Definitions) — final pass collecting new terms
          ↓
Step 12: Quality validation pass
          ↓
Step 13: Assemble .docx from all section JSONs
```

### 6.2 LLM Interaction Pattern — Phase 2

```
[SYSTEM]
Phase 2 guidance document (includes output format rules)

[CONTEXT]
Full Phase 1 analysis.md (no truncation)
Previously generated sections (for cross-references)

[TASK]
"Generate SDS Section 6.3.1. Output as JSON matching the schema.
 Trust the analysis document — do not attempt to read code files."
```

Key prompt rules enforced:
- **TRUST THE ANALYSIS**: LLM must use `analysis.md` as ground truth, not try to access code
- **rows format**: `table` and `decision_table` rows must always be `[[val1, val2], ...]` — never a list of dicts
- **items format**: `bullet_list` and `numbered_list` items must be plain strings — never nested JSON objects

Each section's output is structured JSON consumed by the docx engine. Content types supported:

| Type | Description | docx Rendering |
|---|---|---|
| `paragraph` | Body text | Body Text style (Times New Roman) |
| `heading` | Sub-heading within a section | Heading 3/4/5 style (Arial, bold) |
| `bullet_list` | Unordered list | Bulleted List style |
| `numbered_list` | Ordered list | Numbered List style |
| `table` | Standard table | Bordered table with header row shading |
| `decision_table` | Decision logic table | Bordered table, smaller font |
| `note` | Callout note | Bold "Note:" prefix |
| `figure_placeholder` | Diagram placeholder | Highlighted yellow text |

The `tbc` flag on any content item triggers yellow highlighting in docx.
**Critical format constraints** (enforced in prompts and normalized in renderer):
- `table`/`decision_table` rows: always `[[val1, val2], ...]` — the renderer normalizes common LLM variants (`{"cells": [...]}`, `{"conditions": [...], "action": "..."}`, `{"ColName": "val", ...}`) but plain lists are preferred.
- `bullet_list`/`numbered_list` items: plain strings only — never nested JSON objects.
Example section JSON:

```json
{
  "section_number": "6.3.1",
  "heading": "Weekly Insight Generation",
  "content": [
    {
      "type": "paragraph",
      "text": "The software uses generative AI to evaluate user data and provide weekly insights."
    },
    {
      "type": "decision_table",
      "headers": ["First Insight", "Has Options", "Feedback", "Behavior"],
      "rows": [
        ["Y", "N", "N/A", "Using random options"],
        ["N", "N", "Positive", "Using same options as most recent tip"]
      ]
    },
    {
      "type": "paragraph",
      "text": "[TBC — Confirm grader threshold with Data Science team.]",
      "tbc": true
    }
  ]
}
```

### 6.4 Definitions Two-Pass

Same as before: initial pass from Phase 1 terminology, final pass scanning all generated section content for undefined terms.

### 6.5 Quality Validation (Step 12)

Same as before: feed all section JSONs to Gemini with the Phase 2 quality checklist. FAIL items auto-corrected, WARN items printed to terminal.

---

## 7. DOCX ENGINE

### 7.1 Rendering Pipeline

```python
def assemble_docx(cache_dir: Path, output_path: Path, template_path: Path):
    doc = Document(template_path)

    add_doc_identification(doc, config.sw_number, config.sw_name)

    for section_file in sorted(cache_dir.glob("sections/sec_*.json")):
        section = json.loads(section_file.read_text())
        render_section(doc, section)

    insert_toc(doc)
    doc.save(output_path)
```

### 7.2 Content Type → docx Style Mapping

```python
def render_content(doc, item):
    match item["type"]:
        case "paragraph":
            p = doc.add_paragraph(style="Body Text")
            add_markdown_runs(p, item["text"])   # handles **bold** and `code`
            if item.get("tbc"):
                highlight_yellow(p.runs[-1])

        case "heading":
            level_map = {3: "Heading 3", 4: "Heading 4", 5: "Heading 5"}
            doc.add_paragraph(item["text"], style=level_map[item["level"]])

        case "bullet_list":
            for entry in item["items"]:
                # entry may be str, or dict {"text": "...", "items": [...]}
                text = entry if isinstance(entry, str) else entry.get("text", "")
                p = doc.add_paragraph(style="List Bullet")
                add_markdown_runs(p, text)

        case "numbered_list":
            for entry in item["items"]:
                text = entry if isinstance(entry, str) else entry.get("text", "")
                p = doc.add_paragraph(style="List Number")
                add_markdown_runs(p, text)

        case "table" | "decision_table":
            render_table(doc, item)   # normalizes dict rows automatically

        case "note":
            p = doc.add_paragraph(style="Body Text")
            p.add_run("Note: ").bold = True
            add_markdown_runs(p, item["text"])

        case "figure_placeholder":
            p = doc.add_paragraph(item["text"], style="Body Text")
            highlight_yellow(p.runs[0])
```

**Inline markdown rendering** (`add_markdown_runs`): splits text on `**bold**` and `` `code` `` patterns and renders them as bold or monospace runs respectively. Plain text between markers is rendered normally.

**Dict-row normalization** in `render_table`: LLM output varies; the renderer handles all known variants:

| LLM format | Normalized to |
|---|---|
| `["val1", "val2"]` | Used as-is |
| `{"cells": ["val1", "val2"], "tbc": true}` | `["val1", "val2"]` |
| `{"conditions": ["c1", "c2"], "action": "a"}` | `["c1", "c2", "a"]` |
| `{"ColName": "val", ...}` | Values ordered by header names |

### 7.3 Template Styles (matching CORPFT-010522)

| Style Name | Font | Size | Usage |
|---|---|---|---|
| Heading 1 | Arial, Bold | 16pt | Section headings (1, 2, 3...) |
| Heading 2 | Arial, Bold | 14pt | Subsections (6.1, 6.2...) |
| Heading 3 | Arial, Bold | 12pt | Sub-subsections (6.3.1...) |
| Heading 4 | Arial, Bold | 11pt | Feature sub-headings |
| Body Text | Times New Roman | 12pt | All prose |
| List Bullet | Times New Roman | 12pt | Bulleted lists |
| List Number | Times New Roman | 12pt | Numbered lists |
| Code | Courier New | 10pt | Technical identifiers (minimal) |

### 7.4 TBC Highlighting

Any content with `"tbc": true` or containing `[TBC` is rendered with yellow background highlighting, making TBC items visually obvious for QA review.

---

## 8. ERROR HANDLING AND RESILIENCE

### 8.1 Clone Failures

| Failure | Handling |
|---|---|
| Invalid URL | Parse error with example of correct format |
| Auth failure (401/403) | Prompt user to run `dpai_sds_gen auth` or pass `--token` |
| Repo not found (404) | Clear error with URL echo |
| Network timeout | Retry up to 3 times |
| Scope path doesn't exist | Error listing actual directories at that level |

### 8.2 API Failures

| Failure Type | Handling |
|---|---|
| Rate limit (429) | Exponential backoff, max 5 retries, then pause with user prompt |
| Timeout | Retry up to 3 times, then reduce context and retry |
| Model overloaded (503) | Wait 60s, retry up to 5 times |
| Invalid JSON response | Retry with stricter format instructions, max 3 times |
| Context too long | Split input, analyze in chunks, merge results |
| Function call loop | Hard cap at 15 per section |

### 8.3 Resume and Re-run Behavior

```bash
$ dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo
# First run: clone → analyze → generate → clean clone. Cache saved.

$ dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo
# Re-run: clone → check HEAD SHA → matches cache → skip Phase 1
# → found 7/12 section JSONs → resume Phase 2 from section 8
# → assemble docx → clean clone

$ dpai_sds_gen run https://github.com/org/repo/tree/main/apps/foo --reanalyze
# Force: clone → re-run Phase 1 → re-run Phase 2 → clean clone

$ dpai_sds_gen regenerate https://github.com/org/repo/tree/main/apps/foo --section 6.3
# Clone → re-generate only sec_06_03_*.json → re-assemble full docx → clean clone
```

### 8.4 Cleanup Guarantee

The clone is deleted in a `finally` block — even if the pipeline crashes. The `--keep-clone` flag overrides this for debugging:

```python
try:
    clone_dir = clone_repo(target, token)
    run_pipeline(clone_dir, target, config)
finally:
    if not args.keep_clone:
        shutil.rmtree(clone_dir, ignore_errors=True)
```

### 8.5 Cost Tracking

Same as before. Token counts logged to `~/.dpai_sds_gen/cache/{key}/cost.json`. Terminal display shows running cost. Configurable ceiling via `--max-cost`.

---

## 9. PROJECT STRUCTURE

```
dpai_sds_gen/
├── src/
│   ├── cli/
│   │   ├── main.py                # Entry point (typer), run command
│   │   └── commands/              # (reserved for future subcommands)
│   │
│   ├── core/
│   │   ├── url_parser.py          # GitHub URL → RepoTarget
│   │   ├── repo_manager.py        # Clone, cleanup, cache key generation
│   │   ├── code_reader.py         # Scope-aware file access
│   │   ├── config.py              # .env + .dpai_sds_gen.yaml loading
│   │   └── cost_tracker.py        # Token counting and cost estimation
│   │
│   ├── phase1/
│   │   ├── pipeline.py            # Phase 1 orchestrator (all 10 steps inline)
│   │   │                          # includes: carry_over_files mechanism,
│   │   │                          #           full accumulated context passing
│   │   └── prompts.py             # System prompt + step-by-step instructions
│   │
│   ├── phase2/
│   │   ├── pipeline.py            # Phase 2 orchestrator (all 12 sections)
│   │   │                          # FC disabled; full analysis.md passed to each section
│   │   ├── prompts.py             # System prompt + per-section instructions
│   │   └── schemas/               # (reserved)
│   │
│   ├── llm/
│   │   └── adapter.py             # Gemini API wrapper (FC loop + retry loop separated)
│   │
│   └── docx_engine/
│       ├── assembler.py           # Reads section JSONs → .docx
│       ├── renderer.py            # Content type → docx elements
│       │                          # includes: add_markdown_runs(), dict-row normalization
│       ├── styles.py              # Style constants (fonts, colors, sizes)
│       └── templates/             # .docx base templates
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docs/
│   ├── Tool_Design_Document.md    # This document
│   ├── Phase1_Code_Analysis_Guidance.md
│   ├── Phase1_Prompt_Templates.md
│   ├── Phase2_SDS_Generation_Guidance.md
│   └── Phase2_Prompt_Templates.md
│
├── pyproject.toml
├── README.md
└── .env.example
```

### Cache directory layout

```
~/.dpai_sds_gen/
├── clones/
│   └── {org}_{repo}_{hash}/       # Temporary (auto-deleted after run)
└── cache/
    └── {org}_{repo}_{scope_hash}/
        ├── commit_sha.txt          # Cache invalidation key
        ├── cost.json               # API call / token / cost log
        ├── analysis.md             # Phase 1 output (all 10 steps)
        └── sections/
            ├── purpose_scope.json  # Section 1+2
            ├── references.json     # Section 3
            ├── definitions.json    # Section 4 (initial)
            ├── overview.json       # Section 5
            ├── components.json     # Section 6.1
            ├── integrations.json   # Section 6.2
            ├── feature_6_3_1.json  # Section 6.3.x (count = auto-detected features)
            ├── feature_6_3_2.json
            ├── ...
            ├── ai_principles.json  # Section 6.4
            ├── security.json       # Section 6.5
            ├── attachments.json    # Section 7
            ├── definitions_final.json  # Section 4 (final pass)
            └── quality_check.json  # Quality validation results
```

## 10. KEY TECHNICAL DECISIONS

### 10.1 Language: Python

Rationale: Google's Gemini SDK (`google-genai`) is Python-first. `python-docx` is the most mature Word library. `typer` + `rich` give polished CLI output. `GitPython` or subprocess `git` for cloning.

### 10.2 GitHub URL as Input (not local path)

Rationale: The URL naturally encodes three pieces of information — repo identity, branch, and scope path — in a single string. It also makes the tool work identically in local development and CI/CD environments. The developer doesn't need to pre-clone; the tool handles everything.

### 10.3 Full Clone with Scope-Aware Analysis

Rationale: A subdirectory in a monorepo is not self-contained. It imports shared code, reads root configs, and depends on monorepo-level build tooling. Cloning only the subdirectory (sparse checkout) would blind the AI to critical dependencies. Instead, we clone the full repo but direct the AI's primary attention to the scope path. The AI is allowed — encouraged — to follow imports outward, but does not pre-analyze the entire repo.

### 10.4 Shallow Clone (`--depth=1`)

Rationale: We need current code, not history. Shallow cloning is faster and uses less disk. Git history is nice-to-have context (commit messages), but not worth the clone time for large repos. If needed later, `git fetch --unshallow` can be added as an option.

### 10.5 Cache in Home Directory (not in repo)

Rationale: The clone is temporary and gets deleted. Cache must survive across runs, so it lives in `~/.dpai_sds_gen/cache/`. Cache is keyed by repo+branch+scope+commit SHA, so different scopes and branches don't collide.

### 10.6 Code Verification via Gemini Function Calling

Same rationale as before: Phase 2 uses Gemini's native Function Calling to let the LLM reach into the codebase during generation. Pre-loading + on-demand verification for critical sections.

---

## 11. DEVELOPMENT ROADMAP

### v0.1 — Walking Skeleton (2 weeks)

**Goal**: One command, one URL, one .docx.

- URL parser (org, repo, branch, scope_path)
- `git clone --depth=1` with token auth
- Code Reader (basic: tree, read_file, search — scope-aware)
- Gemini adapter (single-shot, basic retry)
- Phase 1: Steps 1-3 (structure, build configs, dependencies)
- Phase 2: Sections 1-5 (Purpose, Scope, References, Definitions, Overview)
- docx engine (headings, paragraphs, tables, bullet lists)
- Auto-cleanup of clone
- Test against one real internal repo URL

**Deliverable**: `dpai_sds_gen run https://github.com/org/repo` produces a .docx with correct formatting for the first 5 sections.

### v0.2 — Core Design Sections (2 weeks)

**Goal**: The Design section works for a single-service or monorepo subdirectory.

- Phase 1: Steps 4-6 (API surface, data models, feature deep dive)
- Phase 2: Sections 6.1-6.3 (Components, Integrations, Features)
- Multi-turn for Phase 1
- Function Calling for Phase 2 code verification
- Section JSON caching and resume
- Cost tracking
- `dpai_sds_gen analyze` and `dpai_sds_gen generate` as separate commands
- Cache with commit SHA invalidation

**Deliverable**: A complete SDS for a repo subdirectory, with working Design section including decision tables.

### v0.3 — Full Pipeline (2 weeks)

**Goal**: All sections, quality validation, TBC handling.

- Phase 1: Steps 7-10 (safety, security, testing, synthesis)
- Phase 2: Sections 6.4-7 (AI Principles, Security, Attachments)
- Definitions two-pass
- Quality validation pass
- TBC yellow highlighting
- `dpai_sds_gen validate` command
- `.dpai_sds_gen.yaml` auto-detection in repo

**Deliverable**: Complete SDS with all sections, TBC items highlighted, quality report.

### v0.4 — Production Hardening (2 weeks)

**Goal**: Ready for team-wide use.

- `dpai_sds_gen auth` credential management
- `dpai_sds_gen regenerate --section` targeted re-generation
- Context window optimization
- Error recovery hardening
- Rich terminal UI (progress bars, cost display)
- Testing against 3+ repos of varying size and complexity
- Prompt tuning based on QA feedback
- Documentation

**Deliverable**: v1.0 release candidate.
