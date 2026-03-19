# Phase 2: SDS Report Generation Guidance

## For AI-Driven SDS (Software Design Specification) Generation Tool

**Document Purpose**: This document instructs the AI on how to transform the Phase 1 code analysis output into a high-quality, IEC 62304-compliant Software Design Specification (SDS). The SDS must be technically accurate, readable by non-developers (regulatory reviewers, quality engineers, clinicians), and reflect genuine design intent — not just code mechanics.

**Applicable Standard**: IEC 62304 + AMD1 — Medical Device Software Life Cycle Processes

**Input**: Phase 1 structured analysis output (see Phase 1 guidance document for format)

---

## 1. GENERATION PHILOSOPHY

### 1.1 The SDS Is Not a Code Walkthrough

An SDS explains **design** — the *what*, *why*, and *how* of the software — not the implementation details. A developer reads code; a regulatory reviewer reads the SDS. The SDS must convey the same understanding of the software that code would give a developer, but in prose that a non-developer can follow.

Bad (code walkthrough):
> "The `generate_insight()` function calls `fetch_user_data()`, which queries BigQuery using the `user_id` parameter, then passes the result to `compose_prompts()` which iterates over the `PROMPT_TEMPLATES` list..."

Good (design specification):
> "The software retrieves the user's weekly data from the analytics data warehouse and composes a series of prompts using a fixed prompt template. User data is injected into the prompts, and the prompts are sent sequentially to the LLM. The response from each prompt is used as input to the next prompt in the sequence. At the end of the prompt sequence, the LLM generates a personalized insight."

The difference: the good version describes the **design behavior** — what the system does and why, at the level of architectural decisions — without naming functions, variables, or internal implementation patterns.

### 1.2 Write for the Audience, Not for Yourself

The SDS will be read by three distinct audiences:

- **Regulatory reviewers** need to see that the software design is controlled, traceable, safe, and conforms to IEC 62304. They care about: what the software does, how it handles risk, how outputs are verified, and how versions are controlled.
- **Quality engineers** need to see testable design specifications. They will write verification and validation (V&V) test cases based on what the SDS describes. If the SDS is vague, V&V will be impossible.
- **Clinical/domain experts** need to understand what the software delivers to users and what safety mechanisms protect against harm. They do not need to understand HTTP response codes, but they need to understand what happens when the software cannot generate a safe output.

Write every paragraph with all three audiences in mind. When you describe a technical mechanism, immediately explain its purpose in terms of safety, quality, or user impact.

### 1.3 The Zero Fabrication Rule

**If Phase 1 analysis does not contain the information, do not invent it.** This is the most critical rule of Phase 2.

When information is insufficient or uncertain:

- Mark the section with `[TBC — To Be Confirmed]` and describe what information is needed.
- If you suspect something might be true based on partial evidence from Phase 1, state it as: "Based on the code analysis, the software appears to [behavior]. This should be confirmed with the development team."
- **Never** fill gaps with plausible-sounding but unverified content. A wrong SDS is worse than an incomplete one — it can lead to incorrect risk assessments, inadequate testing, and regulatory findings.

### 1.4 When in Doubt, Trust the Analysis

Phase 2 does not have access to the codebase. All information must come from `analysis.md` — the output of Phase 1. Phase 1 was specifically designed to extract everything Phase 2 needs: configurable values, decision logic, error handling, integration details, and AI model versions.

If a detail is missing from `analysis.md`:
- Mark it as `[TBC — information not captured in Phase 1 analysis]`
- Do not invent it
- Do not attempt to read code files

If you find that Phase 1 consistently misses certain types of detail, the fix is to improve Phase 1 prompts and the `carry_over_files` mechanism — not to add code access to Phase 2.

---

## 2. DOCUMENT STRUCTURE AND MANDATORY SECTIONS

The SDS must contain the following numbered sections. If a section is not applicable, place "N/A" under the heading — never omit a section.

```
DOCUMENT IDENTIFICATION:
[SW Number] [Software Name]
Software Design Specification

TABLE OF CONTENTS

1  Purpose
2  Scope
3  References
4  Definitions
5  Overview
6  Design
   6.x  (subsections as needed — see Section 3 of this guidance)
7  Attachments
```

