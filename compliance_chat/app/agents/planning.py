
from ..config import llm_gpt4o
from ..models import ComplianceState, QueryContext, PlanOutput, PlanItem, ScopeValidation
from langchain_core.prompts import ChatPromptTemplate

# ============================================================================
# AGENT 1: Query Understanding
# ============================================================================

query_understanding_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Australian financial services regulatory analyst with 15+ years experience.

YOUR TASK: Analyze user queries with EXTREME PRECISION using step-by-step reasoning.

CRITICAL RULES:
- Think step-by-step (Chain-of-Thought)
- Never assume details not stated
- If confidence < 0.80, flag for human clarification
- Be conservative - uncertainty is better than incorrect assumptions"""),
    ("user", """USER QUERY: "{query}"

STEP 1: IDENTIFY THE CORE REGULATORY QUESTION
What is the user REALLY asking for? What is the regulatory INTENT?

STEP 2: EXTRACT BUSINESS CONTEXT
Identify:
- Product type (home loans, BNPL, financial advice, etc.)
- Business model (lender, broker, platform, aggregator)
- License requirements (ACL, AFSL, AR, unlicensed)
- Target market (retail, wholesale, consumer, commercial)
- Jurisdiction (Federal, State-specific)

STEP 3: IDENTIFY AMBIGUITIES
What is unclear or underspecified?

STEP 4: DETERMINE REGULATORY SCOPE
Which regulators are relevant? (ASIC, APRA, AUSTRAC, OAIC)

STEP 5: CLASSIFY QUERY INTENT
Is this:
- Full obligation register (comprehensive checklist)
- Specific regulation lookup (targeted question)
- Licensing requirements
- Ongoing compliance obligations
- Product-specific obligations

STEP 6: ASSESS CONFIDENCE
Rate confidence: HIGH / MEDIUM / LOW

Output JSON with reasoning for each step.""")
])

query_understanding_chain = query_understanding_prompt | llm_gpt4o.with_structured_output(QueryContext)

def query_understanding_agent(state: ComplianceState) -> ComplianceState:
    """Agent 1: Deep understanding of business context with Chain-of-Thought reasoning"""
    print("\n" + "="*80)
    print("AGENT 1: QUERY UNDERSTANDING (Chain-of-Thought)")
    print("="*80)
    print(f"Query: {state['user_query'][:100]}...")
    
    try:
        query_context = query_understanding_chain.invoke({"query": state["user_query"]})
        
        print(f"\n[ANALYSIS COMPLETE]")
        print(f"  Product Type: {query_context.product_type}")
        print(f"  Business Model: {query_context.business_model}")
        print(f"  License Required: {query_context.license_class_required}")
        print(f"  Query Intent: {query_context.query_intent}")
        print(f"  Confidence: {query_context.confidence:.2f}")
        
        if query_context.ambiguities:
            print(f"  ⚠ Ambiguities: {query_context.ambiguities}")
        
        if query_context.confidence < 0.80:
            print(f"  ⚠ LOW CONFIDENCE - May need user clarification")
        
        state["query_context"] = query_context
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Query understanding failed: {str(e)}")
        # Fallback
        state["query_context"] = QueryContext(
            product_type="general",
            business_model="other",
            license_class_required=["ACL"],
            query_intent="full_obligation_register",
            confidence=0.5,
            notes="Failed to parse query - using defaults"
        )
        return state

# ============================================================================
# AGENT 2: Planning
# ============================================================================

planning_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a compliance planning expert. Your job is to break down regulatory research into comprehensive, granular tasks.

COMPLIANCE TAXONOMY (7 categories):
1. Licensing & Authorization
2. Conduct & Disclosure (design, distribution, ongoing obligations)
3. Financial Resources & Risk Management
4. Operational & Systems
5. Governance & Personnel
6. Record Keeping & Reporting
7. Dispute Resolution & Remediation

PRODUCT-SPECIFIC REGULATORY SOURCES:
- Home Loans/Credit: NCCP, RG 209, RG 254, Corporations Act s 912A
- Financial Advice: RG 175, RG 244, Corporations Act Part 7.6
- Margin Lending: RG 227, Corporations Act s 761EA
- General Insurance: RG 271, Insurance Contracts Act
- Responsible Entity: RG 132, Corporations Act Chapter 5C

YOUR TASK: Create 12-18 granular search tasks ensuring 100% coverage."""),
    ("user", """BUSINESS CONTEXT:
Product: {product_type}
Model: {business_model}
License: {license_class_required}
Intent: {query_intent}

CREATE COMPREHENSIVE PLAN:

STEP 1: Map product to regulatory sources
STEP 2: Expand across 7 compliance categories
STEP 3: Create granular tasks (12-18 tasks minimum)
STEP 4: For each task specify:
   - category (from 7 above)
   - task (specific research question)
   - topic_keywords (for search)
   - regulatory_sources (which regulations to search)
   - priority (HIGH/MEDIUM/LOW)
   - expected_obligation_count (estimate)

STEP 5: Validate coverage - ensure NO gaps

Output JSON array of PlanItem objects.""")
])

