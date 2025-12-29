import json
import re
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from ..config import llm_gpt4o
from ..models import AgentState, Obligation, RelatedObligation

# Cell 11: Agent 7 - Synthesis Agent (FIXED)

synthesis_prompt_template = """You are a compliance synthesizer extracting obligations from regulatory text.

QUERY: {query}
PRODUCT TYPE: {product_type}

RETRIEVED CHUNKS: {chunk_count} from ASIC guides and legislation

CHUNKS (Top 100):
{chunks_text}

YOUR TASK: Extract individual compliance obligations for this product type.

OUTPUT FORMAT (JSON):
{{
  "obligations": [
    {{
      "obligation_name": "Obtain Australian Credit License",
      "regulator": "ASIC",
      "document_name": "RG 206",
      "document_subsection": "RG 206.39",
      "confidence_score": 0.95,
      "description": "Must hold an Australian Credit License before engaging in credit activities",
      "type": "must_do",
      "priority": "critical",
      "relates_to": [
        {{
          "related_regulator": "ASIC",
          "related_obligation": "Responsible Lending Assessment",
          "related_document": "RG 209"
        }}
      ]
    }},
    {{
      "obligation_name": "Meet Financial Requirements",
      "regulator": "ASIC",
      "document_name": "Corporations Act 2001",
      "document_subsection": "s 912A(1)(d)",
      "confidence_score": 0.92,
      "description": "Maintain adequate financial resources as required under Corporations Act",
      "type": "must_do",
      "priority": "high",
      "relates_to": []
    }}
  ]
}}

FIELD MAPPING RULES:
1. "obligation_name" = Short action name (e.g., "Obtain ACL", "Conduct Responsible Lending")
2. "document_name" = For ASIC use "RG X", for legislation use act name
3. "document_subsection" = For ASIC use "RG X.YZ", for legislation use "s X"
4. "confidence_score" = 0.7-1.0
5. "description" = 1-2 sentence explanation of what must be done
6. "type" = "must_do" | "must_not_do" | "conditional"
7. "priority" = "critical" | "high" | "medium" | "low"
8. "relates_to" = Related obligations (can be empty list)

Generate 40-60 obligations. Output ONLY valid JSON (no markdown)."""

def synthesis_agent(state: AgentState) -> AgentState:
    """
    Agent 7: Synthesize chunks into obligations
    """
    print("\n" + "="*80)
    print("AGENT 7: SYNTHESIS")
    print("="*80)

    chunks = state["all_chunks"]
    if not chunks:
        print("No chunks to synthesize")
        state["obligations"] = []
        return state

    # Prepare chunk text with proper citations
    chunks_text = "\n\n".join([
        f"[{i+1}] {chunk.document_name} - {chunk.subsection_reference}\n" +
        f"Heading: {chunk.heading or 'No heading'}\n" +
        f"Text: {chunk.text[:400]}"
        for i, chunk in enumerate(chunks[:100])
    ])

    pc = state.get("product_context")
    product_type = pc.product_type if pc else "fintech product"

    prompt = PromptTemplate(
        template=synthesis_prompt_template,
        input_variables=["query", "product_type", "chunk_count", "chunks_text"]
    )

    chain = prompt | llm_gpt4o | StrOutputParser()

    try:
        # Invoke LLM
        result = chain.invoke({
            "query": state["query"],
            "product_type": product_type,
            "chunk_count": len(chunks),
            "chunks_text": chunks_text
        })

        # Parse JSON
        # Remove markdown code blocks
        content = result.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)

        parsed = json.loads(content)

        # Convert to Obligation objects
        obligations = []
        for obl_dict in parsed.get("obligations", []):
            try:
                # Convert relates_to
                relates_to = []
                for rel in obl_dict.get("relates_to", []):
                    relates_to.append(RelatedObligation(**rel))

                obl_dict["relates_to"] = relates_to

                # Ensure confidence_score is float
                obl_dict["confidence_score"] = float(obl_dict.get("confidence_score", 0.85))

                obligations.append(Obligation(**obl_dict))

            except Exception as e:
                print(f"  Skipping invalid obligation: {e}")

        state["obligations"] = obligations
        print(f"✓ Generated {len(obligations)} obligations")

        # Print summary
        if obligations:
            from collections import Counter
            regulators = Counter([o.regulator for o in obligations])
            for reg, count in regulators.most_common():
                print(f"  {reg}: {count}")

    except Exception as e:
        print(f"ERROR: {e}")
        state["errors"].append(f"Synthesis failed: {str(e)}")
        state["obligations"] = []
        
        # Debug output
        if 'result' in locals():
            print(f"\nRAW OUTPUT (first 300 chars):\n{result[:300]}...")

    return state
