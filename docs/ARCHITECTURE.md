# Architecture

React frontend -> FastAPI -> Google ADK -> Pipeline/RCA/Fix/Release agents.

All agent nodes create OpenTelemetry spans. The default exporter sends traces to a local Arize Phoenix instance for zero-cost local development, while the console exporter remains enabled for debugging.

## Production-hardening checklist
- Add authentication and authorization.
- Store GitHub credentials in GitHub Secrets or a secret manager.
- Never send secrets or sensitive source code into telemetry.
- Validate generated patches in an isolated environment.
- Require human approval before destructive actions.
- Add real GitHub webhook ingestion.
- Add persistent run storage.


## RAG layer

The RAG retrieval node runs after the Pipeline Agent and before RCA. It uses the current scenario, real workflow logs, and commit diff as a query against the local `knowledge_base/`. Retrieved incident/runbook/document chunks are passed to Llama 3.2 as grounded context through the provider-independent LLM service. The RAG layer is intentionally local and provider-independent for a ₹0 personal project.


## Model vs telemetry

Llama 3.2 is the local reasoning model and runs through Ollama. OpenTelemetry is independent of the model and records the execution of the agents and LLM calls. This lets the project use Llama locally while Phoenix provides AI/agent-focused tracing.
