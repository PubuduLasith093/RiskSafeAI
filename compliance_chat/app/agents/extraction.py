
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from ..config import llm_gpt4o
from ..models import (
    ComplianceState,
    EnterpriseObligation, ApplicabilityFactors, TrustValidation, ConfidenceLevel
)
# Note: I need to be careful with imports. I defined these models in models.py
# Let's check models.py content again. I put main models there.
# But `ObligationDetection`, `AtomicExtractionOutput`, `ConfidenceScoring` were NOT in my `models.py` write.
# I missed them in Step 4183 (I only copied Cell 2).
# Cell 10 and 11 had *local* models inside the cell.
# I should define them here or update models.py.
# defining them here is fine as they are agent-specific DTOs.

from pydantic import BaseModel, Field
from enum import Enum
from ..models import ObligationType, ActionType, SourceGrounding, ObligationStructure, CertaintyLevel
from ..models import EnterpriseObligation

# ============================================================================
# MODELS (Agent Specific)
# ============================================================================

class DetectedObligation(BaseModel):
    """Single detected obligation"""
    obligation_statement: str
    obligation_type: ObligationType
    action_type: ActionType
    subject: str
    action: str
    trigger: str
    object_scope: Optional[str] = None
    standard: Optional[str] = None
    reasoning: str
    detection_confidence: float

class ObligationDetection(BaseModel):
    """Detection output for one chunk"""
    obligations: List[DetectedObligation]
    chunk_id: str
    total_detected: int

class AtomicObligation(BaseModel):
    """Atomic obligation with grounding"""
    obligation_statement: str
    source_grounding: SourceGrounding
    structure: ObligationStructure
    obligation_type: ObligationType
    action_type: ActionType
    is_atomic: bool
    atomic_check_reasoning: str

class AtomicExtractionOutput(BaseModel):
    """Output from atomic extraction"""
    atomic_obligations: List[AtomicObligation]
    original_was_atomic: bool

class ConfidenceScoring(BaseModel):
    """Confidence assessment"""
    confidence_level: ConfidenceLevel
    confidence_score: float
    confidence_language: str
    certainty_level: CertaintyLevel
    factors: Dict[str, str] = Field(default_factory=dict)
    reasoning: str

# ============================================================================
# AGENT 9: Obligation Detection
# ============================================================================

obligation_detection_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at detecting regulatory obligations using step-by-step reasoning.

OBLIGATION INDICATORS:
- MANDATORY: must, shall, required, obliged, need to, have to
- CONDITIONAL: if...then, where, when, in circumstances
- GUIDANCE: should, may, could, recommended, good practice
- INFORMATIONAL: background, explanation, definitions

USE CHAIN-OF-THOUGHT REASONING:
STEP 1: SCAN FOR OBLIGATION LANGUAGE
STEP 2: CLASSIFY EACH CANDIDATE
STEP 3: EXTRACT STRUCTURE
STEP 4: VALIDATE

Output JSON array of detected obligations with reasoning."""),
    ("user", """CHUNK TO ANALYZE:
{chunk_text}

METADATA:
Regulator: {regulator}
Document: {document_name}
Section: {section}

BUSINESS CONTEXT:
Product: {product_type}
License: {license_class}

Detect ALL obligations using step-by-step reasoning.""")
])

obligation_detection_chain = obligation_detection_prompt | llm_gpt4o.with_structured_output(ObligationDetection)

import concurrent.futures

def obligation_detection_agent(state: ComplianceState) -> ComplianceState:
    """Agent 9: Detects obligations in chunks using Chain-of-Thought"""
    print("\n" + "="*80)
    print("AGENT 9: OBLIGATION DETECTION (Chain-of-Thought)")
    print("="*80)
    
    chunks = state["chunks"]
    query_context = state["query_context"]
    all_detected = []
    
    print(f"\nProcessing {len(chunks)} chunks... (Parallel Execution)")
    
    def process_chunk(arg):
        idx, chunk = arg
        try:
            detection = obligation_detection_chain.invoke({
                "chunk_text": chunk.text[:4000],
                "regulator": chunk.regulator,
                "document_name": chunk.document_name or "Unknown",
                "section": chunk.section or "Unknown",
                "product_type": query_context.product_type,
                "license_class": query_context.license_class_required
            })
            
            results = []
            for obl in detection.obligations:
                results.append({
                    "chunk_id": chunk.id,
                    "chunk_metadata": chunk.metadata,
                    "detected": obl
                })
            return results
        except Exception as e:
            if idx <= 3:
                print(f"    ERROR processing chunk {idx}: {e}")
            return []

    # Parallel processing
    # Limit to top 50
    chunks_to_process = list(enumerate(chunks[:50], 1))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_chunk, item): item for item in chunks_to_process}
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                all_detected.extend(result)
            except Exception as e:
                print(f"    Thread error: {e}")
    
    print(f"\n[DETECTION COMPLETE]")
    print(f"  Total obligations detected: {len(all_detected)}")
    
    state["_detected_obligations"] = all_detected
    return state


# ============================================================================
# AGENT 10 & 11: Atomic Extraction & Scoring
# ============================================================================

atomic_extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an atomic obligation extraction expert.
CRITICAL RULE: ONE ACTION PER OBLIGATION
Output atomic obligations with FULL grounding."""),
    ("user", """DETECTED OBLIGATION:
{obligation_statement}

SOURCE CHUNK:
{source_chunk}

METADATA:
Regulator: {regulator}
Document: {document_name}
Section: {section}

Split into atomic obligations if needed. Extract full grounding.""")
])

