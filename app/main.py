"""Minimal FastAPI server for the CV Optimization Assistant."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .graph import build_graph

logger = logging.getLogger(__name__)

app = FastAPI(title="CV Optimization Assistant")
templates = Jinja2Templates(directory="app/templates")

_GRAPH = None
_GRAPH_ERROR: Optional[str] = None


def get_graph_executor():
    """Lazy-load the LangGraph workflow."""

    global _GRAPH, _GRAPH_ERROR
    if _GRAPH is not None:
        return _GRAPH
    if _GRAPH_ERROR is not None:
        return None

    try:
        _GRAPH = build_graph()
    except RuntimeError as exc:  # Likely LangGraph missing
        _GRAPH_ERROR = str(exc)
        logger.warning("LangGraph unavailable: %s", exc)
        return None

    return _GRAPH


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the upload form."""

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result_markdown": None,
            "error": None,
            "job_description_text": "",
        },
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    cv_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    """Accept the CV + JD and invoke the LangGraph workflow (placeholder)."""

    error: Optional[str] = None
    result_markdown: Optional[str] = None

    if cv_file.content_type not in {"application/pdf", "application/x-pdf"}:
        error = "Only PDF CVs are supported in this version."
    elif not job_description.strip():
        error = "Please paste a job description so the system can tailor your CV."

    if error:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "error": error,
                "result_markdown": result_markdown,
                "job_description_text": job_description,
            },
        )

    cv_bytes = await cv_file.read()
    executor = get_graph_executor()
    state: Dict[str, Any] = {
        "cv_pdf_bytes": cv_bytes,
        "job_description_text": job_description,
    }

    if executor is None:
        # LangGraph dependency missing; return a friendly message instead of failing.
        result_markdown = (
            "## CV Optimization Assistant\n\n"
            "The LangGraph dependency is not installed yet, so analysis cannot run."
        )
    else:
        result = await executor.ainvoke(state)
        result_markdown = result.get(
            "final_markdown",
            "## CV Optimization Assistant\n\nPipeline nodes are still placeholders.",
        )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "error": error,
            "result_markdown": result_markdown,
            "job_description_text": job_description,
        },
    )
