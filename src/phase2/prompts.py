"""Phase 2 prompt templates — core principles and per-section instructions."""


def core_principles(scope_path: str, sw_number: str, sw_name: str) -> str:
    return f"""You are generating an IEC 62304-compliant Software Design Specification (SDS) for medical device software. You are writing one section at a time. Your input is a structured code analysis from Phase 1.

ABSOLUTE RULES:

1. ZERO FABRICATION.
   If the Phase 1 analysis does not contain the information, and you cannot verify by reading code via tools, mark as [TBC — To Be Confirmed] with a note. A wrong SDS is worse than an incomplete one.

2. SDS IS DESIGN, NOT CODE.
   Write about what the software does and why, not code structure. Never mention function names, variable names, or class names.
   Bad: "The generate_insight() function calls fetch_user_data()..."
   Good: "The software retrieves the user's weekly data from the analytics data warehouse."

3. THREE AUDIENCES.
   Regulatory reviewers (safety, compliance), quality engineers (testable specs), clinical experts (user impact, safety). Every paragraph should serve at least one.

4. "THE SOFTWARE" IS YOUR SUBJECT.
   Not "we," "the system," "it," or module names. Introduce component names in the Components section, then use consistently.

5. PRECISION OVER BREVITY.
   Configurable values with defaults: "...configurable period (default: 56 hours)."
   Thresholds: "...pass rate of ≥ 90%."
   Never "various," "several," "many," "etc." — be specific.

6. VERIFY BEFORE WRITING.
   You have code access via read_file, search_code tools. When writing decision tables, configurable values, error handling — verify against code. Don't trust Phase 1 blindly.

7. TBC FORMAT.
   Gaps: [TBC — description]. Set "tbc": true on the JSON content item.

8. OUTPUT FORMAT.
   JSON with content array. Types: paragraph, heading (level 3-5), bullet_list, numbered_list, table, decision_table, note, figure_placeholder. Each has "type" + "text" (or "items"/"headers"/"rows"). Optional "tbc": true.

SCOPE: {scope_path or '(full repository)'}
SOFTWARE: {sw_number} {sw_name}"""


# ─── Section-specific prompts ────────────────────────────────────────────────

SECTION_INSTRUCTIONS = {}
SECTION_TASKS = {}


# ── Sections 1+2: Purpose + Scope ───────────────────────────────────────────

SECTION_INSTRUCTIONS["purpose_scope"] = """Generate SDS Section 1 (Purpose) and Section 2 (Scope).

Section 1: "The purpose of this document is to present the software design specifications for [SW Number] [Software Name]."
Section 2: "This document applies to [SW Number] [Software Name] and provides a description of the software features and functions."
If part of a larger system, mention it."""

SECTION_TASKS["purpose_scope"] = """Output TWO JSON objects as a JSON array:
[
  {{"section_number": "1", "heading": "Purpose", "content": [...]}},
  {{"section_number": "2", "heading": "Scope", "content": [...]}}
]"""


# ── Section 3: References ───────────────────────────────────────────────────

SECTION_INSTRUCTIONS["references"] = """Generate SDS Section 3 (References).

Always include:
- IEC 62304 + AMD1: Medical Device Software - Software life cycle processes
- CORPSOP-040800: Software Development Life Cycle Procedure
- CORPSOP-040500: Risk Management Procedure

Add project-specific references: RA, SRS, SAD, SDP, related SW SDS docs, IDD, AI policy docs.
Use [TBC] for unknown document numbers but include the description."""

SECTION_TASKS["references"] = """Output:
{{"section_number": "3", "heading": "References", "content": [{{"type": "table", "headers": ["Document No.", "Description"], "rows": [...]}}]}}"""


# ── Section 4: Definitions ──────────────────────────────────────────────────

SECTION_INSTRUCTIONS["definitions"] = """Generate SDS Section 4 (Definitions) — INITIAL PASS.

Rules:
- Include every domain term, abbreviation, product-specific concept.
- Write definitions a non-engineer can understand.
- Contextual, not generic: "LLM: ...trained on large datasets... [Software Name] uses [model] to [purpose]."
- Alphabetical order.
- Over-define rather than under-define."""

SECTION_TASKS["definitions"] = """Output:
{{"section_number": "4", "heading": "Definitions", "content": [{{"type": "table", "headers": ["Term", "Definition"], "rows": [...]}}]}}"""


# ── Section 5: Overview ─────────────────────────────────────────────────────

SECTION_INSTRUCTIONS["overview"] = """Generate SDS Section 5 (Overview).

Structure:
1. Opening: "[Software Name] ([SW Number]) is a software [type] that [core purpose]."
2. Capabilities as bullet points: what each delivers and to whom.
3. Cross-refs to other systems' SDS docs (Notes).
4. Closing: "This document describes the design of [Software Name], including..."

No algorithms, no config details, no decision logic. "What does it do and for whom" only."""

SECTION_TASKS["overview"] = """Output:
{{"section_number": "5", "heading": "Overview", "content": [...]}}
Keep to 2-4 paragraphs plus optional bullet list."""


# ── Section 6.1: Software Components ────────────────────────────────────────

SECTION_INSTRUCTIONS["components"] = """Generate SDS Section 6.1 (Software Components).

Bolded component names in bullet list with sub-bullets for responsibilities. Group by role. Name from code but explain meaning. Differentiate which features each serves. Include DBs, queues, caches as components."""

