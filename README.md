# AutoHeal CI/CD — Google ADK + Local Llama 3.2 + RAG + Arize Phoenix

An end-to-end, local-first **multi-agent CI/CD failure diagnosis and remediation system**.

AutoHeal connects GitHub Actions failures to specialized AI agents that collect CI context, retrieve relevant internal knowledge, diagnose the root cause, propose a candidate fix, validate it in isolation, and produce a release decision with Human-in-the-Loop (HITL) controls.

## 1. Technology Stack

| Layer | Technology |
|---|---|
| Agent framework | Google ADK |
| Orchestration | ADK `SequentialAgent` |
| LLM | Llama 3.2 |
| Local model runtime | Ollama |
| LLM integration | LiteLLM |
| Backend | FastAPI |
| Frontend | React + Vite |
| RAG | Sentence Transformers + lexical fallback |
| Knowledge base | Local Markdown |
| Observability | Arize Phoenix |
| Telemetry | OpenTelemetry / OpenInference |
| CI | GitHub Actions |
| Integration | GitHub webhook |
| Validation | Isolated test execution |
| Safety | HITL |
| Cost model | Local-first; no paid LLM API required |

---

## 2. End-to-End Architecture

```text
Developer
   |
   v
GitHub Push / PR
   |
   v
GitHub Actions
   |
   | workflow_run failure
   v
GitHub Webhook
   |
   v
FastAPI Backend :8000
   |
   v
Google ADK SequentialAgent
   |
   +--> Pipeline Agent
   |       |
   |       +--> workflow metadata
   |       +--> real CI logs
   |       +--> commit/diff context
   |
   +--> RAG Agent
   |       |
   |       +--> local runbooks
   |       +--> historical incidents
   |       +--> safety guidance
   |
   +--> RCA Agent
   |       |
   |       +--> Llama 3.2 via Ollama
   |       +--> evidence-based diagnosis
   |
   +--> Fix Agent
   |       |
   |       +--> candidate remediation
   |
   +--> Isolated Testing
   |       |
   |       +--> validate candidate fix
   |
   +--> Release Decision Agent
           |
           +--> risk assessment
           +--> HITL gate
           |
           +--> Approve -> controlled PR/release
           +--> Reject  -> escalate

Observability:
Agents -> OpenTelemetry/OpenInference -> Arize Phoenix :6006

Frontend:
React/Vite :5173 -> FastAPI :8000
```

### Local services

```text
React/Vite       http://localhost:5173
FastAPI          http://localhost:8000
FastAPI Swagger  http://localhost:8000/docs
Ollama           http://localhost:11434
Phoenix          http://localhost:6006
```

---

## 3. Why Google ADK?

The current edition uses **Google ADK, not LangGraph**.

ADK handles:

- agent definitions
- agent instructions
- sequential orchestration
- execution through an ADK Runner/session
- coordination of the specialized agents

The workflow is:

```text
Pipeline Agent
      |
      v
RAG Agent
      |
      v
RCA Agent
      |
      v
Fix Agent
      |
      v
Release Decision Agent
```

The FastAPI layer uses a workflow adapter so the frontend/API can trigger the complete ADK execution without knowing the orchestration internals.

---

## 4. Why Llama 3.2 + Ollama?

The project is designed to avoid a paid hosted LLM.

Runtime:

```text
Google ADK
    |
    v
LiteLLM
    |
    v
Ollama
    |
    v
Llama 3.2
```

Default configuration:

```env
LLM_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

Inference therefore runs locally.

No Gemini/OpenAI/Anthropic API key is required for the intended local LLM flow.

---

## 5. Agents

### 5.1 Pipeline Agent

Collects and normalizes CI failure context.

Inputs may include:

- workflow/pipeline ID
- repository
- workflow status
- failure logs
- commit SHA
- source diff
- failure scenario

Typical questions:

```text
Which workflow failed?
Which job failed?
What is the actual failure message?
Which commit introduced the failure?
Which files changed?
```

Output becomes the context for downstream agents.

### 5.2 RAG Agent

Retrieves relevant project knowledge from:

```text
knowledge_base/
├── runbooks/
├── incidents/
└── docs/
```

Examples:

- CI failure triage
- timeout handling
- health-check failures
- dependency failures
- remediation safety
- architecture/RAG documentation

Flow:

```text
Failure context
      |
      v
Retrieval query
      |
      v
Sentence Transformer embedding
      |
      v
Similarity search
      |
      v
Relevant documents
      |
      v
