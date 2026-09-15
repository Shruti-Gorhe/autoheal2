import hashlib
import json
import logging
import os
from pathlib import Path
from contextlib import contextmanager

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except ImportError:
    OTLPSpanExporter = None

logger = logging.getLogger("autoheal")

# Load project .env before reading telemetry settings.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:
    pass


def _fingerprint(config: dict) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def setup_telemetry():
    service_name = os.getenv("OTEL_SERVICE_NAME", "autoheal-cicd")
    service_version = os.getenv("OTEL_SERVICE_VERSION", "1.0.0")
    phoenix_project = os.getenv("PHOENIX_PROJECT_NAME", "autoheal-cicd")
    endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces").rstrip("/")

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.getenv("APP_ENV", "local"),
        "telemetry.backend": "phoenix",
        "phoenix.project.name": phoenix_project,
        "openinference.project.name": phoenix_project,
        "config.fingerprint": _fingerprint({
            "llm.provider": os.getenv("LLM_PROVIDER", "ollama"),
            "llm.model": os.getenv("LLM_MODEL", "llama3.2"),
            "workflow": "v1",
        }),
    })

    # Use Phoenix's supported OTEL registration helper. It configures the
    # Phoenix-aware exporter and project association for the local collector.
    # batch=False is intentional for this local demo so every span is sent
    # immediately and short evaluation runs cannot exit before export.
    try:
        from phoenix.otel import register

        tracer_provider = register(
            project_name=phoenix_project,
            endpoint=endpoint,
            batch=False,
            auto_instrument=False,
            verbose=True,
        )
        tracer = tracer_provider.get_tracer("autoheal-cicd")
        logger.info("Phoenix OTEL tracing enabled: %s (project=%s)", endpoint, phoenix_project)
    except Exception as exc:
        logger.exception("Phoenix tracing could not be configured: %s", exc)
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        tracer = trace.get_tracer("autoheal-cicd")

    # Metrics remain local/in-process. Phoenix is used as the tracing backend.
    meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter("autoheal-cicd")

    agent_invocations = meter.create_counter(
        "autoheal.agent.invocations",
        description="Number of AutoHeal agent invocations",
    )
    agent_errors = meter.create_counter(
        "autoheal.agent.errors",
        description="Number of AutoHeal agent errors",
    )
    agent_duration = meter.create_histogram(
        "autoheal.agent.duration_ms",
        unit="ms",
        description="Agent execution duration in milliseconds",
    )
    llm_calls = meter.create_counter(
        "autoheal.llm.calls",
        description="Number of LLM calls",
    )
    llm_duration = meter.create_histogram(
        "autoheal.llm.duration_ms",
        unit="ms",
        description="LLM call duration in milliseconds",
    )

    return tracer, meter, {
        "agent_invocations": agent_invocations,
        "agent_errors": agent_errors,
        "agent_duration": agent_duration,
        "llm_calls": llm_calls,
        "llm_duration": llm_duration,
    }


tracer, meter, telemetry_metrics = setup_telemetry()


@contextmanager
def agent_span(agent_name: str, **attrs):
    import time

    start = time.perf_counter()
    telemetry_metrics["agent_invocations"].add(1, {"agent.name": agent_name})
    with tracer.start_as_current_span(agent_name) as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute(
            "openinference.span.kind",
            "LLM" if agent_name == "llm-call" else ("RETRIEVER" if agent_name == "rag-retrieval" else "CHAIN"),
        )
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, str(value))
        try:
            yield span
        except Exception as exc:
            telemetry_metrics["agent_errors"].add(1, {"agent.name": agent_name})
            span.record_exception(exc)
            span.set_attribute("error.type", type(exc).__name__)
            logger.exception("Agent failed: %s", agent_name)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("agent.duration_ms", duration_ms)
            logger.info("Agent completed: %s duration_ms=%.2f", agent_name, duration_ms)
            telemetry_metrics["agent_duration"].record(
                duration_ms, {"agent.name": agent_name}
            )
            if agent_name == "llm-call":
                model = os.getenv("LLM_MODEL", "llama3.2")
                telemetry_metrics["llm_calls"].add(1, {"llm.model": model})
                telemetry_metrics["llm_duration"].record(
                    duration_ms, {"llm.model": model}
                )
