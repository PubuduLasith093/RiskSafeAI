
from typing import List, Dict, Any, Literal
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from ..config import llm_gpt4o
from ..models import ComplianceState, PostureCheck, GroundingValidation, PrivacyScan

# ============================================================================
# AGENT 6: Posture Enforcer
# ============================================================================

posture_check_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a regulatory posture enforcement agent.

CRITICAL POLICY RULES:
1. INFORMATION ONLY - Never provide legal advice or recommendations
2. ACCURACY > COMPLETENESS - If uncertain, say so
3. CONSERVATIVE - Err on the side of caution
4. GROUNDED - Every statement must be traceable to source

DETECT VIOLATIONS:
- Legal advice language: "you should", "we recommend", "best practice is"
- Ungrounded claims: statements without source citation
- Overconfidence: definitive statements on ambiguous regulations
- Scope creep: answering questions outside regulatory information

OUTPUT: posture_compliant (bool), violations (list), action (CONTINUE/BLOCK/ESCALATE)"""),
    ("user", """RETRIEVED CHUNKS SAMPLE (first 5):
{chunks_sample}

BUSINESS CONTEXT:
{business_context}

Check for posture violations.""")
])

posture_check_chain = posture_check_prompt | llm_gpt4o.with_structured_output(PostureCheck)

def regulatory_posture_enforcer(state: ComplianceState) -> ComplianceState:
    """Agent 6: Enforces regulatory posture policy"""
    print("\n" + "="*80)
    print("AGENT 6: REGULATORY POSTURE ENFORCER")
    print("="*80)
    
    chunks = state["chunks"]
    query_context = state["query_context"]
    
    # Sample first 5 chunks for review
    chunks_sample = "\n\n".join([
        f"[{i+1}] {chunk.text[:300]}..."
        for i, chunk in enumerate(chunks[:5])
    ])
    
    try:
        posture_check = posture_check_chain.invoke({
            "chunks_sample": chunks_sample,
            "business_context": f"Product: {query_context.product_type}, Model: {query_context.business_model}"
        })
        
        print(f"\n[POSTURE CHECK]")
        print(f"  Compliant: {'✓' if posture_check.posture_compliant else '✗'}")
        print(f"  Action: {posture_check.action}")
        
        if posture_check.action == "BLOCK":
            state["should_continue"] = False
            state["errors"].append("BLOCKED: Posture violations detected")
        elif posture_check.action == "ESCALATE":
            state["trust_flags"].append("POSTURE_ESCALATION")
        
        state["trust_check_passed"] = posture_check.posture_compliant
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Posture check failed: {str(e)}")
        state["trust_check_passed"] = True  # Default to proceed
        return state

# ============================================================================
# AGENT 7: Grounding Validator (Placeholder Logic)
# ============================================================================

def grounding_validator_agent(state: ComplianceState) -> ComplianceState:
    """
    Agent 7: Validates that all obligations have proper grounding
    NOTE: This runs AFTER extraction (Phase 4), so placeholder for now
    """
    print("\n" + "="*80)
    print("AGENT 7: GROUNDING VALIDATOR (will run checks later)")
    print("="*80)
    return state

# ============================================================================
# AGENT 8: Privacy Scanner
# ============================================================================

privacy_scan_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a privacy and security scanner.

SCAN FOR SENSITIVE CONTENT:
1. PII (names, addresses, phone numbers, emails)
2. Financial data (account numbers, credit cards)
3. Internal business information (passwords, API keys, internal URLs)
4. Confidential regulatory communications
5. Customer-specific data

OUTPUT: clean (bool), sensitive_items (list), redaction_required (bool)"""),
    ("user", """CONTENT TO SCAN:
{content_sample}

Identify any sensitive information that should not be in output.""")
])

privacy_scan_chain = privacy_scan_prompt | llm_gpt4o.with_structured_output(PrivacyScan)

def privacy_security_scanner(state: ComplianceState) -> ComplianceState:
    """Agent 8: Scans for PII and sensitive information"""
    print("\n" + "="*80)
    print("AGENT 8: PRIVACY & SECURITY SCANNER")
    print("="*80)
    
    chunks = state["chunks"]
    
    # Sample chunks for privacy scan
    content_sample = "\n\n".join([
        chunk.text[:500]
        for chunk in chunks[:10]
    ])
    
    try:
        scan_result = privacy_scan_chain.invoke({
            "content_sample": content_sample
        })
        
        print(f"\n[PRIVACY SCAN]")
        print(f"  Clean: {'✓' if scan_result.clean else '✗'}")
        
        if scan_result.action == "BLOCK":
            state["should_continue"] = False
            state["errors"].append("BLOCKED: Sensitive information detected")
        elif scan_result.action == "ESCALATE":
            state["trust_flags"].append("PRIVACY_ESCALATION")
        
        return state
        
    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Privacy scan failed: {str(e)}")
        return state