RCA context
```

A lexical fallback is also available when semantic retrieval is unavailable.

### 5.3 RCA Agent

Combines:

```text
CI logs
+ pipeline context
+ source diff
+ RAG context
```

and uses local Llama 3.2 to produce a structured diagnosis.

Expected reasoning includes:

- likely root cause
- supporting evidence
- confidence
- affected component
- recommended remediation

### 5.4 Fix Agent

Converts the RCA into a **candidate remediation**.

The fix is not treated as automatically trusted production code.

```text
RCA
 |
 v
Fix Agent
 |
 v
Candidate patch
 |
 v
Isolated testing
```

### 5.5 Release Decision Agent

Evaluates the result after candidate remediation.

It considers:

- RCA quality
- candidate fix availability
- isolated test result
- risk
- whether human approval is required

The intended policy is:

```text
AI proposal
    |
    v
Validation
    |
    v
Release decision
    |
    v
HITL when required
    |
    v
Controlled repository action
```

---

## 6. Isolated Testing

Candidate fixes should be tested away from the main production branch.

```text
Candidate Fix
     |
     v
Isolated Workspace
     |
     v
Test Command
     |
   +---+---+
   |       |
 PASS    FAIL
   |       |
   v       v
Release  Escalate
Decision
```

Default:

```env
ISOLATED_TEST_COMMAND=python -m pytest -q
```

This is a key safety boundary.

---

## 7. HITL Safety Model

Recommended enterprise flow:

```text
CI Failure
    |
    v
AI Investigation
    |
    v
Candidate Fix
    |
    v
Isolated Validation
    |
    v
Release Decision
    |
    v
Human Approval
    |
    +--> Approve -> Create PR / controlled release
    |
    +--> Reject  -> Escalate
```

Avoid blindly pushing AI-generated changes directly to `main`.

HITL is especially useful for:

- production changes
- dependency upgrades
- infrastructure changes
- security-sensitive changes
- large source modifications
- low-confidence RCA
- failed validation

---

## 8. Arize Phoenix Observability

Phoenix provides local observability across the agent workflow.

```text
ADK Agents
    |
    v
OpenTelemetry / OpenInference
    |
    v
Phoenix OTEL registration
    |
    v
Arize Phoenix
    |
    v
http://localhost:6006
```

The project traces important operations such as:

- workflow stages
- agent execution
- RAG retrieval
- pipeline processing
- remediation/testing stages

Telemetry resources include metadata such as:

- service name
- service version
- environment
- Phoenix project
- OpenInference project
- configuration fingerprint

For short local executions, immediate exporting is used so traces are visible without waiting for a batch flush.

### What to inspect in Phoenix

After a workflow runs, verify:

```text
Which agent ran?
What was the execution sequence?
How long did each stage take?
Did RAG return results?
Where did the workflow fail?
Which stage produced the release decision?
```

Phoenix should show **real AutoHeal executions**, not just prove that the Phoenix server is running.

---

## 9. Project Structure

```text
autoheal-phoenix/
│
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   └── agents.py
│   │   ├── observability/
│   │   │   └── telemetry.py
│   │   ├── rag/
│   │   │   ├── ingest.py
│   │   │   └── rag_service.py
│   │   ├── services/
│   │   │   ├── github_service.py
│   │   │   ├── isolated_test.py
│   │   │   ├── llm_service.py
│   │   │   └── workflow.py
│   │   └── main.py
│   │
│   ├── evaluation/
│   │   ├── dataset.jsonl
│   │   ├── evaluate.py
│   │   └── __init__.py
│   ├── phoenix_smoke.py
│   ├── tests.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── pages/
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   └── index.html
│
├── knowledge_base/
│   ├── runbooks/
│   │   ├── ci-failure-triage.md
│   │   └── remediation-safety.md
│   ├── incidents/
│   │   ├── incident-timeout.md
│   │   ├── incident-health-check.md
│   │   └── incident-dependency.md
│   └── docs/
│       ├── rag.md
│       └── architecture.md
│
├── sample-repo/
│   ├── README.md
│   └── tests/
│       └── test_demo.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── autoheal-demo.yml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── REAL_FLOW.md
│   ├── PHOENIX_TRACING.md
│   └── ADK_MIGRATION.md
│
├── scripts/
│   └── start_phoenix.ps1
│
└── README.md
```

---

## 10. Important Backend Files

### `backend/app/main.py`

FastAPI entry point.

Responsibilities:

- FastAPI application
- API endpoints
- workflow requests
- GitHub webhook
- invoking the AutoHeal workflow
- returning workflow results

### `backend/app/services/workflow.py`

ADK orchestration adapter.

Conceptually:

```python
root_agent = SequentialAgent(
    name="autoheal_workflow",
    sub_agents=[
        pipeline_agent,
        rag_retrieval_agent,
        rca_agent,
        fix_agent,
        release_decision_agent,
    ],
)
```

It uses ADK components such as:

```python
Agent
SequentialAgent
Runner
InMemorySessionService
LiteLlm
```

### `backend/app/agents/agents.py`

Contains the specialized agent behavior.

### `backend/app/rag/rag_service.py`

Handles retrieval, similarity ranking, formatting, and fallback.

### `backend/app/rag/ingest.py`

Prepares the local knowledge base.

### `backend/app/services/llm_service.py`

Model-facing service layer.

### `backend/app/services/github_service.py`

GitHub workflow metadata/log/diff integration.

### `backend/app/services/isolated_test.py`

Candidate remediation validation.

### `backend/app/observability/telemetry.py`

Phoenix/OpenTelemetry initialization and tracing.

---

## 11. Environment Variables

Create a `.env` file from:

```text
backend/.env.example
```

Important values:

```env
LLM_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

