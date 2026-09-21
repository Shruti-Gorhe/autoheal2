import asyncio

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


APP_NAME = "adk_test"
USER_ID = "test-user"
SESSION_ID = "test-session"


model = LiteLlm(
    model="ollama/llama3.2",
    api_base="http://localhost:11434",
)

agent = Agent(
    name="test_agent",
    model=model,
    instruction="Reply with exactly: ADK and Ollama are working.",
)

session_service = InMemorySessionService()

runner = Runner(
    agent=agent,
    app_name=APP_NAME,
    session_service=session_service,
)


async def main():
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={},
    )

    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text="Test the local Llama model."
            )
        ],
    )

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    print("ADK RESPONSE:", part.text)


if __name__ == "__main__":
    asyncio.run(main())