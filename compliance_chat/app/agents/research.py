from ..models import AgentState
from ..tools import rag_search_tool

# Cell 10: Agent 3 - Research Executor (Simplified)

def research_executor_agent(state: AgentState) -> AgentState:
    """
    Agent 3: Execute research plan by searching for obligations

    Simplified version: Execute all plan tasks sequentially
    """
    print("\n" + "="*80)
    print("AGENT 3: RESEARCH EXECUTOR")
    print("="*80)

    all_chunks = []

    # Execute each task in the plan
    for task in state["plan"]:
        print(f"\nExecuting Task {task.id}: {task.task}")

        # Build search query from task keywords
        search_query = " ".join(task.topic_keywords)

        try:
            # Search vector DB
            chunks = rag_search_tool(
                query=search_query,
                top_k=20,
                regulators=["ASIC"]  # Currently only ASIC indexed (and Legislation)
                # Wait, rag_search_tool handles 'regulators' filter in Pinecone.
                # If filter=['ASIC'], it checks meta['regulator']='ASIC'.
                # Corporations Act might have regulator='ASIC' or something else?
                # In upload script: regulator='ASIC'. So filter is safe.
            )

            all_chunks.extend(chunks)
            task.status = "completed"

            print(f"  Retrieved {len(chunks)} chunks")

        except Exception as e:
            print(f"  ERROR: {e}")
            state["errors"].append(f"Task {task.id} failed: {str(e)}")
            task.status = "failed"

    # Remove duplicates
    seen_ids = set()
    unique_chunks = []
    for chunk in all_chunks:
        if chunk.id not in seen_ids:
            unique_chunks.append(chunk)
            seen_ids.add(chunk.id)

    state["all_chunks"] = unique_chunks
    print(f"\n✓ Research complete: {len(unique_chunks)} unique chunks retrieved")

    return state
