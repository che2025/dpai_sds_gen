"""Phase 1 prompt templates — core principles and per-step instructions."""


def core_principles(scope_path: str) -> str:
    return f"""You are analyzing a code repository to extract knowledge for generating an IEC 62304-compliant Software Design Specification (SDS) for medical device software.

ABSOLUTE RULES — these apply to every step of your analysis:

1. CODE IS THE SINGLE SOURCE OF TRUTH.
   The code is the only authoritative source of what the software does. README, wiki, /docs, and comments may be outdated or wrong. If documentation conflicts with code, the code wins. Flag the discrepancy.

2. DO NOT INVENT OR ASSUME.
   If the code does not reveal something, say so explicitly. Record it as a gap. Never fill gaps with plausible guesses.

3. REVERSE-ENGINEER DESIGN INTENT, NOT CODE MECHANICS.
   Extract *what* the software does and *why*, not how the code is structured. Think about purpose from a clinical/user/safety perspective.

4. CONFIGURATION IS DESIGN.
   Every configurable value (threshold, timeout, retry count, batch size, probability weight, character limit) is an SDS-level design specification. Extract them all with exact defaults.

5. TESTS ARE SPECIFICATIONS.
   Test cases encode intended behavior. Test names, assertions, fixtures, and mocks reveal correct behavior and edge cases.

6. SEVEN-QUESTION DEPTH TEST.
   For every significant component: (a) Purpose? (b) Inputs/outputs? (c) Interactions? (d) Business/clinical logic? (e) Safety constraints? (f) Configuration? (g) Failure behavior?

7. SCOPE AWARENESS.
   Primary analysis target: {scope_path or '(full repository)'}
   You have access to the full repo for shared code lookups. Focus on the scope. When you encounter imports from outside scope, you may read those files to understand dependencies.

8. WHEN YOU NEED MORE CODE.
   If provided files are insufficient, include a FILES_NEEDED section listing paths and reasons. Do not guess when you could look."""


# ─── Step-specific instructions and task prompts ─────────────────────────────

STEP_INSTRUCTIONS = {}
TASK_PROMPTS = {}


# ── STEP 1: Structural Map ──────────────────────────────────────────────────

STEP_INSTRUCTIONS[1] = """CURRENT STEP: Repository Reconnaissance — Structural Map

Focus on (priority order):
1. Directory structure — services, modules, separation of concerns.
2. Build/deployment files — Dockerfile, docker-compose, Makefile, CI/CD pipelines, Terraform, K8s manifests.
3. Configuration files — .env.example, config.yaml, settings.py, feature flags.
4. Primary language(s) and framework(s) — from imports/dependencies/entry points, NOT README.
5. README/docs — skim with skepticism. Treat claims as hypotheses. Record discrepancies.

For monorepos with a scoped subdirectory, also scan the repo root to identify shared libraries."""

TASK_PROMPTS[1] = """Analyze the repository structure and files provided.

Produce a structured analysis with these sections:

## REPO TYPE
Single-service or monorepo? If monorepo, list visible services/packages.

## SCOPE SUMMARY
What does the analysis target directory contain?

## TECH STACK
Language(s), framework(s), key tooling — cite the file proving each (e.g., "Python 3.11 — pyproject.toml").

## DIRECTORY MAP
Annotated directory tree (3 levels deep). Annotate directories with likely purpose.

## BUILD & DEPLOYMENT
Build and deployment setup from Dockerfiles, CI/CD, IaC. State if none found.

## CONFIGURATION FILES FOUND
List config files with one-line summaries.

## ENTRY POINTS
Main entry point(s) of the application.

## SHARED CODE DEPENDENCIES
Directories outside scope that scope depends on (from imports or build config).

## README CLAIMS
Key claims from README to verify against code later.

## DISCREPANCIES FOUND
Conflicts between documentation and code already visible.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 2: Build/Deploy/Config ─────────────────────────────────────────────

STEP_INSTRUCTIONS[2] = """CURRENT STEP: Build, Deployment, and Configuration Deep Dive

Build and deploy artifacts are highly reliable — if wrong, the software wouldn't run.

Focus on:
- Dockerfile layers, installed deps, runtime command
- CI/CD pipeline stages
- Infrastructure-as-Code resources (databases, queues, AI services)
- Configuration hierarchy (env vars vs code changes, defaults)
- Feature flags"""

TASK_PROMPTS[2] = """Analyze build, deployment, and configuration files.

## BUILD PROCESS
Build steps, dependencies, output artifacts.

## DEPLOYMENT ARCHITECTURE
Deployment target, process, environment-specific configs.

## RUNTIME CONFIGURATION
Every configurable parameter: name, default value, what it controls, can it change without redeployment?