---

## 3. SECTION-BY-SECTION GENERATION INSTRUCTIONS

### 3.1 Section 1 — Purpose

**Template**: One sentence. Formulaic. Do not over-elaborate.

**Pattern**:
> "The purpose of this document is to present the software design specifications for [SW Number] [Software Name]."

**Source**: Phase 1 META section (software identifier and name).

**Rules**:
- If Phase 1 did not identify a formal SW number, use `[TBC]` as a placeholder.
- Do not add background, context, or motivation here. That belongs in Overview (Section 5).

---

### 3.2 Section 2 — Scope

**Template**: One to two sentences. States what the document covers and what it provides.

**Pattern**:
> "This document applies to [SW Number] [Software Name] and provides a description of the software features and functions."

If the software has an external interface document (IDD), add:
> "The external interface to [Software Name] is [IDD document number]."

**Source**: Phase 1 META and API Surface sections.

**Rules**:
- Keep this concise. The detailed scope (what features, what integrations) belongs in Overview and Design.
- If the software is part of a larger system, mention the system name briefly (e.g., "...implemented as part of the [System Name]").

---

### 3.3 Section 3 — References

**Template**: A two-column table (Document No. | Description).

**Always include these standard references**:

| Document No. | Description |
|---|---|
| IEC 62304 + AMD1 | Medical Device Software - Software life cycle processes |
| CORPSOP-040800 | Software Development Life Cycle Procedure |
| CORPSOP-040500 | Risk Management Procedure |

**Then add project-specific references** derived from Phase 1 analysis:

- **Risk documents**: RA-##### (Software Risk and Hazard Analysis) — use `[TBC]` if not known.
- **SRS document**: SRS-##### — use `[TBC]` if not known.
- **Architecture document**: SAD-##### — use `[TBC]` if not known.
- **Development plan**: SDP-##### — use `[TBC]` if not known.
- **Related software SDS documents**: For each external software system the software integrates with (identified in Phase 1 Integration Inventory), include a reference line with its SW number and name.
- **AI/ML policy documents**: If the software uses AI/ML, include the company's Responsible AI Policy if referenced or implied in the code.
- **Interface documents**: IDD-##### for each external interface.

**Source**: Phase 1 Integration Inventory, META section, and any document references found in code comments or configuration.

**Rules**:
- List every SW number for every integrated software system. Phase 1's Integration Inventory is your primary source.
- It is acceptable to have `[TBC]` entries — this signals to the document reviewers what needs to be filled in.
- Do not fabricate document numbers. If you don't know the number, write the description and mark the number as `[TBC]`.

---

### 3.4 Section 4 — Definitions

**Template**: A two-column table (Term | Definition).

This section must be **comprehensive and written for non-technical readers**. The definitions table is often the first place a regulatory reviewer looks to understand the domain.

**Rules for good definitions**:

- **Include every domain-specific term** found in the Phase 1 Terminology section. This includes: technical abbreviations (API, LLM, SDK, etc.), product-specific concepts (any feature names, data entity names, processing stage names), clinical/medical terms, and AI/ML terminology if applicable.
- **Write definitions that a non-engineer can understand.** Do not define an abbreviation with another abbreviation. Do not assume the reader knows what an LLM is, what a grader does, or what "faithfulness" means in an AI context.
- **Definitions should be contextual, not generic.** Don't write "LLM: Large Language Model." Instead, write: "Large Language Model (LLM): A type of machine learning model trained on large datasets to comprehend and generate human-readable text. [Software Name] uses [specific model name and version] as its foundation model to generate [specific output type]."
- **Define product-specific concepts from the user's perspective.** If the software has a concept like "weekly insight" or "grader," define what it means to the user and to the system.
- **Order alphabetically** for ease of lookup.
- **Err on the side of over-defining.** If in doubt about whether a term needs a definition, include it. A reviewer unfamiliar with the domain will thank you.

**Source**: Phase 1 Terminology section, supplemented by any terms you encounter during SDS writing that were not captured in Phase 1.

---

