# AutoHeal CI/CD

> **Local-first multi-agent CI/CD failure analysis and remediation system powered by Google ADK, Llama 3.2 via Ollama, RAG, GitHub Actions, FastAPI, React, and Arize Phoenix.**

AutoHeal CI/CD is an AI-assisted DevOps system designed to analyze failed CI/CD pipelines, retrieve relevant troubleshooting knowledge, identify likely root causes, generate a constrained remediation patch, validate that patch inside an isolated workspace, and make a release decision with a Human-in-the-Loop (HITL) gate.

The project is designed to run locally with free/open tooling wherever possible. The LLM is served locally through **Ollama**, so the core workflow does not require a paid hosted LLM API.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Problem Statement](#problem-statement)
3. [Goals](#goals)
4. [Key Features](#key-features)
5. [High-Level Architecture](#high-level-architecture)
6. [End-to-End Workflow](#end-to-end-workflow)
7. [Agent Architecture](#agent-architecture)
8. [Detailed Working](#detailed-working)
9. [RAG Pipeline](#rag-pipeline)
10. [RCA Workflow](#rca-workflow)
11. [Fix Generation and Safety](#fix-generation-and-safety)
12. [Isolated Validation](#isolated-validation)
13. [Release Decision and HITL](#release-decision-and-hitl)
14. [GitHub Actions Integration](#github-actions-integration)
15. [Webhook Flow](#webhook-flow)
16. [Observability with Arize Phoenix](#observability-with-arize-phoenix)
17. [RAG Evaluation](#rag-evaluation)
18. [Frontend](#frontend)
19. [Backend API](#backend-api)
20. [Project Structure](#project-structure)
21. [Technology Stack](#technology-stack)
22. [Prerequisites](#prerequisites)
23. [Installation](#installation)
24. [Environment Configuration](#environment-configuration)
25. [Running the System](#running-the-system)
26. [Testing the Local Pipeline](#testing-the-local-pipeline)
27. [Testing the GitHub Webhook](#testing-the-github-webhook)
28. [Frontend Workflow](#frontend-workflow)
29. [Phoenix Workflow](#phoenix-workflow)
30. [Security and Safety Controls](#security-and-safety-controls)
31. [Failure Scenarios](#failure-scenarios)
32. [Example AutoHeal Run](#example-autoheal-run)
33. [Troubleshooting](#troubleshooting)
34. [Future Improvements](#future-improvements)
35. [Limitations](#limitations)
36. [License](#license)

---

# Project Overview

Traditional CI/CD pipelines can identify that a build or test job failed, but diagnosing the failure and deciding what to do next often requires a developer to inspect logs manually.

AutoHeal CI/CD adds an AI-assisted remediation layer after a pipeline failure:

```text
GitHub Actions
      |
      v
Webhook
      |
      v
Pipeline Agent
      |
      v
RAG Retrieval
      |
      v
RCA Agent
      |
      v
Fix Agent
      |
      v
Isolated Validation
      |
      v
Release Decision Agent
      |
      v
Human-in-the-Loop
```

The system deliberately separates:

- failure detection
- knowledge retrieval
- root-cause analysis
- fix generation
- patch safety
- isolated validation
- release decision
- human approval
- observability

This separation makes the workflow easier to inspect, test, and extend.

---

# Problem Statement

A failed CI/CD run usually produces logs containing symptoms rather than a ready-made explanation.

For example:

```text
FAILED tests/test_calculator.py::test_add
assert -1 == 5
```

A developer must determine:

1. What actually failed?
2. Which source file is responsible?
3. Is the failure caused by code, dependency, configuration, or environment?
4. Is there historical troubleshooting knowledge that can help?
5. What is the smallest safe fix?
6. Does the proposed fix actually work?
7. Should the release continue?
8. Does a human need to approve the change?

AutoHeal automates these analysis steps while keeping the final release decision controllable.

---

# Goals

## Primary goals

- Process real GitHub Actions workflow runs.
- Retrieve real CI logs.
- Identify likely root causes.
- Use RAG to retrieve relevant troubleshooting knowledge.
- Generate a minimal remediation patch.
- Prevent modification of test files by the Fix Agent.
- Apply the patch only to an isolated workspace.
- Execute the configured test command against the isolated workspace.
- Separate patch application from test success.
- Require HITL review when appropriate.
- Record agent activity through OpenTelemetry/Phoenix.
- Provide RAG evaluation metrics.
- Provide a React dashboard for the complete workflow.

## Design principles

### Local-first

The core LLM is local:

```text
Ollama
  |
  +-- Llama 3.2
```

### Evidence-first

Agents should use actual CI evidence rather than inventing failure causes.

### Minimal changes

The Fix Agent should propose the smallest change supported by the RCA.

### Never modify tests

The remediation path is designed to prevent the AI from "fixing" a failing test instead of fixing the implementation.

### Isolated execution

The candidate patch is tested in an isolated workspace rather than directly against the developer's source tree.

### Human control

The automated system can analyze and validate a proposed remediation without silently turning every proposal into an unrestricted release.

---

# Key Features

- Multi-agent CI/CD workflow
- Google ADK orchestration
- Local Llama 3.2 through Ollama
- FastAPI backend
- React/Vite frontend
- GitHub Actions integration
- GitHub webhook processing
- CI log retrieval
- Commit diff retrieval
- RAG troubleshooting knowledge base
- Lexical retrieval fallback
- RCA with evidence and confidence
- Safe unified-diff generation
- Patch validation
- Isolated test execution
- Release decision agent
- Human-in-the-Loop approval
- OpenTelemetry tracing
- Arize Phoenix observability
- RAG evaluation
- Pipeline result dashboard
- CI log viewer
- Proposed patch viewer
- Validation output viewer

---

# High-Level Architecture

```text
                              +----------------------+
                              |     GitHub Actions   |
                              |    CI/CD Workflow    |
                              +----------+-----------+
                                         |
                                         | workflow_run
                                         v
                              +----------------------+
                              |   GitHub Webhook     |
                              |      FastAPI         |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |    Pipeline Agent    |
                              |  Pipeline status +   |
                              |     CI evidence      |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |  RAG Retrieval Agent |
                              | Troubleshooting KB   |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |      RCA Agent       |
                              | Root cause + evidence|
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              |      Fix Agent       |
                              | Minimal safe diff    |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              | Isolated Validation  |
                              | Patch + pytest       |
                              +----------+-----------+
                                         |
                                         v
                              +----------------------+
                              | Release Decision     |
                              | Agent / Gate         |
                              +----------+-----------+
                                         |
                            +------------+------------+
                            |                         |
                            v                         v
                     HUMAN REVIEW              Release decision
                       / HITL
```

---

# Runtime Architecture

The project is intended to run locally as several processes:

```text
Windows PC
│
├── Ollama
│     └── Llama 3.2
│
├── FastAPI
│     └── localhost:8000
│
├── Arize Phoenix
│     └── localhost:6006
│
└── React + Vite
      └── localhost:5173
```

Typical startup:

```text
Terminal 1 → Ollama
Terminal 2 → Phoenix
Terminal 3 → FastAPI
Terminal 4 → React/Vite
```

---

# End-to-End Workflow

## Workflow A — Successful pipeline

```text
GitHub Actions
      |
      | conclusion = success
      v
Pipeline status
      |
      v
Successful result
      |
      v
Release decision
      |
      v
No remediation required
```

A successful pipeline should not unnecessarily execute the remediation chain.

---

## Workflow B — Failed pipeline

```text
GitHub Actions
      |
      v
workflow_run = completed
      |
      v
conclusion = failure
      |
      v
Fetch logs
      |
      v
Fetch commit diff
      |
      v
RAG retrieval
      |
      v
RCA
      |
      v
Fix proposal
      |
      v
Safety validation
      |
      v
Isolated patch application
      |
      v
Run tests
      |
      v
Release Decision
      |
      +-------------------+
      |                   |
      v                   v
HUMAN_REVIEW          REJECTED /
                      APPROVED
```

---

# Agent Architecture

The system contains the following logical stages.

## 1. Pipeline Agent

Purpose:

- Understand pipeline execution evidence.
- Determine the pipeline state.
- Preserve the CI evidence needed by later agents.

Important design constraint:

```text
The pipeline routing path is deterministic.
```

The workflow reads the GitHub workflow conclusion directly for reliable routing.

This prevents an LLM from deciding whether a GitHub Actions run actually succeeded or failed.

---

## 2. RAG Retrieval

Purpose:

- Retrieve troubleshooting knowledge related to the failure.
- Supply context to the RCA/remediation workflow.

Input:

```text
scenario
CI logs
commit diff
```

Output:

```text
retrieved troubleshooting context
```

The application performs one deterministic retrieval before the remediation workflow.

This prevents an unnecessary tool-retrieval loop.

---

## 3. RCA Agent

Purpose:

- Analyze CI evidence.
- Identify likely root cause.
- Provide supporting evidence.
- Identify likely affected implementation files.
- Assign a confidence value.

Example:

```json
{
  "summary": "The add function is performing subtraction instead of addition.",
  "confidence": 0.99,
  "evidence": [
    "tests/test_calculator.py::test_add failed with assert -1 == 5.",
    "The failing call is add(2, 3), which returned -1 instead of the expected 5."
  ],
  "likely_files": [
    "calculator.py"
  ]
}
```

---

## 4. Fix Agent

Purpose:

- Convert the RCA into the smallest safe code change.
- Generate a unified diff.
- Avoid changing tests.
- Avoid changing unrelated files.

Example:

```diff
diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
```

The Fix Agent does not claim that the tests passed.

That claim belongs to the validation stage.

---

## 5. Validation

Purpose:

- Apply the proposed patch in an isolated workspace.
- Run the configured test command.
- Record whether patch application succeeded.
- Record whether test execution succeeded.
- Record whether all tests passed.

These are intentionally separate states.

Example:

```json
{
  "attempted": true,
  "patch_applied": true,
  "tests_passed": false,
  "test_execution_success": true,
  "exit_code": 1,
  "changed_files": [
    "calculator.py"
  ]
}
```

This means:

```text
Patch applied      = YES
Tests executed     = YES
All tests passed   = NO
```

This distinction is important.

---

# RAG Pipeline

The RAG layer uses a local knowledge base.

Conceptually:

```text
Knowledge Files
      |
      v
Document Loading
      |
      v
Chunking
      |
      v
Retrieval
      |
      v
Top-K Context
      |
      v
RCA / Remediation Workflow
```

The knowledge base contains CI troubleshooting material such as:

- test failures
- dependency failures
- configuration failures
- deployment failures
- remediation guidance

The application can use a lexical fallback when embedding-based retrieval is unavailable.

Example status endpoint:

```text
GET /api/rag/stats
```

Example response:

```json
{
  "knowledge_dir": "..\\knowledge_base",
  "chunks": 7,
  "retrieval_mode": "lexical-fallback",
  "embedding_model": null,
  "top_k": 4
}
```

---

# RCA Workflow

RCA receives:

```text
CI logs
+
commit diff
+
retrieved troubleshooting context
```

It then produces:

```text
Root cause
Confidence
Evidence
Likely files
```

For the sample failure:

```text
CI:
assert -1 == 5

Implementation:
return a - b

Expected:
return a + b
```

The RCA identifies the implementation mismatch.

The important architectural rule is:

```text
CI evidence → RCA → supported files
```

rather than:

```text
LLM guess → arbitrary files
```

---

# Fix Generation and Safety

The Fix Agent is constrained to generate a minimal unified diff.

Safety controls include:

## 1. Unified diff validation

The patch must contain valid diff structure.

## 2. File allow-list derived from RCA

Changed implementation files should be supported by the RCA's `likely_files`.

## 3. Test protection

The remediation layer should not allow test files to be modified as part of the candidate fix.

## 4. Isolated application

The patch is applied to a temporary workspace.

## 5. Verification

Changed files are recorded after patch application.

---

# Isolated Validation

The remediation flow uses:

```text
Original repository
       |
       | copy / isolated workspace
       v
Temporary workspace
       |
       v
Apply candidate patch
       |
       v
Run configured test command
```

The original source tree is not directly modified by the remediation execution path.

Typical test command:

```text
python -m pytest -q
```

The result contains:

```text
patch_applied
tests_passed
test_execution_success
exit_code
stdout
stderr
changed_files
workspace
```

---

# Release Decision and HITL

The Release Decision Agent receives:

```text
Original pipeline status
+
RCA
+
Fix
+
Validation
```

Possible decisions:

```text
APPROVED_FOR_RELEASE
HUMAN_REVIEW
REJECTED
```

A proposed patch by itself is not considered proof that the release is safe.

For a failed original pipeline, the system can require:

```text
HUMAN_REVIEW
```

unless the workflow has explicit verified validation evidence supporting a different decision.

The frontend exposes the HITL action:

```text
[ Approve ] [ Reject ]
```

The backend endpoint is:

```text
POST /api/pipelines/{pipeline_id}/decision
```

Example request:

```json
{
  "action": "approve"
}
```

---

# GitHub Actions Integration

The demo repository contains a GitHub Actions workflow:

```text
.github/
└── workflows/
    └── autoheal-ci.yml
```

The workflow executes the project's tests.

For the sample failure:

```text
tests/test_calculator.py::test_add
tests/test_demo.py::test_autoheal_demo
```

The intentionally broken implementation is:

```python
def add(a, b):
    return a - b
```

The calculator test expects:

```python
assert add(2, 3) == 5
```

This creates a reproducible failure for AutoHeal.

---

# Webhook Flow

GitHub sends a `workflow_run` event to:

```text
/api/github/webhook
```

The webhook checks:

```text
event = workflow_run
action = completed
```

Only completed workflow runs are processed for the AutoHeal workflow.

The backend then:

1. Creates a pipeline ID.
2. Reads the GitHub workflow result.
3. Retrieves workflow logs.
4. Retrieves the commit diff.
5. Starts AutoHeal processing.
6. Stores the initial processing state.
7. Updates the stored pipeline result when processing completes.

The webhook uses background processing so GitHub receives a quick HTTP response rather than waiting for the entire AI workflow.

---

# Cloudflare Tunnel

For local webhook development, a temporary public tunnel can expose FastAPI.

Example:

```cmd
cloudflared tunnel --url http://localhost:8000
```

The generated URL can be configured in GitHub:

```text
https://<tunnel-host>/api/github/webhook
```

Keep the tunnel terminal running while testing.

A temporary tunnel URL can change between sessions.

---

# Observability with Arize Phoenix

AutoHeal uses OpenTelemetry-compatible tracing with Arize Phoenix.

Local Phoenix:

```text
http://localhost:6006
```

The application registers a Phoenix tracer provider using:

```python
from phoenix.otel import register
```

The workflow records spans around important operations such as:

```text
pipeline
rag-retrieval
rca
fix
validation
release
```

Conceptually:

```text
AutoHeal Workflow
       |
       +---- Pipeline span
       |
       +---- RAG span
       |
       +---- RCA span
       |
       +---- Fix span
       |
       +---- Validation span
       |
       +---- Release span
```

This allows the workflow to be inspected at the operation level.

---

# RAG Evaluation

The frontend includes a RAG evaluation section.

The evaluation compares RCA behavior:

```text
Without RAG
    vs
With RAG
```

The evaluation reports metrics such as:

- dataset size
- Recall@K
- MRR
- RCA keyword accuracy without RAG
- RCA keyword accuracy with RAG
- improvement delta

Endpoint:

```text
POST /api/evaluation/run
```

The purpose is to measure whether retrieval provides useful additional context rather than assuming that RAG automatically improves the system.

---

# Frontend

The frontend is built using:

```text
React
Vite
Lucide React
```

Current frontend structure:

```text
frontend/
├── src/
│   ├── main.jsx
│   └── styles.css
├── index.html
├── package.json
└── package-lock.json
```

The dashboard provides:

### Control Center

```text
Scenario selector
Run Pipeline
```

### Pipeline Summary

```text
Pipeline
Run ID
Branch
RCA confidence
Validation
Decision
```

### Agent Execution

```text
Pipeline Agent
RAG Retrieval
RCA Agent
Fix Agent
Validation
Release Decision
```

### GitHub Actions

Displays:

```text
Run ID
Branch
Commit
Conclusion
Open GitHub Run
```

### RCA

Displays:

```text
Confidence
Summary
Evidence
Likely files
```

### RAG

Displays retrieved troubleshooting context.

### Fix

Displays the candidate unified diff.

### Validation

Displays:

```text
Patch applied
Test execution
Tests
Exit code
Changed files
Test output
```

### HITL

Displays:

```text
Approve
Reject
```

### RAG Evaluation

Displays the evaluation metrics.

### Phoenix

Provides a link to the local Phoenix UI.

---

# Backend API

The main API surface includes the following logical endpoints.

## Run a local pipeline

```text
POST /api/pipelines/run
```

Example:

```json
{
  "scenario": "test_failure"
}
```

Supported scenarios:

```text
test_failure
dependency_failure
config_failure
deployment_failure
success
```

---

## Get pipeline result

```text
GET /api/pipelines/{pipeline_id}
```

This returns the stored pipeline state/result.

---

## Human decision

```text
POST /api/pipelines/{pipeline_id}/decision
```

Example:

```json
{
  "action": "approve"
}
```

or:

```json
{
  "action": "reject"
}
```

---

## GitHub webhook

```text
POST /api/github/webhook
```

Used by GitHub Actions workflow-run events.

---

## RAG statistics

```text
GET /api/rag/stats
```

Used to inspect retrieval configuration and knowledge-base statistics.

---

## RAG evaluation

```text
POST /api/evaluation/run
```

Runs the configured evaluation dataset.

---

## Remediation gate health

```text
GET /api/gate/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "autoheal-remediation-gate"
}
```

---

# Project Structure

A representative structure is:

```text
autoheal2/
│
├── backend/
│   ├── app/
│   │   ├── gate/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── router.py
│   │   │   └── service.py
│   │   │
│   │   ├── rag/
│   │   │   └── rag_service.py
│   │   │
│   │   ├── services/
│   │   │   ├── workflow.py
│   │   │   ├── github_service.py
│   │   │   ├── remediation_service.py
│   │   │   ├── patch_executor.py
│   │   │   └── isolated_test.py
│   │   │
│   │   └── main.py
│   │
│   ├── knowledge_base/
│   │   └── CI troubleshooting documents
│   │
│   ├── .env
│   └── .venv/
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── package-lock.json
│
├── sample-repo/
│   ├── calculator.py
│   ├── README.md
│   └── tests/
│       ├── test_calculator.py
│       └── test_demo.py
│
├── .github/
│   └── workflows/
│       └── autoheal-remediation-gate.yml
│
└── docs/
    └── CI_CD_REMEDIATION_GATE.md
```

The exact directory structure can evolve as the project grows.

---

# Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Frontend tooling | Vite |
| Icons | Lucide React |
| Backend | FastAPI |
| Agent framework | Google ADK |
| LLM runtime | Ollama |
| LLM | Llama 3.2 |
| RAG | Local retrieval |
| Embeddings | sentence-transformers when available |
| Retrieval fallback | Lexical retrieval |
| CI/CD | GitHub Actions |
| GitHub integration | GitHub REST API + webhook |
| Observability | OpenTelemetry |
| Trace UI | Arize Phoenix |
| Validation | pytest |
| Environment | python-dotenv |
| HTTP | httpx |

---

# Prerequisites

Install:

## Python

Recommended:

```text
Python 3.11+
```

## Node.js

Install a current LTS Node.js release.

Verify:

```cmd
python --version
node --version
npm --version
```

## Ollama

Install Ollama and pull the local model:

```cmd
ollama pull llama3.2
```

Verify:

```cmd
ollama list
```

Start:

```cmd
ollama serve
```

---

# Installation

## 1. Clone the repository

```cmd
git clone https://github.com/Shruti-Gorhe/autoheal2.git
cd autoheal2
```

If the repository is already present:

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2
```

---

# Backend Setup

Open a terminal:

```cmd
cd backend
```

Create a virtual environment:

```cmd
python -m venv .venv
```

Activate:

```cmd
.venv\Scripts\activate
```

Install dependencies:

```cmd
pip install -r requirements.txt
```

Verify:

```cmd
pip check
```

Expected:

```text
No broken requirements found.
```

---

# Frontend Setup

Open another terminal:

```cmd
cd frontend
npm install
```

Start Vite:

```cmd
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# Environment Configuration

Create:

```text
backend/.env
```

Example:

```env
LLM_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

ISOLATED_REPO_PATH=C:\Users\shrut\Downloads\autoheal2\autoheal2\sample-repo
ISOLATED_TEST_COMMAND=python -m pytest -q

GITHUB_TOKEN=<your-token>
GITHUB_OWNER=Shruti-Gorhe
GITHUB_REPO=autoheal-demo-repo
GITHUB_WEBHOOK_SECRET=<your-webhook-secret>
```

## Important

Never commit:

```text
.env
```

Never paste your GitHub token into source code.

A fine-grained GitHub token should be limited to the repository and permissions required by the integration.

---

# Running the System

Use four terminals.

## Terminal 1 — Ollama

```cmd
ollama serve
```

Keep this terminal running.

---

## Terminal 2 — Phoenix

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
python -m phoenix.server.main serve
```

Open:

```text
http://localhost:6006
```

---

## Terminal 3 — FastAPI

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
uvicorn app.main:app
```

Backend:

```text
http://127.0.0.1:8000
```

---

## Terminal 4 — React

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\frontend
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# Testing the Local Pipeline

Open:

```text
http://localhost:5173
```

Select:

```text
Test failure
```

Click:

```text
Run Pipeline
```

The expected conceptual workflow is:

```text
Pipeline
   ↓
RAG
   ↓
RCA
   ↓
Fix
   ↓
Isolated Validation
   ↓
Release Decision
   ↓
HITL
```

For the sample calculator failure, the RCA should identify the subtraction/addition mismatch.

The candidate patch is:

```diff
- return a - b
+ return a + b
```

The isolated test environment should execute the configured pytest command.

---

# Testing the GitHub Webhook

## 1. Start FastAPI

```cmd
uvicorn app.main:app
```

## 2. Start Cloudflare Tunnel

```cmd
cloudflared tunnel --url http://localhost:8000
```

Copy the generated HTTPS URL.

For example:

```text
https://<generated-host>
```

## 3. GitHub webhook URL

Configure:

```text
https://<generated-host>/api/github/webhook
```

## 4. GitHub webhook configuration

In the repository:

```text
Settings
→ Webhooks
→ Add webhook
```

Configure:

```text
Payload URL:
https://<generated-host>/api/github/webhook

Content type:
application/json

Secret:
same value as GITHUB_WEBHOOK_SECRET
```

Select the workflow-run event.

Enable:

```text
Active
```

---

# GitHub Workflow Test

Make a harmless commit to the demo repository.

Example:

```cmd
git status
```

Then:

```cmd
git add .
git commit -m "trigger AutoHeal workflow"
git push origin main
```

GitHub Actions runs.

The webhook receives the workflow-run event.

AutoHeal processes the run.

The frontend can then display the resulting pipeline.

---

# Frontend Workflow

Once the frontend is running:

```text
1. Select scenario
        ↓
2. Click Run Pipeline
        ↓
3. Backend executes workflow
        ↓
4. Result returned
        ↓
5. Dashboard updates
```

For a real GitHub run:

```text
GitHub
  ↓
Webhook
  ↓
Backend
  ↓
Pipeline result
  ↓
Frontend
```

The dashboard can display:

```text
Run ID
Branch
Commit
RCA
RAG
Fix
Validation
Decision
HITL
```

---

# Phoenix Workflow

Start Phoenix:

```cmd
python -m phoenix.server.main serve
```

Open:

```text
http://localhost:6006
```

Run AutoHeal.

Then inspect the corresponding trace/spans in Phoenix.

The goal is to observe the workflow as:

```text
AutoHeal
├── pipeline
├── rag-retrieval
├── rca
├── fix
├── validation
└── release
```

---

# Security and Safety Controls

AutoHeal is designed around several safety boundaries.

## 1. Local LLM

The project uses:

```text
Ollama → Llama 3.2
```

instead of requiring a paid external LLM API.

## 2. GitHub token protection

Tokens belong in `.env`, not source code.

## 3. Test protection

The remediation path should reject patches that attempt to modify tests.

## 4. RCA-supported files

The patch should be restricted to files identified as relevant by RCA.

## 5. Isolated workspace

The candidate patch is applied outside the original working tree.

## 6. Validation before release

A proposed patch is not treated as proof of correctness.

## 7. HITL

Human approval can remain required before release.

## 8. Observability

Agent operations are traced for inspection.

---

# Failure Scenarios

The project can model different failure categories.

## Test failure

Example:

```text
assert -1 == 5
```

Possible cause:

```text
incorrect implementation
```

---

## Dependency failure

Example:

```text
ModuleNotFoundError
```

Possible investigation:

```text
requirements
environment
dependency versions
```

---

## Configuration failure

Example:

```text
missing environment variable
invalid configuration
```

---

## Deployment failure

Example:

```text
deployment command failed
```

The RCA should use the actual logs and retrieved context rather than assuming a single fixed cause.

---

# Example AutoHeal Run

## 1. GitHub Actions failure

```text
FAILED tests/test_calculator.py::test_add
assert -1 == 5

FAILED tests/test_demo.py::test_autoheal_demo
assert 1 == 2
```

---

## 2. RAG

The retrieval stage searches the troubleshooting knowledge base for relevant CI failure information.

---

## 3. RCA

Example result:

```text
Summary:
The add function is performing subtraction instead of addition.

Confidence:
99%

Likely file:
calculator.py
```

---

## 4. Fix

Candidate patch:

```diff
diff --git a/calculator.py b/calculator.py
--- a/calculator.py
+++ b/calculator.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
```

---

## 5. Safety

The system verifies:

```text
Unified diff structure
+
Allowed target file
+
No test modification
```

---

## 6. Isolated validation

The patch is applied in a temporary workspace.

Tests execute:

```text
python -m pytest -q
```

A possible result:

```text
1 passed
1 failed
```

This means:

```text
calculator test → passed
intentional demo test → failed
```

Therefore the entire suite is not considered successful.

---

## 7. Release Decision

The system can return:

```text
HUMAN_REVIEW
```

because the original pipeline was failed and the complete configured test suite did not pass.

---

## 8. Human decision

The dashboard exposes:

```text
Approve
Reject
```

The human can inspect:

```text
RCA
+
Evidence
+
Patch
+
Validation
+
CI Logs
```

before making the decision.

---

# Troubleshooting

## Backend unavailable

Frontend message:

```text
Backend unavailable. Start FastAPI on port 8000.
```

Check:

```cmd
curl http://localhost:8000
```

or open:

```text
http://127.0.0.1:8000
```

---

## Ollama unavailable

Check:

```cmd
ollama list
```

Start:

```cmd
ollama serve
```

Check the model:

```cmd
ollama run llama3.2
```

---

## Phoenix unavailable

Start:

```cmd
python -m phoenix.server.main serve
```

Then open:

```text
http://localhost:6006
```

---

## Frontend blank page

First inspect:

```text
F12
→ Console
```

Look for JavaScript import/runtime errors.

Also run:

```cmd
npm run build
```

---

## GitHub token failure

Check that `.env` contains:

```env
GITHUB_TOKEN=...
GITHUB_OWNER=...
GITHUB_REPO=...
```

Do not print or share the token.

Verify configuration from Python without printing the token:

```cmd
python -c "from app.services.github_service import GitHubService; g=GitHubService(); print('configured:', g.configured()); print('repo:', g.repo_slug)"
```

Expected:

```text
configured: True
repo: Shruti-Gorhe/autoheal-demo-repo
```

---

## RAG fallback mode

If:

```text
retrieval_mode = lexical-fallback
```

the system is still able to retrieve using the configured fallback mechanism.

Check:

```cmd
curl http://localhost:8000/api/rag/stats
```

---

## Patch target does not exist

If validation reports:

```text
Patch target does not exist
```

check:

```text
ISOLATED_REPO_PATH
```

and verify that the isolated workspace actually contains the repository files before patch execution.

---

## GitHub webhook does not process

Check:

1. Cloudflare Tunnel is running.
2. Payload URL is correct.
3. Secret matches `GITHUB_WEBHOOK_SECRET`.
4. Workflow-run events are enabled.
5. GitHub workflow actually completed.
6. FastAPI is running.
7. GitHub token has access to the repository.

---

# Future Improvements

Potential future extensions include:

## Exact commit checkout

Instead of relying only on a configured local repository path, create the isolated workspace from the exact GitHub commit SHA associated with the failed run.

```text
GitHub SHA
    ↓
Fresh isolated checkout
    ↓
Patch
    ↓
Tests
```

This makes remediation reproducible against the exact failing revision.

---

## Pipeline history

Add a persistent run history:

```text
Run ID
Branch
Commit
Status
RCA
Validation
Decision
Timestamp
```

---

## Improved HITL

Add:

```text
Patch preview
RCA evidence
Validation summary
Approve
Reject
Comments
```

---

## Better RAG knowledge base

Expand the troubleshooting knowledge base with:

```text
test failures
dependency failures
Docker failures
configuration failures
deployment failures
GitHub Actions failures
Python failures
Node.js failures
```

---

## Better observability

Add more span attributes:

```text
pipeline_id
github_run_id
commit_sha
branch
scenario
rca_confidence
rag_result_count
changed_files
validation_status
release_decision
```

---

## Persistent state

Move from in-memory state to a persistent store for production-style operation.

Possible local choices include:

```text
SQLite
PostgreSQL
```

---

## More robust remediation

Future remediation can include:

```text
Retry with revised patch
       ↓
Re-run validation
       ↓
Compare validation results
       ↓
Escalate to HITL
```

---

# Limitations

This is an AI-assisted remediation prototype and should not be treated as an unrestricted autonomous production deployment system.

Important limitations include:

- LLM-generated RCA can be incorrect.
- RAG retrieval can return irrelevant context.
- A candidate patch can be syntactically valid but logically incorrect.
- Passing tests do not prove complete correctness.
- Local workspace state may differ from the exact GitHub runner environment.
- The current demo uses a controlled sample repository.
- The GitHub webhook development flow depends on a reachable tunnel.
- In-memory workflow state is not a production persistence solution.
- A real production deployment would require stronger isolation, authentication, authorization, secret management, concurrency control, audit storage, and release controls.

---

# Architecture Summary

The central design can be summarized as:

```text
             CI/CD FAILURE
                   |
                   v
          +------------------+
          | Pipeline Agent   |
          +--------+---------+
                   |
                   v
          +------------------+
          | RAG Retrieval    |
          +--------+---------+
                   |
                   v
          +------------------+
          | RCA Agent        |
          +--------+---------+
                   |
                   v
          +------------------+
          | Fix Agent        |
          +--------+---------+
                   |
                   v
          +------------------+
          | Safety Checks    |
          +--------+---------+
                   |
                   v
          +------------------+
          | Isolated Tests   |
          +--------+---------+
                   |
                   v
          +------------------+
          | Release Decision |
          +--------+---------+
                   |
                   v
          +------------------+
          | HITL Gate        |
          +------------------+

       Observability
              |
              v
        OpenTelemetry
              |
              v
       Arize Phoenix
```

---

# Quick Start

For the shortest path to a working local demo:

### Terminal 1

```cmd
ollama serve
```

### Terminal 2

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
python -m phoenix.server.main serve
```

### Terminal 3

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
uvicorn app.main:app
```

### Terminal 4

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\frontend
npm run dev
```

Open:

```text
Frontend:
http://localhost:5173

Backend:
http://127.0.0.1:8000

Phoenix:
http://localhost:6006
```

Then select:

```text
Test failure
```

and click:

```text
Run Pipeline
```

---

# Project Outcome

AutoHeal CI/CD demonstrates how an AI-assisted DevOps workflow can connect:

```text
CI/CD
  +
GitHub
  +
Multi-Agent AI
  +
RAG
  +
Root Cause Analysis
  +
Code Remediation
  +
Isolated Testing
  +
Release Governance
  +
Human-in-the-Loop
  +
Observability
```

The key architectural idea is not simply to ask an LLM to "fix the error."

Instead, AutoHeal separates the complete lifecycle:

```text
Detect
  ↓
Retrieve
  ↓
Analyze
  ↓
Propose
  ↓
Validate
  ↓
Decide
  ↓
Approve
```

This separation provides clearer evidence, safer remediation boundaries, and a workflow that can be observed and evaluated at each stage.

---

