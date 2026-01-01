
from typing import Dict, Any, List
from datetime import datetime

from .models import ComplianceState, ConfidenceLevel
from .graph import build_enterprise_compliance_workflow

class EnterpriseComplianceOrchestrator:
    def __init__(self):
        self.workflow = build_enterprise_compliance_workflow()

    def _transform_obligation(self, obl) -> Dict[str, Any]:
        """Transform internal EnterpriseObligation to client-facing format"""
        # Handle Pydantic models vs dicts interaction if needed, assuming obl is Object here
        return {
            "obligation_id": obl.obligation_id,
            "statement": obl.obligation_statement,
            "source": {
                "regulator": obl.source_grounding.regulator,
                "instrument": obl.source_grounding.legal_instrument,
                "section": obl.source_grounding.section_clause,
                "excerpt": obl.source_grounding.verbatim_excerpt
            },
            "type": obl.obligation_type.value if hasattr(obl.obligation_type, "value") else str(obl.obligation_type),
            "action_type": obl.action_type.value if hasattr(obl.action_type, "value") else str(obl.action_type),
            "confidence": {
                "level": obl.confidence_level.value if hasattr(obl.confidence_level, "value") else str(obl.confidence_level),
                "score": obl.confidence_score
            },
            "applicability": {
                "rules": obl.applicability_rules,
                "entity_types": obl.applicability_factors.entity_type,
                "products": obl.applicability_factors.product_service
            },
            "plain_english": obl.plain_english_explanation
        }

    def run_enterprise_compliance_system(self, user_query: str) -> Dict[str, Any]:
        """
        Main entry point for the enterprise compliance system
        """
        print("=" * 100)
        print("ENTERPRISE COMPLIANCE OBLIGATION SYSTEM")
        print("=" * 100)
        print(f"\nQuery: {user_query}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize state
        initial_state: ComplianceState = {
            "user_query": user_query,
            "query_context": None,
            "plan": [],
            "plan_validated": False,
            "chunks": [],
            "trust_check_passed": False,
            "trust_flags": [],
            "_detected_obligations": [],
            "obligations": [],
            "clustered_obligations": [],
            "canonical_obligations": [],
            "review_packages": [],
            "final_output": [],
            "errors": [],
            "should_continue": True
        }
        
        try:
            # Execute workflow
            result = self.workflow.invoke(initial_state)
            
            print("\n" + "=" * 100)
            print("EXECUTION COMPLETE")
            print("=" * 100)
            
            # Extract results
            final_obligations = result.get("final_output", [])
            review_packages = result.get("review_packages", [])
            errors = result.get("errors", [])
            
            # Statistics
            total_obligations = len(final_obligations)
            high_confidence = sum(1 for o in final_obligations if o.confidence_level == ConfidenceLevel.HIGH)
            medium_confidence = sum(1 for o in final_obligations if o.confidence_level == ConfidenceLevel.MEDIUM)
            low_confidence = sum(1 for o in final_obligations if o.confidence_level == ConfidenceLevel.LOW)
            
            print(f"\n[RESULTS SUMMARY]")
            print(f"  Total Obligations: {total_obligations}")
            print(f"  HIGH confidence: {high_confidence}")
            print(f"  MEDIUM confidence: {medium_confidence}")
            print(f"  LOW confidence: {low_confidence}")
            
            # Transform obligations to match client-facing structure
            transformed_obligations = [self._transform_obligation(obl) for obl in final_obligations]
            
            return {
                "final_obligations": transformed_obligations,
                "review_packages": review_packages,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_obligations": total_obligations,
                    "high_confidence_count": high_confidence,
                    "medium_confidence_count": medium_confidence,
                    "low_confidence_count": low_confidence
                },
                "errors": errors
            }
            
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