SECTION_TASKS["components"] = """Output:
{{"section_number": "6.1", "heading": "Software Components", "content": [...]}}"""


# ── Section 6.2: Software Integrations ──────────────────────────────────────

SECTION_INSTRUCTIONS["integrations"] = """Generate SDS Section 6.2 (Software Integrations).

Group by feature area. For each: system name (+ SW number), purpose, protocol, direction. For AI/ML models: exact name, version, specific use. Verify model versions via code tools."""

SECTION_TASKS["integrations"] = """Use read_file/search_code to verify model names and versions.

Output:
{{"section_number": "6.2", "heading": "Software Integrations", "content": [...]}}"""


# ── Section 6.3.x: Key Features (per feature) ──────────────────────────────

SECTION_INSTRUCTIONS["feature"] = """Generate SDS Section {section_number} for feature: {feature_name}.

MOST DETAILED section. Structure:
a) Overview — end-to-end narrative ("First... Next... At the end...")
b) Input data — required vs optional, null handling
c) Decision tables — every branch, complete scenarios, exact probabilities
d) Constraints — what must/must not be output, term mappings
e) Quality evaluation — each grader: name, type, pass/fail definition, execution method
f) Post-market monitoring — metrics, thresholds, corrective actions

USE TOOLS to verify every decision table row, every configurable default, every grader criterion."""

SECTION_TASKS["feature"] = """Output:
{{"section_number": "{section_number}", "heading": "{feature_name}", "content": [...]}}

Include decision_table content types for branching logic. Mark unverifiable details as TBC."""


# ── Section 6.4: AI/ML Design Principles ───────────────────────────────────

SECTION_INSTRUCTIONS["ai_principles"] = """Generate SDS Section 6.4 (Design Principles for Ethical and Responsible AI Use).

SKIP if no AI/ML. Cover:
a) Dataset practices (selection, representativeness, de-identification)
b) Data privacy (what sent to model, pseudonymization, retention, model training)
c) Prompt transparency (SME involvement, auditability)
d) Storage and auditability
e) Post-market monitoring (drift detection, corrective actions)
f) Versioning (exact model versions locked, how maintained)

Mark dataset composition and SME details as [TBC] if not in code."""

SECTION_TASKS["ai_principles"] = """Output:
{{"section_number": "6.4", "heading": "Design Principles for Ethical and Responsible AI Use", "content": [...]}}"""


# ── Section 6.5: Security and Privacy ───────────────────────────────────────

SECTION_INSTRUCTIONS["security"] = """Generate SDS Section 6.5 (Security and Privacy).

Intro paragraph about security philosophy, then bulleted mechanisms:
logging/monitoring, TLS (version, ciphers), mTLS, DB access control, auth (JWT), secrets management.
Be specific about TLS versions. No key file paths or secret names."""

SECTION_TASKS["security"] = """Output:
{{"section_number": "6.5", "heading": "Security and Privacy", "content": [...]}}"""


# ── Section 7: Attachments ──────────────────────────────────────────────────

SECTION_INSTRUCTIONS["attachments"] = """Generate SDS Section 7 (Attachments) and TBC Summary Table.

List:
- Attachment 1: SRS-SDS Trace Worksheet (skeleton)
- Additional attachments (AI model version lock evidence, clinical evidence, etc.)

Then generate TBC Summary Table collecting ALL [TBC] items from all previous sections."""

SECTION_TASKS["attachments"] = """Scan all previously generated sections for [TBC] items.

Output:
{{"section_number": "7", "heading": "Attachments", "content": [
  ...attachment list...,
  {{"type": "heading", "level": 3, "text": "TBC Summary"}},
  {{"type": "table", "headers": ["SDS Section", "TBC Item", "Information Needed", "Suggested Source"], "rows": [...]}}
]}}"""


# ── Definitions Final Pass ──────────────────────────────────────────────────

SECTION_INSTRUCTIONS["definitions_final"] = """Update Definitions table — FINAL PASS.

Scan ALL generated sections. Find every term/abbreviation/concept used but NOT defined. Add them. Do not remove existing definitions. Sort alphabetically."""

SECTION_TASKS["definitions_final"] = """Output the COMPLETE updated definitions:
{{"section_number": "4", "heading": "Definitions", "content": [{{"type": "table", "headers": ["Term", "Definition"], "rows": [...]}}]}}"""


# ── Quality Validation ──────────────────────────────────────────────────────

SECTION_INSTRUCTIONS["quality_check"] = """Review complete SDS against five checks:
1. COMPLETENESS: All sections present? All features documented? All integrations? All params?
2. ACCURACY: All claims traceable? No fabrication? Decision tables match code?
3. READABILITY: Non-dev can understand Overview? QA can write tests from Features?
4. IEC 62304: Traceability demonstrated? Safety identifiable? OTS versioned?
5. CONSISTENCY: Names consistent? Cross-refs correct? Terms match Definitions?"""

SECTION_TASKS["quality_check"] = """Output:
{{"validation_results": [{{"check": "...", "section": "...", "severity": "FAIL|WARN", "description": "...", "fix": "corrected content (FAIL only)"}}]}}

Be thorough but practical. Focus on regulatory/QA concerns."""
