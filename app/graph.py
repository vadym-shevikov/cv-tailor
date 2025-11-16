"""LangGraph workflow definition for the CV Optimization Assistant."""
from __future__ import annotations

from typing import Optional, TypedDict

try:
    from langgraph.graph import END, StateGraph
except ModuleNotFoundError:  # pragma: no cover - allows the server to boot without LangGraph
    END = "__end__"
    StateGraph = None  # type: ignore

from .agents import run_analysis_agent, run_parsing_agent, run_rewriting_agent
from .models import AnalysisReport, ParsedJD, RewrittenSections, StructuredCV


class GraphState(TypedDict, total=False):
    """Shared state passed between graph nodes."""

    cv_pdf_bytes: bytes
    job_description_text: str
    structured_cv: StructuredCV
    parsed_jd: ParsedJD
    analysis_report: AnalysisReport
    rewritten_sections: RewrittenSections
    final_markdown: str


def build_graph():
    """Create the LangGraph with placeholder agent nodes.

    The graph follows the linear flow described in AGENT.md:
    parsing -> analysis -> rewriting. Each node currently calls a stub
    implementation so we can exercise the pipeline end-to-end.
    """

    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed. Please add it to your environment before running the workflow."
        )

    workflow = StateGraph(GraphState)
    workflow.add_node("parsing", run_parsing_agent)
    workflow.add_node("analysis", run_analysis_agent)
    workflow.add_node("rewriting", run_rewriting_agent)

    workflow.set_entry_point("parsing")
    workflow.add_edge("parsing", "analysis")
    workflow.add_edge("analysis", "rewriting")
    workflow.add_edge("rewriting", END)

    return workflow.compile()
