# Phase 1: Code Repository Deep Analysis Guidance

## For AI-Driven SDS (Software Design Specification) Generation Tool

**Document Purpose**: This document instructs the AI on how to systematically analyze a GitHub code repository to extract sufficient knowledge for generating an IEC 62304-compliant Software Design Specification (SDS) in Phase 2. Since no companion documents (SRS, SAD, RA) are available, ALL understanding must be derived from the code itself. The code is the single source of truth — prose documentation (README, wiki, /docs) may exist but is treated as unverified reference material, never as authoritative input.

**Applicable Standard**: IEC 62304 + AMD1 — Medical Device Software Life Cycle Processes

---

## 1. ANALYSIS PHILOSOPHY

### 1.1 Code is the Single Source of Truth

**The code — and only the code — is the authoritative source of what the software actually does.** README files, wiki pages, `/docs` folders, inline comments describing high-level intent, and any other prose documentation may be outdated, incomplete, or outright contradictory to the current implementation. Documentation rot is a universal problem: code gets refactored, features get added or removed, but nobody updates the README.

Therefore:

- **Never trust documentation over code.** If a README says "this service uses Redis for caching" but the code imports and connects to Memcached, the truth is Memcached.
- **Prose documentation is a secondary signal, not a primary source.** You may glance at a README to get an initial orientation (what the repo claims to be), but immediately verify every claim by examining the actual code. If they conflict, the code wins — always.
- **Derive your understanding bottom-up from code, not top-down from docs.** Build your mental model by reading source files, configuration, dependency manifests, test cases, and build scripts. Only then compare against whatever documentation exists to see if it adds any context the code alone could not reveal (e.g., historical design rationale).
- **Flag documentation-code discrepancies.** When you find a conflict between docs and code, record it explicitly in your analysis output. These discrepancies are valuable feedback for the engineering team.

### 1.2 Reverse-Engineering Design Intent

You are not simply reading code. You are **reverse-engineering the design intent** behind the code. An SDS is not a code walkthrough — it is a document that explains *what* the software does, *why* it is designed this way, and *how* it ensures safety and effectiveness for a medical device. Your analysis must bridge the gap between raw implementation and human-readable design rationale.

### 1.3 Dual Perspective

At all times, maintain two parallel lenses:

- **Technical Lens**: Architecture, data flow, algorithms, integrations, error handling, security mechanisms.
- **Human/Regulatory Lens**: Why does this component exist? What clinical or user need does it serve? What could go wrong and how does the code mitigate it? What safety-critical decisions are embedded in the logic?

### 1.4 Depth Standard

The analysis must reach a depth where you could confidently answer the following for every significant component:

1. What is its purpose in the overall system?
2. What are its inputs, outputs, and side effects?
3. What other components does it interact with?
4. What business/clinical logic does it encode?
5. What safety constraints or guardrails are embedded?
6. What configuration parameters govern its behavior?
7. What happens when it fails?

If you cannot answer all seven questions for a component, your analysis is not deep enough.

---

## 2. ANALYSIS EXECUTION ORDER

Follow this sequence strictly. Each step builds on the previous.

### Step 1: Repository Reconnaissance (Macro Structure)

**Goal**: Understand the overall shape and scope before diving into details. **Start from code artifacts, not prose documentation.**

**Actions (in priority order)**:

- **First: Map the complete directory tree** (2-3 levels deep). The directory structure itself tells you what the software is — service names, module organization, separation of concerns. This is your primary orientation tool, not the README.
- **Second: Read build and deployment configuration files** — these are machine-consumed and therefore almost always accurate and up-to-date (a stale Dockerfile means broken builds, so teams fix these):
  - `Dockerfile`, `docker-compose.yml`
  - `Makefile`, `build.gradle`, `pom.xml`, `package.json`, `pyproject.toml`, `setup.py`, `go.mod`
  - CI/CD pipelines: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`
  - Infrastructure-as-Code: Terraform (`*.tf`), Kubernetes manifests (`*.yaml` in `/k8s`, `/deploy`, `/helm`)
- **Third: Read all configuration files** — these reveal real runtime behavior:
  - Environment configs: `.env.example`, `config.yaml`, `settings.py`, `application.properties`
  - Feature flags and toggles
- **Fourth: Identify the primary programming language(s) and framework(s)** by examining imports, dependencies, and entry points — not by reading the README's tech stack section.
- **Last (and with skepticism): Skim `README.md` and `/docs`** — treat these as *hypotheses to verify*, not facts. If a README claims the service does X, check if the code actually implements X. Record any discrepancies you find.
- For **monorepos**: Identify all services/packages, their boundaries, and inter-dependencies by examining the directory structure, shared dependency configurations, and import patterns across services. Create a service inventory table before proceeding.

**Output**: A structural map of the repository that identifies:
- Whether this is a monorepo or single-service repo
- Each deployable unit (service/component) and its root directory
- The tech stack for each unit (derived from actual code and dependencies, not docs)
- Build and deployment pipeline overview
- Any discrepancies found between documentation claims and code reality

### Step 2: Dependency and Integration Mapping (External Boundaries)

**Goal**: Identify everything the software talks to.

**Actions**:

- Parse dependency manifests (`requirements.txt`, `package.json`, `go.mod`, `pom.xml`, etc.) and categorize dependencies:
  - **Third-party libraries**: Classify as OTS (Off-The-Shelf) software — note version pinning.
  - **Internal/sister services**: Other company-internal microservices referenced.
  - **Cloud platform services**: GCP, AWS, Azure managed services (BigQuery, Cloud Storage, Pub/Sub, SQS, etc.).
  - **AI/ML models and APIs**: Any foundation model or AI service integrations (e.g., Google Vertex AI, OpenAI, Anthropic, HuggingFace). **Pay special attention** — for medical device AI/ML software, the specific model name, version, and how it is version-locked are critical.
  - **Databases**: Type (SQL, NoSQL, cache), connection strings, ORM models.
  - **Message queues/event buses**: Kafka, RabbitMQ, Pub/Sub topics.
  - **Monitoring/observability**: Datadog, Prometheus, Sentry, logging frameworks.

- Search the codebase for:
  - HTTP client calls (`requests`, `httpx`, `fetch`, `axios`, `http.Client`)
  - gRPC service definitions (`.proto` files)
  - SDK client instantiations (e.g., `BigQueryClient()`, `VertexAIClient()`)
  - Environment variable references that point to external URLs or service addresses

**Output**: A complete integration inventory table:

| Integration Target | Type | Direction (Inbound/Outbound/Both) | Protocol | Purpose | Version Pinned? |
|---|---|---|---|---|---|

### Step 3: API Surface Analysis (External Interfaces)

**Goal**: Understand how the outside world interacts with this software.

**Actions**:

- **Start from the code, not spec files.** Locate API route definitions directly in the source:
  - REST: Route decorators/handlers in code (e.g., `@app.route`, `@GetMapping`, `router.get`, `http.HandleFunc`). Then, if OpenAPI/Swagger specs exist (`swagger.json`, `openapi.yaml`), cross-check them against the code — spec files can be auto-generated or manually maintained, and manually maintained ones frequently drift from reality.
  - gRPC: `.proto` files (these tend to be accurate since they are compiled, but verify the service implementation matches the proto definition).
  - GraphQL: schema files and resolver implementations.
- For each endpoint, document:
  - HTTP method and path
  - Request parameters and body schema
  - Response codes and body schema (pay special attention to error responses)
  - Authentication/authorization requirements (JWT, API key, OAuth scopes)
  - Rate limiting or throttling configuration
- Identify **inbound** API endpoints (what this service exposes) vs. **outbound** API calls (what this service consumes from others).
- Look for API versioning strategies.

**Output**: A complete API surface map, distinguishing between:
- User/client-facing endpoints
- Service-to-service endpoints
- Internal/health-check endpoints
- Webhook/callback endpoints

### Step 4: Data Model and Flow Analysis (The Bloodstream)

**Goal**: Understand what data flows through the system, how it transforms, and where it persists.

**Actions**:

- Locate and analyze:
  - Database schema definitions (ORM models, migration files, SQL DDL scripts)
  - Data transfer objects (DTOs), serializers, Pydantic models, protobuf messages
  - Data validation logic (input validation, schema validation)
- Trace the end-to-end data flow for each major feature:
  - Where does the data originate?
  - What transformations does it undergo?
  - Where is it persisted? In what format?
  - Who can access it downstream?
- **Critical for medical devices**: Identify all user/patient data fields. Track:
  - Which fields are PII/PHI (Protected Health Information)?
  - Where is de-identification or pseudonymization applied?
  - Is data shared with third parties (e.g., sent to an LLM API)? If so, what data?
  - Data retention policies (if encoded in code or config)

**Output**: For each major data entity:
- Schema/field definitions
- Lifecycle: creation → transformation → storage → retrieval → deletion
- Classification: PII/PHI, clinical data, configuration data, audit data

### Step 5: Core Business Logic Deep Dive (The Brain)

**Goal**: Understand the algorithms, decision trees, and clinical/safety logic that define the software's behavior.

This is the most critical step. The Design section of an SDS requires extremely detailed documentation of business logic, including decision tables, conditional behaviors, configurable thresholds, and retry strategies. Surface-level summaries are not sufficient — you must trace logic at the level of individual branching conditions.

**Actions**:

- Identify the main "feature modules" or "domain logic" areas. For each:

  **a) Algorithm and Decision Logic**
  - Trace the core processing pipeline step by step.
  - Identify all conditional branches and the criteria that govern them.
  - Document decision tables where applicable (e.g., "if condition A AND condition B, then action X").
  - Note all configurable parameters, their defaults, and their valid ranges.
  - Identify any randomization or probabilistic logic (e.g., A/B testing, random selection with probability weights).

  **b) AI/ML-Specific Logic (if applicable)**
  - **Prompt templates**: Read every prompt template verbatim. Understand what data is injected, what instructions are given to the model, and what output format is expected.
  - **Model interaction flow**: How are prompts composed? Is it a single call or a chain of calls? Does the output of one call feed into the next?
  - **Grading/evaluation mechanisms**: Are there quality checks on AI output? What criteria do they use? Are they LLM-based or deterministic? What are the pass/fail thresholds?
  - **Hallucination mitigation**: What guardrails prevent the AI from generating incorrect or harmful content?
  - **Retry and fallback logic**: What happens when the AI generates a failing response? How many retries? What is the timeout?
  - **Content filtering**: Are there blocked terms, sentiment analysis, readability checks?
  - **Model versioning**: How are foundation model versions locked? Where is this configured?

  **c) Scheduling and Batch Processing**
  - Identify all scheduled jobs (cron, Airflow, Cloud Scheduler, Dataflow).
  - Document their frequency, trigger conditions, and batch sizes.
  - Understand the processing pipeline for batch operations.

  **d) Feature Flags and Configuration**
  - Catalogue all feature flags and their effects.
  - Document all tunable parameters (thresholds, timeouts, retry counts, percentage rollouts).
  - Note which configurations can change without a code deployment.

**Output**: For each feature/function, a structured description covering:
- Purpose and user-facing behavior
- Input data and preconditions
- Processing steps (the algorithm)
- Decision logic and branching rules
- Output format and delivery mechanism
- Configurable parameters with defaults
- Error/failure handling

### Step 6: Safety, Error Handling, and Resilience (The Immune System)

**Goal**: Identify all mechanisms that protect users from harm — this is especially critical for IEC 62304 medical device software.

**Actions**:

- **Error Handling Patterns**:
  - How are exceptions caught and handled? Is there a global error handler?
  - What errors are retried vs. surfaced to the user vs. silently logged?
  - Are there circuit breakers for external service calls?
  - What is the behavior when a dependency is unavailable?

- **Safety-Critical Code Paths**:
  - Identify any code that directly affects clinical output (e.g., glucose values, health recommendations, diagnostic information).
  - Trace what validation or verification exists before such output reaches the user.
  - Look for safety-related comments in the code (`# SAFETY`, `// WARNING`, `TODO: safety`, `CRITICAL`).
  - Identify any hard-coded safety thresholds or boundaries.