PHOENIX_PROJECT=autoheal-cicd
PHOENIX_ENDPOINT=http://localhost:6006

ADK_ENABLED=true

GITHUB_TOKEN=
GITHUB_OWNER=
GITHUB_REPO=
GITHUB_WEBHOOK_SECRET=

ISOLATED_REPO_PATH=
ISOLATED_TEST_COMMAND=python -m pytest -q
```

Never commit secrets.

---

## 12. Windows Setup

From CMD:

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
python -m venv .venv
.venv\Scripts\activate
```

Verify:

```cmd
pip check
```

Expected:

```text
No broken requirements found.
```

Verify ADK:

```cmd
python -c "from google.adk.agents import Agent, SequentialAgent; print('ADK OK')"
```

Verify LiteLLM:

```cmd
python -c "import litellm; print('LiteLLM OK')"
```

Verify Phoenix:

```cmd
python -c "import phoenix; print('Phoenix OK')"
```

---

## 13. Ollama Setup

Start:

```cmd
ollama serve
```

Check models:

```cmd
ollama list
```

Expected:

```text
llama3.2
```

If necessary:

```cmd
ollama pull llama3.2
```

The local endpoint is:

```text
http://localhost:11434
```

---

## 14. Start Phoenix

Open a dedicated CMD:

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
python -m phoenix.server.main serve
```

Open:

```text
http://localhost:6006
```

Keep this terminal open.

For the browser, use `localhost:6006`; `0.0.0.0:6006` is not the normal browser address.

---

## 15. Start FastAPI

Open another CMD:

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

---

## 16. Start React

Open another CMD:

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## 17. Four-Terminal Local Runtime

### Terminal 1 — Ollama

```cmd
ollama serve
```

### Terminal 2 — Phoenix

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
python -m phoenix.server.main serve
```

### Terminal 3 — FastAPI

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

### Terminal 4 — React

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\frontend
npm run dev
```

---

## 18. GitHub Actions Workflow

A representative CI workflow:

```yaml
name: AutoHeal CI

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run tests
        run: |
          cd backend
          pytest -q
```

This supplies the real CI failure that AutoHeal investigates.

---

## 19. GitHub Webhook Workflow

Real integration:

```text
Developer Push
      |
      v
GitHub Actions
      |
      v
workflow_run event
      |
      v
GitHub webhook
      |
      v
POST /api/github/webhook
      |
      v
Pipeline Agent
      |
      v
RAG -> RCA -> Fix -> Test -> Release Decision
```

The webhook can provide:

- workflow metadata
- status
- failure logs
- commit SHA
- commit diff
- repository information

---

## 20. Local GitHub Webhook

GitHub cannot directly call:

```text
localhost:8000
```

from the public internet.

For local development, use an HTTPS tunnel.

Conceptually:

```text
GitHub
   |
   | HTTPS
   v
Public Tunnel
   |
   v
localhost:8000
   |
   v
FastAPI
```

A free temporary Cloudflare Tunnel can be used.

Webhook endpoint:

```text
<public-tunnel-url>/api/github/webhook
```

Use:

```env
GITHUB_WEBHOOK_SECRET=<secret>
```

and validate the webhook signature.

---

## 21. Complete Development Workflow

```text
1. Start Ollama
        |
2. Start Phoenix
        |
3. Start FastAPI
        |
4. Start React
        |
5. Open frontend
        |
6. Trigger CI failure
        |
7. Receive GitHub workflow event
        |
8. Pipeline Agent collects real context
        |
9. RAG retrieves knowledge
        |
10. RCA diagnoses failure
        |
11. Fix Agent creates candidate remediation
        |
