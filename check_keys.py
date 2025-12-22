import os
from dotenv import load_dotenv

def check_keys():
    load_dotenv()
    keys = ["OPENAI_API_KEY", "PINECONE_API_KEY", "TAVILY_API_KEY", "COHERE_API_KEY"]
    for k in keys:
        val = os.getenv(k)
        if val:
            print(f"{k}: FOUND (starts with {val[:5]}...)")
        else:
            print(f"{k}: MISSING")

if __name__ == "__main__":
    check_keys()
