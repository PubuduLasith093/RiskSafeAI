
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from ..config import llm_gpt4o
from ..models import ComplianceState, ApplicabilityFactors

# ============================================================================
# AGENT 14: Applicability Analyzer
# ============================================================================

applicability_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an applicability analysis expert using Chain-of-Thought reasoning.

YOUR TASK: Determine EXACTLY when an obligation applies using IF/THEN logic.

8 APPLICABILITY DIMENSIONS:
1. Entity Type 2. Regulatory Status 3. Jurisdiction 4. Product/Service
5. Customer Type 6. Thresholds 7. Operational 8. Temporal

CHAIN-OF-THOUGHT:
STEP 1: IDENTIFY EXPLICIT APPLICABILITY MARKERS
STEP 2: INFER IMPLICIT APPLICABILITY
STEP 3: CONSTRUCT IF/THEN RULES
STEP 4: IDENTIFY EXCEPTIONS
STEP 5: SPECIFY EVIDENCE REQUIREMENTS

Output structured applicability analysis."""),
    ("user", """OBLIGATION:
{obligation_statement}

STRUCTURE:
Subject: {subject}
Trigger: {trigger}

SOURCE:
Instrument: {legal_instrument}
Section: {section_clause}

BUSINESS CONTEXT:
Product: {product_type}
License: {license_class}

Analyze applicability with step-by-step reasoning.""")
])

class ApplicabilityAnalysis(BaseModel):
    applicability_factors: ApplicabilityFactors
    applicability_rules: str
    exceptions: List[str]
    evidence_expectations: List[str]
    plain_english_explanation: str
    reasoning: str

applicability_chain = applicability_prompt | llm_gpt4o.with_structured_output(ApplicabilityAnalysis)

def applicability_analyzer(state: ComplianceState) -> ComplianceState:
    """Agent 14: Analyzes applicability for each obligation with Chain-of-Thought"""
    print("\n" + "="*80)
    print("AGENT 14: APPLICABILITY ANALYZER (Chain-of-Thought)")
    print("="*80)
    
    canonical_obligations = state["canonical_obligations"]
    query_context = state["query_context"]
    updated_obligations = []
    
    print(f"\nAnalyzing applicability for {len(canonical_obligations)} obligations...")
    
    # Process batch (limit 50)
    for idx, obl in enumerate(canonical_obligations[:50], 1):
        if idx % 10 == 0:
            print(f"  Progress: {idx}...")
        
        try:
            analysis = applicability_chain.invoke({
                "obligation_statement": obl.obligation_statement,
                "subject": obl.structure.subject,
                "trigger": obl.structure.trigger,
                "legal_instrument": obl.source_grounding.legal_instrument,
                "section_clause": obl.source_grounding.section_clause,
                "product_type": query_context.product_type,
                "license_class": query_context.license_class_required
            })
            
            obl.applicability_factors = analysis.applicability_factors
            obl.applicability_rules = analysis.applicability_rules
            obl.evidence_expectations = analysis.evidence_expectations
            obl.plain_english_explanation = analysis.plain_english_explanation
            
            updated_obligations.append(obl)
            
        except Exception as e:
            if idx <= 3: print(f"    ERROR analyzing obligation {idx}: {e}")
            updated_obligations.append(obl)
            
    if len(canonical_obligations) > 50:
        updated_obligations.extend(canonical_obligations[50:])
        
    state["canonical_obligations"] = updated_obligations
    return state