## INFRASTRUCTURE DEPENDENCIES
Cloud resources required (databases, storage, queues, AI endpoints, monitoring).

## FEATURE FLAGS
Feature flags/toggles: what each controls, default state.

## ENVIRONMENT VARIANTS
Differences between dev/staging/prod configurations.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 3: Dependencies & Integrations ─────────────────────────────────────

STEP_INSTRUCTIONS[3] = """CURRENT STEP: Dependency and Integration Mapping

Categorize every dependency:
- Third-party libraries (OTS) — version pinning
- Internal services
- Cloud platform services
- AI/ML models — CRITICAL: exact model name, version, how version-locked
- Databases, message queues, monitoring

Search code for: HTTP clients, gRPC definitions, SDK instantiations, env vars pointing to external URLs."""

TASK_PROMPTS[3] = """Analyze dependency manifests and source files.

## DEPENDENCY INVENTORY
For each: Name | Version | Category (OTS/Internal/Cloud/AI-ML/DB/Queue/Monitoring) | Purpose

## INTEGRATION MAP
| Integration Target | Type | Direction (In/Out/Both) | Protocol | Purpose | Version Pinned? |

## AI/ML MODEL INTEGRATIONS
For each AI model: name, provider, exact version, how locked, what for, what data sent.

## SHARED CODE DEPENDENCIES
Imports from outside scope: path, functionality, source file.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 4: API Surface ─────────────────────────────────────────────────────

STEP_INSTRUCTIONS[4] = """CURRENT STEP: API Surface Analysis

Start from CODE route handlers, not spec files. OpenAPI/Swagger specs are secondary — cross-check against code.

For each endpoint: method, path, request/response schema, response codes, auth, rate limiting.
Distinguish: user-facing, service-to-service, internal (health checks)."""

TASK_PROMPTS[4] = """Analyze API route definitions.

## INBOUND API ENDPOINTS
For each: method+path, purpose, request schema, response codes+schema, auth, rate limiting, category.

## OUTBOUND API CALLS
For each external API called: target, purpose, data sent, expected response, error handling.

## API VERSIONING
How is the API versioned?

## SPEC FILE DISCREPANCIES
Conflicts between OpenAPI specs and actual code routes.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 5: Data Models ─────────────────────────────────────────────────────

STEP_INSTRUCTIONS[5] = """CURRENT STEP: Data Model and Flow Analysis

Critical for medical devices: identify PII/PHI, de-identification, data shared with third parties.

Look at: ORM models, migrations, DTOs, Pydantic models, protobuf, serializers, validators."""

TASK_PROMPTS[5] = """Analyze data model definitions.

## DATA ENTITIES
For each: name, fields+types, where defined, how stored, relationships.

## DATA FLOW
Per major feature: origin → transformations → storage → consumers → retention policy.

## PII/PHI CLASSIFICATION
Fields that are PII/PHI: name, entity, classification, de-identification method, shared with third parties?

## DATA VALIDATION
Validation applied to incoming data: validators, schema checks, constraints.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 6: Feature & Business Logic ────────────────────────────────────────

STEP_INSTRUCTIONS[6] = """CURRENT STEP: Core Business Logic Deep Dive

THE MOST CRITICAL STEP. The SDS requires extremely detailed documentation of business logic — decision tables, conditional behaviors, configurable thresholds, retry strategies.

For each feature:
a) Processing pipeline step by step
b) Every conditional branch with criteria
c) All configurable parameters with defaults
d) Randomization/probabilistic logic
e) Output format and delivery

IF AI/ML: prompt templates (full), model interaction flow, grading mechanisms, hallucination mitigation, retry/fallback, content filtering, model versioning.

Analyze one feature at a time in maximum depth."""

TASK_PROMPTS[6] = """Analyze feature: {feature_name}

## FEATURE: {feature_name}

### Purpose
What it does, who consumes output, what need it serves.

### Trigger
What initiates execution (API call, scheduled job, event, user action)?

### Input Data
For each input: field/source, required/optional, null handling.

### Processing Pipeline
Every step in order. For each: what happens, data in/out, what can go wrong.

### Decision Logic
Decision tables for every significant branch:
| Condition A | Condition B | ... | Resulting Behavior |
Include defaults and fallbacks. State exact probability weights if randomization exists.

### Configurable Parameters
For each: name, default, valid range, what it controls, where defined.

### AI/ML Details
(If applicable) Prompt template summary, model flow, grading mechanism, retry logic, content safety.

### Output
Format, delivery mechanism, behavior when no output available.

### Error Handling
Failure behavior: silent, logged, retried, surfaced?

### Source Files
All files implementing this feature.

### GAPS
What could not be determined.