planning_chain = planning_prompt | llm_gpt4o.with_structured_output(PlanOutput)

def planning_agent(state: ComplianceState) -> ComplianceState:
    """Agent 2: Creates comprehensive research plan with 12-18 granular tasks"""
    print("\n" + "="*80)
    print("AGENT 2: PLANNING AGENT (Chain-of-Thought)")
    print("="*80)
    
    query_context = state["query_context"]
    
    try:
        plan_output = planning_chain.invoke({
            "product_type": query_context.product_type,
            "business_model": query_context.business_model,
            "license_class_required": query_context.license_class_required,
            "query_intent": query_context.query_intent
        })
        
        print(f"\n[PLAN CREATED]")
        print(f"  Total Tasks: {len(plan_output.plan_items)}")
        print(f"  Coverage Reasoning: {plan_output.coverage_reasoning[:200]}...")
        print(f"  Expected Obligations: {plan_output.total_expected_obligations}")
        
        # Show breakdown by category
        categories = {}
        for item in plan_output.plan_items:
            categories[item.category] = categories.get(item.category, 0) + 1
        
        print(f"\n[TASK BREAKDOWN BY CATEGORY]")
        for cat, count in categories.items():
            print(f"  {cat}: {count} tasks")
        
        state["plan"] = plan_output.plan_items
        state["plan_validated"] = False
        
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Planning failed: {str(e)}")
        state["plan"] = []
        return state

# ============================================================================
# AGENT 3: Scope Validator
# ============================================================================

scope_validation_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a regulatory scope validator. Check that the plan has comprehensive coverage.

VALIDATION CHECKLIST:
1. All 7 compliance categories represented?
2. Product-specific regulations included?
3. Cross-cutting obligations (privacy, AML, consumer protection)?
4. Licensing vs ongoing obligations separated?
5. Temporal dimensions (pre-launch, ongoing, exit)?
6. Edge cases and exceptions covered?

OUTPUT: validation_passed (bool) and gaps (list)"""),
    ("user", """PLAN TO VALIDATE:
{plan_summary}

BUSINESS CONTEXT:
Product: {product_type}
Model: {business_model}

Check for gaps and confirm comprehensive coverage.""")
])

scope_validation_chain = scope_validation_prompt | llm_gpt4o.with_structured_output(ScopeValidation)

def regulatory_scope_validator(state: ComplianceState) -> ComplianceState:
    """Agent 3: Validates plan for comprehensive coverage"""
    print("\n" + "="*80)
    print("AGENT 3: REGULATORY SCOPE VALIDATOR")
    print("="*80)
    
    query_context = state["query_context"]
    plan = state["plan"]
    
    plan_summary = "\n".join([
        f"{i+1}. [{item.category}] {item.task} (Sources: {item.regulatory_sources})"
        for i, item in enumerate(plan[:10])
    ])
    
    try:
        validation = scope_validation_chain.invoke({
            "plan_summary": plan_summary,
            "product_type": query_context.product_type,
            "business_model": query_context.business_model
        })
        
        print(f"\n[VALIDATION RESULT]")
        print(f"  Passed: {'✓' if validation.validation_passed else '✗'}")
        
        if validation.gaps_identified:
            print(f"  Gaps Found: {len(validation.gaps_identified)}")
            for gap in validation.gaps_identified:
                print(f"    - {gap}")
        
        if validation.suggestions:
            print(f"  Suggestions: {len(validation.suggestions)}")
            for sug in validation.suggestions[:3]:
                print(f"    - {sug}")
        
        state["plan_validated"] = validation.validation_passed
        
        # Add suggested tasks to plan if gaps found
        if not validation.validation_passed and validation.suggestions:
            print(f"\n  Adding {len(validation.suggestions)} additional tasks to close gaps...")
            # In production, you'd parse suggestions into PlanItems
        
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Scope validation failed: {str(e)}")
        state["plan_validated"] = True
        return state