12. Isolated test validates candidate
        |
13. Release Decision evaluates risk
        |
14. HITL approves/rejects when required
        |
15. Controlled PR/release
        |
16. Inspect Phoenix traces
```

---

## 22. Failure Scenarios

The knowledge base covers examples such as:

### Timeout

```text
CI timeout
   |
   v
Pipeline Agent
   |
   v
Timeout runbook
   |
   v
RCA
   |
   v
Candidate fix
```

### Health check

```text
Health check returns 503
   |
   v
Health-check incident
   |
   v
RCA
   |
   v
Remediation
```

### Dependency

```text
Import/dependency failure
   |
   v
Dependency incident
   |
   v
RCA
   |
   v
Candidate dependency remediation
```

---

## 23. Testing Strategy

### Environment

```cmd
pip check
```

Must return:

```text
No broken requirements found.
```

### Package checks

```cmd
python -c "from google.adk.agents import Agent, SequentialAgent; print('ADK OK')"
```

```cmd
python -c "import litellm; print('LiteLLM OK')"
```

```cmd
python -c "import phoenix; print('Phoenix OK')"
```

### API

Open:

```text
http://localhost:8000/docs
```

Use Swagger to inspect and exercise the available endpoints.

### RAG

Test queries such as:

```text
pytest timed out while waiting for health endpoint
```

```text
health check returned 503
```

```text
dependency import failed after package upgrade
```

Verify that relevant local knowledge is retrieved.

### Agent workflow

Verify execution order:

```text
Pipeline
  -> RAG
  -> RCA
  -> Fix
  -> Release Decision
```

### Phoenix

Run a real workflow, then inspect:

```text
http://localhost:6006
```

Verify traces/spans for the workflow.

---

## 24. Evaluation

The evaluation directory is:

```text
backend/evaluation/
├── dataset.jsonl
├── evaluate.py
└── __init__.py
```

Useful evaluation dimensions:

| Dimension | Question |
|---|---|
| RCA accuracy | Did the agent identify the likely cause? |
| Evidence | Was the diagnosis grounded in failure evidence? |
| Retrieval | Was relevant knowledge returned? |
| Fix quality | Is the remediation relevant? |
| Validation | Did the candidate pass isolated tests? |
| Safety | Was risky action gated? |
| Decision | Was the release decision justified? |

RAG should be evaluated on relevance and usefulness to RCA, not merely whether it returns text.

---

## 25. Observability Evaluation

Phoenix should help answer:

```text
What happened?
Which agent handled it?
In what order?
How long did each stage take?
Did RAG retrieve useful context?
Where did execution fail?
What release decision was produced?
```

This makes observability a first-class part of the system.

---

## 26. Configuration Fingerprint

The telemetry resource includes a configuration fingerprint.

Concept:

```text
Configuration
     |
     v
Fingerprint
     |
     v
OTel resource attribute
     |
     v
Phoenix trace
```

This helps distinguish executions produced under different:

- prompts
- model settings
- agent configuration
- retrieval configuration
- application configuration

---

## 27. Security

Never commit:

```text
.env
GITHUB_TOKEN
GITHUB_WEBHOOK_SECRET
```

Use minimum GitHub permissions.

Validate GitHub webhook signatures.

Use HTTPS for the public webhook.

Do not automatically execute untrusted AI-generated changes against production.

Prefer:

```text
Candidate Fix
    |
    v
Isolated Test
    |
    v
HITL
    |
    v
Pull Request
    |
    v
Review / Merge
```

---

## 28. Why This Is Agentic AI

This is not a single:

```text
User -> LLM -> Answer
```

system.

It is a coordinated multi-agent workflow:

```text
Pipeline Agent
       |
       v
RAG Agent
       |
       v
RCA Agent
       |
       v
Fix Agent
       |
       v
Release Decision Agent
       |
       v
HITL
```

Each agent has a focused responsibility.

The system also combines:

```text
Agent reasoning
+
Tool/data retrieval
+
CI execution
+
Validation
+
Governance
+
Observability
```

---

## 29. Why RAG Matters

The model receives project-specific information through retrieval:

```text
Current CI logs
      +
Source diff
      +
Internal runbooks
      +
Historical incidents
      +
Model reasoning
      =
Grounded RCA
```

This is more appropriate for enterprise engineering support than relying only on generic model knowledge.

---

## 30. Why Observability Matters

Agentic workflows can fail inside individual stages.

Instead of only seeing:

```text
Workflow failed
```

you want:

```text
Pipeline Agent
     |
     | context collection
     v
RAG Agent
     |
     | retrieval
     v
RCA Agent
     |
     | diagnosis
     v
