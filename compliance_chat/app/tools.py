from typing import List, Optional
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .config import llm_gpt4o_mini, openai_client, pinecone_index, bm25_encoder
from .models import Chunk

# ==========================================
# Agent 4 - Query Expansion Agent
# ==========================================

def create_query_expansion_agent():
    """Agent 4: Expand search query for better recall"""

    expansion_prompt = PromptTemplate(
        template="""Generate 2 diverse variations of this regulatory search query.
One variation MUST focus on finding literal 'must', 'must not', or 'shall' statements.

Topic: '{query}'

Return ONLY a Python list of strings:
['literal phrase search for must/must not', 'general topic search']""",
        input_variables=["query"]
    )

    chain = expansion_prompt | llm_gpt4o_mini | StrOutputParser()

    def expand_query(query: str) -> List[str]:
        try:
            result = chain.invoke({"query": query})
            # Parse the list from string
            if "[" in result and "]" in result:
                import ast
                expanded = ast.literal_eval(result[result.find("["):result.find("]")+1])
                return [query] + expanded
            return [query]
        except Exception as e:
            print(f"Query expansion failed: {e}")
            return [query]

    return expand_query

query_expander = create_query_expansion_agent()

# ==========================================
# RAG Search Tool with Hybrid Retrieval
# ==========================================

def rag_search_tool(
    query: str,
    top_k: int = 50,
    regulators: Optional[List[str]] = None
) -> List[Chunk]:
    """
    Search Pinecone - NO reranking, just hybrid search for maximum coverage
    """
    print(f"\n[RAG SEARCH] Query: {query[:100]}...")
    
    # Step 1: Query expansion
    queries = query_expander(query)
    print(f"  Expanded to {len(queries)} queries")
    
    all_matches = []
    seen_ids = set()
    
    for q in queries:
        try:
            # Dense embedding
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=q
            )
            query_embedding = embedding_response.data[0].embedding
            
            # Sparse BM25 (if available)
            sparse_vec = None
            if bm25_encoder:
                try:
                    sparse_vec = bm25_encoder.encode_queries(q)
                except:
                    pass
            
            # Query Pinecone
            search_params = {
                "vector": query_embedding,
                "top_k": 60,  # Get more candidates per query
                "include_metadata": True
            }
            if sparse_vec:
                search_params["sparse_vector"] = sparse_vec
            if regulators:
                search_params["filter"] = {"regulator": {"$in": regulators}}
            
            results = pinecone_index.query(**search_params)
            
            # Deduplicate
            for match in results.matches:
                if match.id not in seen_ids:
                    all_matches.append(match)
                    seen_ids.add(match.id)
        
        except Exception as e:
            print(f"  Search error for '{q}': {e}")
    
    # Step 2: Sort by score and take top_k (NO RERANKING)
    all_matches = sorted(all_matches, key=lambda x: x.score, reverse=True)[:top_k]
    
    # Step 3: Convert to Chunk objects
    chunks = []
    for match in all_matches:
        meta = match.metadata
        
        # Detect source type
        is_asic_guide = 'document' in meta and meta.get('document', '').startswith('RG')
        is_legislation = 'act_name' in meta
        
        chunk_dict = {
            "id": match.id,
            "score": match.score,
            "text": meta.get('text', ''),
            "regulator": meta.get('regulator', 'ASIC'),
            "type": meta.get('type', 'unknown'),
            "metadata": meta
        }
        
        if is_asic_guide:
            # ASIC Guide fields
            chunk_dict.update({
                "document": meta.get('document'),
                "doc_title": meta.get('doc_title'),
                "reg_no": meta.get('reg_no'),
                "rg_number": meta.get('rg_number'),
                "heading": meta.get('heading'),
                "parent_heading": meta.get('parent_heading'),
                "section_number": meta.get('section_number')
            })
        
        elif is_legislation:
            # Legislation fields
            chunk_dict.update({
                "act_name": meta.get('act_name'),
                "section": meta.get('section'),
                "citations": meta.get('citations'),
                "chapter_number": meta.get('chapter_number'),
                "chapter_title": meta.get('chapter_title'),
                "part_number": meta.get('part_number'),
                "part_title": meta.get('part_title'),
                "division_number": meta.get('division_number'),
                "division_title": meta.get('division_title'),
                "document_type": meta.get('document_type'),
                "source": meta.get('source'),
                "heading": meta.get('heading')
            })
        
        chunks.append(Chunk(**chunk_dict))
    
    print(f"  ✓ Retrieved {len(chunks)} chunks (no reranking)")
    print(f"    ASIC Guides: {sum(1 for c in chunks if c.is_asic_guide)}")
    print(f"    Legislation: {sum(1 for c in chunks if c.is_legislation)}")
    if chunks:
        print(f"    Score range: {chunks[0].score:.3f} - {chunks[-1].score:.3f}")
    
    return chunks
