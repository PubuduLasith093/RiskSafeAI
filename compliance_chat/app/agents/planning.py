from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..config import llm_gpt4o
from ..models import AgentState, PlanItem

# Cell 5: Agent 2 - Planning Agent

# Product-specific regulatory sources mapping
PRODUCT_SOURCES = {
    "home_loans": [
        "RG 209 - Responsible lending conduct",
        "NCCP Act ss128-133 - Responsible lending obligations",
        "RG 274 - Design and distribution obligations (DDO)",
        "RG 206 - Credit licensing",
        "RG 165 - Licensing: Internal and external dispute resolution",
        "RG 78 - Breach reporting"
    ],
    "personal_loans": [
        "RG 209 - Responsible lending conduct",
        "NCCP Act - Consumer credit obligations",
        "RG 274 - DDO",
        "SACC provisions (if <$2000)"
    ]
}

# Mandatory topics per product
MANDATORY_TOPICS = {
    "home_loans": [
        "ACL license requirement",
        "Responsible lending assessment",
        "Unsuitable credit prohibition",
        "Target Market Determination (TMD)",
        "Credit Guide disclosure",
        "Breach reporting obligations",
        "Hardship provisions",
        "Privacy notice",
        "AFCA membership",
        "Financial requirements"
    ]
}

planning_prompt_template = """User Query: "{query}"

Product Context:
- Product Type: {product_type}
- Business Model: {business_model}
- License Required: {license_required}

You are an Expert Compliance Planner for Australian Financial Services.
Your goal is to break down this request into a logical series of RESEARCH TASKS using the compliance taxonomy.

COMPLIANCE TAXONOMY (7 Categories):
1. **Licensing:** License requirements, fit & proper person, org competence, financial resources
2. **Conduct:** Responsible lending, conflicts of interest, best interests duty
3. **Disclosure:** Product disclosure, credit guide, warnings
4. **Reporting:** Breach reporting, significant events, financial reporting
5. **Design & Distribution:** Target market determinations (TMD), product governance
6. **Governance:** Risk management, compliance frameworks, training, AFCA
7. **Prohibitions:** Unsuitable credit, misleading conduct, disqualifications

PRODUCT-SPECIFIC SOURCES FOR {product_type}:
{product_sources}

MANDATORY TOPICS TO COVER:
{mandatory_topics}

TASK GENERATION RULES:
1. Create 10-15 granular research tasks
2. Cover ALL 7 compliance categories
3. Each task must specify regulatory source and keywords
4. Prioritize "Must Do" and "Must Not Do" obligations

Output a JSON object with this structure:
{{
  "plan": [
    {{
      "id": 1,
      "category": "Licensing",
      "task": "Search for ACL license requirements in RG 206",
      "topic_keywords": ["Australian Credit License", "ACL application"],
      "regulatory_sources": ["RG 206", "NCCP Act s29"],
      "priority": "Critical"
    }},
    ...
  ]
}}
"""

planning_prompt = PromptTemplate(
    template=planning_prompt_template,
    input_variables=["query", "product_type", "business_model", "license_required", "product_sources", "mandatory_topics"]
)

planning_chain = planning_prompt | llm_gpt4o | JsonOutputParser()

def planning_agent(state: AgentState) -> AgentState:
    """
    Agent 2: Generate comprehensive research plan
    """
    print("\n" + "="*80)
    print("AGENT 2: PLANNING")
    print("="*80)
    
    product_context = state["product_context"]
    product_type = product_context.product_type
    
    # Get product-specific sources
    sources = PRODUCT_SOURCES.get(product_type, PRODUCT_SOURCES.get("home_loans"))
    topics = MANDATORY_TOPICS.get(product_type, MANDATORY_TOPICS.get("home_loans"))
    
    try:
        result = planning_chain.invoke({
            "query": state["query"],
            "product_type": product_type,
            "business_model": product_context.business_model,
            "license_required": ", ".join(product_context.license_class_required),
            "product_sources": "\n".join([f"- {s}" for s in sources]),
            "mandatory_topics": "\n".join([f"- {t}" for t in topics])
        })
        
        # Convert to PlanItem objects
        # Check if 'plan' exists, if not assume list?
        plan_list = result.get("plan", [])
        plan = [PlanItem(**item) for item in plan_list]
        
        print(f"Generated {len(plan)} research tasks:")
        for item in plan:
            print(f"  {item.id}. [{item.category}] {item.task}")
        
        state["plan"] = plan
        state["current_task_index"] = 0
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Planning failed: {str(e)}")
        # Fallback plan
        state["plan"] = [
            PlanItem(
                id=1,
                category="General",
                task="Search for general obligations",
                topic_keywords=["obligations"],
                regulatory_sources=["ASIC"],
                priority="High"
            )
        ]
        state["current_task_index"] = 0
        return state
