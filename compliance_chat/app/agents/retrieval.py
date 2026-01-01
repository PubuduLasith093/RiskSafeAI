
from typing import List, Dict, Optional, Any
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from ..config import llm_gpt4o_mini, pinecone_index, bm25_encoder, openai_client
from ..models import ComplianceState, Chunk

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_embedding(text: str) -> List[float]:
    """Get OpenAI embedding"""
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return response.data[0].embedding

def get_sparse_vector(text: str) -> Dict:
    """Get BM25 sparse vector"""
    if bm25_encoder is None:
        return {"indices": [], "values": []}
    
    sparse_vector = bm25_encoder.encode_queries(text)
    return {
        "indices": sparse_vector["indices"],
        "values": sparse_vector["values"]
    }

def hybrid_search(query: str, top_k: int = 50, alpha: float = 0.7) -> List[Any]:
    """
    Hybrid search combining dense + sparse vectors
    alpha: weight for dense (0.7 = 70% dense, 30% sparse)
    """
    # Get both vectors
    dense_vector = get_embedding(query)
    sparse_vector = get_sparse_vector(query)
    
    # Query Pinecone
    results = pinecone_index.query(
        vector=dense_vector,
        sparse_vector=sparse_vector,
        top_k=top_k,
        include_metadata=True
    )
    
    return results.matches

def retrieve_parent_chunk(child_id: str) -> Optional[str]:
    """Retrieve full parent section for a child chunk"""
    try:
        # Fetch the child chunk
        fetch_response = pinecone_index.fetch(ids=[child_id])
        
        if child_id not in fetch_response.vectors:
            return None
        
        metadata = fetch_response.vectors[child_id].metadata
        parent_id = metadata.get("parent_id")
        
        if not parent_id:
            return metadata.get("text", "")
        
        # Fetch parent
        parent_response = pinecone_index.fetch(ids=[parent_id])
        
        if parent_id in parent_response.vectors:
            return parent_response.vectors[parent_id].metadata.get("text", "")
        
        return metadata.get("text", "")
        
    except Exception as e:
        print(f"    ERROR retrieving parent for {child_id}: {e}")
        return None

# ============================================================================
# AGENT 4: Query Expansion
# ============================================================================

query_expansion_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a search query expansion expert for Australian regulatory content.

YOUR TASK: Expand search queries to maximize recall while maintaining precision.

TECHNIQUES:
1. Synonyms (ACL = Australian Credit License)
2. Regulatory variations (must/shall/required, obligation/requirement)
3. Abbreviations (NCCP = National Consumer Credit Protection)
4. Related concepts (credit = lending = finance)
5. Legal terminology variations

CRITICAL: Maintain search precision - don't dilute with unrelated terms."""),
    ("user", """ORIGINAL TASK: {task}
KEYWORDS: {keywords}

Generate 5-8 expanded search queries that:
1. Use synonyms and abbreviations
2. Rephrase with regulatory language variations
3. Include specific and broad versions
4. Cover edge cases

Output JSON array of search strings.""")
])

class QueryExpansion(BaseModel):
    expanded_queries: List[str]
    reasoning: str

query_expansion_chain = query_expansion_prompt | llm_gpt4o_mini.with_structured_output(QueryExpansion)

def query_expansion_agent(state: ComplianceState) -> ComplianceState:
    """Agent 4: Expands search queries for comprehensive retrieval"""
    print("\n" + "="*80)
    print("AGENT 4: QUERY EXPANSION AGENT")
    print("="*80)
    
    plan = state["plan"]
    
    # Expand queries for each plan item
    for item in plan:
        try:
            expansion = query_expansion_chain.invoke({
                "task": item.task,
                "keywords": item.topic_keywords
            })
            
            item.search_terms = expansion.expanded_queries
            print(f"\n[{item.category}] {item.task[:60]}...")
            print(f"  Original keywords: {item.topic_keywords[:3]}")
            print(f"  Expanded to {len(expansion.expanded_queries)} search queries")
            
        except Exception as e:
            print(f"  ERROR expanding task {item.id}: {e}")
            item.search_terms = item.topic_keywords  # Fallback
    
    state["plan"] = plan
    return state

# ============================================================================
# AGENT 5: Hybrid RAG
# ============================================================================

def hybrid_rag_agent(state: ComplianceState) -> ComplianceState:
    """Agent 5: Hybrid RAG retrieval with parent-child chunking"""
    print("\n" + "="*80)
    print("AGENT 5: HYBRID RAG RETRIEVAL")
    print("="*80)
    
    plan = state["plan"]
    all_chunks = []
    seen_chunk_ids = set()
    
    # Execute searches for each plan item
    for idx, item in enumerate(plan[:15], 1):  # Limit to first 15 tasks for performance
        print(f"\n[TASK {idx}/{len(plan[:15])}] {item.category}: {item.task[:60]}...")
        
        # Use first expanded search term
        search_query = item.search_terms[0] if item.search_terms else item.task
        
        try:
            # Hybrid search
            matches = hybrid_search(search_query, top_k=30)
            
            print(f"  Retrieved {len(matches)} chunks")
            
            # Process matches
            for match in matches:
                chunk_id = match.id
                
                if chunk_id in seen_chunk_ids:
                    continue
                
                seen_chunk_ids.add(chunk_id)
                
                # Get parent chunk (full context)
                parent_text = retrieve_parent_chunk(chunk_id)
                
                if parent_text:
                    chunk = Chunk(
                        id=chunk_id,
                        score=match.score,
                        text=parent_text,  # Use PARENT text for full context
                        metadata=match.metadata or {},
                        regulator=match.metadata.get("regulator", "ASIC"),
                        document_name=match.metadata.get("document_name"),
                        section=match.metadata.get("section")
                    )
                    all_chunks.append(chunk)
            
            item.status = "completed"
            
        except Exception as e:
            print(f"  ERROR: {e}")
            state["errors"].append(f"Retrieval failed for task {item.id}: {str(e)}")
            item.status = "failed"
    
    print(f"\n[RETRIEVAL COMPLETE]")
    print(f"  Total unique chunks: {len(all_chunks)}")
    
    # Sort by score
    all_chunks.sort(key=lambda x: x.score, reverse=True)
    
    state["chunks"] = all_chunks
    return state
