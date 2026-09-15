# RAG pipeline

The local RAG pipeline ingests Markdown and text files from `knowledge_base/`, chunks them, creates local semantic embeddings with `all-MiniLM-L6-v2` when `sentence-transformers` is available, and retrieves the top relevant chunks for each pipeline failure.

For a zero-cost fallback, retrieval uses a deterministic lexical cosine-style overlap score. This means the application remains runnable even if the embedding model cannot be downloaded.

The retrieved context is supplied to the RCA Agent along with real GitHub Actions logs and the commit diff. RAG is retrieval augmentation; Gemini remains the generator/reasoner.
