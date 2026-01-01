
from langgraph.graph import StateGraph, END

from .models import ComplianceState
from .agents.planning import query_understanding_agent, planning_agent, regulatory_scope_validator
from .agents.retrieval import query_expansion_agent, hybrid_rag_agent
from .agents.trust import regulatory_posture_enforcer, privacy_security_scanner, grounding_validator_agent
from .agents.extraction import obligation_detection_agent, atomic_extractor_and_scorer
from .agents.normalization import normalization_agents
from .agents.applicability import applicability_analyzer
from .agents.validation import safety_validator_and_packager

def build_enterprise_compliance_workflow() -> StateGraph:
    """Constructs the complete 15-agent enterprise compliance workflow"""
    
    workflow = StateGraph(ComplianceState)
    
    # Phase 1
    workflow.add_node("query_understanding", query_understanding_agent)
    workflow.add_node("planning", planning_agent)
    workflow.add_node("scope_validation", regulatory_scope_validator)
    
    # Phase 2
    workflow.add_node("query_expansion", query_expansion_agent)
    workflow.add_node("hybrid_rag", hybrid_rag_agent)
    
    # Phase 3
    workflow.add_node("posture_enforcer", regulatory_posture_enforcer)
    workflow.add_node("privacy_scanner", privacy_security_scanner)
    workflow.add_node("grounding_validator_placeholder", grounding_validator_agent)
    
    # Phase 4
    workflow.add_node("obligation_detection", obligation_detection_agent)
    workflow.add_node("atomic_extraction_scoring", atomic_extractor_and_scorer)
    
    # Phase 5
    workflow.add_node("normalization", normalization_agents)
    
    # Phase 6
    workflow.add_node("applicability_analysis", applicability_analyzer)
    
    # Phase 7
    workflow.add_node("safety_validation", safety_validator_and_packager)
    
    # --- Edges ---
    workflow.set_entry_point("query_understanding")
    workflow.add_edge("query_understanding", "planning")
    workflow.add_edge("planning", "scope_validation")
    
    workflow.add_edge("scope_validation", "query_expansion")
    workflow.add_edge("query_expansion", "hybrid_rag")
    
    workflow.add_edge("hybrid_rag", "posture_enforcer")
    workflow.add_edge("posture_enforcer", "privacy_scanner")
    workflow.add_edge("privacy_scanner", "grounding_validator_placeholder")
    
    def check_should_continue(state: ComplianceState) -> str:
        if not state.get("should_continue", True):
            return "END"
        return "continue"
    
    workflow.add_conditional_edges(
        "grounding_validator_placeholder",
        check_should_continue,
        {
            "continue": "obligation_detection",
            "END": END
        }
    )
    
    workflow.add_edge("obligation_detection", "atomic_extraction_scoring")
    workflow.add_edge("atomic_extraction_scoring", "normalization")
    workflow.add_edge("normalization", "applicability_analysis")
    workflow.add_edge("applicability_analysis", "safety_validation")
    workflow.add_edge("safety_validation", END)
    
    return workflow.compile()
