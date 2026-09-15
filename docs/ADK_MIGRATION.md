# AutoHeal CI/CD — Google ADK Edition

This version replaces LangGraph orchestration with **Google Agent Development Kit (ADK)** while keeping the local-first design: Llama 3.2 via Ollama, local RAG, FastAPI, GitHub Actions, and Arize Phoenix.

```text
GitHub Actions / Frontend
          |
          v
       FastAPI
          |
          v
   ADK SequentialAgent
          |
   +------+------+------+------+
   |      |      |      |      |
Pipeline RAG    RCA    Fix   Release
          |                    |
          v                    v
     Local RAG              HITL
```

ADK is the orchestration framework. LiteLLM connects ADK agents to the local Ollama server, so the project can remain ₹0 and does not require Gemini.

## Run

1. Start Ollama: `ollama serve`
2. Ensure `llama3.2` exists: `ollama pull llama3.2`
3. Start Phoenix: `python -m phoenix.server.main serve`
4. Install backend dependencies: `pip install -r requirements.txt`
5. Start FastAPI: `uvicorn app.main:app --reload`
6. Start frontend: `npm run dev`
