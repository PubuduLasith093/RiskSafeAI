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

# --- Import New Modular App ---
# Ensure root is in path if needed (it is by default when running python main.py)
from compliance_chat.app.main import ObligationRegisterOrchestrator
from compliance_chat.logger import GLOBAL_LOGGER as log

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
def format_obligations_to_markdown(result: Dict) -> str:
    """Format the obligations list into a nice Markdown string for the UI."""
    obligations = result.get("obligations", [])
    product_type = result.get("product_type", "Unknown")
    
    md_lines = []
    md_lines.append(f"# Obligation Register: {product_type}")
    md_lines.append(f"**Total Obligations:** {len(obligations)}\n")
    
    if not obligations:
        md_lines.append("No obligations found.")
        return "\n".join(md_lines)

    # Summary Table
    md_lines.append("## Summary Table")
    md_lines.append("| Obligation | Priority | Type | Source |")
    md_lines.append("|---|---|---|---|")
    for obl in obligations:
        name = obl.get("obligation_name", "N/A")
        prio = obl.get("priority", "medium")
        otyp = obl.get("type", "must_do")
        doc = f"{obl.get('document_name', '')} {obl.get('document_subsection', '')}"
        md_lines.append(f"| {name} | {prio} | {otyp} | {doc} |")
    
    md_lines.append("\n## Detailed Obligations")
    
    for i, obl in enumerate(obligations, 1):
        name = obl.get("obligation_name", "N/A")
        desc = obl.get("description", "No description")
        conf = obl.get("confidence_score", 0.0)
        reg = obl.get("regulator", "N/A")
        doc_name = obl.get("document_name", "N/A")
        sub = obl.get("document_subsection", "")
        
        md_lines.append(f"### {i}. {name}")
        md_lines.append(f"- **Regulator:** {reg}")
        md_lines.append(f"- **Source:** {doc_name} {sub}")
        md_lines.append(f"- **Description:** {desc}")
        md_lines.append(f"- **Priority:** {obl.get('priority', 'medium').upper()}")
        md_lines.append(f"- **Type:** {obl.get('type', 'must_do').replace('_', ' ').title()}")
        md_lines.append(f"- **Confidence:** {conf:.2f}")
        
        rels = obl.get("relates_to", [])
        if rels:
            md_lines.append("- **Related To:**")
            for r in rels:
                md_lines.append(f"  - {r.get('related_obligation')} ({r.get('related_document')})")
        
        md_lines.append("")

    return "\n".join(md_lines)

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/react/obligation_register", response_model=ObligationRegisterResponse)
async def generate_obligation_register(req: ObligationRegisterRequest) -> ObligationRegisterResponse:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Initialize Orchestrator
        orchestrator = ObligationRegisterOrchestrator()
        result_dict = orchestrator.generate_obligation_register(query)
        
        # Format output to Markdown
        markdown_answer = format_obligations_to_markdown(result_dict)
        
        # We ignore extra metadata in the final response as requested
        return ObligationRegisterResponse(
            answer=markdown_answer,
            metadata={"source": "risk_safe_ai_orchestrator"}
        )

    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace) # Print to console
        raise HTTPException(
            status_code=500, 
            detail=f"ERROR: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    # Make sure to run from root: python main.py
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
