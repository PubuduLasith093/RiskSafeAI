"""
Pydantic models for ReAct Agent state and data structures.
Aligned with compliance_project/agents/react_agent_langgraph_pydantic.ipynb
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================
# Enums
# ============================================

class Regulator(str, Enum):
    """Australian regulators"""
    ASIC = "ASIC"
    # TODO: Add other regulators when their embeddings are uploaded
    # APRA = "APRA"
    # AML = "AML"
    # CONSUMER = "Consumer"
    # PRIVACY = "Privacy"
    # FAIRWORK = "FairWork"
    # TREASURY = "Treasury"


class Priority(str, Enum):
    """Obligation priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionType(str, Enum):
    """ReAct agent action types"""
    RAG_SEARCH = "rag_search"
    COMPLETENESS_CHECK = "completeness_check"
    WEB_SEARCH = "web_search"
    VALIDATE_CITATIONS = "validate_citations"
    FINALIZE_ANSWER = "finalize_answer"


# ============================================
# Data Models
# ============================================

class Chunk(BaseModel):
    """Vector database chunk"""
    id: str
    score: float
    text: str
    regulator: str
    document: str
    heading: Optional[str] = None
    parent_heading: Optional[str] = None
    section_number: Optional[str] = None


class Obligation(BaseModel):
    """Single compliance obligation"""
    title: str = Field(description="What must be done")
    description: str = Field(description="Detailed explanation")
    regulator: str = Field(description="Enforcing regulator")
    priority: Priority = Field(description="Urgency level")
    deadline: str = Field(description="When it must be completed")
    cost_estimate: str = Field(description="Estimated cost")
    time_estimate: str = Field(description="Estimated time to complete")
    penalty: str = Field(description="Penalty for non-compliance")
    citation: str = Field(description="Source with section/page")
    detailed_explanation: str = Field(description="Comprehensive explanation with legal context")
    dependencies: List[str] = Field(default_factory=list, description="Prerequisites")


class RAGSearchInput(BaseModel):
    """Input for RAG search tool"""
    query: str = Field(description="Search query")
    regulators: Optional[List[Regulator]] = Field(default=None, description="Filter by regulators")
    top_k: int = Field(default=20, description="Number of results")


class RAGSearchOutput(BaseModel):
    """Output from RAG search tool"""
    chunks: List[Chunk]
    count: int
    query: str
    regulators_searched: List[str]


class CompletenessCheckInput(BaseModel):
    """Input for completeness check"""
    business_type: str = Field(description="Type of business (e.g., 'fintech personal loans')")
    regulators_covered: List[Regulator] = Field(description="Regulators already searched")
    obligation_count: int = Field(description="Number of obligations found so far")


class CompletenessCheckOutput(BaseModel):
    """Output from completeness check"""
    is_complete: bool
    applicable_regulators: List[str]
    missing_regulators: List[str]
    expected_obligation_range: tuple[int, int]
    current_obligation_count: int
    missing_topics: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class WebSearchInput(BaseModel):
    """Input for web search verification"""
    query: str
    allowed_domains: List[str] = Field(
        default=["asic.gov.au", "ato.gov.au", "oaic.gov.au", "fairwork.gov.au", "apra.gov.au", "austrac.gov.au"]
    )
    max_results: int = Field(default=3)


class WebSearchOutput(BaseModel):
    """Output from web search"""
    results: List[Dict]
    count: int
    verified: bool
    summary: str


class ValidationOutput(BaseModel):
    """Output from citation validation"""
    grounding_score: float = Field(ge=0.0, le=1.0)
    all_cited: bool
    uncited_claims: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: List[str] = Field(default_factory=list)


# ============================================
# ReAct Agent State
# ============================================

class Thought(BaseModel):
    """Single thought in ReAct loop"""
    iteration: int
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class Action(BaseModel):
    """Single action in ReAct loop"""
    iteration: int
    action_type: ActionType
    parameters: Dict
    timestamp: datetime = Field(default_factory=datetime.now)


class Observation(BaseModel):
    """Single observation in ReAct loop"""
    iteration: int
    content: str
    action_type: ActionType
    timestamp: datetime = Field(default_factory=datetime.now)


