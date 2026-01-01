
from typing import List, Optional
import numpy as np
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

try:
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    # Fallback to simple cosine similarity if sklearn not present
    def cosine_similarity(a, b):
        norm_a = np.linalg.norm(a, axis=1, keepdims=True)
        norm_b = np.linalg.norm(b, axis=1, keepdims=True)
        return np.dot(a, b.T) / (norm_a * norm_b.T)

from ..config import llm_gpt4o
from ..models import ComplianceState, EnterpriseObligation, SourceGrounding, ConfidenceLevel
from .retrieval import get_embedding

# ============================================================================
# AGENT 12: Similarity Clustering
# ============================================================================

def cluster_similar_obligations(obligations: List[EnterpriseObligation], threshold: float = 0.85) -> List[List[int]]:
    """Cluster obligations by semantic similarity"""
    if len(obligations) < 2:
        return [[0]] if obligations else []
    
    # Get embeddings
    statements = [obl.obligation_statement for obl in obligations]
    embeddings = [get_embedding(stmt) for stmt in statements]
    embeddings_array = np.array(embeddings)
    
    # Similarity matrix
    similarity_matrix = cosine_similarity(embeddings_array)
    
    # Simple clustering
    clusters = []
    assigned = set()
    
    for i in range(len(obligations)):
        if i in assigned: continue
        
        cluster = [i]
        assigned.add(i)
        
        for j in range(i+1, len(obligations)):
            if j in assigned: continue
            
            # cosine_similarity output shape depends on input.
            # sklearn returns (n, n) for (n, d).
            sim = similarity_matrix[i][j]
            if sim >= threshold:
                cluster.append(j)
                assigned.add(j)
        
        clusters.append(cluster)
    
    return clusters

# ============================================================================
# AGENT 13: Canonical Synthesis
# ============================================================================

canonical_synthesis_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a canonical obligation synthesizer.

TASK: Given multiple similar obligations, create ONE canonical version.

SYNTHESIS RULES:
1. PRESERVE STRICTEST STANDARD - If one says "7 years" and another "5 years", use "7 years"
2. COMBINE APPLICABILITY - Union of all applicability factors
3. MAINTAIN ALL SOURCE CITATIONS - List all sources
4. HIGHEST CONFIDENCE LANGUAGE - Use most authoritative wording
5. NO INFORMATION LOSS - Document what was merged

OVER-NORMALIZATION SAFEGUARDS:
- If obligations have DIFFERENT subjects → DO NOT MERGE
- If obligations have DIFFERENT triggers → DO NOT MERGE
- If obligations CONTRADICT → DO NOT MERGE (flag for human review)
- Only merge if >80% semantic overlap

Output canonical obligation with merge reasoning."""),
    ("user", """OBLIGATIONS TO SYNTHESIZE:
{obligations_text}

Create canonical version preserving strictest standards.""")
])

class CanonicalSynthesis(BaseModel):
    should_merge: bool
    canonical_statement: str
    strictest_standard: Optional[str]
    all_source_citations: List[SourceGrounding]
    merged_obligation_ids: List[str]
    synthesis_reasoning: str
    confidence_level: ConfidenceLevel
    over_normalization_check: str

canonical_synthesis_chain = canonical_synthesis_prompt | llm_gpt4o.with_structured_output(CanonicalSynthesis)

import concurrent.futures

def normalization_agents(state: ComplianceState) -> ComplianceState:
    """Agents 12 & 13: Cluster similar obligations and create canonical versions"""
    print("\n" + "="*80)
    print("AGENTS 12 & 13: SIMILARITY CLUSTERING + CANONICAL SYNTHESIS")
    print("="*80)
    
    obligations = state["obligations"]
    
    if len(obligations) < 2:
        print("  Fewer than 2 obligations - skipping normalization")
        state["canonical_obligations"] = obligations
        return state
    
    print(f"\n[CLUSTERING {len(obligations)} obligations...]")
    clusters = cluster_similar_obligations(obligations, threshold=0.85)
    print(f"  Found {len(clusters)} clusters")
    
    canonical_obligations = []
    
    print(f"Synthesizing clusters... (Parallel Execution)")
    
    def process_cluster(arg):
        cluster_idx, cluster = arg
        if len(cluster) == 1:
            return [obligations[cluster[0]]]
        
        # Merge logic
        cluster_obls = [obligations[i] for i in cluster]
        
        obligations_text = "\n\n".join([
            f"OBLIGATION {i+1}:\nStatement: {obl.obligation_statement}\nSource: {obl.source_grounding.legal_instrument} {obl.source_grounding.section_clause}"
            for i, obl in enumerate(cluster_obls)
        ])
        
        results = []
        try:
            synthesis = canonical_synthesis_chain.invoke({
                "obligations_text": obligations_text[:4000]
            })
            
            if synthesis.should_merge:
                template = cluster_obls[0]
                canonical = EnterpriseObligation(
                    obligation_id=f"CANONICAL-{cluster_idx:04d}",
                    obligation_statement=synthesis.canonical_statement,
                    source_grounding=synthesis.all_source_citations[0], # Primary
                    structure=template.structure,
                    obligation_type=template.obligation_type,
                    action_type=template.action_type,
                    confidence_level=synthesis.confidence_level,
                    confidence_score=max(o.confidence_score for o in cluster_obls),
                    certainty_level=template.certainty_level,
                    plain_english_explanation=template.plain_english_explanation,
                    applicability_factors=template.applicability_factors,
                    applicability_rules=template.applicability_rules,
                    evidence_expectations=template.evidence_expectations,
                    trust_validation=template.trust_validation,
                    source_obligation_ids=[o.obligation_id for o in cluster_obls],
                    strictest_standard=synthesis.strictest_standard
                )
                results.append(canonical)
                if cluster_idx <= 3:
                     # Note: this print might interleave in parallel, but acceptable
                    print(f"\n  Cluster {cluster_idx}: Merged {len(cluster_obls)} obligations")
                    print(f"    Canonical: {synthesis.canonical_statement[:80]}...")
            else:
                results.extend(cluster_obls)
                print(f"\n  Cluster {cluster_idx}: NOT merged (safety check failed)")
                
        except Exception as e:
            print(f"  ERROR synthesizing cluster {cluster_idx}: {e}")
            results.extend(cluster_obls)
            
        return results

    # Parallel processing
    items = list(enumerate(clusters, 1))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Use map to preserve order so CANONICAL IDs match cluster order roughly?
        # Actually CANONICAL ID is generated inside process_cluster using cluster_idx.
        # So independent.
        # But we want 'canonical_obligations' list to be deterministic.
        results = list(executor.map(process_cluster, items))
        for res in results:
            canonical_obligations.extend(res)
            
    print(f"\n[NORMALIZATION COMPLETE]")
    print(f"  Original obligations: {len(obligations)}")
    print(f"  Canonical obligations: {len(canonical_obligations)}")
    print(f"  Reduction: {len(obligations) - len(canonical_obligations)}")
    
    state["canonical_obligations"] = canonical_obligations
    return state
