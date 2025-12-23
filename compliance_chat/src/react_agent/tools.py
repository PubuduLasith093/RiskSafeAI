"""
ReAct Agent Tools implementation.
Aligned with compliance_project/agents/react_agent_langgraph_pydantic.ipynb
"""

import json
import sys
from typing import List

from pinecone import Pinecone
from tavily import TavilyClient

from compliance_chat.utils.model_loader import ModelLoader
from compliance_chat.utils.config_loader import load_config
from compliance_chat.logger import GLOBAL_LOGGER as log, safe_print
from compliance_chat.exception.custom_exception import DocumentPortalException
from compliance_chat.src.react_agent.models import (
    RAGSearchInput,
    RAGSearchOutput,
    CompletenessCheckInput,
    CompletenessCheckOutput,
    WebSearchInput,
    WebSearchOutput,
    ValidationOutput,
    Chunk,
    Regulator,
)


class ReactAgentTools:
    """Collection of tools for ReAct agent"""

    def __init__(self):
        """Initialize tools with API clients and config"""
        self.config = load_config()
        self.model_loader = ModelLoader()

        # Initialize clients
        self.openai_client = self._init_openai()
        self.pinecone_index = self._init_pinecone()
        self.tavily_client = self._init_tavily()

        # Load config values
        self.embedding_model = self.config["embedding_model"]["model_name"]
        self.llm_model = self.config["llm"]["openai"]["model_name"]
        self.temperature = self.config["llm"]["openai"]["temperature"]

        # Business regulator mappings
        self.business_mappings = self.config["react_agent"]["business_mappings"]

        log.info("ReactAgentTools initialized")

    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
            import os
            api_key = os.getenv("OPENAI_API_KEY") or self.model_loader.api_key_mgr.get("OPENAI_API_KEY")
            return OpenAI(api_key=api_key)
        except Exception as e:
            log.error("Failed to initialize OpenAI client", error=str(e))
            raise DocumentPortalException("OpenAI initialization error", sys)

    def _init_pinecone(self):
        """Initialize Pinecone index"""
        try:
            index_name = self.model_loader.get_pinecone_index_name()
            return self.model_loader.pc.Index(index_name)
        except Exception as e:
            log.error("Failed to initialize Pinecone index", error=str(e))
            raise DocumentPortalException("Pinecone initialization error", sys)

    def _init_tavily(self):
        """Initialize Tavily client for web search"""
        try:
            import os
            api_key = os.getenv("TAVILY_API_KEY") or self.model_loader.api_key_mgr.get("TAVILY_API_KEY")
            return TavilyClient(api_key=api_key)
        except Exception as e:
            log.error("Failed to initialize Tavily client", error=str(e))
            raise DocumentPortalException("Tavily initialization error", sys)

    # ============================================
    # Tool 1: RAG Search
    # ============================================

    def rag_search_tool(self, input_data: RAGSearchInput) -> RAGSearchOutput:
        """
        Search vector database for compliance information using Hybrid Search + Reranking.
        """

        safe_print(f"\n[SEARCH] RAG Search: {input_data.query}")
        if input_data.regulators:
            safe_print(f"   Regulators: {[r.value for r in input_data.regulators]}")

        # 1. Multi-Query Expansion to increase recall
        queries = [input_data.query]
        try:
            expansion_prompt = f"""Generate 2 diverse variations of the following regulatory search query. 
            One variation MUST focus on finding literal 'must', 'must not', or 'shall' statements within the text.
            Topic: '{input_data.query}'. 
            Return ONLY a Python list of strings, e.g., ['literal phrase search for must/must not', 'general topic search']"""
            expansion_resp = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": expansion_prompt}],
                temperature=0.3,
                max_tokens=150
            )
            expanded_text = expansion_resp.choices[0].message.content
            if "[" in expanded_text and "]" in expanded_text:
                import ast
                extra_queries = ast.literal_eval(expanded_text[expanded_text.find("["):expanded_text.find("]")+1])
                queries.extend(extra_queries)
                safe_print(f"   Searching multiple angles: {queries}")
        except Exception as e:
            log.warning("Multi-query expansion failed", error=str(e))

        all_matches = []
        seen_ids = set()
        
        # 2. Iterate through expanded queries
        for q in list(set(queries)):
            try:
                # Generate Dense Embedding
                embedding_response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=q
                )
                query_embedding = embedding_response.data[0].embedding

                # Generate Sparse Vector (Hybrid Search)
                sparse_vec = None
                bm25 = self.model_loader.load_bm25_encoder()
                if bm25:
                    sparse_vec = bm25.encode_queries(q)

                # Build filter
                query_filter = {}
                if input_data.regulators:
                    regulator_values = [r.value for r in input_data.regulators]
                    if len(regulator_values) == 1:
                        query_filter["regulator"] = regulator_values[0]
                    else:
                        query_filter["regulator"] = {"$in": regulator_values}

                # Search Pinecone
                search_top_k = 30 # Pull 30 per angle to ensure high recall
                search_params = {
                    "vector": query_embedding,
                    "top_k": search_top_k,
                    "include_metadata": True,
                    "filter": query_filter if query_filter else None
                }
                if sparse_vec:
                    search_params["sparse_vector"] = sparse_vec

                results = self.pinecone_index.query(**search_params)
                for match in results.matches:
                    if match.id not in seen_ids:
                        all_matches.append(match)
                        seen_ids.add(match.id)
            except Exception as e:
                safe_print(f"   [ERROR] Search for variation '{q}' failed: {str(e)}")

        matches = all_matches
        if self.model_loader.cohere_client and len(matches) > 0:
            try:
                safe_print(f"   Reranking {len(matches)} candidates with Cohere...")
                texts = [m.metadata.get('text', '') for m in matches]
                rerank_resp = self.model_loader.cohere_client.rerank(
                    model="rerank-english-v3.0",
                    query=input_data.query,
                    documents=texts,
                    top_n=input_data.top_k
                )
                
                # Rebuild matches based on rerank order
                reranked_matches = []
                for r in rerank_resp.results:
                    match = matches[r.index]
                    match.score = r.relevance_score # Update score to rerank score
                    reranked_matches.append(match)
                matches = reranked_matches
                safe_print(f"   Reranking complete. Top score: {matches[0].score:.4f}")
            except Exception as e:
                log.warning("Cohere reranking failed, falling back to vector scores", error=str(e))

        # Process results with score threshold
        score_threshold = self.config["retriever"].get("score_threshold", 0.15) 
        
        # Collect Parent IDs to fetch
        parent_ids_to_fetch = []
        child_id_to_parent_map = {}
        
        filtered_matches = []
        for match in matches:
            if match.score >= score_threshold:
                parent_id = match.metadata.get('parent_id')
                if parent_id:
                    parent_ids_to_fetch.append(parent_id)
                    child_id_to_parent_map[match.id] = parent_id
                filtered_matches.append(match)
        
        # Batch fetch parents
        parent_data_map = {}
        if parent_ids_to_fetch:
            try:
                unique_parents = list(set(parent_ids_to_fetch))
                safe_print(f"    Fetching {len(unique_parents)} full parent documents for deeper context...")
                fetch_resp = self.pinecone_index.fetch(ids=unique_parents)
                # Correctly access vectors from FetchResponse object
                if hasattr(fetch_resp, 'vectors'):
                    for pid, pdata in fetch_resp.vectors.items():
                        parent_data_map[pid] = pdata.metadata
            except Exception as e:
                safe_print(f"   [WARNING] Parent fetch failed: {str(e)}")

        chunks = []
        seen_parent_ids = set() # Avoid context duplication if multiple children hit same parent
        
        for match in filtered_matches:
            pid = child_id_to_parent_map.get(match.id)
            source_metadata = match.metadata
            
            # Use parent data if available, otherwise fallback to child
            if pid and pid in parent_data_map:
                if pid in seen_parent_ids:
                    continue # Skip duplicate parents
                seen_parent_ids.add(pid)
                source_metadata = parent_data_map[pid]
                effective_id = pid
            else:
                effective_id = match.id

            chunk = Chunk(
                id=effective_id,
                score=match.score,
                text=source_metadata.get('text', ''),
                regulator=source_metadata.get('regulator', 'Unknown'),
                document=source_metadata.get('document', 'Unknown'),
                heading=source_metadata.get('heading'),
                parent_heading=source_metadata.get('parent_heading'),
                section_number=source_metadata.get('section_number')
            )
            chunks.append(chunk)

        regulators_found = list(set([c.regulator for c in chunks])) if chunks else []
        if chunks:
            safe_print(f"    Found {len(chunks)} relevant chunks from regulators: {regulators_found}")
        else:
            safe_print(f"   [NONE] No chunks found matching criteria")

        log.info("RAG search completed", query=input_data.query, chunks_found=len(chunks))

        return RAGSearchOutput(
            chunks=chunks,
            count=len(chunks),
            query=input_data.query,
            regulators_searched=regulators_found
        )

    # ============================================
    # Tool 2: Completeness Check
    # ============================================

    def completeness_check_tool(self, input_data: CompletenessCheckInput) -> CompletenessCheckOutput:
        """
        Check if all applicable regulators and key obligation categories have been covered.
        Specifically verifies coverage of MUST DO and MUST NOT DO statements.

        Args:
            input_data: CompletenessCheckInput with business type and regulators covered

        Returns:
            CompletenessCheckOutput with completeness status and recommendations
        """

        safe_print(f"\n[CHECK] Completeness Check: {input_data.business_type}")
        safe_print(f"   Regulators covered: {[r.value for r in input_data.regulators_covered]}")
        safe_print(f"   Obligations found: {input_data.obligation_count}")

        # Determine applicable regulators
        business_lower = input_data.business_type.lower()

        applicable_regulators = []
        expected_range = (10, 20)  # Default

        # Fintech lending
        if "fintech" in business_lower and ("loan" in business_lower or "lending" in business_lower or "credit" in business_lower):
            mapping = self.business_mappings["fintech"]["lending"]
            applicable_regulators = [Regulator(r) for r in mapping["regulators"]]
            expected_range = tuple(mapping["expected_range"])

        # Fintech payments
        elif "fintech" in business_lower and "payment" in business_lower:
            mapping = self.business_mappings["fintech"]["payments"]
            applicable_regulators = [Regulator(r) for r in mapping["regulators"]]
            expected_range = tuple(mapping["expected_range"])

        # Fintech investment
        elif "fintech" in business_lower and "invest" in business_lower:
            mapping = self.business_mappings["fintech"]["investment"]
            applicable_regulators = [Regulator(r) for r in mapping["regulators"]]
            expected_range = tuple(mapping["expected_range"])

        # General business
        else:
            mapping = self.business_mappings["general_business"]
            applicable_regulators = [Regulator(r) for r in mapping["regulators"]]
            expected_range = tuple(mapping["expected_range"])

        # Check regulator coverage
        covered_values = [r.value for r in input_data.regulators_covered]
        applicable_values = [r.value for r in applicable_regulators]
        missing = [r for r in applicable_values if r not in covered_values]

        is_complete = len(missing) == 0
        warnings = []

        # Check obligation count
        if input_data.obligation_count < expected_range[0]:
            warnings.append(f"Obligation count ({input_data.obligation_count}) below expected minimum ({expected_range[0]})")
            is_complete = False
        elif input_data.obligation_count > expected_range[1] * 1.5:
            warnings.append(f"Obligation count ({input_data.obligation_count}) significantly higher than expected ({expected_range[1]})")

        # ENHANCED: Check for coverage of key obligation categories
        # These are critical topics that should have both MUST and MUST NOT statements
        key_topics_to_check = [
            "licensing requirements",
            "responsible lending",
            "disclosure obligations",
            "conduct obligations",
            "reporting requirements",
            "prohibited conduct",
            "fit and proper person",
            "conflicts of interest"
        ]

        safe_print(f"\n   Checking coverage of key obligation categories...")
        missing_topics = []
        
        # Quick semantic search to verify each topic has been covered
        for topic in key_topics_to_check:
            try:
                # Generate embedding for the topic
                embedding_response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=topic
                )
                query_embedding = embedding_response.data[0].embedding

                # Quick check: search for this topic in the index
                search_results = self.pinecone_index.query(
                    vector=query_embedding,
                    top_k=3,
                    include_metadata=True,
                    filter={"regulator": {"$in": applicable_values}} if applicable_values else None
                )

                # If we found relevant results, topic is covered
                if not search_results.matches or search_results.matches[0].score < 0.7:
                    missing_topics.append(topic)
                    safe_print(f"      ⚠️  '{topic}' - Low coverage (score: {search_results.matches[0].score if search_results.matches else 0:.2f})")
                else:
                    safe_print(f"      ✓ '{topic}' - Covered (score: {search_results.matches[0].score:.2f})")

            except Exception as e:
                safe_print(f"      ⚠️  '{topic}' - Check failed: {str(e)}")
                missing_topics.append(topic)

        # Add warnings for missing topics
        if missing_topics:
            is_complete = False
            warnings.append(f"Missing coverage for key topics: {', '.join(missing_topics[:3])}")
            safe_print(f"\n   [INCOMPLETE] Missing {len(missing_topics)} key topics")
        else:
            safe_print(f"\n   [COMPLETE] All key topics covered")

        safe_print(f"   Applicable regulators: {applicable_values}")
        safe_print(f"   Missing regulators: {missing if missing else 'None'}")
        safe_print(f"   Expected range: {expected_range[0]}-{expected_range[1]}")
        safe_print(f"   Overall Status: {'[COMPLETE]' if is_complete else '[INCOMPLETE]'}")

        log.info("Completeness check completed", 
                 is_complete=is_complete, 
                 missing_regulators=missing,
                 missing_topics=missing_topics)

        return CompletenessCheckOutput(
            is_complete=is_complete,
            applicable_regulators=applicable_values,
            missing_regulators=missing,
            expected_obligation_range=expected_range,
            current_obligation_count=input_data.obligation_count,
            warnings=warnings
        )

    # ============================================
    # Tool 3: Web Search
    # ============================================

    def web_search_tool(self, input_data: WebSearchInput) -> WebSearchOutput:
        """
        Search web for verification (restricted to official domains)

        Args:
            input_data: WebSearchInput with query and allowed domains

        Returns:
            WebSearchOutput with search results
        """

        safe_print(f"\n[WEB] Web Search: {input_data.query}")
        safe_print(f"   Allowed domains: {input_data.allowed_domains[:3]}...")

        try:
            # Tavily search
            response = self.tavily_client.search(
                query=input_data.query,
                max_results=input_data.max_results,
                include_domains=input_data.allowed_domains
            )

            results = []
            for result in response.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0.0)
                })

            summary = f"Found {len(results)} results from official sources"
            if results:
                summary += f". Top result: {results[0]['title']}"

            print(f"    {len(results)} results found")

            log.info("Web search completed", query=input_data.query, results_count=len(results))

            return WebSearchOutput(
                results=results,
                count=len(results),
                verified=len(results) > 0,
                summary=summary
            )

        except Exception as e:
            safe_print(f"   [ERROR] Web search error: {str(e)}")
            log.error("Web search failed", error=str(e))
            return WebSearchOutput(
                results=[],
                count=0,
                verified=False,
                summary=f"Web search failed: {str(e)}"
            )

    # ============================================
    # Tool 4: Citation Validator
    # ============================================

    def validate_citations_tool(self, answer: str, sources: List[Chunk]) -> ValidationOutput:
        """
        Validate that all claims in answer are cited and grounded in sources

        Args:
            answer: Generated answer text
            sources: Source chunks used

        Returns:
            ValidationOutput with grounding score and citation status
        """

        safe_print(f"\n[VALIDATE] Validating citations...")

        # Prepare source context
        source_context = "\n\n".join([f"Source {i+1}: {chunk.text[:500]}..."
                                       for i, chunk in enumerate(sources[:10])])

        validation_prompt = f"""
You are a validation agent. Check if this answer is properly grounded in the sources.

Answer to validate:
{answer[:2000]}

Sources:
{source_context}

Validate:
1. Are all factual claims supported by sources?
2. Are citations present for each claim?
3. Is any information hallucinated (not in sources)?

Output JSON:
{{
  "grounding_score": 0.0-1.0 (how well grounded in sources),
  "all_cited": true/false (all claims have citations),
  "uncited_claims": ["list of claims without citations"],
  "confidence": 0.0-1.0 (overall confidence in answer),
  "warnings": ["any issues found"]
}}
"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": validation_prompt}],
                response_format={"type": "json_object"},
                temperature=0
            )

            result = json.loads(response.choices[0].message.content)

            validation = ValidationOutput(
                grounding_score=result.get('grounding_score', 0.0),
                all_cited=result.get('all_cited', False),
                uncited_claims=result.get('uncited_claims', []),
                confidence=result.get('confidence', 0.0),
                warnings=result.get('warnings', [])
            )

            safe_print(f"   Grounding score: {validation.grounding_score:.2f}")
            safe_print(f"   All cited: {validation.all_cited}")
            safe_print(f"   Confidence: {validation.confidence:.2f}")

            log.info("Citation validation completed", grounding_score=validation.grounding_score)

            return validation

        except Exception as e:
            safe_print(f"   [ERROR] Validation error: {str(e)}")
            log.error("Citation validation failed", error=str(e))
            return ValidationOutput(
                grounding_score=0.5,
                all_cited=False,
                confidence=0.5,
                warnings=[f"Validation failed: {str(e)}"]
            )

    # ============================================
    # Tool 5: Answer Generation
    # ============================================

    def generate_comprehensive_answer(self, query: str, chunks_by_regulator: dict) -> str:
        """
        Generate final comprehensive answer with all obligations

        Args:
            query: User's original query
            chunks_by_regulator: Dictionary of chunks grouped by regulator

        Returns:
            Comprehensive obligation register in markdown format
        """

        safe_print(f"\n[FINAL] Generating comprehensive final answer...")

        # Prepare context from all unique chunks, sorted by score
        all_flattened = []
        for reg_chunks in chunks_by_regulator.values():
            all_flattened.extend(reg_chunks)
        
        # Sort by score descending and take top 60 to avoid context overflow while maintaining depth
        top_chunks = sorted(all_flattened, key=lambda x: x.score, reverse=True)[:60]
        
        context_parts = []
        for i, chunk in enumerate(top_chunks):
            # Include headings and section numbers for high-precision citation
            meta_parts = []
            if chunk.section_number:
                meta_parts.append(f"SECTION: {chunk.section_number}")
            if chunk.parent_heading:
                meta_parts.append(f"PARENT HEADING: {chunk.parent_heading}")
            if chunk.heading:
                meta_parts.append(f"SUB-HEADING: {chunk.heading}")
            
            meta_header = "\n".join(meta_parts) + "\n" if meta_parts else ""
            
            # Use the Section Number as the primary ID in the Source header
            source_id = chunk.section_number if chunk.section_number else f"Source {i+1}"
            context_parts.append(f"--- SOURCE ID: {source_id} [{chunk.regulator}: {chunk.document}] ---\n{meta_header}{chunk.text}")
        
        context = "\n\n".join(context_parts)

        final_prompt = f"""
