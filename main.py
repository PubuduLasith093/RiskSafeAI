import os
import sys
import io
import traceback
import json
from pathlib import Path
from typing import Dict, List, Any, Union

# --- GLOBAL WINDOWS FIX FOR [Errno 22] ---
def patch_windows_console():
    if sys.platform == "win32":
        class SafeStream:
            def __init__(self, original_stream):
                self.original_stream = original_stream
            def write(self, data):
                try:
                    self.original_stream.write(data)
                except OSError as e:
                    if e.errno == 22:
                        try:
                            clean_data = data.encode('ascii', 'ignore').decode('ascii')
                            self.original_stream.write(clean_data)
                        except:
                            pass
                    else:
                        raise
            def flush(self):
                try:
                    self.original_stream.flush()
                except:
                    pass
            def __getattr__(self, name):
                return getattr(self.original_stream, name)
        
        try:
            sys.stdout = SafeStream(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
            sys.stderr = SafeStream(io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace'))
        except:
            sys.stdout = SafeStream(sys.stdout)
            sys.stderr = SafeStream(sys.stderr)

patch_windows_console()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# --- Import New Research Module ---
# Ensure root is in path
if str(Path.cwd()) not in sys.path:
    sys.path.append(str(Path.cwd()))

try:
    # Importing from the new location specified by user
    # from compliance_chat.research.modules.supervisor import run_supervisor
    from compliance_chat.app.orchestrator import EnterpriseComplianceOrchestrator
    from compliance_chat.logger import GLOBAL_LOGGER as log
except ImportError as e:
    print(f"Import Error: {e}")
    # Fallback to local path if package is not installed as root
    sys.path.append(str(Path.cwd() / "compliance_chat" / "app"))
    try:
        from orchestrator import EnterpriseComplianceOrchestrator
    except ImportError:
        pass

# Initialize the orchestrator globally to reuse resources
try:
    print("Initializing EnterpriseComplianceOrchestrator...")
    orchestrator = EnterpriseComplianceOrchestrator()
    print("✓ Orchestrator initialized successfully")
except Exception as e:
    print(f"✗ CRITICAL: Failed to initialize orchestrator: {e}")
    traceback.print_exc()
    # Create a dummy orchestrator that will return errors
    orchestrator = None

app = FastAPI(title="RiskSafeAI Compliance Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

class ObligationRegisterRequest(BaseModel):
    query: str

class ObligationRegisterResponse(BaseModel):
    answer: str  # Returning Markdown string to UI
    metadata: Dict

# --- Helper to Format Markdown ---
# --- Helper to Format Markdown ---
def format_obligations_to_markdown(result: Dict) -> str:
    """Format the obligations list into a nice Markdown string for the UI."""
    # New Enterprise System Output Format
    final_obligations = result.get("final_obligations", [])
    
    # Check if this is the old format or new format
    if not final_obligations and "obligations" in result:
        # Fallback for old format if somehow used
        return format_old_obligations(result)
        
    obligations = final_obligations
    
    md_lines = []
    md_lines.append(f"# Enterprise Compliance Report")
    md_lines.append(f"**Total Obligations:** {len(obligations)}\n")
    
    # Review Packages Warning
    reviews = result.get("review_packages", [])
    if reviews:
        md_lines.append(f"::: warning\n**ATTENTION:** {len(reviews)} obligations require human review.\n:::\n")
    
    if not obligations:
        md_lines.append("No obligations found for this query.")
        return "\n".join(md_lines)

    # Summary Table
    md_lines.append("## Executive Summary")
    md_lines.append("| ID | Obligation | Confidence | Source |")
    md_lines.append("|---|---|---|---|")
    for obl in obligations:
        # Pydantic model dump or dict access
        if hasattr(obl, "model_dump"):
            o = obl.model_dump()
        else:
            o = obl
            
        oid = o.get("obligation_id", "N/A")
        stmt = o.get("obligation_statement", "")[:50] + "..."
        conf = o.get("confidence_level", "LOW")
        source = o.get("source_grounding", {})
        ref = f"{source.get('legal_instrument', '')} {source.get('section_clause', '')}"
        
        md_lines.append(f"| {oid} | {stmt} | {conf} | {ref} |")
    
    md_lines.append("\n## Detailed Obligations")
    
    for i, obl in enumerate(obligations, 1):
        if hasattr(obl, "model_dump"):
            o = obl.model_dump()
        else:
            o = obl
            
        oid = o.get("obligation_id", "N/A")
        stmt = o.get("obligation_statement", "N/A")
        conf_score = o.get("confidence_score", 0.0)
        conf_level = o.get("confidence_level", "LOW")
        
        source = o.get("source_grounding", {})
        regulator = source.get("regulator", "N/A")
        instrument = source.get("legal_instrument", "N/A")
        section = source.get("section_clause", "")
        excerpt = source.get("verbatim_excerpt", "")
        
        struct = o.get("structure", {})
        action = struct.get("action", "")
        trigger = struct.get("trigger", "")
        
        applicability = o.get("applicability_rules", "N/A")

        md_lines.append(f"### {i}. {oid}: {stmt}")
        md_lines.append(f"- **Confidence:** {conf_level} ({conf_score:.2f})")
        md_lines.append(f"- **Source:** {regulator} - {instrument} {section}")
        md_lines.append(f"> *\"{excerpt}\"*")
        md_lines.append(f"- **Action:** {action}")
        md_lines.append(f"- **Trigger:** {trigger}")
        md_lines.append(f"- **Applicability:** {applicability}")
        md_lines.append("")

    return "\n".join(md_lines)

def format_old_obligations(result: Dict) -> str:
    """Legacy formatter"""
    obligations = result.get("obligations", [])
    md_lines = ["# Obligation Register (Legacy)"]
    for obl in obligations:
        md_lines.append(f"- {obl.get('obligation_name', 'Obligation')}")
    return "\n".join(md_lines)

def format_statements_to_markdown(result: Dict) -> str:
    """Format statement extractor results to Markdown."""
    statements = result.get("statements", [])
    doc_name = result.get("document_name", "Unknown")
    
    md_lines = []
    md_lines.append(f"# Statement Extraction: {doc_name}")
    md_lines.append(f"**Total Statements:** {len(statements)}\n")
    
    if not statements:
        md_lines.append("No statements found matching criteria.")
        return "\n".join(md_lines)

    md_lines.append("## Extracted Statements")
    
    for i, stmt in enumerate(statements, 1):
        text = stmt.get("statement_text", "")
        kw = stmt.get("keyword", "")
        sect = stmt.get("section", "")
        stype = stmt.get("statement_type", "")
        conf = stmt.get("confidence", 0.0)
        
        md_lines.append(f"### {i}. {sect}")
        md_lines.append(f"> \"{text}\"")
        md_lines.append(f"- **Type:** {stype}")
        md_lines.append(f"- **Keyword Match:** {kw}")
        md_lines.append(f"- **Confidence:** {conf:.2f}")
        md_lines.append("")

    return "\n".join(md_lines)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/react/obligation_register", response_model=ObligationRegisterResponse)
async def generate_obligation_register(req: ObligationRegisterRequest) -> ObligationRegisterResponse:
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service initialization failed. Check logs.")

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Calls Enterprise System
        # result_dict = run_supervisor(query)
        result_dict = orchestrator.run_enterprise_compliance_system(query)
        
        # Format for UI
        markdown_answer = format_obligations_to_markdown(result_dict)
        source = "enterprise_system"
        
        return ObligationRegisterResponse(
            answer=markdown_answer,
            metadata={"source": source, "execution_meta": result_dict.get("metadata")}
        )

    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)
        raise HTTPException(
            status_code=500, 
            detail=f"ERROR: {str(e)}"
        )

@app.post("/api/obligations")
async def get_raw_obligations(req: ObligationRegisterRequest) -> Dict:
    """Dedicated API endpoint returning raw JSON obligations list"""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service initialization failed. Check logs.")

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        result_dict = orchestrator.run_enterprise_compliance_system(query)
        
        # Return clean JSON dict
        # Ensure Pydantic models are serialized
        # The Orchestrator returns objects which might prevent simple dict return
        # But FastAPI handles Pydantic serialization usually if response model is generic Dict?
        # Let's manual dump if needed. EnterpriseObligation is Pydantic.
        
        # Just return the result_dict. FastAPI's JSONResponse encoder usually handles dicts with primitives.
        # But if list contains Pydantic models, we might need jsonable_encoder.
        # However, result_dict has "final_obligations" which is List[EnterpriseObligation].
        
        return result_dict

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("="*80)
    print("STARTING RISKSAFEAI APPLICATION")
    print("="*80)
    print(f"Python version: {sys.version}")
    print(f"Working directory: {Path.cwd()}")
    print(f"OPENAI_API_KEY present: {bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"PINECONE_API_KEY present: {bool(os.getenv('PINECONE_API_KEY'))}")
    print("="*80)
    # Make sure to run from root: python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