### 3.5 Section 5 — Overview

**Template**: 2-4 paragraphs of prose, optionally followed by a high-level block diagram.

**Structure**:

1. **Opening sentence**: Identify the software and its core purpose in one sentence. Use the pattern: "[Software Name] ([SW Number]) is a software [platform/service/system/component] that [core purpose]."

2. **Capability summary**: Describe the major capabilities or features the software provides. Use a bulleted list if there are 2+ distinct capabilities. For each capability, explain:
   - What it delivers to the end user or consuming system.
   - How the delivery mechanism works at a high level (e.g., "The mobile app client requests X, and the software delivers X if available").

3. **Cross-references** (if applicable): If a capability involves significant interaction with another system that has its own SDS, include a **Note** directing the reader to that document.

4. **Closing sentence**: State what this document covers: "This document describes the design of [Software Name], including its software components and features, as well as its interaction with third-party services and with other [company] software and services."

**Source**: Phase 1 FEATURE ANALYSIS (purpose fields), Integration Inventory, and Structural Map.

**Rules**:
- The Overview must be understandable without reading the Design section. It is the "executive summary" of the software.
- Do not include design details, algorithms, or configuration parameters here. Keep it at the "what does this software do and for whom" level.
- If Phase 1 identified architecture diagrams or data flow diagrams, include a high-level one here (or reference a Figure that will appear at the start of the Design section).

---

### 3.6 Section 6 — Design

This is the core of the SDS and will be by far the longest section. It must be organized into clear subsections that progressively increase in detail.

#### 3.6.1 Opening: Design Diagrams

**Start the Design section with architecture or data flow diagrams** — before any text. If Phase 1 identified the component relationships and data flows clearly enough, generate diagram descriptions (or placeholder references for diagrams to be created). Each diagram must have:
- A Figure number and descriptive title (e.g., "Figure 1: [Software Name] Design Diagram: [Feature Name]")
- One diagram per major feature or data flow path

If diagrams cannot be generated, write: "[Figure X: Placeholder — [Description of what the diagram should show]]" and proceed with the text.

#### 3.6.2 Subsection: Software Components

**Purpose**: Describe each deployable component/module of the software and its responsibility.

**Source**: Phase 1 STRUCTURAL MAP and FEATURE ANALYSIS.

**Writing pattern**: Use a bulleted list where each top-level bullet is a bolded component name followed by a colon and description. Use sub-bullets for detailed responsibilities. Group components by their role in the system.

**Example pattern** (generalized):
> - **[Component Name]**: Coordinates [feature] dataflow jobs that:
>   - Prepare the prompts and data sent to the LLM.
>   - Grade outputs using evaluation mechanisms.
>   - Store results and grading outcomes.
> - **[API Component Name]** is used to respond to requests from clients. It includes the following endpoints:
>   - An endpoint that [client type] calls to request [output type].
>   - An endpoint for [internal service] to use to request [output type].
>   - An endpoint that the software uses to perform a health check.

**Rules**:
- Name components as they are named in the code (service names, module names), but explain what each name means.
- Differentiate between components that participate in different features.
- Describe the Operational Database, message queues, and caches as components if they play a distinct role.

#### 3.6.3 Subsection: Software Integrations

**Purpose**: Describe every external system the software interacts with and the nature of each interaction.

**Source**: Phase 1 INTEGRATION INVENTORY.

**Writing pattern**: Group integrations by feature area. For each feature, list the integrations as a bulleted list. For each integration, state:
- What system it integrates with (name and SW number if internal)
- What the integration does (purpose)
- What protocol is used
- What direction (inbound, outbound, bidirectional)

For AI/ML model integrations, be highly specific: state the exact model name, version, and what the model is used for. Each distinct use of a model (e.g., generation vs. evaluation) should be listed separately.

**Rules**:
- Integrations for different features should be listed in separate groups, clearly labeled.
- This section must be exhaustive — every external touchpoint identified in Phase 1 must appear here.
- For each integration, a reader should understand: who calls whom, with what data, and for what purpose.

#### 3.6.4 Subsection: Key Features and Functions

