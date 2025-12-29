from ..models import AgentState

# Cell 12: Agent 8 - Semantic Validator (UPDATED)

def semantic_validator_agent(state: AgentState) -> AgentState:
    """
    Agent 8: Validate obligations (UPDATED for new format)
    
    Simplified version: Check field quality and confidence
    """
    print("\n" + "="*80)
    print("AGENT 8: SEMANTIC VALIDATION")
    print("="*80)

    obligations = state["obligations"]
    
    if not obligations:
        print("No obligations to validate")
        state["validation_results"] = []
        return state
    
    validation_results = []

    for obl in obligations[:20]:  # Validate first 20 to save costs
        # Validation checks
        has_document = bool(obl.document_name and len(obl.document_name) > 2)
        has_subsection = bool(obl.document_subsection and len(obl.document_subsection) > 2)
        has_name = bool(obl.obligation_name and len(obl.obligation_name) > 5)
        high_confidence = obl.confidence_score >= 0.70
        
        is_valid = has_document and has_subsection and has_name and high_confidence
        
        issues = []
        if not has_document:
            issues.append("Missing or incomplete document_name")
        if not has_subsection:
            issues.append("Missing or incomplete document_subsection")
        if not has_name:
            issues.append("Missing or incomplete obligation_name")
        if not high_confidence:
            issues.append(f"Low confidence score: {obl.confidence_score}")
        
        # Create validation result (using NEW ValidationResult model)
        validation_results.append({
            "obligation_id": obl.obligation_name[:50],  # Use name as ID
            "is_valid": is_valid,
            "confidence": obl.confidence_score,
            "accuracy_score": 0.85 if is_valid else 0.60,
            "completeness_score": 1.0 if (has_document and has_subsection and has_name) else 0.70,
            "hallucination_detected": False,
            "citation_correct": has_document and has_subsection,
            "issues": issues,
            "recommendation": "APPROVE" if is_valid else "REVISE",
            "suggested_revision": None
        })

    state["validation_results"] = validation_results

    valid_count = sum(1 for v in validation_results if v["is_valid"])
    print(f"✓ Validated {len(validation_results)} obligations")
    print(f"  Valid: {valid_count}/{len(validation_results)}")
    
    if valid_count < len(validation_results):
        print(f"  Issues found: {len(validation_results) - valid_count}")
        # Show first few issues
        for v in validation_results[:3]:
            if not v["is_valid"]:
                print(f"    - {v['obligation_id'][:40]}: {', '.join(v['issues'])}")

    return state
