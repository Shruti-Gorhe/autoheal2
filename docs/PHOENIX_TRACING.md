# Phoenix Tracing

AutoHeal uses OpenTelemetry to send traces to Arize Phoenix. Phoenix is the observability layer for the multi-agent workflow.

## Start Phoenix locally

For this Windows setup, install/run Phoenix with Python if `uvx` is unavailable:

```powershell
pip install arize-phoenix
python -m phoenix.server.main serve
```

Alternatively, if `uvx` is installed:


```powershell
uvx arize-phoenix serve
```

Open `http://localhost:6006`. Keep this terminal running and open `http://localhost:6006`.

The AutoHeal exporter uses an immediate local OTLP span processor so short evaluation runs are exported before the process exits.

## Configure AutoHeal

In `backend/.env`:

```env
PHOENIX_ENABLED=true
PHOENIX_PROJECT_NAME=autoheal-cicd
PHOENIX_ENDPOINT=http://localhost:6006/v1/traces
PHOENIX_API_KEY=
OTEL_CONSOLE_EXPORTER=true
```

Start the backend after Phoenix is running:

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

## What you will see

A real run appears as a trace with spans for:

```text
workflow
├── github-webhook (when triggered from GitHub)
├── pipeline-agent
├── rag-retrieval
├── rca-agent
│   └── llm-call
├── fix-agent
│   └── llm-call
├── isolated-test
└── release-agent
```

The existing application code creates these spans using OpenTelemetry, so Phoenix is not tied to the LLM vendor.

## Optional Phoenix Cloud

If you later use Phoenix Cloud, keep the same application instrumentation and change the endpoint/API key in `.env`. Phoenix OTLP trace ingestion uses a `/v1/traces` endpoint. Do not commit the API key.

## Troubleshooting

- If the backend starts but Phoenix is empty, confirm Phoenix is running on port `6006`.
- Confirm `PHOENIX_ENABLED=true`.
- Confirm `PHOENIX_ENDPOINT=http://localhost:6006/v1/traces`.
- Keep `OTEL_CONSOLE_EXPORTER=true` so you can still see spans in the backend terminal.


## Troubleshooting empty traces

This project uses `phoenix.otel.register(..., batch=False)` with the local OTLP HTTP endpoint `http://localhost:6006/v1/traces`. The `.env` file is loaded from `backend/.env`. To smoke-test tracing independently of the agents, run from `backend`:

```powershell
python phoenix_smoke.py
```

Then refresh the `autoheal-cicd` project in Phoenix.