**This is the most critical and detailed subsection of the entire SDS.** Phase 2 must invest the majority of its effort here.

For **each major feature**, create a sub-subsection (e.g., 6.3.1, 6.3.2, etc.) and develop the following structure:

**a) Feature Generation/Processing Overview**

Describe the end-to-end pipeline for the feature:
- What triggers the processing (scheduled job, API request, event)?
- What data is retrieved and from where?
- What processing steps occur in sequence?
- What is the output and how is it delivered to the user/consumer?
- What happens when the output fails quality checks (retry logic, fallback behavior)?
- How are results stored and for what purpose (audit, retrieval, analysis)?

Write this as a narrative with clear temporal ordering: "First, the software... Next, the software... At the end of the process, the software..."

**b) Feature-Specific Details**

Enumerate the data inputs the feature uses, distinguishing between:
- Required data (the feature cannot function without it)
- Optional data (the feature operates with degraded richness if this is missing)

For each data input, explain:
- Where it comes from
- What happens when it is null or missing
- How it affects the output

**c) Detailed Logic and Decision Tables**

This is where the SDS must reach maximum specificity. Whenever the code contains conditional branching that governs behavior the user or a reviewer would care about, document it in a **decision table**.

**Decision table format**:

| Condition A | Condition B | Condition C | Resulting Behavior |
|---|---|---|---|
| Y | N | N/A | Description of what the software does |
| N | Y | Positive | Description of what the software does |
| N | Y | Negative | Description of what the software does |

**Rules for decision tables**:
- Every row must describe a complete scenario — no ambiguity about what the software does.
- Include default values and fallback behaviors.
- If the logic involves randomization or probabilistic selection, state the probabilities explicitly (e.g., "with a probability of 0.5").
- If the decision table comes from Phase 1 analysis, use it directly. If the Phase 1 analysis is ambiguous or incomplete, mark the row as `[TBC — Logic to be confirmed with development team]`.

**d) Specific Constraints and Safety Considerations**

Document any constraints the software enforces on its own output:
- Content that must not be generated (e.g., the software must not generate outputs that imply cause-and-effect relationships between certain factors)
- Term replacements or mappings (e.g., the software maps a sensitive input term to a safer alternative before processing)
- Hard-coded boundaries or thresholds

For each constraint, explain:
- What the constraint is
- Why it exists (clinical safety, regulatory requirement, user safety)
- How it is implemented (prompt engineering, deterministic filter, validation rule)

**e) Quality Evaluation Mechanisms (if applicable)**

If the software evaluates the quality/safety of its own output before delivery (e.g., grading systems, validation pipelines, content filters), this must be documented in extreme detail:

For each evaluation mechanism (grader, validator, filter):
- **Name and type**: Is it LLM-based, deterministic, AI-model-based, or hybrid?
- **What it evaluates**: What specific quality or safety attribute does it check?
- **Pass/fail criteria**: Write explicitly using the pattern: "A passing score means [condition]. A failing score means [condition]."
- **Execution method**: How many times is it run? If multiple times, what aggregation method is used (e.g., majority vote / jury method)?
- **Where results are stored**: For audit and post-market surveillance.
- **Online filtering vs. monitoring**: Can the mechanism be set to active (blocks failing content) or monitoring-only (logs scores without blocking)? What percentage of outputs does it monitor?

After describing all individual mechanisms, describe the **aggregate pass/fail logic**: How does the software combine the scores of all mechanisms to make a final pass/fail decision? What happens to failing outputs (retry, discard, escalate)?

State the **performance targets** (e.g., "The software is designed to achieve a pass rate of greater than or equal to X% against each evaluation mechanism").

**f) Post-Market Monitoring Design (if applicable)**

If the software includes monitoring for production performance (dashboards, alerts, drift detection), describe:
- What metrics are monitored
- What thresholds trigger alerts
- What corrective actions are available (e.g., reduce rollout percentage to 0%)

#### 3.6.5 Subsection: Design Principles for Ethical and Responsible AI Use (if applicable)

Include this subsection if the software uses AI/ML. Structure it as follows:

**a) Dataset Practices**
- How were the datasets used for development selected?
- Are they representative of the intended user population?
- Were they de-identified? How?
- Are they used in production, or only for development/validation?

**b) Data Privacy in Production**
- What data is sent to the AI model during production use?
- Is the data pseudonymized or de-identified before being sent?
- Does the AI model store or retain user data?
- Does the AI model use the data for its own training?
- Who hosts the data and the AI model? What access controls are in place?

**c) Prompt Transparency**
- Were prompts developed with subject matter expert input?
- Are prompts designed to be understandable and auditable?
- Does the AI model explain its reasoning (rationale) alongside its output?

**d) Storage and Auditability**
- Are generated outputs and their evaluation scores stored for review?
- Where are they stored and who can access them?

**e) Post-Market Monitoring for AI-Specific Risks**
- How is model drift detected?
- What corrective actions are available?
- How often is performance reviewed?

**f) Versioning**
- What specific AI model versions are locked for this release?
- How is version control maintained (contractual agreement, API parameter, configuration)?

List each AI model used with its exact version string and its specific use case. State that the software is developed, tested, and versioned using established QMS processes.

**Source**: Phase 1 FEATURE ANALYSIS (AI/ML-specific logic sections), Safety Profile, Security Profile.

**Rules**:
- If any of this information is not available from Phase 1 or code, mark it `[TBC]` with a note explaining what the development team needs to provide.
- Reference the company's Responsible AI Policy document if identified in Phase 1.

#### 3.6.6 Subsection: Security and Privacy

**Purpose**: Document the security design of the software.

**Source**: Phase 1 SECURITY PROFILE.

**Structure**: Use a brief introductory paragraph about the security design philosophy, then a bulleted list of specific mechanisms.

**Cover the following topics**:
- Logging and monitoring for security events
- Transport encryption (TLS version, cipher suite standards)
- Mutual TLS for service-to-service communication (if applicable)
- Database access control
- Authentication requirements (JWT, token validation, trusted STS)
- Secrets management approach

**Writing pattern for the introductory paragraph**:
> "[Software Name] prevents breaches where possible and maintains an audit log of actions. Since complete prevention is not possible when considering all possible attack vectors, [Software Name] attempts to reduce the likelihood or increase the difficulty of an attack to an acceptable level, considering the value of the attack target when combined with the complexity, time, and skills necessary to execute the attack."

Followed by: "The following techniques are employed in the security design of the software:" and then the bulleted list.

**Rules**:
- Be specific about TLS versions and cipher suite standards. If the code specifies "TLS 1.2 or above," say that.
- Do not include implementation details (key file paths, secret names) — describe the mechanisms at the design level.
- If Phase 1 Security Profile has gaps, mark them `[TBC]`.

---

### 3.7 Section 7 — Attachments

**Mandatory attachment**: SRS-SDS Trace Worksheet.

Since no SRS document exists as input, generate a **skeleton trace worksheet** based on the implicit requirements identified from code behavior in Phase 1. Structure:

| SRS ID | Requirement Text | Safety Critical | Risk ID | SDS Section | Comments |
|---|---|---|---|---|---|
| [TBC] | [Behavior identified from code] | [TBC] | [TBC] | 6.x.x | Auto-generated from code analysis |

**Additional attachments** (include if applicable, based on Phase 1 findings):
- AI model version lock evidence (if AI/ML is used)
- Clinical/medical evidence referenced in code or prompts
- Any supplementary technical evidence identified during analysis

For each attachment, provide a one-line description of what it contains.

---

## 4. WRITING STYLE RULES

### 4.1 Voice and Subject

- Use **"the software"** as the primary subject, not "we," "the system," "it," or the codebase module name.
  - Good: "The software retrieves user data from the analytics data warehouse."
  - Bad: "We fetch user data using the BigQuery client."
  - Bad: "The DataPipeline module queries BigQuery."
- Use **passive voice sparingly** — prefer active voice with "the software" as the subject.
- When referring to a specific component by name, introduce it in the Software Components subsection first, then use that name consistently.

### 4.2 Precision Over Brevity

