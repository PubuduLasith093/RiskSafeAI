#!/bin/bash

# RiskSafeAI Quick Start Script
# This script sets up and runs RiskSafeAI locally

echo "========================================="
echo "   RiskSafeAI Local Setup"
echo "========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and add your API keys:"
    echo "   cp .env.example .env"
    echo "   Edit .env and add: OPENAI_API_KEY, PINECONE_API_KEY, TAVILY_API_KEY"
    exit 1
fi

echo "✅ .env file found"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || venv\Scripts\activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "========================================="
echo "   Testing Pinecone Connection"
echo "========================================="

# Test Pinecone
python -c "
import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

try:
    pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
    index = pc.Index('asic-compliance-rag')
    stats = index.describe_index_stats()
    print(f'✅ Pinecone connected!')
    print(f'   Index: asic-compliance-rag')
    print(f'   Vectors: {stats.total_vector_count:,}')
    print(f'   Dimension: {stats.dimension}')
except Exception as e:
    print(f'❌ Pinecone connection failed: {e}')
    exit(1)
"

echo ""
echo "========================================="
echo "   Starting RiskSafeAI Server"
echo "========================================="
echo ""
echo "Server will start at: http://localhost:8000"
echo ""
echo "Test with:"
echo "  curl http://localhost:8000/health"
echo ""
echo "Or generate obligation register:"
echo '  curl -X POST http://localhost:8000/react/obligation_register \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"query": "Generate obligation register for fintech personal loans"}'"'"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

# Run server
python main.py
