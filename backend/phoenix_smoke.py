from app.observability.telemetry import agent_span

print("Sending Phoenix smoke-test span...")
with agent_span("phoenix-smoke-test", test="true") as span:
    span.set_attribute("test.message", "AutoHeal Phoenix tracing is connected")
print("Smoke-test span sent. Refresh Phoenix -> Tracing -> autoheal-cicd.")
