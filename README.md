# RiskSafeAI

**RiskSafeAI** is a compliance-focused document chat assistant powered by Retrieval-Augmented Generation (RAG). Built with FastAPI, LangChain, and Pinecone, it enables users to upload compliance documents and chat with them using advanced LLM capabilities.

## Features

- **Document Upload & Indexing**: Upload PDF, DOCX, and TXT files with automatic chunking and vector indexing to Pinecone
- **RAG-Powered Chat**: Conversational Q&A using context-aware retrieval with MMR (Maximal Marginal Relevance)
- **Session Management**: Isolated sessions using Pinecone namespaces with persistent chat history
- **LLM Support**: Google Gemini and Groq models
- **Cloud Vector DB**: Pinecone for scalable, serverless vector storage
- **Production-Ready**: Dockerized deployment to AWS ECS Fargate with CI/CD via GitHub Actions
- **Structured Logging**: JSON-formatted logs with structlog
- **Test Coverage**: Unit and integration tests with pytest

## Project Structure

```
RiskSafeAI/
├── compliance_chat/          # Main application package
│   ├── config/               # Configuration files
│   ├── exception/            # Custom exception handling
│   ├── logger/               # Structured logging
│   ├── model/                # Pydantic models
│   ├── prompts/              # LLM prompt templates
│   ├── src/
│   │   ├── document_ingestion/  # Document loading & Pinecone indexing
│   │   └── document_chat/       # RAG retrieval & chat logic
│   └── utils/                # Utilities (config, file I/O, model loading)
├── .github/workflows/        # CI/CD pipelines
├── static/                   # Frontend CSS
├── templates/                # HTML templates
├── tests/                    # Test suite
├── Dockerfile                # Container definition
├── main.py                   # FastAPI application
└── requirements.txt          # Python dependencies
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://astral.sh/uv) (recommended) or pip
- Docker (for containerization)
- AWS account (for ECS deployment)
- Pinecone account (for vector database)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd RiskSafeAI
   ```

2. **Set up Pinecone**:
   - Create a free account at [Pinecone](https://www.pinecone.io/)
   - Create a new index named `risksafeai-index`
   - Set dimension to `768` (matches Google text-embedding-004)
   - Choose your preferred region (e.g., `us-east-1`)

3. **Create `.env` file** with your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key
   GOOGLE_API_KEY=your_google_api_key
   PINECONE_API_KEY=your_pinecone_api_key
   LLM_PROVIDER=google
   ```

4. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

5. **Update configuration** (optional):
   Edit [compliance_chat/config/config.yaml](compliance_chat/config/config.yaml) to customize:
   - Pinecone index name and environment
   - Embedding model settings
   - LLM provider and model

6. **Run locally**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Access the app**:
   Open [http://localhost:8000](http://localhost:8000)

## Docker Build

```bash
docker build -t risksafeai:latest .
docker run -p 8080:8080 --env-file .env risksafeai:latest
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=compliance_chat
```

## AWS ECS Deployment

### Prerequisites

1. Create an ECR repository: `risksafeai-repo`
2. Create ECS cluster: `risksafeai-cluster`
3. Create ECS service: `risksafeai-service`
4. Store API keys in AWS Secrets Manager
5. Update `.github/workflows/task_definition.json` with your AWS account ID

### GitHub Actions Setup

Add these secrets to your GitHub repository:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

Push to `main` branch to trigger CI/CD:
1. **CI Pipeline**: Runs tests
2. **Build & Push**: Builds Docker image and pushes to ECR
3. **Deploy**: Updates ECS service with new task definition

## API Endpoints

### `GET /health`
Health check endpoint

### `POST /upload`
Upload documents for indexing
- **Request**: Multipart form data with files
- **Response**: `{ "session_id": "...", "indexed": true, "message": "..." }`

### `POST /chat`
Chat with uploaded documents
- **Request**: `{ "session_id": "...", "message": "..." }`
- **Response**: `{ "answer": "..." }`

## Configuration

Edit [compliance_chat/config/config.yaml](compliance_chat/config/config.yaml) to customize:
- **Pinecone**: Index name, environment, dimension
- **Embedding model**: Google Text Embedding 004 (768 dimensions)
- **LLM provider**: Gemini 2.0 Flash or Groq
- **Retrieval parameters**: MMR, top-k, fetch-k, lambda_mult

## Architecture

1. **Document Ingestion**: Files → Chunking → Embeddings → Pinecone (namespaced by session)
2. **Retrieval**: User Query → Context Retrieval (MMR) → LLM Response
3. **Session Management**: Pinecone namespaces + in-memory chat history
4. **Deployment**: Docker → ECR → ECS Fargate → ALB

## Pinecone Setup

### Local Development
1. Create a Pinecone account at https://www.pinecone.io/
2. Create an index with these settings:
   - **Name**: `risksafeai-index`
   - **Dimensions**: `768`
   - **Metric**: `cosine`
   - **Cloud**: AWS (or your preference)
   - **Region**: `us-east-1` (or your preference)

### Production (AWS Secrets Manager)
Store API keys in AWS Secrets Manager as JSON:
```json
{
  "GROQ_API_KEY": "your_groq_key",
  "GOOGLE_API_KEY": "your_google_key",
  "PINECONE_API_KEY": "your_pinecone_key"
}
```

## License

MIT License

## Contributing

Pull requests are welcome! Please ensure tests pass before submitting.

## Support

For issues or questions, please open a GitHub issue.