atomic_extraction_chain = atomic_extraction_prompt | llm_gpt4o.with_structured_output(AtomicExtractionOutput)

confidence_scoring_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a confidence scoring expert.
Output confidence level, score, mandatory language, and assess each factor."""),
    ("user", """OBLIGATION:
{obligation_statement}

SOURCE GROUNDING:
Regulator: {regulator}
Instrument: {legal_instrument}
Section: {section_clause}
Excerpt: {verbatim_excerpt}

OBLIGATION TYPE: {obligation_type}
""")
])

confidence_scoring_chain = confidence_scoring_prompt | llm_gpt4o.with_structured_output(ConfidenceScoring)

def atomic_extractor_and_scorer(state: ComplianceState) -> ComplianceState:
    """Agents 10 & 11: Extract atomic obligations and score confidence"""
    print("\n" + "="*80)
    print("AGENTS 10 & 11: ATOMIC EXTRACTION + CONFIDENCE SCORING")
    print("="*80)
    
    detected_obligations = state.get("_detected_obligations", [])
    chunks = {chunk.id: chunk for chunk in state["chunks"]}
    final_obligations = []
    
    print(f"\nProcessing {len(detected_obligations)} detected obligations... (Parallel Execution)")
    
    def process_obligation(arg):
        idx, det_obl = arg
        chunk = chunks.get(det_obl["chunk_id"])
        if not chunk: return []
        
        detected = det_obl["detected"]
        results = []
        
        try:
            # Atomic
            atomic_output = atomic_extraction_chain.invoke({
                "obligation_statement": detected.obligation_statement,
                "source_chunk": chunk.text[:2000],
                "regulator": chunk.regulator,
                "document_name": chunk.document_name or "Unknown",
                "section": chunk.section or "Unknown"
            })
            
            # Score
            for atomic_obl in atomic_output.atomic_obligations:
                confidence = confidence_scoring_chain.invoke({
                    "obligation_statement": atomic_obl.obligation_statement,
                    "regulator": atomic_obl.source_grounding.regulator,
                    "legal_instrument": atomic_obl.source_grounding.legal_instrument,
                    "section_clause": atomic_obl.source_grounding.section_clause,
                    "verbatim_excerpt": atomic_obl.source_grounding.verbatim_excerpt,
                    "obligation_type": atomic_obl.obligation_type
                })
                
                # Create EnterpriseObligation (Partial, ID to be assigned later)
                enterprise_obl = EnterpriseObligation(
                    obligation_id="TEMP", # Placeholder
                    obligation_statement=atomic_obl.obligation_statement,
                    source_grounding=atomic_obl.source_grounding,
                    structure=atomic_obl.structure,
                    obligation_type=atomic_obl.obligation_type,
                    action_type=atomic_obl.action_type,
                    confidence_level=confidence.confidence_level,
                    confidence_score=confidence.confidence_score,
                    certainty_level=confidence.certainty_level,
                    plain_english_explanation=confidence.confidence_language,
                    applicability_factors=ApplicabilityFactors(),
                    applicability_rules="TBD",
                    evidence_expectations=[],
                    trust_validation=TrustValidation(
                        grounding_validated=False,
                        posture_compliant=True,
                        no_legal_advice=True,
                        privacy_clear=True,
                        action="CONTINUE"
                    )
                )
                results.append(enterprise_obl)
            return results
                
        except Exception as e:
            if idx <= 3: print(f"    ERROR: {e}")
            return []

    # Parallel processing limit 100
    obls_to_process = list(enumerate(detected_obligations[:100], 1))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Use map to preserve order if possible, or list of futures
        # We need to assign IDs later so order consistency is nice but not strictly critical
        # Using futures + as_completed is simpler for progress
        futures = {executor.submit(process_obligation, item): item for item in obls_to_process}
        
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                final_obligations.extend(res)
            except Exception as e:
                print(f"    Thread error: {e}")

    # Assign IDs
    for i, obl in enumerate(final_obligations, 1):
        obl.obligation_id = f"OBL-{i:04d}"

    print(f"\n[EXTRACTION COMPLETE] Total: {len(final_obligations)}")
    state["obligations"] = final_obligations
    return state
