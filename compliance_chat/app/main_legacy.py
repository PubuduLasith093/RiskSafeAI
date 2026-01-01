from typing import Dict, List
import json
from pathlib import Path
from .graph import compliance_workflow
from .models import Obligation

# Cell 15: Orchestrator Class

class ObligationRegisterOrchestrator:
    """
    Main orchestrator for the multi-agent system
    """

    def __init__(self):
        self.workflow = compliance_workflow

    def generate_obligation_register(self, query: str) -> Dict:
        """
        Generate complete obligation register from user query
        """
        print("\n" + "#"*80)
        print("# STARTING MULTI-AGENT OBLIGATION REGISTER GENERATION")
        print("#"*80)
        print(f"\nQuery: {query}")

        # Initialize state
        initial_state = {
            "query": query,
            "product_context": None,
            "plan": [],
            "current_task_index": 0,
            "iteration": 0,
            "all_chunks": [],
            "raw_obligations": [],
            "obligations": [],
            "validation_results": [],
            "web_verification": {},
            "expert_review": None,
            "final_answer": "",
            "should_continue": True,
            "errors": []
        }

        # Run workflow
        try:
            final_state = self.workflow.invoke(initial_state)

            # Format output (FIXED)
            output = {
                "product_type": final_state["product_context"].product_type if final_state.get("product_context") else "Unknown",
                "obligations": [obl.model_dump() for obl in final_state.get("obligations", [])],
                "summary": {
                    "total_obligations": len(final_state.get("obligations", [])),
                    "by_regulator": self._count_by_regulator(final_state.get("obligations", [])),
                    "by_confidence": self._count_by_confidence(final_state.get("obligations", []))
                },
                "verification": {
                    "validation_results": final_state.get("validation_results", []),  # Already dicts
                    "expert_review": final_state["expert_review"].model_dump() if final_state.get("expert_review") else None
                },
                "metadata": {
                    "chunks_retrieved": len(final_state.get("all_chunks", [])),
                    "plan_tasks": len(final_state.get("plan", [])),
                    "errors": final_state.get("errors", [])
                }
            }

            print("\n" + "#"*80)
            print("# WORKFLOW COMPLETE")
            print("#"*80)
            print(f"\n✓ Generated {len(final_state.get('obligations', []))} obligations")
            print(f"✓ Retrieved {len(final_state.get('all_chunks', []))} source chunks")

            if final_state.get("expert_review"):
                print(f"✓ Expert Grade: {final_state['expert_review'].overall_grade}")

            return output

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "obligations": [],
                "product_type": "Unknown"
            }

    def _count_by_regulator(self, obligations: List[Obligation]) -> Dict[str, int]:
        """Count obligations by regulator"""
        from collections import Counter
        if not obligations:
            return {}
        # obligations is a list of Obligation objects here? 
        # wait, final_state.get("obligations") returns list of Obligation objects.
        return dict(Counter([o.regulator for o in obligations]))

    def _count_by_confidence(self, obligations: List[Obligation]) -> Dict[str, int]:
        """Count by confidence score ranges"""
        if not obligations:
            return {}
        high = sum(1 for o in obligations if o.confidence_score >= 0.9)
        medium = sum(1 for o in obligations if 0.8 <= o.confidence_score < 0.9)
        low = sum(1 for o in obligations if o.confidence_score < 0.8)
        return {
            "High (≥0.9)": high,
            "Medium (0.8-0.89)": medium,
            "Low (<0.8)": low
        }

if __name__ == "__main__":
    # Example usage
    orchestrator = ObligationRegisterOrchestrator()
    query = "Provide obligation register for a fintech company focusing on home loans"
    result = orchestrator.generate_obligation_register(query)
    
    # Save output
    outputs_dir = Path("output")
    outputs_dir.mkdir(exist_ok=True)
    with open(outputs_dir / "result.json", "w") as f:
        json.dump(result, f, indent=2)
    print("✓ Result saved to output/result.json")
