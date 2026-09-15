"""Rebuild the local RAG index.

Usage:
    python -m app.rag.ingest
"""
from app.rag.rag_service import rag

if __name__ == "__main__":
    print(rag.refresh())