Fix Agent
     |
     | candidate remediation
     v
Release Decision
```

Phoenix provides a trace-oriented view of this execution.

---

## 31. Demo / Presentation Flow

### Step 1
Start:

```text
Ollama
Phoenix
FastAPI
React
```

### Step 2
Open:

```text
http://localhost:5173
```

### Step 3
Trigger a representative CI failure.

### Step 4
Show GitHub Actions failure.

### Step 5
Show AutoHeal receiving the workflow event.

### Step 6
Show Pipeline Agent extracting logs/context.

### Step 7
Show RAG retrieving relevant runbook/incident.

### Step 8
Show RCA Agent diagnosis.

### Step 9
Show Fix Agent candidate remediation.

### Step 10
Show isolated validation.

### Step 11
Show Release Decision/HITL.

### Step 12
Open:

```text
http://localhost:6006
```

and show the corresponding Phoenix trace.

---

## 32. Suggested Technical Explanation

> AutoHeal CI/CD is a multi-agent CI/CD remediation system built using Google ADK. GitHub Actions provides the real pipeline failure context. The Pipeline Agent collects logs and metadata, the RAG Agent retrieves relevant runbooks and historical incidents from a local knowledge base, and the RCA Agent uses locally hosted Llama 3.2 through Ollama to diagnose the failure. The Fix Agent generates a candidate remediation, which is validated in an isolated environment. The Release Decision Agent then evaluates the result and routes risky changes through human approval. Arize Phoenix with OpenTelemetry provides observability across the agent workflow.

---

## 33. Current ADK vs Previous LangGraph Edition

The earlier project used LangGraph.

Current edition:

```text
Google ADK
   |
   +-- SequentialAgent
          |
          +-- Pipeline Agent
          +-- RAG Agent
          +-- RCA Agent
          +-- Fix Agent
          +-- Release Decision Agent
```

The surrounding architecture remains:

```text
FastAPI
RAG
Ollama
Llama 3.2
GitHub
Phoenix
HITL
```

---

## 34. Success Checklist

The system is ready when:

- [ ] Ollama is running
- [ ] `llama3.2` is available
- [ ] ADK imports successfully
- [ ] LiteLLM imports successfully
- [ ] Phoenix imports successfully
- [ ] `pip check` reports no broken requirements
- [ ] Phoenix runs on `localhost:6006`
- [ ] FastAPI runs on `localhost:8000`
- [ ] Swagger opens at `/docs`
- [ ] React runs on `localhost:5173`
- [ ] RAG retrieves relevant knowledge
- [ ] ADK workflow executes
- [ ] Llama 3.2 responds through Ollama
- [ ] Phoenix receives workflow telemetry
- [ ] Candidate fixes are isolated/tested
- [ ] Release decisions can require HITL
- [ ] GitHub Actions produces realistic failure context
- [ ] GitHub webhook can trigger AutoHeal

---

## 35. Quick Start

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
uvicorn app.main:app --reload
```

### Terminal 4

```cmd
cd C:\Users\shrut\Downloads\autoheal2\autoheal2\frontend
npm run dev
```

Open:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
Swagger:  http://localhost:8000/docs
Phoenix:  http://localhost:6006
Ollama:   http://localhost:11434
```

---

## 36. Final System

```text
                       DEVELOPER
                           |
                           v
                      GitHub Push
                           |
                           v
                  +------------------+
                  | GitHub Actions   |
                  | CI / Tests       |
                  +--------+---------+
                           |
                         failure
                           |
                           v
                  +------------------+
                  | GitHub Webhook   |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | FastAPI Backend  |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  | Google ADK       |
                  | SequentialAgent |
                  +--------+---------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
      Pipeline            RAG              RCA
       Agent             Agent            Agent
          |                |                |
          +----------------+----------------+
                           |
                           v
                       Fix Agent
                           |
                           v
                  Isolated Testing
                           |
                    +------+------+
                    |             |
                   PASS          FAIL
                    |             |
                    v             v
             Release Decision   Escalate
                    |
                    v
                   HITL
                    |
              +-----+-----+
              |           |
           Approve       Reject
              |
              v
          Create PR
              |
              v
        Controlled merge

Observability:
Agents -> OpenTelemetry -> Phoenix :6006
```

## Design Principle

```text
Detect
  ↓
Understand
  ↓
Retrieve knowledge
  ↓
Diagnose
  ↓
Propose
  ↓
Validate
  ↓
Decide
  ↓
Human approval
  ↓
Controlled release
```

This provides an agentic CI/CD remediation workflow while keeping the system local-first, observable, testable, and safety-gated.