- **Input Validation and Sanitization**:
  - How is user input validated?
  - How is data from external services validated before use?
  - Are there schema validations for API requests and responses?

- **Graceful Degradation**:
  - What happens when partial data is available?
  - How does the system handle null/missing values for critical fields?
  - Is there fallback behavior for each major feature?

- **Monitoring and Alerting**:
  - What metrics are emitted? (Look for Datadog, Prometheus, StatsD, CloudWatch metric calls)
  - What log levels are used and for what events?
  - Are there health check endpoints?
  - What alerting thresholds are configured?

**Output**: A safety and resilience profile for the software:
- Catalogue of error handling strategies by component
- List of safety-critical code paths with their protection mechanisms
- Monitoring coverage map
- Known failure modes and system responses

### Step 7: Security and Privacy Analysis (The Shield)

**Goal**: Document how the software protects data and prevents unauthorized access.

**Actions**:

- **Authentication and Authorization**:
  - What authentication mechanism is used (JWT, OAuth, mTLS, API keys)?
  - How are tokens validated? Which authority issues them?
  - What authorization model is used (RBAC, ABAC, scopes)?
  - Are there different permission levels for different endpoints?

- **Data Protection**:
  - Is data encrypted in transit? What TLS version? What cipher suites?
  - Is data encrypted at rest? What encryption mechanism?
  - How are secrets managed (environment variables, secret managers, vaults)?
  - Are there data masking or redaction mechanisms in logs?

