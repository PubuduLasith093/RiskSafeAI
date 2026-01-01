
from typing import List, Dict, Optional, Any, TypedDict, Literal, Set
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field

# ============================================================================
# ENUMS
# ============================================================================

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ObligationType(str, Enum):
    MANDATORY = "MANDATORY_OBLIGATION"
    CONDITIONAL = "CONDITIONAL_OBLIGATION"
    GUIDANCE = "NON_BINDING_GUIDANCE"
    INFORMATIONAL = "INFORMATIONAL_CONTENT"

class ActionType(str, Enum):
    MUST_DO = "MUST_DO"
    MUST_NOT_DO = "MUST_NOT_DO"
    CONDITIONAL = "CONDITIONAL"

class CertaintyLevel(str, Enum):
    CERTAIN = "CERTAIN"
    LIKELY = "LIKELY"
    UNCERTAIN = "UNCERTAIN"

class ReviewAction(str, Enum):
    APPROVE = "APPROVE"
    EDIT = "EDIT"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"

# ============================================================================
# CORE DATA MODELS
# ============================================================================

class SourceGrounding(BaseModel):
    """Complete source citation for an obligation (MANDATORY)"""
    regulator: str = Field(description="Regulator name (ASIC, APRA, AUSTRAC)")
    legal_instrument: str = Field(description="Legal instrument (RG 206, Corporations Act 2001)")
    section_clause: str = Field(description="Specific section (RG 206.45, s 912A)")
    verbatim_excerpt: str = Field(description="Exact text from regulation", min_length=20)
    effective_date: Optional[date] = None

class ObligationStructure(BaseModel):
    """Parsed components of an obligation"""
    subject: str = Field(description="Who must comply (e.g., 'ACL holders')")
    action: str = Field(description="What must be done")
    trigger: Optional[str] = Field(default=None, description="When/under what circumstances")
    object_scope: Optional[str] = Field(default=None, description="What the action is performed on")
    standard: Optional[str] = Field(default=None, description="To what standard (7 years, reasonable steps)")

class ApplicabilityFactors(BaseModel):
    """All factors determining when obligation applies"""
    entity_type: List[str] = Field(default_factory=list)
    regulatory_status: List[str] = Field(default_factory=list)
    jurisdiction: List[str] = Field(default_factory=list)
    product_service: List[str] = Field(default_factory=list)
    customer_type: List[str] = Field(default_factory=list)
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    operational: List[str] = Field(default_factory=list)
    temporal: List[str] = Field(default_factory=list)

class TrustValidation(BaseModel):
    """Trust layer validation results"""
    grounding_validated: bool
    posture_compliant: bool
    no_legal_advice: bool
    privacy_clear: bool
    trust_flags: List[str] = Field(default_factory=list)
    action: Literal["CONTINUE", "BLOCK", "ESCALATE"] = "CONTINUE"

class EnterpriseObligation(BaseModel):
    """Complete enterprise-grade obligation record"""
    
    # Core Identity
    obligation_id: str
    obligation_statement: str
    
    # Source Grounding (MANDATORY)
    source_grounding: SourceGrounding
    
    # Obligation Structure
    structure: ObligationStructure
    
    # Classification
    obligation_type: ObligationType
    action_type: ActionType
    confidence_level: ConfidenceLevel
    confidence_score: float = Field(ge=0.0, le=1.0)
    
    # Applicability
    applicability_factors: ApplicabilityFactors
    applicability_rules: str  # IF/THEN logic
    plain_english_explanation: str
    certainty_level: CertaintyLevel
    
    # Normalization
    canonical_obligation_id: Optional[str] = None
    source_obligation_ids: List[str] = Field(default_factory=list)
    strictest_standard: Optional[str] = None
    
    # Compliance Metadata
    evidence_expectations: List[str] = Field(default_factory=list)
    review_frequency: Optional[str] = None
    change_sensitivity: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    
    # Trust Layer
    trust_validation: TrustValidation
    human_reviewed: bool = False
    reviewer_decision: Optional[ReviewAction] = None
    
    # Relationships
    related_obligations: List[str] = Field(default_factory=list)

# ============================================================================
# AGENT OUTPUT MODELS (Used by Agents)
# ============================================================================

class PlanItem(BaseModel):
    """Single research task in the plan"""
    id: int
    category: str
    task: str
    topic_keywords: List[str]
    regulatory_sources: List[str]
    priority: str
    expected_obligation_count: str = "Unknown"
    search_terms: List[str] = Field(default_factory=list)
    status: str = "pending"

class PlanOutput(BaseModel):
    plan_items: List[PlanItem]
    coverage_reasoning: str
    total_expected_obligations: str

class ScopeValidation(BaseModel):
    validation_passed: bool
    gaps_identified: List[str]
    suggestions: List[str]
    reasoning: str

class PostureCheck(BaseModel):
    """Posture enforcement output"""
    posture_compliant: bool
    violations: List[str]
    warnings: List[str]
    action: Literal["CONTINUE", "BLOCK", "ESCALATE"]
    reasoning: str

class GroundingValidation(BaseModel):
    """Grounding validation for all obligations"""
    validations: List[Dict[str, Any]]  # {obligation_id, grounding_valid, issues}
    overall_pass_rate: float
    action: Literal["CONTINUE", "BLOCK", "ESCALATE"]

class PrivacyScan(BaseModel):
    """Privacy scan results"""
    clean: bool
    sensitive_items: List[str]
    redaction_required: bool
    action: Literal["CONTINUE", "BLOCK", "ESCALATE"]

class FinalSafetyValidation(BaseModel):
    all_checks_passed: bool
    failed_checks: List[str]
    review_required_count: int
    high_priority_reviews: List[str]
    medium_priority_reviews: List[str]
    action: Literal["APPROVE", "REVIEW_REQUIRED", "BLOCK"]

# ============================================================================
# WORKFLOW STATE MODELS
# ============================================================================

class QueryContext(BaseModel):
    """Output from Query Understanding Agent"""
    product_type: str
    product_type_variations: List[str] = Field(default_factory=list)
    business_model: str
    license_class_required: List[str]
    jurisdiction: str = "all_australia"
    specific_services: List[str] = Field(default_factory=list)
    target_market: str = ""
    distribution_channel: str = ""
    query_intent: str
    confidence: float
    ambiguities: List[str] = Field(default_factory=list)
    reasoning: str = ""
    regulatory_scope: List[str] = Field(default_factory=list)
    notes: str = ""

class Chunk(BaseModel):
    """Retrieved chunk from vector DB"""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    regulator: str = "ASIC"
    document_name: Optional[str] = None
    section: Optional[str] = None

class ComplianceState(TypedDict):
    """State that flows through the entire workflow"""
    # Input
    user_query: str
    
    # Phase 1: Understanding
    query_context: Optional[QueryContext]
    plan: List[PlanItem]
    plan_validated: bool
    
    # Phase 2: Retrieval
    chunks: List[Chunk]
    
    # Phase 3: Trust Layer (initial)
    trust_check_passed: bool
    trust_flags: List[str]
    
    # Phase 4: Extraction
    _detected_obligations: List[Dict]  # Intermediate storage from Agent 9
    obligations: List[EnterpriseObligation]
    # Note: notebook had duplicate "obligations" line.
    
    # Phase 5: Normalization
    clustered_obligations: List[Dict]
    canonical_obligations: List[EnterpriseObligation]
    
    # Phase 6: Applicability (already in obligations)
    
    # Phase 7: Final validation
    review_packages: List[Dict]
    final_output: List[EnterpriseObligation]
    
    # Control
    errors: List[str]
    should_continue: bool