### FILES NEEDED
Additional files needed with reasons."""


# ── STEP 7: Safety & Error Handling ─────────────────────────────────────────

STEP_INSTRUCTIONS[7] = """CURRENT STEP: Safety, Error Handling, and Resilience

Identify every mechanism protecting users from harm. Critical for IEC 62304.

Look for: error handling patterns, safety-critical code paths, input validation, graceful degradation, monitoring/alerting, safety comments (SAFETY, WARNING, CRITICAL, TODO)."""

TASK_PROMPTS[7] = """Analyze safety and resilience mechanisms.

## ERROR HANDLING PATTERNS
Global handler, per-feature handling, retry logic, circuit breakers.

## SAFETY-CRITICAL CODE PATHS
Code paths affecting user-delivered output: what it does, validation before delivery, what could go wrong.

## INPUT VALIDATION
User/client input validation, external data validation, schema validation.

## GRACEFUL DEGRADATION
Partial data behavior, null handling, fallback behavior.

## MONITORING & ALERTING
Metrics emitted (names + what they measure), log levels, health checks, alerting thresholds.

## SAFETY COMMENTS FOUND
All comments with SAFETY, WARNING, CRITICAL, FIXME, HACK, or safety-related TODOs.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 8: Security ────────────────────────────────────────────────────────

STEP_INSTRUCTIONS[8] = """CURRENT STEP: Security and Privacy Analysis

Focus on: auth (JWT, OAuth, mTLS), authorization (RBAC, ABAC), encryption (TLS version, ciphers), secrets management, network security, audit logging, data masking."""

TASK_PROMPTS[8] = """Analyze security and privacy mechanisms.

## AUTHENTICATION
Mechanism, token validation, issuer, enforcement point.

## AUTHORIZATION
Model, per-endpoint permissions, how decisions are made.

## ENCRYPTION IN TRANSIT
TLS version, cipher restrictions, mTLS.

## ENCRYPTION AT REST
Database encryption, storage encryption, key management.

## SECRETS MANAGEMENT
How secrets are stored/accessed, exposure risks.

## AUDIT LOGGING
What is logged, fields, storage, tamper-proofing.

## DATA MASKING
PII/PHI masking in logs, implementation.

## NETWORK SECURITY
VPC, firewall rules, service mesh.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 9: Test Suite ──────────────────────────────────────────────────────

STEP_INSTRUCTIONS[9] = """CURRENT STEP: Test Suite Analysis

Tests are code = source of truth. Focus on: what is tested (and what is NOT), behavioral specs from assertions, edge cases, test fixtures/mock data shapes, CI/CD quality gates."""

TASK_PROMPTS[9] = """Analyze the test suite.

## TEST ARCHITECTURE
Frameworks, directory structure, test categories (unit/integration/e2e/perf).

## KEY BEHAVIORAL SPECIFICATIONS
Per test file/class: what behavior it verifies, edge cases covered, fixture data insights.

## INTEGRATION TEST BOUNDARIES
What is mocked vs hit by integration tests.

## TEST COVERAGE FOCUS
Most-covered components. Least-covered components (potential SDS gaps).

## CI/CD QUALITY GATES
Required tests for deployment, coverage thresholds, quality gates.

## NOTABLE TEST DATA
Fixtures/mock data revealing expected formats, ranges, edge cases.

## FILES NEEDED
Additional files needed with reasons."""


# ── STEP 10: Synthesis ──────────────────────────────────────────────────────

STEP_INSTRUCTIONS[10] = """CURRENT STEP: Synthesis and Gap Assessment

Final Phase 1 step. Compile all findings into a coherent document. Compile terminology, discrepancies, gaps, and SDS readiness assessment."""

TASK_PROMPTS[10] = """Compile the final synthesis from all step findings.

## TERMINOLOGY
Complete term-definition list. Non-engineer-readable definitions.
| Term | Definition |

## DOCUMENTATION-CODE DISCREPANCIES
| Source | What it claims | What the code does |

## GAPS AND UNCERTAINTIES
| Gap | SDS section affected | Information needed | Suggested source |

## SDS SECTION READINESS ASSESSMENT
| SDS Section | Readiness (Ready/Partial/Insufficient) | Notes |
| 1. Purpose | | |
| 2. Scope | | |
| 3. References | | |
| 4. Definitions | | |
| 5. Overview | | |
| 6.1 Software Components | | |
| 6.2 Software Integrations | | |
| 6.3 Key Features | | |
| 6.4 AI/ML Design Principles | | |
| 6.5 Security and Privacy | | |
| 7. Attachments | | |

## CROSS-CUTTING OBSERVATIONS
Patterns, architectural decisions, or design philosophies spanning multiple features."""