- **Network Security**:
  - What network boundaries exist (VPC, private endpoints)?
  - Are there IP allowlists or firewall rules configured in code?
  - Is mTLS used for service-to-service communication?

- **Audit Logging**:
  - What actions are logged for audit purposes?
  - Are audit logs tamper-proof?
  - What fields are included in audit records?

**Output**: A security design profile:
- Authentication/authorization architecture
- Data protection mechanisms (transit and rest)
- Network security model
- Audit logging coverage

### Step 8: Testing and Quality Evidence (The Proof)

**Goal**: Understand what the test suite reveals about intended behavior and quality standards.

**Actions**:

- Survey the test directory structure and testing frameworks used.
- Read test files — **tests are documentation**. They reveal:
  - Intended behavior for each component
  - Edge cases the developers considered
  - Integration boundaries
  - Expected error behaviors
- Categorize tests:
  - Unit tests: What units are tested? What is the coverage focus?
  - Integration tests: What integration points are validated?
  - End-to-end tests: What user scenarios are covered?
  - Performance/load tests: What are the performance expectations?
- Look for test fixtures and mock data — these reveal expected data shapes and ranges.
- Check for test configuration that reveals:
  - CI/CD test gates
  - Coverage thresholds
  - Quality gates

**Output**: A testing profile:
- Test architecture overview
- Key behavioral expectations revealed by tests
- Coverage focus areas
- Notable edge cases documented in tests

---

## 3. SPECIAL CONSIDERATIONS FOR MONOREPOS

When analyzing a monorepo, add these additional steps:

1. **Service Boundary Identification**: Map each service to its own directory. Treat each as a semi-independent analysis target, then synthesize.
2. **Inter-Service Communication**: Document how services talk to each other (REST, gRPC, message queues, shared databases).
3. **Shared Libraries**: Identify common/shared code and understand which services depend on it.
4. **Deployment Independence**: Determine if services can be deployed independently or must be deployed together.
5. **SDS Scoping Decision**: Determine whether one SDS covers the entire repo or each service gets its own SDS. This depends on the software item decomposition per IEC 62304.

