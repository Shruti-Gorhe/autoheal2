import asyncio

from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.genai import types


async def main():
    model = LiteLlm(
        model="ollama/llama3.2",
        api_base="http://localhost:11434",
    )

    request = LlmRequest(
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text="Reply with exactly: ADK_OK")
                ],
            )
        ]
    )

    async for response in model.generate_content_async(request):
        print(response)


asyncio.run(main())