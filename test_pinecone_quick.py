import os
from pinecone import Pinecone

# Load from .env manually
env_path = "D:\\Deltone Solutions\\scraping\\RiskSafeAI\\.env"
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key and value:
            os.environ[key] = value

# Test Pinecone connection
api_key = os.getenv("PINECONE_API_KEY")
print(f"Using API key: {api_key[:10]}...")

try:
    pc = Pinecone(api_key=api_key)

    # List indexes
    indexes = pc.list_indexes()
    print(f"\nSUCCESS: Pinecone connection successful!")
    print(f"Available indexes: {[idx.name for idx in indexes]}")

    # Check for asic-compliance-rag index
    index_name = "asic-compliance-rag"
    index_names = [idx.name for idx in indexes]

    if index_name in index_names:
        print(f"\nSUCCESS: Found index: {index_name}")
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        print(f"Index stats: {stats}")
    else:
        print(f"\nWARNING: Index '{index_name}' not found. Available: {index_names}")

except Exception as e:
    print(f"\nERROR: Pinecone connection failed: {e}")