- State configurable values with their defaults: "...within a configurable period of time (default: 56 hours)."
- State thresholds: "...a pass rate of greater than or equal to 90%."
- State counts and ranges: "...the title must be between 5 and 100 characters."
- Never use "various," "several," "many," or "etc." when you can be specific. If Phase 1 identified the exact items, list them all.

### 4.3 Cross-Referencing

- Reference other SDS sections using the pattern: "See section 6.x.x, '[Section Title]', for more information about [topic]."
- Reference external documents using: "For more information, see [Document Number] [Document Title]."
- When describing a capability that depends on another system, include a **Note** pointing to that system's SDS.

### 4.4 Formatting Conventions

- **Headings**: Use Arial font. Section hierarchy: Heading 1 (numbered), Heading 2 (numbered), Heading 3 (numbered).
- **Body text**: Use Times New Roman font.
- **Code or technical identifiers**: Use Courier New font for API endpoint paths, configuration keys, and code references (use sparingly — the SDS should minimize raw code references).
- **Tables**: Use tables for: references, definitions, decision logic, response codes, grader descriptions, and any structured data. Include clear column headers.
- **Figures**: Number sequentially (Figure 1, Figure 2, ...). Include a descriptive caption. Place figures before the text that discusses them.
- **Bold**: Use for component names on first mention in a bulleted list, and for emphasis of critical terms.
- **Notes**: Format as: "**Note**: [text]" — indent if within a bulleted list.

### 4.5 Depth Calibration

Different parts of the SDS require different levels of detail:

| Section | Depth Level | Guideline |
|---|---|---|
| Purpose | Minimal | 1 sentence |
| Scope | Minimal | 1-2 sentences |
| References | Exhaustive | Every referenced document, no exceptions |
| Definitions | Exhaustive | Every term a non-engineer might not know |
| Overview | Summary | 2-4 paragraphs, no implementation detail |
| Design — Components | Moderate | Role and responsibility of each, not internals |
| Design — Integrations | Moderate | What, with whom, for what purpose, which protocol |
| Design — Features | Maximum | Decision tables, thresholds, null handling, retry logic, every branch |
| Design — AI Principles | High | Dataset practices, data privacy, versioning, monitoring |
| Design — Security | Moderate | Mechanisms and standards, not key file paths |
| Attachments | Structural | Skeleton trace worksheet + attachment list |

---

## 5. QUALITY SELF-CHECK BEFORE DELIVERY

Before finalizing the SDS, run through the following quality checks:

### 5.1 Completeness Check
- [ ] Every mandatory section (1-7) is present and populated (or marked N/A with justification).
- [ ] Every feature identified in Phase 1 has a corresponding subsection under Section 6 — Design.
- [ ] Every integration from Phase 1's Integration Inventory appears in the Software Integrations subsection.
- [ ] Every configurable parameter from Phase 1 is mentioned with its default value.
- [ ] Every evaluation/grading mechanism from Phase 1 is described with pass/fail criteria.
- [ ] The Definitions table covers every domain term, abbreviation, and product-specific concept used in the document.
- [ ] The References table includes all external documents, standards, and related SW numbers.

### 5.2 Accuracy Check
- [ ] Every factual claim in the SDS is traceable to Phase 1 analysis or direct code reading.
- [ ] No content has been fabricated or assumed. All uncertain items are marked `[TBC]`.
- [ ] Decision tables match the conditional logic described in the Phase 1 analysis. Ambiguous rows are marked [TBC].
- [ ] Configurable parameter values match what is in the code or configuration files.
- [ ] AI model names and versions match what Phase 1 identified from dependency manifests and SDK calls.

### 5.3 Readability Check
- [ ] A regulatory reviewer unfamiliar with the codebase could understand what the software does by reading the Overview alone.
- [ ] A quality engineer could write V&V test cases based on the Feature subsections without needing to read code.
- [ ] No raw code (function names, variable names, class names) appears in the body text unless absolutely necessary for precision.
- [ ] Every technical term used in the document appears in the Definitions table.
- [ ] Decision tables have no ambiguous rows — every scenario leads to exactly one described behavior.

