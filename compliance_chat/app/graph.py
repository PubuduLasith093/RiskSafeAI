from langgraph.graph import StateGraph, END
from .models import AgentState
from .agents import (
    query_understanding_agent,
    planning_agent,
    research_executor_agent,
    synthesis_agent,
    semantic_validator_agent,
    expert_review_agent
)

# Cell 14: Build LangGraph Workflow

def create_workflow():
    """
    Build LangGraph StateGraph connecting all agents
    """

    # Define workflow
    workflow = StateGraph(AgentState)

    # Add nodes (agents)
    workflow.add_node("query_understanding", query_understanding_agent)
    workflow.add_node("planning", planning_agent)
    workflow.add_node("research", research_executor_agent)
    workflow.add_node("synthesis", synthesis_agent)
    workflow.add_node("validation", semantic_validator_agent)
    workflow.add_node("expert_review", expert_review_agent)

    # Define edges (workflow flow)
    workflow.set_entry_point("query_understanding")
    workflow.add_edge("query_understanding", "planning")
    workflow.add_edge("planning", "research")
    workflow.add_edge("research", "synthesis")
    workflow.add_edge("synthesis", "validation")
    workflow.add_edge("validation", "expert_review")
    workflow.add_edge("expert_review", END)

    # Compile
    app = workflow.compile()

    return app

# Create the workflow
compliance_workflow = create_workflow()