---

## 4. INFORMATION SUFFICIENCY CHECKLIST

Before declaring Phase 1 complete and moving to Phase 2 (SDS generation), verify that you have gathered enough information to populate **every** section of the SDS. Use this checklist:

### Section 1 — Purpose
- [ ] Software identifier (SW number/name) is known
- [ ] One-sentence description of what the software does can be written
- [ ] The type of medical device or system this software is part of can be identified

### Section 2 — Scope
- [ ] The boundaries of the software are clear (what is in scope, what is not)
- [ ] External interfaces are identified (which systems it talks to)
- [ ] The intended users of the software are understood (end users, other systems, administrators)

### Section 3 — References
- [ ] All third-party dependencies (OTS software) are catalogued with version numbers
- [ ] All external services and APIs are identified
- [ ] Applicable standards (IEC 62304, etc.) are noted
- [ ] Related internal software components are listed

### Section 4 — Definitions
- [ ] All domain-specific terms found in the code are collected
- [ ] All abbreviations used in variable names, comments, and docs are decoded
- [ ] AI/ML-specific terminology is defined (if applicable)
- [ ] Clinical/medical terminology is defined (if applicable)

### Section 5 — Overview
- [ ] A high-level narrative of the software can be written (2-3 paragraphs)
- [ ] The major features/capabilities can be listed
- [ ] The primary data flows can be described at a high level
- [ ] A conceptual architecture diagram could be described (components and their relationships)

### Section 6 — Design

#### 6.1 Architecture/Design Diagrams
- [ ] All major components and their relationships are understood
- [ ] Data flow between components can be described
- [ ] External integration points are mapped

#### 6.2 Software Components
- [ ] Each deployable component/service is identified
- [ ] The responsibility of each component is understood
- [ ] The technology stack of each component is documented

#### 6.3 Software Integrations
- [ ] All external integrations are catalogued (third-party services, cloud services, AI models)
- [ ] For each integration: protocol, direction, data exchanged, version pinning

#### 6.4 Key Features and Functions
- [ ] Each user-facing feature is identified and can be described
- [ ] The processing pipeline for each feature is traced end-to-end
- [ ] Business logic and decision rules are documented with sufficient detail to reproduce the behavior
- [ ] All configurable parameters are catalogued with defaults and valid ranges
- [ ] AI/ML-specific logic is fully traced (prompts, model interactions, grading, retry logic)
- [ ] Null handling and edge cases are documented

#### 6.5 Safety and Quality Mechanisms
- [ ] All grading, validation, or quality-check mechanisms are documented
- [ ] Pass/fail criteria for each mechanism are recorded
- [ ] Performance targets (e.g., pass rates) are identified from code or config
- [ ] Monitoring and alerting mechanisms are catalogued
- [ ] Post-deployment monitoring design is understood

#### 6.6 AI/ML Design Principles (if applicable)
- [ ] Dataset handling practices are understood (de-identification, pseudonymization)
- [ ] Data sharing with third parties is documented
- [ ] Model versioning and lock-down strategy is documented
- [ ] Bias mitigation or fairness considerations found in code are noted
- [ ] Content safety guardrails are catalogued

#### 6.7 Security and Privacy
- [ ] Authentication mechanism is documented
- [ ] Authorization model is documented
- [ ] Encryption (transit and rest) is documented
- [ ] Audit logging is documented
- [ ] Secret management approach is documented

### Section 7 — Attachments
- [ ] Enough information exists to create an SRS-SDS traceability matrix skeleton
  - (Since no SRS exists, identify the implicit requirements from code behavior to list as SDS design elements)

---

## 5. OUTPUT FORMAT FOR PHASE 2 HANDOFF