Query: {query}

Context from Australian Regulatory Documents:
{context}

You are an expert Australian Regulatory Assistant with deep knowledge of financial products and regulatory applicability.

PRODUCT-SPECIFIC INTELLIGENCE:
   - **CRITICAL**: Carefully analyze the user's query to identify the SPECIFIC PRODUCT TYPE they are asking about (e.g., "home loans", "personal loans", "credit cards", "margin lending").
   - **RELEVANCE FILTERING**: Only include obligations that are DIRECTLY APPLICABLE to that specific product type.
   - **IMPLICIT REFERENCES**: Understand that regulations may refer to the product using different terminology:
     * "Home loans" may appear as: "residential mortgage", "housing credit", "secured lending for property purchase", "home finance"
     * "Personal loans" may appear as: "unsecured credit", "consumer credit", "small amount credit contracts"
     * "Credit cards" may appear as: "continuing credit", "revolving credit facility"
   - **SCOPE DETERMINATION**: Use your expertise to determine if a regulation applies:
     * Does it mention the product type explicitly or implicitly?
     * Does it apply to "all credit licensees" or "all credit providers" (then it applies to this product)?
     * Does it specifically EXCLUDE this product type (then skip it)?
     * Is it about a completely different product category (then skip it)?
   - **WHEN IN DOUBT**: If a mandate could reasonably apply to the product type, INCLUDE it. Better to be over-inclusive than miss critical obligations.

