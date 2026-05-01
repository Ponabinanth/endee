# Personal RAG Chatbot

A standalone Retrieval Augmented Generation chatbot for your own documents. It runs locally with deterministic embeddings and extractive answers, and it can use OpenAI for richer grounded responses when `OPENAI_API_KEY` is configured.

## Features

- Upload TXT, Markdown, PDF, and DOCX documents
- Chunk documents with overlap
- Embed chunks into a local vector index
- Ask questions and receive cited answers
- Stream chat responses
- List and delete indexed documents
- React + TypeScript frontend
- FastAPI backend with OpenAPI docs
- Docker-ready project structure

## Project Structure

```text
rag-chatbot/
  backend/
    app/
      main.py              FastAPI routes
      document_loader.py   File parsing and chunking
      embeddings.py        Local deterministic embedding backend
      vector_store.py      JSON-persisted local vector store
      rag_chain.py         Retrieval + answer generation
      schemas.py           API models
      config.py            Environment settings
    tests/
  frontend/
    src/
  data/
  logs/
```

## Backend Setup

```powershell
cd rag-chatbot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open API docs at `http://127.0.0.1:8000/docs`.

## Frontend Setup

```powershell
cd rag-chatbot\frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## API Quick Test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Upload documents from the web UI or use `/docs` to call `POST /upload`.
For script-based testing without multipart uploads, use `POST /ingest` with JSON:

```json
{
  "files": [
    {
      "filename": "runbook.txt",
      "content": "Rollback is required when production alerts fire."
    }
  ]
}
```

## Production Notes

- Use the local vector store for demos and small corpora.
- Swap `vector_store.py` for Pinecone, Weaviate, or Chroma when you need managed persistence and scale.
- Set `OPENAI_API_KEY` to enable LLM-generated grounded answers.
- Keep uploaded documents and `data/index.json` out of Git.
- Add authentication before deploying with private documents.
