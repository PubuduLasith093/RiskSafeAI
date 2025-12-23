"""
ReAct Agent implementation with LangGraph workflow.
Aligned with compliance_project/agents/react_agent_langgraph_pydantic.ipynb
"""

import json
import sys
from typing import Dict

from langgraph.graph import StateGraph, END

from compliance_chat.utils.model_loader import ModelLoader
from compliance_chat.utils.config_loader import load_config
from compliance_chat.logger import GLOBAL_LOGGER as log, safe_print
from compliance_chat.exception.custom_exception import DocumentPortalException
from compliance_chat.src.react_agent.models import (
    AgentState,
    AgentStateDict,
    Thought,
    Action,
    Observation,
    ActionType,
    Regulator,
    convert_to_dict_state,
    convert_from_dict_state,
)
from compliance_chat.src.react_agent.tools import ReactAgentTools


class ReactAgent:
    """ReAct Agent for Australian compliance obligation generation"""

    def __init__(self):
        """Initialize ReAct agent with tools and config"""
        self.config = load_config()
        self.model_loader = ModelLoader()
        self.tools = ReactAgentTools()

        # Load config values
        self.max_iterations = self.config["react_agent"]["max_iterations"]
        self.llm_model = self.config["llm"]["openai"]["model_name"]
        self.temperature = self.config["llm"]["openai"]["temperature"]

        # Initialize OpenAI client
        import os
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY") or self.model_loader.api_key_mgr.get("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=api_key)

        # Build LangGraph workflow
        self.agent = self._build_workflow()

        log.info("ReactAgent initialized", max_iterations=self.max_iterations)

    # ============================================
    # ReAct Loop Functions
    # ============================================

    def should_continue(self, state: AgentState) -> str:
        """Decide whether to continue ReAct loop or finish"""
        if state.final_answer:
            return "finish"
        
        if state.iteration >= self.max_iterations:
            safe_print(f"\n[WARNING] Iteration limit ({self.max_iterations}) reached.")
            return "finish"
            
        return "continue"

    def think_step(self, state: AgentState) -> AgentState:
        """
        Agent thinks about what to do next

        This is the "Reasoning" part of ReAct
        """

        state.iteration += 1
        safe_print(f"\n{'='*80}")
        safe_print(f"ITERATION {state.iteration}")
        safe_print(f"{'='*80}")

        # Build context from previous observations
        context = f"""
Query: {state.query}

Current Status:
- Iteration: {state.iteration}/{self.max_iterations}
- Chunks retrieved: {len(state.all_chunks)}
- Regulators covered: {state.regulators_covered}
- Completeness checked: {state.completeness_checked}
- Citations validated: {state.citations_validated}
- Grounding score: {state.grounding_score:.2f}

Previous thoughts:
"""

        # Add recent thoughts
        for thought in state.thoughts[-3:]:
            context += f"\n[Iteration {thought.iteration}] {thought.content}"

        # Add recent observations
        context += "\n\nRecent observations:"
        for obs in state.observations[-3:]:
            context += f"\n[{obs.action_type.value}] {obs.content[:200]}"

        thinking_prompt = f"""
{context}

IMPORTANT: You are an expert AUSTRALIAN regulatory assistant.
You have two modes based on the user's query:

MODE 1: SIMPLE FACTUAL QUERY
- Use this for basic questions (e.g., "What is RG 209?", "What is a PDS?")
- Action: 1-2 searches, then finalize_answer
- Goal: Quick, cited answer to a specific question
- Completeness check: NOT REQUIRED

MODE 2: OBLIGATION/PROHIBITION QUERY (COMPLIANCE-CRITICAL)
- Use this when the user asks for "must do", "must not do", obligations, prohibitions, or requirements
- Action: Multiple deep searches (3-5+), completeness_check, then finalize_answer
- IMPORTANT: If the user wants 'Must Do' statements, vary your searches across different topics like 'Responsible Lending', 'Conduct', and 'Reporting' to find ALL verbatim mandates.
- CRITICAL: You MUST also perform specific searches for "PROHIBITIONS" using keywords like "prohibited", "must not", "not eligible", "offence", and "conviction" to ensure you find all Section B mandates.
- Completeness check: MANDATORY - Run before finalize_answer to verify all key topics covered
- Goal: Comprehensive, verified list of every mandatory obligation and prohibition

Available AUSTRALIAN Regulator:
- ASIC (Australian Securities and Investments Commission) - Primary source

Available actions:
1. rag_search - Search vector database for ASIC regulations
   - Parameters: {{"query": "search query", "regulators": ["ASIC"], "top_k": 20}}

2. completeness_check - Verify coverage for a business type (for Mode 2)
   - Parameters: {{"business_type": "fintech personal loans"}}

3. web_search - Verify from official Australian government sources (for current info)
   - Parameters: {{"query": "verification query", "max_results": 3}}

4. validate_citations - Check all claims are cited in sources
   - Parameters: {{}}

5. finalize_answer - Generate final answer (Mode 1 or Mode 2)
   - Parameters: {{}}

DECISION RULES:
- **CRITICAL FOR COMPLIANCE**: If the user is asking for "must do", "must not do", or any obligations/prohibitions, you MUST run completeness_check BEFORE finalize_answer.
- For simple factual questions (e.g., "What is RG 209?"), 1-2 searches + finalize is enough.
- For obligation queries:
  1. Do 3-5 targeted searches (must do, must not do, prohibitions, disqualifiers, etc.)
  2. Run completeness_check to verify all key topics are covered
  3. If completeness_check shows missing topics, do additional searches for those topics
  4. Only then run finalize_answer

STATE CHECK:
- Before calling 'finalize_answer', look at your previous actions.
- If Mode 2 (Obligation Query): Did you run 'completeness_check'?
  - NO -> You MUST run 'completeness_check' now. Do NOT finalize.
  - YES -> Proceed to finalize if coverage is good.
- ALWAYS cite your answers using [Document, Section].
- YOUR PRIORITY IS ACCURACY AND COMPLETENESS FROM ASIC SOURCES.

Output JSON with this EXACT format:
{{
  "thought": "I need to search for [specific term] to answer the user's question about...",
  "next_action": "rag_search",
  "action_params": {{"query": "specific search query", "regulators": ["ASIC"], "top_k": 20}},
  "reasoning": "This will provide the specific regulatory clause needed for..."
}}
"""

        # Get agent's thought
        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": thinking_prompt}],
                response_format={"type": "json_object"},
                temperature=self.temperature,
                seed=42
            )

            result = json.loads(response.choices[0].message.content)

            # Record thought
            thought = Thought(
                iteration=state.iteration,
                content=result['thought']
            )
            state.thoughts.append(thought)

            safe_print(f"\n[THOUGHT] THOUGHT:")
            safe_print(f"   {thought.content}")
            safe_print(f"\n   Reasoning: {result['reasoning']}")
            safe_print(f"   Next action: {result['next_action']}")

            # Record planned action
            action = Action(
                iteration=state.iteration,
                action_type=ActionType(result['next_action']),
                parameters=result['action_params']
            )
            state.actions.append(action)

            log.info("Think step completed", iteration=state.iteration, action=result['next_action'])

        except Exception as e:
            print(f"\n[ERROR] Think step error: {str(e)}")
            log.error("Think step failed", error=str(e))
            state.errors.append(f"Think step error: {str(e)}")

        return state

    def act_step(self, state: AgentState) -> AgentState:
        """
        Agent executes the planned action

        This is the "Acting" part of ReAct
        """

        # Get last planned action
        last_action = state.actions[-1]

        safe_print(f"\n[ACTION] ACTION: {last_action.action_type.value}")
        safe_print(f"   Parameters: {last_action.parameters}")

        observation_content = ""

        # Execute action
        try:
            if last_action.action_type == ActionType.RAG_SEARCH:
                # RAG Search
                from compliance_chat.src.react_agent.models import RAGSearchInput
                regulators_param = last_action.parameters.get('regulators', [])
                regulators = [Regulator(r) for r in regulators_param] if regulators_param else None

                input_data = RAGSearchInput(
                    query=last_action.parameters['query'],
                    regulators=regulators,
                    top_k=last_action.parameters.get('top_k', 20)
                )

                result = self.tools.rag_search_tool(input_data)

                # Update state
                state.all_chunks.extend(result.chunks)
                state.regulators_covered.extend(result.regulators_searched)
                state.regulators_covered = list(set(state.regulators_covered))  # Deduplicate

                if result.chunks:
                    observation_content = (
                        f"Retrieved {result.count} chunks. "
                        f"Regulators: {result.regulators_searched}. "
                        f"Top result score: {result.chunks[0].score:.3f}"
                    )
                else:
                    observation_content = (
                        f"Retrieved 0 chunks for query '{result.query}'. "
                        f"No matching data found in vector database. "
                        f"Try different search terms or check if data exists for this regulator."
                    )

            elif last_action.action_type == ActionType.COMPLETENESS_CHECK:
                # Completeness Check
                from compliance_chat.src.react_agent.models import CompletenessCheckInput
                regulators_covered = [Regulator(r) for r in state.regulators_covered]

                input_data = CompletenessCheckInput(
                    business_type=last_action.parameters['business_type'],
                    regulators_covered=regulators_covered,
                    obligation_count=len(state.all_chunks)
                )

                result = self.tools.completeness_check_tool(input_data)

                # Update state
                state.completeness_checked = True

                if not result.is_complete:
                    state.warnings.extend(result.warnings)

                observation_content = (
                    f"Completeness: {' Complete' if result.is_complete else ' Incomplete'}. "
                    f"Missing regulators: {result.missing_regulators if result.missing_regulators else 'None'}. "
                    f"Obligation count: {result.current_obligation_count} "
                    f"(expected: {result.expected_obligation_range[0]}-{result.expected_obligation_range[1]})"
                )

            elif last_action.action_type == ActionType.WEB_SEARCH:
                # Web Search
                from compliance_chat.src.react_agent.models import WebSearchInput
                input_data = WebSearchInput(
                    query=last_action.parameters['query'],
                    max_results=last_action.parameters.get('max_results', 3)
                )

                result = self.tools.web_search_tool(input_data)

                # Update state
                state.web_verified = True

                observation_content = result.summary

            elif last_action.action_type == ActionType.VALIDATE_CITATIONS:
                # Citation Validation
                if len(state.all_chunks) > 0:
                    draft_answer = f"Draft obligation register with {len(state.all_chunks)} obligations"
                    result = self.tools.validate_citations_tool(draft_answer, state.all_chunks[:20])

                    # Update state
                    state.citations_validated = True
                    state.grounding_score = result.grounding_score
                    state.confidence = result.confidence

                    if result.warnings:
                        state.warnings.extend(result.warnings)

                    observation_content = (
                        f"Grounding score: {result.grounding_score:.2f}. "
                        f"All cited: {result.all_cited}. "
                        f"Confidence: {result.confidence:.2f}. "
                        f"Uncited claims: {len(result.uncited_claims)}"
                    )
                else:
                    observation_content = "Cannot validate citations - no chunks retrieved yet. Need to search regulators first."
                    state.warnings.append("Attempted citation validation with no data")

            elif last_action.action_type == ActionType.FINALIZE_ANSWER:
                # Finalize answer
                if len(state.all_chunks) > 0:
                    chunks_by_regulator = {}
                    for chunk in state.all_chunks:
                        if chunk.regulator not in chunks_by_regulator:
                            chunks_by_regulator[chunk.regulator] = []
                        chunks_by_regulator[chunk.regulator].append(chunk)

                    state.final_answer = self.tools.generate_comprehensive_answer(state.query, chunks_by_regulator)
                    state.is_complete = True
                    observation_content = "Final answer generated with comprehensive details and citations."
                else:
                    observation_content = "Cannot finalize answer - no data retrieved. Obligation register is empty."
                    state.final_answer = "Unable to generate obligation register - no compliance data was retrieved from the vector database."
                    state.is_complete = True

            else:
                observation_content = f"Unknown action type: {last_action.action_type}"

        except Exception as e:
            import traceback
            observation_content = f"Error executing action: {str(e)}"
            state.errors.append(observation_content)
            print(f"   [ERROR] {observation_content}")
            print(f"   Stack trace: {traceback.format_exc()}")
            log.error("Act step failed", error=str(e), action=last_action.action_type.value)

        # Record observation
        observation = Observation(
            iteration=state.iteration,
            content=observation_content,
            action_type=last_action.action_type
        )
        state.observations.append(observation)

        safe_print(f"\n[OBSERVATION] OBSERVATION:")
        safe_print(f"   {observation_content}")

        log.info("Act step completed", iteration=state.iteration)

        return state

    # ============================================
    # LangGraph Workflow
    # ============================================

    def _build_workflow(self):
        """Build LangGraph workflow for ReAct agent"""

        # Wrapper functions for LangGraph (work with dict state)
        def think_step_wrapper(state: dict) -> dict:
            pydantic_state = convert_from_dict_state(state)
            result_state = self.think_step(pydantic_state)
            return convert_to_dict_state(result_state)

        def act_step_wrapper(state: dict) -> dict:
            pydantic_state = convert_from_dict_state(state)
            result_state = self.act_step(pydantic_state)
            return convert_to_dict_state(result_state)

        def should_continue_wrapper(state: dict) -> str:
            pydantic_state = convert_from_dict_state(state)
            return self.should_continue(pydantic_state)

        # Build LangGraph workflow
        workflow = StateGraph(AgentStateDict)

        # Add nodes
        workflow.add_node("think", think_step_wrapper)
        workflow.add_node("act", act_step_wrapper)

        # Set entry point
        workflow.set_entry_point("think")

        # Add edges
        workflow.add_edge("think", "act")

        # Conditional edge from act
        workflow.add_conditional_edges(
            "act",
            should_continue_wrapper,
            {
                "continue": "think",
                "finish": END
            }
        )

        # Compile
        compiled_agent = workflow.compile()

        log.info("LangGraph workflow built")

        return compiled_agent

    # ============================================
    # Public API
    # ============================================

    def run(self, query: str) -> Dict:
        """
        Run ReAct agent on a query

        Args:
            query: User query

        Returns:
            Final result with answer and metadata
        """

        safe_print(f"\n{'#'*80}")
        safe_print(f"STARTING REACT AGENT")
        safe_print(f"{'#'*80}")
        safe_print(f"\nQuery: {query}\n")

        # Initialize state
        initial_state = AgentState(query=query)
        initial_dict = convert_to_dict_state(initial_state)

        # Run workflow
        try:
            # Increase recursion limit to handle more iterations
            final_state_dict = self.agent.invoke(initial_dict, config={"recursion_limit": 100})
            final_state = convert_from_dict_state(final_state_dict)

            # SAFETY CHECK: If limit reached but no final_answer generated in loop
            if not final_state.final_answer:
                safe_print("\n[SAFETY] Limit reached without finalize_answer - generating now...")
                if len(final_state.all_chunks) > 0:
                    chunks_by_regulator = {}
                    for chunk in final_state.all_chunks:
                        if chunk.regulator not in chunks_by_regulator:
                            chunks_by_regulator[chunk.regulator] = []
                        chunks_by_regulator[chunk.regulator].append(chunk)
                    final_state.final_answer = self.tools.generate_comprehensive_answer(final_state.query, chunks_by_regulator)
                else:
                    final_state.final_answer = "Process completed, but no compliance data could be gathered for the request."

            safe_print(f"\n{'#'*80}")
            safe_print(f"REACT AGENT COMPLETED")
            safe_print(f"{'#'*80}")
            safe_print(f"\nIterations: {final_state.iteration}")
            safe_print(f"Chunks retrieved: {len(final_state.all_chunks)}")
            safe_print(f"Regulators covered: {final_state.regulators_covered}")
            safe_print(f"Grounding score: {final_state.grounding_score:.2f}")
            safe_print(f"Confidence: {final_state.confidence:.2f}")

            if final_state.warnings:
                print(f"\n[WARNING] Warnings: {len(final_state.warnings)}")
                for warning in final_state.warnings:
                    print(f"   - {warning}")

            if final_state.errors:
                print(f"\n[ERROR] Errors: {len(final_state.errors)}")
                for error in final_state.errors:
                    print(f"   - {error}")

            log.info("ReAct agent completed", iterations=final_state.iteration, chunks=len(final_state.all_chunks))

            return {
                "answer": final_state.final_answer,
                "metadata": {
                    "iterations": final_state.iteration,
                    "chunks_retrieved": len(final_state.all_chunks),
                    "regulators_covered": final_state.regulators_covered,
                    "grounding_score": final_state.grounding_score,
                    "confidence": final_state.confidence,
                    "completeness_checked": final_state.completeness_checked,
                    "citations_validated": final_state.citations_validated,
                    "warnings": final_state.warnings,
                    "errors": final_state.errors
                },
                "trace": {
                    "thoughts": [t.model_dump() for t in final_state.thoughts],
                    "actions": [a.model_dump() for a in final_state.actions],
                    "observations": [o.model_dump() for o in final_state.observations]
                }
            }

        except Exception as e:
            print(f"\n[ERROR] Agent failed: {str(e)}")
            log.error("ReAct agent failed", error=str(e))
            import traceback
            traceback.print_exc()
            return {
                "answer": "",
                "error": str(e)
            }