### 5.4 IEC 62304 Alignment Check
- [ ] The SDS demonstrates that design outputs are traceable (the Trace Worksheet attachment exists, even if skeletal).
- [ ] Safety-critical design elements are identifiable — a reviewer can find the safety mechanisms without searching.
- [ ] The document distinguishes between safety-relevant and non-safety-relevant functionality where applicable.
- [ ] Version control of OTS components (including AI models) is documented.
- [ ] Post-market monitoring design is described for any AI/ML-driven output delivered to users.

### 5.5 Consistency Check
- [ ] Component names are used consistently throughout (same name in Components, Integrations, and Features subsections).
- [ ] Section cross-references point to correct section numbers.
- [ ] Figure numbering is sequential and all figures are referenced in text.
- [ ] Terminology is consistent — the same concept is always called by the same term (defined in the Definitions table).

---

## 6. HANDLING GAPS AND TBC ITEMS

Phase 1 analysis from code alone will inevitably leave gaps. This is expected and acceptable. The SDS should handle gaps as follows:

### What to mark as TBC:
- Document numbers (SRS, RA, IDD, SDP) that could not be determined from code
- Safety classification of specific requirements (requires risk analysis input)
- Risk IDs in the Trace Worksheet
- Dataset composition details not visible in code (e.g., how many users, demographic representation)
- Clinical evidence or SME input that was referenced but not contained in code
- Exact post-market surveillance procedures that live outside the codebase

### What to NOT mark as TBC (derive from code instead):
- Software behavior and logic — this is always derivable from code
- Configurable parameters and their defaults — these are in the code
- Integration targets and protocols — these are in the code
- API endpoints and response codes — these are in the code
- Security mechanisms — these are in the code
- AI model names and versions — these are in dependency manifests or SDK calls

### TBC Summary Table

At the end of the SDS (before Attachments), include a summary table of all TBC items:

| SDS Section | TBC Item | Information Needed | Suggested Source |
|---|---|---|---|
| 3 | RA document number | Risk analysis document ID | QMS/Document Control |
| 6.4.1 | Dataset composition | Demographic breakdown of validation dataset | Data Science team |

This table serves as a clear action list for the development and quality teams to complete the SDS.

---

## 7. CRITICAL REMINDERS

1. **The SDS describes design, not implementation.** Never write about code constructs. Write about what the software does, how it behaves, what it enforces, and what it delivers.

2. **Every configurable value is a design specification.** If the code has a constant, threshold, timeout, retry count, batch size, character limit, or probability weight — it belongs in the SDS with its exact value.

3. **Decision tables are your most powerful tool.** Complex conditional logic is unreadable in prose. Convert it to decision tables. Use the Phase 1 analysis as your source; mark ambiguous rows [TBC].

4. **When in doubt, mark it [TBC].** Phase 2 does not have code access. A single wrong value is worse than a clearly-marked [TBC] item. Be transparent about what the analysis doesn't cover.

5. **Write for the person who will test this software.** A quality engineer will read your Feature subsections and write test cases. If they cannot derive a test case from your description, the description is too vague.

6. **Be transparent about what you don't know.** `[TBC]` items are a feature, not a flaw. They tell the team exactly what human input is still needed. A complete SDS with three `[TBC]` items is infinitely more useful than a half-written SDS with no markers.

7. **Safety mechanisms deserve the most detail.** If the software has grading, filtering, validation, or any mechanism that prevents harmful output from reaching users — document it with the highest level of precision. Regulatory reviewers will spend the most time reading these sections.

8. **Think in terms of SDS sections, not code modules.** The SDS structure follows the template (Purpose → Scope → References → Definitions → Overview → Design → Attachments), not the code's directory structure. A single code module might contribute content to multiple SDS sections, and a single SDS section might synthesize information from many code modules.

9. **Cross-reference liberally.** When a section mentions a concept described elsewhere in the SDS, include a cross-reference. When a section depends on an external document, reference it. The SDS is a navigational document — make it easy to follow threads.

10. **The Definitions table is not an afterthought.** Write it early in Phase 2, update it continuously as you write the Design section, and do a final pass at the end to ensure every term used in the document is defined. A reviewer who encounters an undefined term loses confidence in the entire document.
