from typing import List, Dict, Optional, Any, TypedDict, Literal
from enum import Enum
from pydantic import BaseModel, Field

# ============================================
# Enums
# ============================================

class Regulator(str, Enum):
    ASIC = "ASIC"
    APRA = "APRA"
    AML = "AML"
    PRIVACY = "Privacy"

class Priority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ObligationType(str, Enum):
    MUST_DO = "must_do"
    MUST_NOT_DO = "must_not_do"
    CONDITIONAL = "conditional"

class DeadlineType(str, Enum):
    PRE_APPROVAL = "pre_approval"
    ONGOING = "ongoing"
    PER_TRANSACTION = "per_transaction"
    EVENT_TRIGGERED = "event_triggered"
    PERIODIC = "periodic"

# ============================================
# Data Models
# ============================================

class QueryContext(BaseModel):
    """Output from Query Understanding Agent"""
    product_type: str
    product_type_variations: List[str] = Field(default_factory=list)
    business_model: str
    license_class_required: List[str]
    jurisdiction: str = "all_australia"
    specific_services: List[str] = Field(default_factory=list)
    target_market: str = ""
    query_intent: str
    confidence: float
    notes: str = ""

class PlanItem(BaseModel):
    """Single research task in the plan"""
    id: int
    category: str
    task: str
    topic_keywords: List[str]
    regulatory_sources: List[str]
    priority: str
    status: str = "pending"

class Chunk(BaseModel):
    """Retrieved chunk from vector DB - supports ASIC guides AND legislation"""
    # Common fields
    id: str
    score: float
    text: str
    regulator: str
    document_type: Optional[str] = None  # "act", "Regulatory Guide"
    type: str  # "structure_parent", "clause_child", "legislation_section", etc.

    # ASIC Guide fields
    document: Optional[str] = None  # "RG 1", "RG 206", etc
    doc_title: Optional[str] = None  # "Applying for and varying an AFS licence"
    reg_no: Optional[str] = None  # "1", "206.45"
    rg_number: Optional[str] = None  # "1", "206"
    heading: Optional[str] = None
    parent_heading: Optional[str] = None
    section_number: Optional[str] = None

    # Legislation fields
    act_name: Optional[str] = None  # "Corporations Act 2001"
    section: Optional[str] = None  # "5", "913B"
    citations: Optional[str] = None  # "s 5", "s 913B"
    chapter_number: Optional[str] = None  # "1"
    chapter_title: Optional[str] = None
    part_number: Optional[str] = None  # "1.1"
    part_title: Optional[str] = None
    division_number: Optional[str] = None
    division_title: Optional[str] = None
    
    source: Optional[str] = None  # "Corporations Act_vol1.pdf"

    # Raw metadata
    metadata: Dict = Field(default_factory=dict)

     # Computed properties
    @property
    def document_name(self) -> str:
        """Unified document name for output"""
        if self.document:  # ASIC guide
            return self.document
        elif self.act_name:  # Legislation
            return self.act_name
        return "Unknown"

    @property
    def subsection_reference(self) -> str:
        """Unified subsection reference"""
        if self.reg_no:  # ASIC guide
            return f"RG {self.reg_no}"
        elif self.citations:  # Legislation
            return self.citations
        elif self.section:
            return f"Section {self.section}"
        return ""

    @property
    def is_asic_guide(self) -> bool:
        return self.document is not None

    @property
    def is_legislation(self) -> bool:
        return self.act_name is not None

class RelatedObligation(BaseModel):
    """Related obligation reference"""
    related_regulator: str
    related_obligation: str
    related_document: str

class Obligation(BaseModel):
    """Single compliance obligation"""
    obligation_name: str = Field(description="Short name of obligation")
    regulator: str = Field(description="ASIC, APRA, AUSTRAC, etc")
    document_name: str = Field(description="RG 102, Corporations Act 2001, etc")
    document_subsection: str = Field(description="Section 1.2, RG 206.45, s 913B, etc")
    confidence_score: float = Field(description="0-1 confidence score", ge=0, le=1)
    description: str = Field(description="1-2 sentence explanation")  # ← Now required
    type: Literal["must_do", "must_not_do", "conditional"] = Field(default="must_do")  # ← With default
    priority: Literal["critical", "high", "medium", "low"] = Field(default="medium")  # ← With default
    relates_to: List[RelatedObligation] = Field(default_factory=list)

class ValidationResult(BaseModel):
    """Result from semantic validation"""
    obligation_id: str
    is_valid: bool
    confidence: float
    accuracy_score: float
    completeness_score: float
    hallucination_detected: bool
    citation_correct: bool
    issues: List[str] = Field(default_factory=list)
    recommendation: str
    suggested_revision: Optional[str] = None

class ExpertReview(BaseModel):
    """Output from Expert Review Agent"""
    overall_grade: str
    confidence_level: float
    is_complete: bool
    is_fit_for_purpose: bool
    missing_obligations: List[str] = Field(default_factory=list)
    priority_corrections: List[str] = Field(default_factory=list)
    implementation_roadmap: List[Dict] = Field(default_factory=list)
    regulatory_intelligence: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    expert_notes: str = ""

def map_chunk_to_citation(chunk: Chunk) -> Dict[str, str]:
    """
    Map chunk metadata to your required output format

    Returns:
        {
            "document_name": "RG 102" or "Corporations Act 2001",
            "document_subsection": "Section 1.2" or "s 913B"
        }
    """
    if chunk.is_asic_guide:
        # ASIC Regulatory Guide
        doc_name = chunk.document or "Unknown"

        # Build subsection reference
        if chunk.reg_no:
            subsection = f"RG {chunk.reg_no}"
        elif chunk.section_number:
            subsection = f"Section {chunk.section_number}"
        else:
            subsection = "General"

        return {
            "document_name": doc_name,
            "document_subsection": subsection
        }

    elif chunk.is_legislation:
        # Legislation (e.g., Corporations Act)
        doc_name = chunk.act_name or "Unknown Act"

        # Build subsection reference
        if chunk.citations:  # "s 913B"
            subsection = chunk.citations
        elif chunk.section:
            subsection = f"Section {chunk.section}"
        elif chunk.part_number:
            subsection = f"Part {chunk.part_number}"
        else:
            subsection = "General"

        return {
            "document_name": doc_name,
            "document_subsection": subsection
        }

    else:
        return {
            "document_name": "Unknown",
            "document_subsection": "Unknown"
        }

# ============================================
# LangGraph State
# ============================================

class AgentState(TypedDict):
    """State passed between all agents in the workflow"""
    # Input
    query: str
    
    # Agent outputs
    product_context: Optional[QueryContext]
    plan: List[PlanItem]
    current_task_index: int
    
    # Research state
    iteration: int
    all_chunks: List[Chunk]
    raw_obligations: List[Dict]
    
    # Synthesis
    obligations: List[Obligation]
    
    # Verification
    validation_results: List[ValidationResult]
    web_verification: Dict
    expert_review: Optional[ExpertReview]
    
    # Output
    final_answer: str
    
    # Control flow
    should_continue: bool
    errors: List[str]
