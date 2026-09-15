import json
import os
from typing import Any

import httpx

from app.observability.telemetry import agent_span


class LLMService:
    """Provider-independent LLM service.

    Default provider is Ollama with Llama 3.2 running locally. The agents do not
    depend on a specific model vendor, so the model can be changed via .env.
    """

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.model = os.getenv("LLM_MODEL", "llama3.2")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))

    @property
    def configured(self) -> bool:
        if self.provider == "ollama":
            return bool(self.model and self.base_url)
        return False

    def generate(self, prompt: str) -> str:
        if not self.configured:
            return ""

        with agent_span(
            "llm-call",
            **{
                "llm.provider": self.provider,
                "llm.model": self.model,
            },
        ) as span:
            try:
                span.set_attribute("llm.request.model", self.model)
                span.set_attribute("input.value", prompt[-12000:])
                if self.provider == "ollama":
                    response = httpx.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    text = response.json().get("response", "")
                    span.set_attribute("llm.response_available", bool(text))
                    span.set_attribute("output.value", text[-12000:])
                    return text.strip()
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("llm.error", str(exc)[:500])
                return ""

        return ""

    def structured_rca(
        self,
        logs: str,
        diff: str,
        metadata: dict[str, Any],
        rag_context: str = "",
    ) -> dict[str, Any]:
        prompt = f"""
You are the Root Cause Analysis agent in a CI/CD recovery system.
Analyze the GitHub Actions failure using the evidence below.
Return ONLY valid JSON with these keys: summary, confidence, evidence, likely_files.
confidence must be a number between 0 and 1.
evidence must be an array of concise strings.
likely_files must be an array of file paths.

PIPELINE METADATA:
{metadata}

GITHUB ACTIONS LOGS:
{logs[-30000:]}

COMMIT DIFF:
{diff[-20000:]}

RETRIEVED RAG KNOWLEDGE:
{rag_context[-16000:]}
"""
        text = self.generate(prompt)
        if not text:
            return {}
        try:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception:
            return {
                "summary": text,
                "confidence": 0.7,
                "evidence": [],
                "likely_files": [],
            }

    def generate_patch(self, rca: dict[str, Any], logs: str, diff: str) -> str:
        prompt = f"""
You are a careful remediation engineer.
Create the smallest safe unified diff that could fix the CI failure.
Return ONLY a git-compatible unified diff, beginning with --- and +++.
Do not invent files. Prefer changing existing project code/tests/configuration.
If there is not enough evidence for a safe patch, return an empty response.

ROOT CAUSE:
{rca}

LOGS:
{logs[-16000:]}

RECENT DIFF:
{diff[-12000:]}
"""
        return self.generate(prompt)


llm = LLMService()
