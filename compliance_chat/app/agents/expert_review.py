from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..config import llm_gpt4o
from ..models import AgentState, ExpertReview

# Cell 14: Agent 10 - Expert Review (UPDATED)

expert_review_prompt_template = """You are a Senior Compliance Officer with 15+ years experience.

Review this obligation register for a {product_type} client.

Total Obligations: {total_obligations}

Sample Obligations (first 10):
{sample_obligations}

REVIEW TASKS:
1. Is this complete for {product_type}?
2. Any critical obligations missing?
3. Overall grade (A-F)?
4. Confidence level (0-1)?

Output JSON:
{{
  "overall_grade": "A",
  "confidence_level": 0.90,
  "is_complete": true,
  "is_fit_for_purpose": true,
  "missing_obligations": [],
  "priority_corrections": [],
  "implementation_roadmap": [
    {{"phase": "Phase 1", "obligations": ["Obtain ACL"], "focus": "Licensing"}}
  ],
  "regulatory_intelligence": ["ASIC focus on responsible lending 2024-2025"],
  "red_flags": [],
  "recommendations": ["Prioritize ACL application"],
  "expert_notes": "Good coverage of core obligations"
}}"""

def expert_review_agent(state: AgentState) -> AgentState:
    """
    Agent 10: Simulate expert compliance officer review (UPDATED)
    """
    print("\n" + "="*80)
    print("AGENT 10: EXPERT REVIEW")
    print("="*80)

    obligations = state["obligations"]

    if not obligations:
        print("No obligations to review")
        state["expert_review"] = None
        return state

    # Prepare sample obligations (using NEW fields)
    sample_obligations = "\n".join([
        f"{i+1}. {o.obligation_name}\n" +
        f"   Document: {o.document_name} {o.document_subsection}\n" +
        f"   Regulator: {o.regulator}\n" +
        f"   Confidence: {o.confidence_score:.2f}"
        for i, o in enumerate(obligations[:10])
    ])

    prompt = PromptTemplate(
        template=expert_review_prompt_template,
        input_variables=["product_type", "total_obligations", "sample_obligations"]
    )

    chain = prompt | llm_gpt4o | JsonOutputParser()

    try:
        result = chain.invoke({
            "product_type": state["product_context"].product_type,
            "total_obligations": len(obligations),
            "sample_obligations": sample_obligations
        })

        state["expert_review"] = ExpertReview(**result)

        print(f"✓ Expert Review Complete")
        print(f"  Grade: {result['overall_grade']}")
        print(f"  Confidence: {result['confidence_level']:.2f}")
        print(f"  Fit for Purpose: {result['is_fit_for_purpose']}")

    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Expert review failed: {str(e)}")
        state["expert_review"] = None

    return state
