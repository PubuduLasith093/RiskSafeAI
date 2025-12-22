"""
Test script for RiskSafeAI deployment
Tests both local and AWS endpoints
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()


def test_pinecone_connection():
    """Test Pinecone vector database connection"""
    print("\n" + "="*60)
    print("TEST 1: Pinecone Connection")
    print("="*60)

    try:
        api_key = os.getenv('PINECONE_API_KEY')
        if not api_key:
            print("❌ PINECONE_API_KEY not found in .env")
            return False

        pc = Pinecone(api_key=api_key)
        index = pc.Index("asic-compliance-rag")
        stats = index.describe_index_stats()

        print(f"✅ Pinecone Connected Successfully!")
        print(f"   Index Name: asic-compliance-rag")
        print(f"   Total Vectors: {stats.total_vector_count:,}")
        print(f"   Dimension: {stats.dimension}")
        print(f"   Namespaces: {stats.namespaces if hasattr(stats, 'namespaces') else 'default'}")

        if stats.total_vector_count == 0:
            print("⚠️  WARNING: Index has 0 vectors. Upload ASIC documents first!")
            return False

        if stats.dimension != 3072:
            print(f"⚠️  WARNING: Expected dimension 3072, got {stats.dimension}")
            return False

        return True

    except Exception as e:
        print(f"❌ Pinecone connection failed: {str(e)}")
        return False


def test_openai_key():
    """Test OpenAI API key"""
    print("\n" + "="*60)
    print("TEST 2: OpenAI API Key")
    print("="*60)

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not found in .env")
        return False

    if not api_key.startswith('sk-'):
        print("❌ Invalid OpenAI API key format (should start with 'sk-')")
        return False

    print(f"✅ OpenAI API key found: {api_key[:10]}...{api_key[-5:]}")
    return True


def test_tavily_key():
    """Test Tavily API key"""
    print("\n" + "="*60)
    print("TEST 3: Tavily API Key")
    print("="*60)

    api_key = os.getenv('TAVILY_API_KEY')
    if not api_key:
        print("❌ TAVILY_API_KEY not found in .env")
        return False

    if not api_key.startswith('tvly-'):
        print("❌ Invalid Tavily API key format (should start with 'tvly-')")
        return False

    print(f"✅ Tavily API key found: {api_key[:10]}...{api_key[-5:]}")
    return True


def test_health_endpoint(base_url):
    """Test /health endpoint"""
    print("\n" + "="*60)
    print(f"TEST 4: Health Endpoint - {base_url}")
    print("="*60)

    try:
        response = requests.get(f"{base_url}/health", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {data}")
            return True
        else:
            print(f"❌ Health check failed!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"❌ Connection failed - is the server running at {base_url}?")
        return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False


def test_react_agent_endpoint(base_url):
    """Test /react/obligation_register endpoint"""
    print("\n" + "="*60)
    print(f"TEST 5: ReAct Agent Endpoint - {base_url}")
    print("="*60)

    query = "Generate obligation register for fintech personal loans business"

    print(f"Query: {query}")
    print("Sending request... (this may take 30-60 seconds)")

    try:
        response = requests.post(
            f"{base_url}/react/obligation_register",
            json={"query": query},
            timeout=120  # 2 minutes timeout
        )

        if response.status_code == 200:
            data = response.json()

            print(f"✅ ReAct agent executed successfully!")
            print(f"\nMetadata:")
            print(f"   Iterations: {data['metadata']['iterations']}")
            print(f"   Chunks Retrieved: {data['metadata']['chunks_retrieved']}")
            print(f"   Regulators Covered: {data['metadata']['regulators_covered']}")
            print(f"   Grounding Score: {data['metadata']['grounding_score']:.2f}")
            print(f"   Confidence: {data['metadata']['confidence']:.2f}")
            print(f"   Completeness Checked: {data['metadata']['completeness_checked']}")
            print(f"   Citations Validated: {data['metadata']['citations_validated']}")

            if data['metadata'].get('warnings'):
                print(f"\n⚠️  Warnings: {len(data['metadata']['warnings'])}")
                for warning in data['metadata']['warnings']:
                    print(f"      - {warning}")

            if data['metadata'].get('errors'):
                print(f"\n❌ Errors: {len(data['metadata']['errors'])}")
                for error in data['metadata']['errors']:
                    print(f"      - {error}")

            print(f"\nAnswer Preview (first 300 chars):")
            print(f"{data['answer'][:300]}...")

            # Save full answer
            with open('test_answer.md', 'w', encoding='utf-8') as f:
                f.write(data['answer'])
            print(f"\n📄 Full answer saved to: test_answer.md")

            return True
        else:
            print(f"❌ ReAct agent failed!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timeout (>2 minutes) - ReAct agent may be stuck")
        return False
    except Exception as e:
        print(f"❌ ReAct agent error: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("   RiskSafeAI Deployment Test Suite")
    print("="*60)

    # Test 1: Environment variables
    results = {
        "Pinecone Connection": test_pinecone_connection(),
        "OpenAI API Key": test_openai_key(),
        "Tavily API Key": test_tavily_key(),
    }

    # Test 2: Local endpoint (if specified)
    local_url = "http://localhost:8000"
    if len(sys.argv) > 1 and sys.argv[1] == "--skip-local":
        print(f"\nℹ️  Skipping local tests (--skip-local flag)")
    else:
        results["Health Endpoint (Local)"] = test_health_endpoint(local_url)
        if results["Health Endpoint (Local)"]:
            results["ReAct Agent (Local)"] = test_react_agent_endpoint(local_url)

    # Test 3: AWS endpoint (if specified)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        aws_url = sys.argv[1]
        print(f"\nℹ️  Testing AWS endpoint: {aws_url}")
        results["Health Endpoint (AWS)"] = test_health_endpoint(aws_url)
        if results["Health Endpoint (AWS)"]:
            results["ReAct Agent (AWS)"] = test_react_agent_endpoint(aws_url)

    # Summary
    print("\n" + "="*60)
    print("   TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} | {test_name}")

    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)

    if passed == total:
        print("\n🎉 All tests passed! RiskSafeAI is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    print("""
Usage:
  python test_deployment.py                           # Test local only
  python test_deployment.py --skip-local              # Skip local tests
  python test_deployment.py <aws-alb-url>            # Test local + AWS
  python test_deployment.py --skip-local <aws-url>   # Test AWS only

Examples:
  python test_deployment.py
  python test_deployment.py http://risksafeai-alb-123.us-east-1.elb.amazonaws.com
    """)

    sys.exit(main())
