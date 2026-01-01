---
description: How to deploy the new Enterprise Compliance System
---

# Deploy Enterprise Compliance System

## 1. Prerequisites
Ensure you have the following API keys in your `.env` file (or AWS Secrets Manager for production):
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `TAVILY_API_KEY` (Optional)
- `COHERE_API_KEY` (Optional)

## 2. Install Dependencies
The new system requires `scikit-learn` and `numpy`.

```bash
pip install -r requirements.txt
```

## 3. Verify Assets
Ensure the BM25 encoder is present in the app directory:
- `compliance_chat/app/bm25_encoder.pkl`

If missing, it must be generated or copied from `research/output/`.

## 4. Run the Application
Start the FastAPI server:

```bash
python main.py
```

## 5. Usage
- **UI**: Navigate to `http://localhost:8000`
- **API**: POST to `http://localhost:8000/api/obligations` with JSON `{"query": "your query"}`

## 6. Architecture Overview
The system uses 15 agents organized in `compliance_chat/app/agents/`:
1.  **Understanding**: `planning.py` (Agents 1-3)
2.  **Retrieval**: `retrieval.py` (Agents 4-5) - Uses Hybrid RAG
3.  **Trust**: `trust.py` (Agents 6-8) - Posture & Safety
4.  **Extraction**: `extraction.py` (Agents 9-11)
5.  **Normalization**: `normalization.py` (Agents 12-13)
6.  **Applicability**: `applicability.py` (Agent 14)
7.  **Validation**: `validation.py` (Agent 15)

The workflow is defined in `compliance_chat/app/graph.py` and orchestrated by `compliance_chat/app/orchestrator.py`.
