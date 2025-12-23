import os
import sys
import json
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

# Load env variables including API keys
load_dotenv()

try:
    from compliance_chat.src.react_agent.agent import ReactAgent
except ImportError:
    print("Could not import ReactAgent. Make sure you are running this from the root directory 'd:\\Deltone Solutions\\scraping\\RiskSafeAI'")
    sys.exit(1)

def run_test():
    query = "Generate a comprehensive obligation register for a Fintech company offering Small Amount Credit Contracts (SACC) in Australia. Include all responsible lending, prohibited fees, and conduct obligations."
    
    print(f"Initializing Agent...")
    try:
        agent = ReactAgent()
    except Exception as e:
        print(f"Failed to initialize agent. Check your .env file for OPENAI_API_KEY and PINECONE_API_KEY")
        print(f"Error: {e}")
        return

    print(f"\nRunning Query: {query}")
    result = agent.run(query)
    
    print("\n" + "="*80)
    print("FINAL ANSWER JSON:")
    print("="*80)
    
    # Handle Dict or String result
    answer = result.get("answer")
    if isinstance(answer, dict):
        print(json.dumps(answer, indent=2))
    elif isinstance(answer, str):
        try:
            print(json.dumps(json.loads(answer), indent=2))
        except:
            print(answer)
    else:
        print(answer)

    if result.get("error"):
        print(f"\nERROR: {result.get('error')}")

if __name__ == "__main__":
    run_test()
