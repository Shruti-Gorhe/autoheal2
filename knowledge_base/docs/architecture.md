# AutoHeal architecture knowledge

AutoHeal is a four-agent CI/CD recovery workflow. The Pipeline Agent interprets GitHub Actions results. The RCA Agent analyzes pipeline evidence. The Fix Agent proposes and validates a patch in isolation. The Release Decision Agent determines whether the result should be deployed or sent to human review.

The RAG pipeline sits between pipeline collection and root-cause analysis. It retrieves relevant incidents, runbooks, and project documentation and injects those results into the RCA prompt. This grounds the LLM in project-specific operational knowledge.

OpenTelemetry instruments the webhook and agent spans so latency, decisions, confidence, and validation outcomes can be correlated with a pipeline trace.
