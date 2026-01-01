
from typing import List, Literal
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from ..config import llm_gpt4o
from ..models import ComplianceState, ConfidenceLevel, CertaintyLevel

# ============================================================================
# AGENT 15: Safety Validator
# ============================================================================

final_safety_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a final safety validator and human review packager.

SAFETY CHECKS (ALL must pass):
1. ✓ Grounding complete 2. ✓ No legal advice 3. ✓ Confidence appropriate
4. ✓ No PII 5. ✓ Applicability clear 6. ✓ No contradictions 7. ✓ Conservative bias

HUMAN REVIEW TRIGGERS:
- Confidence < 0.90 → MUST REVIEW
- Contradictions detected → MUST REVIEW
- Novel/unusual → SHOULD REVIEW
- High-impact → SHOULD REVIEW

Output safety validation and review packages."""),
    ("user", """OBLIGATIONS TO VALIDATE (sample):
{obligations_sample}

TRUST FLAGS:
{trust_flags}

Perform final safety checks and create review packages.""")
])

class FinalSafetyValidation(BaseModel):
    all_checks_passed: bool
    failed_checks: List[str]
    review_required_count: int
    high_priority_reviews: List[str]
    medium_priority_reviews: List[str]
    action: Literal["APPROVE", "REVIEW_REQUIRED", "BLOCK"]

final_safety_chain = final_safety_prompt | llm_gpt4o.with_structured_output(FinalSafetyValidation)

def safety_validator_and_packager(state: ComplianceState) -> ComplianceState:
    """Agent 15: Final safety validation and human review preparation"""
    print("\n" + "="*80)
    print("AGENT 15: SAFETY VALIDATOR & HUMAN REVIEW PACKAGER")
    print("="*80)
    
    canonical_obligations = state["canonical_obligations"]
    trust_flags = state.get("trust_flags", [])
    
    # Sample
    obligations_sample = "\n\n".join([
        f"[{i+1}] {obl.obligation_statement} (Conf: {obl.confidence_score:.2f})"
        for i, obl in enumerate(canonical_obligations[:10])
    ])
    
    try:
        safety_check = final_safety_chain.invoke({
            "obligations_sample": obligations_sample,
            "trust_flags": str(trust_flags)
        })
        
        print(f"\n[FINAL SAFETY CHECK] Action: {safety_check.action}")
        
        # Package reviews
        review_packages = []
        for obl in canonical_obligations:
            needs_review = (
                obl.confidence_score < 0.90 or
                obl.confidence_level in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW] or
                not obl.trust_validation.grounding_validated
            )
            
            if needs_review:
                package = {
                    "obligation_id": obl.obligation_id,
                    "reason": [],
                    "suggested_action": "REVIEW"
                }
                if obl.confidence_score < 0.90: package["reason"].append(f"Low confidence {obl.confidence_score:.2f}")
                review_packages.append(package)
        
        state["review_packages"] = review_packages
        
        if safety_check.action == "BLOCK":
            state["should_continue"] = False
            state["errors"].append("BLOCKED: Final safety checks failed")
            state["final_output"] = []
        else:
            state["final_output"] = canonical_obligations
            
        print(f"  Approved: {len(state['final_output'])}")
        print(f"  Review Pkgs: {len(review_packages)}")
        
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Final safety check failed: {str(e)}")
        state["final_output"] = canonical_obligations
        return state
