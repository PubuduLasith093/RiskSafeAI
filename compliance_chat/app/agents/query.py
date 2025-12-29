from langchain_core.prompts import ChatPromptTemplate
from ..config import llm_gpt4o
from ..models import AgentState, QueryContext

# Cell 4: Agent 1 - Query Understanding Agent

query_understanding_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a fintech product classification expert specializing in Australian financial services.

Your task is to parse the user's query and extract structured information about the financial product and business context.

EXTRACT THE FOLLOWING:
1. **Product Type:** What financial product is this about? 
   Options: home_loans, personal_loans, credit_cards, buy_now_pay_later, payday_loans, margin_lending, deposit_accounts, payments, remittance, financial_advice, managed_funds, insurance, superannuation, other

2. **Business Model:** How will they operate?
   Options: direct_lender, broker, aggregator, platform, advisor, other

3. **License Class Required:** What ASIC license(s) do they need?
   Options: ACL (Australian Credit License), ACR (Australian Credit Representative), AFSL (Australian Financial Services License), AR (Authorised Representative), none, unsure

4. **Jurisdiction:** Which state/territory? (if mentioned)
   Options: NSW, VIC, QLD, WA, SA, TAS, ACT, NT, all_australia, not_specified

5. **Specific Services:** List specific services mentioned

6. **Target Market:** Who are their customers?

7. **Query Intent:** What does the user want?
   Options: full_obligation_register, specific_regulation_lookup, licensing_requirements, ongoing_compliance, comparison, other

Be precise and conservative. If uncertain, set confidence < 0.80 and flag in notes."""),
    ("user", "User Query: {query}")
])

# Create structured output chain
query_understanding_chain = query_understanding_prompt | llm_gpt4o.with_structured_output(QueryContext)

def query_understanding_agent(state: AgentState) -> AgentState:
    """
    Agent 1: Parse user query and extract product context
    """
    print("\n" + "="*80)
    print("AGENT 1: QUERY UNDERSTANDING")
    print("="*80)
    
    try:
        product_context = query_understanding_chain.invoke({"query": state["query"]})
        
        print(f"Product Type: {product_context.product_type}")
        print(f"Business Model: {product_context.business_model}")
        print(f"License Required: {product_context.license_class_required}")
        print(f"Confidence: {product_context.confidence:.2f}")
        
        state["product_context"] = product_context
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Query understanding failed: {str(e)}")
        # Fallback
        state["product_context"] = QueryContext(
            product_type="general",
            business_model="other",
            license_class_required=["ACL"],
            query_intent="full_obligation_register",
            confidence=0.5,
            notes="Failed to parse query - using defaults"
        )
        return state