AUDIT MODE DIRECTIONS:
   - Your goal is to list EVERY EXPLICIT MANDATE found in the provided sources that is RELEVANT to the specific product type.
   - You MUST categorize them into two specific, bolded sections:
     1. **SECTION A: MANDATORY ACTIONS (MUST DO)**
     2. **SECTION B: PROHIBITED ACTIONS (MUST NOT DO / DISQUALIFIERS)**
   - Extract the sentences VERBATIM (word-for-word from the source).
   - **SECTION B CRITICAL**: This section must include all **DISQUALIFYING CRITERIA**. Even if the sentence does not use the literal words "must not", if it describes a condition that results in a **refusal, cancellation, or ineligibility**, it belongs here.
   - Specifically hunt for source text regarding: **Convictions, Bankruptcy, Banning Orders, Previous Cancellations, Honest/Fair failures, Fit and Proper Person requirements.**
   - **IMPORTANT**: Ensure every quote is a **COMPLETE SENTENCE**. If the source text seems cut off, use the surrounding Parent Heading or Text context to complete it.
   - DO NOT summarize. If you find 20 relevant rules, list all 20 rules.
   - DO NOT include obligations that clearly apply to a different product type (e.g., don't include "margin lending" rules if the query is about "personal loans").

GROUNDING & CITATION: 
   - Every single bullet point MUST have its specific citation attached to the end of the line in brackets [ ].
   - **CITATIONS MUST USE THE SOURCE ID AND SUB-HEADING PROVIDED.** 
   - The "SOURCE ID" is usually the official ASIC Clause (e.g., RG 209.11). You must prioritize this over generic "Source" numbers.
   - Example format: "Mandatory text..." [ASIC: RG 209.11, Sub-heading: Licensing Requirements]
   - If you are quoting word-for-word, use "quotation marks."

STRUCTURE:
   - Start with a brief intro: "# Compliance Obligations for [Product Type]"
   - Use a clear "## Verbatim Regulatory Mandates" section
   - Then show the two subsections: SECTION A and SECTION B
   - Use bullet points with verbatim quotes and citations
   - If helpful, add a final "## Additional Context" section for explanatory notes

QUALITY CHECKS BEFORE FINALIZING:
   1. Have I filtered out obligations that clearly don't apply to this product type?
   2. Have I included all general obligations that apply to "all credit providers" or "all licensees"?
   3. Are my citations using the official ASIC clause numbers (e.g., RG 209.11)?
   4. Are all quotes complete sentences?
   5. Have I included both "must do" AND "must not do" obligations?

Focus on being helpful, thorough, precise, and PRODUCT-SPECIFIC while maintaining Australian legal context.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": final_prompt}],
                temperature=self.temperature,
                max_tokens=16000
            )

            answer = response.choices[0].message.content

            safe_print(f"    Answer generated ({len(answer)} characters)")
            log.info("Comprehensive answer generated", length=len(answer))

            return answer

        except Exception as e:
            safe_print(f"    Answer generation error: {str(e)}")
            log.error("Answer generation failed", error=str(e))
            return f"Error generating obligation register: {str(e)}"