class PlanItem(BaseModel):
    """Item in the execution plan"""
    id: int
    task: str  # e.g. "Search for Responsible Lending obligations"
    topic_keywords: List[str]
    status: str = "pending"  # pending, in_progress, completed, failed
    result_summary: str = ""


class AgentState(BaseModel):
    """Complete state of ReAct/Planner agent"""

    # Input
    query: str
    
    # Planner State
    plan: List[PlanItem] = Field(default_factory=list)
    current_step_index: int = 0
    audit_feedback: str = ""

    # ReAct loop tracking
    iteration: int = 0
    thoughts: List[Thought] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    observations: List[Observation] = Field(default_factory=list)

    # Retrieved information
    all_chunks: List[Chunk] = Field(default_factory=list)
    obligations: List[Obligation] = Field(default_factory=list)

    # Tracking
    regulators_covered: List[str] = Field(default_factory=list)
    completeness_checked: bool = False
    citations_validated: bool = False
    web_verified: bool = False

    # Validation
    grounding_score: float = 0.0
    confidence: float = 0.0

    # Output
    final_answer: str = ""
    is_complete: bool = False

    # Error handling
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


# ============================================
# TypedDict for LangGraph
# ============================================

from typing import TypedDict

class AgentStateDict(TypedDict):
    """Agent state as TypedDict for LangGraph"""
    query: str
    plan: List[dict]
    current_step_index: int
    audit_feedback: str
    iteration: int
    thoughts: List[dict]
    actions: List[dict]
    observations: List[dict]
    all_chunks: List[dict]
    regulators_covered: List[str]
    completeness_checked: bool
    citations_validated: bool
    web_verified: bool
    grounding_score: float
    confidence: float
    final_answer: str
    is_complete: bool
    errors: List[str]
    warnings: List[str]


def convert_to_dict_state(state: AgentState) -> dict:
    """Convert Pydantic state to dict for LangGraph"""
    # OPTIMIZATION: Pass complex objects by reference to avoid OOM
    # usage during long loops (prevent deep copying huge lists)
    return {
        "query": state.query,
        "plan": [p.model_dump() for p in state.plan], # Plan is small, dump is fine
        "current_step_index": state.current_step_index,
        "audit_feedback": state.audit_feedback,
        "iteration": state.iteration,
        "thoughts": state.thoughts, # Pass objects directly
        "actions": state.actions,   # Pass objects directly
        "observations": state.observations, # Pass objects directly
        "all_chunks": state.all_chunks,     # Pass objects directly (CRITICAL for memory)
        "regulators_covered": state.regulators_covered,
        "completeness_checked": state.completeness_checked,
        "citations_validated": state.citations_validated,
        "web_verified": state.web_verified,
        "grounding_score": state.grounding_score,
        "confidence": state.confidence,
        "final_answer": state.final_answer,
        "is_complete": state.is_complete,
        "errors": state.errors,
        "warnings": state.warnings
    }


def convert_from_dict_state(state_dict: dict) -> AgentState:
    """Convert dict state back to Pydantic"""
    
    # helper to handle both Dict and Object
    def parse_list(items, model_class):
        if not items: return []
        if isinstance(items[0], dict):
            return [model_class(**i) for i in items]
        return items # Already objects

    return AgentState(
        query=state_dict["query"],
        plan=[PlanItem(**p) for p in state_dict.get("plan", [])] if state_dict.get("plan") and isinstance(state_dict["plan"][0], dict) else state_dict.get("plan", []),
        current_step_index=state_dict.get("current_step_index", 0),
        audit_feedback=state_dict.get("audit_feedback", ""),
        iteration=state_dict["iteration"],
        thoughts=parse_list(state_dict["thoughts"], Thought),
        actions=parse_list(state_dict["actions"], Action),
        observations=parse_list(state_dict["observations"], Observation),
        all_chunks=parse_list(state_dict["all_chunks"], Chunk),
        regulators_covered=state_dict["regulators_covered"],
        completeness_checked=state_dict["completeness_checked"],
        citations_validated=state_dict["citations_validated"],
        web_verified=state_dict["web_verified"],
        grounding_score=state_dict["grounding_score"],
        confidence=state_dict["confidence"],
        final_answer=state_dict["final_answer"],
        is_complete=state_dict["is_complete"],
        errors=state_dict["errors"],
        warnings=state_dict["warnings"]
    )
