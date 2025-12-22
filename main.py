import os
import sys
import io
import traceback
from pathlib import Path
from typing import Dict, List

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
                        # Try to encode as ASCII if UTF-8 fails
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
        
        # Wrap the buffer in UTF-8 first, then our SafeStream
        try:
            sys.stdout = SafeStream(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
            sys.stderr = SafeStream(io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace'))
        except:
            # Fallback if wrapping fails
            sys.stdout = SafeStream(sys.stdout)
            sys.stderr = SafeStream(sys.stderr)

patch_windows_console()

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from compliance_chat.src.react_agent.agent import ReactAgent
from compliance_chat.exception.custom_exception import DocumentPortalException
from compliance_chat.logger import GLOBAL_LOGGER as log

app = FastAPI(title="RiskSafeAI Compliance Assistant")

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
    answer: str
    metadata: Dict

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
        # Initialize ReAct agent
        agent = ReactAgent()
        result = agent.run(query)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return ObligationRegisterResponse(
            answer=result["answer"],
            metadata=result["metadata"]
        )

    except DocumentPortalException as e:
        error_trace = traceback.format_exc()
        log.error("DocumentPortalException in endpoint", error=str(e), traceback=error_trace)
        raise HTTPException(status_code=500, detail=f"Compliance Error: {str(e)}")
    except Exception as e:
        error_trace = traceback.format_exc()
        log.error(f"Error in endpoint: {e}", traceback=error_trace)
        # We return a very clean error message plus traceback
        raise HTTPException(
            status_code=500, 
            detail=f"ERROR: {str(e)}\n\nCheck terminal for full traceback or see below:\n{error_trace}"
        )

if __name__ == "__main__":
    import uvicorn
    # Set reload=False to see if it's a reloader issue
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
