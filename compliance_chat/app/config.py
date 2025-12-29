import os
import pickle
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pinecone import Pinecone
from tavily import TavilyClient
import cohere
from openai import OpenAI

# Load environment variables
# Assuming .env is in project root (RiskSafeAI)
# This file is in compliance_chat/app/config.py -> ../../../.env
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY not found in .env")

# Initialize API clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
cohere_client = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None

# Initialize LangChain models
llm_gpt4o = ChatOpenAI(model="gpt-4o", temperature=0, api_key=OPENAI_API_KEY)
llm_gpt4o_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=OPENAI_API_KEY)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=OPENAI_API_KEY)

# Pinecone index
INDEX_NAME = "asic-compliance-rag-new"
pinecone_index = pc.Index(INDEX_NAME)

# Load BM25 encoder for hybrid search
# Pickle is at compliance_chat/research/output/bm25_encoder.pkl
# From here: ../research/output/bm25_encoder.pkl
bm25_path = Path(__file__).parent / "bm25_encoder.pkl"
bm25_encoder = None
if bm25_path.exists():
    with open(bm25_path, "rb") as f:
        bm25_encoder = pickle.load(f)
    print("✓ BM25 encoder loaded")
else:
    print(f"Warning: BM25 encoder not found at {bm25_path}")
