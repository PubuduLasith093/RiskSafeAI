
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path so we can import compliance_chat
current_dir = Path.cwd()
sys.path.append(str(current_dir))

# Load environment variables
load_dotenv()

def main():
    print("----------------------------------------------------------------")
    print("RiskSafeAI - Enterprise Compliance System - Local Test")
    print("----------------------------------------------------------------")
    
    try:
        print("[1/3] Importing Orchestrator...")
        # Import the new orchestrator
        from compliance_chat.app.orchestrator import EnterpriseComplianceOrchestrator
        
        print("[2/3] Initializing System (Loading Agents & Models)...")
        orchestrator = EnterpriseComplianceOrchestrator()
        
        query = "I want to launch a Buy Now Pay Later (BNPL) product in Australia. What are the key licensing requirements?"
        print(f"\n[3/3] Running Test Query: '{query}'")
        print("      (This may take 30-60 seconds to run through all 15 agents)...")
        
        # execution
        result = orchestrator.run_enterprise_compliance_system(query)
        
        # Check results
        final_obligations = result.get("final_obligations", [])
        review_packages = result.get("review_packages", [])
        errors = result.get("errors", [])
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        if errors:
            print(f"\nErrors Encountered ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")
        
        print(f"\nTotal Obligations Found: {len(final_obligations)}")
        print(f"Review Packages: {len(review_packages)}")
        
        if final_obligations:
            print("\n--- Sample Obligation [1] ---")
            obl = final_obligations[0]
            print(f"Statement: {obl.obligation_statement}")
            print(f"Source: {obl.source_grounding.legal_instrument} ({obl.source_grounding.section_clause})")
            print(f"Confidence: {obl.confidence_level} ({obl.confidence_score})")

        print("\n✅ System is functioning correctly.")

    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}")
        print("Make sure you have installed dependencies:")
        print("  pip install -r requirements.txt")
        print("  (Especially 'scikit-learn', 'numpy', 'pinecone-client')")
    except Exception as e:
        print(f"\n❌ RUNTIME ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