Organize your Phase 1 findings into the following structured knowledge document. This is the input that Phase 2 will use to generate the SDS.

```
# Phase 1 Analysis Output: [Software Name]

## META
- Repository URL:
- Primary Language(s):
- Repository Type: [Single Service | Monorepo]
- Services/Components Identified: [list]
- Analysis Date:
- Analysis Completeness: [Complete | Partial — with gaps noted]

## STRUCTURAL MAP
[Directory tree with annotations]

## INTEGRATION INVENTORY
[Table from Step 2]

## API SURFACE
[From Step 3]

## DATA MODEL
[From Step 4]

## FEATURE ANALYSIS
### Feature 1: [Name]
- Purpose:
- User/Consumer:
- Input Data:
- Processing Pipeline:
- Decision Logic:
- Output:
- Configuration Parameters:
- Error Handling:
- Safety Guardrails:

### Feature 2: [Name]
[... repeat for each feature]

## SAFETY AND RESILIENCE PROFILE
[From Step 6]

## SECURITY PROFILE
[From Step 7]

## TESTING PROFILE
[From Step 8]

## TERMINOLOGY COLLECTED
[Term — Definition pairs]

## GAPS AND UNCERTAINTIES
[Anything that could not be determined from code alone]

## DOCUMENTATION-CODE DISCREPANCIES
[List every instance where README, docs, or comments contradicted the actual code behavior.
 Format: Source of claim → What it says → What the code actually does]

## SDS SECTION READINESS ASSESSMENT
[For each SDS section, rate: Ready / Partial / Insufficient
 with notes on what is missing]
```

---

## 6. CRITICAL REMINDERS

1. **Code is truth; everything else is hearsay.** Never let a README, wiki page, or comment override what the code actually does. If they conflict, document the discrepancy and report the code's behavior in your analysis. Stale documentation is the norm, not the exception.

2. **Read comments with a critical eye.** In medical device code, comments often contain design rationale, safety justifications, and regulatory context that is nowhere else. Pay attention to `TODO`, `FIXME`, `HACK`, `SAFETY`, `NOTE`, `WARNING` tags. However, apply the same skepticism: a comment that says "this function validates input" is only true if the code below it actually validates input. When a comment contradicts its code, trust the code and flag the inconsistency.

3. **Configuration is design**. Configurable thresholds (e.g., pass rate targets, time windows, retry periods, batch sizes) are all SDS-level design specifications. Extract every configurable value — these live in code and config files, not in documentation, and are therefore reliably current.

4. **Tests are specifications**. When there is no SRS document, test cases are the closest thing to formal requirements. Test names, assertions, and fixtures encode intended behavior. Tests are also code, so they share the same "source of truth" status as production code.

5. **Build/deploy artifacts don't lie.** Dockerfiles, CI/CD pipelines, Terraform configs, and Kubernetes manifests are machine-consumed — if they were wrong, the system wouldn't run. Prioritize these over any human-written documentation about deployment architecture.

6. **Git history is context, not truth.** If accessible, recent commit messages and PR descriptions can reveal design decisions, bug fixes, and feature evolution. But remember: commit messages describe intent at a point in time, and may not reflect later revisions. Use git history to understand *why* something was built, then verify *what* it actually does by reading the current code.

7. **Do not invent or assume**. If the code does not reveal something, record it as a gap. The SDS must reflect what the software actually does, not what it might do. Phase 2 will handle gaps by marking sections as "To Be Confirmed" rather than fabricating content.

8. **Think about the reader**. The SDS will be read by regulatory reviewers, quality engineers, and clinicians — not just software developers. Your analysis must capture enough context for Phase 2 to explain the design in terms those audiences understand.

9. **IEC 62304 awareness**. The SDS exists to demonstrate that the software design meets requirements and manages risk. Even though you do not have the SRS or RA documents, look for code patterns that suggest safety classification awareness (e.g., input validation on clinical data, redundant checks, output verification before delivery to users).
