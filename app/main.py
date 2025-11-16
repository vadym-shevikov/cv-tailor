"""Minimal FastAPI server for the CV Optimization Assistant."""
from __future__ import annotations

from pathlib import Path

from .logging_utils import configure_logging, get_logger

# Configure logging on module load
configure_logging()

# Module-level constants
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()

logger = get_logger("main")


# ============================================================================
# FastAPI Application
# ============================================================================

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .graph import build_graph

app = FastAPI(title="CV Optimization Assistant")

# Templates
templates = Jinja2Templates(directory=str(_PROJECT_ROOT / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main upload form."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    """
    Accept CV (PDF) and job description, run the LangGraph workflow,
    and return the final markdown report as rendered HTML.
    """
    try:
        # Read PDF bytes
        cv_pdf_bytes = await cv_file.read()
        
        # Build and run the graph
        graph = build_graph()
        
        initial_state = {
            "cv_pdf_bytes": cv_pdf_bytes,
            "job_description_text": job_description,
        }
        
        # Run the graph
        final_state = await graph.ainvoke(initial_state)
        
        # Extract the final markdown
        final_markdown = final_state.get("final_markdown", "")
        
        # Return the template with the markdown result
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "result_markdown": final_markdown,
                "job_description_text": job_description,
            },
        )
    except Exception as e:
        logger.exception("Error during CV analysis")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": f"An error occurred during analysis: {str(e)}",
                "job_description_text": job_description,
            },
        )