"""Agent implementations for the CV Optimization Assistant."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .mcp_client import get_kb_text
from .models import (
    AnalysisReport,
    ExperienceEntry,
    ExperienceRewrite,
    ParsedJD,
    RewrittenSections,
    StructuredCV,
)
from .pdf_utils import extract_text_from_pdf


logger = logging.getLogger(__name__)

AgentState = Dict[str, Any]


def parse_json_from_llm(raw: str) -> Dict[str, Any]:
    """
    Parse JSON from LLM output that may contain optional Markdown fences.

    Args:
        raw: Raw LLM output as a string.

    Returns:
        Parsed JSON payload as a dictionary.

    Raises:
        ValueError: If JSON parsing fails even after removing code fences.
    """

    text = (raw or "").strip()
    if not text:
        raise ValueError("LLM response was empty.")

    if text.startswith("```"):
        lines = text.splitlines()
        # Remove the opening ```... fence
        lines = lines[1:]
        if not lines:
            raise ValueError("LLM response started with a code fence but contained no content.")
        # Remove trailing blank lines before checking for the closing fence
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Failed to parse JSON: {exc}") from exc


def run_parsing_agent(state: AgentState) -> AgentState:
    """Parse the uploaded CV + job description into structured objects."""

    cv_bytes: bytes = state.get("cv_pdf_bytes", b"")
    jd_text: str = state.get("job_description_text", "")

    cv_text = extract_text_from_pdf(cv_bytes)
    structured_cv = StructuredCV(
        summary=_extract_cv_summary(cv_text),
        skills=_extract_cv_skills(cv_text),
        experience=_extract_cv_experience(cv_text),
        raw_text=cv_text,
    )
    parsed_jd = _parse_job_description(jd_text)

    updated = dict(state)
    updated["structured_cv"] = structured_cv
    updated["parsed_jd"] = parsed_jd
    return updated


async def run_analysis_agent(state: AgentState) -> AgentState:
    """Use KB knowledge + LLM reasoning to produce an AnalysisReport."""

    structured_cv: StructuredCV = state.get("structured_cv", StructuredCV())
    parsed_jd: ParsedJD = state.get("parsed_jd", ParsedJD())

    ats_tips, cv_best = await asyncio.gather(
        get_kb_text("ats_tips"),
        get_kb_text("cv_best_practices"),
    )

    heuristic_missing = _detect_missing_keywords(
        structured_cv.skills, parsed_jd.required_skills
    )
    llm_payload = await _generate_analysis_summary(structured_cv, parsed_jd, ats_tips, cv_best)

    if llm_payload is None:
        logger.warning("Analysis agent falling back to heuristic output")
        report = _build_heuristic_report(structured_cv, parsed_jd, heuristic_missing)
    else:
        report = AnalysisReport(
            match_level=llm_payload.get("match_level") or _estimate_match_level(
                parsed_jd.required_skills, heuristic_missing
            ),
            ats_readiness=llm_payload.get("ats_readiness") or "Unknown",
            missing_keywords=llm_payload.get("missing_keywords") or heuristic_missing,
            strengths=llm_payload.get("strengths", []),
            issues=llm_payload.get("issues", []),
            improvement_opportunities=llm_payload.get("improvement_opportunities", []),
        )

    updated = dict(state)
    updated["analysis_report"] = report
    return updated


async def run_rewriting_agent(state: AgentState) -> AgentState:
    """Rewrite CV sections using KB knowledge while avoiding hallucinations."""

    structured_cv: StructuredCV = state.get("structured_cv", StructuredCV())
    parsed_jd: ParsedJD = state.get("parsed_jd", ParsedJD())
    analysis: AnalysisReport = state.get("analysis_report", AnalysisReport())

    bullet_examples = await get_kb_text("bullet_examples")
    rewrite_payload = await _generate_rewrites(structured_cv, parsed_jd, analysis, bullet_examples)

    if rewrite_payload is None:
        logger.warning("Rewriting agent could not parse LLM output; returning pass-through sections")
        rewritten = RewrittenSections(
            summary_before=structured_cv.summary,
            summary_after=structured_cv.summary,
            summary_explanation="Rewriting unavailable.",
            skills_before=", ".join(structured_cv.skills) or None,
            skills_after=", ".join(structured_cv.skills) or None,
            skills_explanation="Rewriting unavailable.",
            experience_items=[
                ExperienceRewrite(before=entry.raw_text, after=entry.raw_text, explanation=None)
                for entry in structured_cv.experience[:3]
            ],
        )
    else:
        rewritten = _payload_to_rewrites(rewrite_payload)

    final_markdown = _build_markdown_report(analysis, rewritten)
    rewritten.final_markdown = final_markdown

    updated = dict(state)
    updated["rewritten_sections"] = rewritten
    updated["final_markdown"] = final_markdown
    return updated


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _extract_cv_summary(cv_text: str) -> str | None:
    paragraphs = [p.strip() for p in cv_text.split("\n\n") if p.strip()]
    return paragraphs[0] if paragraphs else None


def _extract_cv_skills(cv_text: str) -> List[str]:
    normalized = cv_text.lower()
    marker_index = -1
    for marker in ["technical skills", "skills", "tech stack", "technologies"]:
        marker_index = normalized.find(marker)
        if marker_index != -1:
            break
    if marker_index == -1:
        return []

    section = cv_text[marker_index:].split("\n\n", 1)[0]
    section = section.split(":", 1)[-1]
    tokens = [token.strip("•-* \n") for token in section.replace("\n", ",").split(",")]
    skills = [token for token in tokens if len(token) > 1]
    # Deduplicate while keeping order
    seen = set()
    ordered: List[str] = []
    for skill in skills:
        lower = skill.lower()
        if lower in seen:
            continue
        seen.add(lower)
        ordered.append(skill)
    return ordered


def _extract_cv_experience(cv_text: str) -> List[ExperienceEntry]:
    blocks = [block.strip() for block in cv_text.split("\n\n") if block.strip()]
    experience_entries: List[ExperienceEntry] = []
    for block in blocks:
        if not _looks_like_experience(block):
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        role = lines[0] if lines else None
        bullets = [line.lstrip("•-* ").strip() for line in lines[1:] if line.startswith(("-", "•", "*"))]
        experience_entries.append(
            ExperienceEntry(
                role=role,
                bullets=bullets,
                raw_text=block,
            )
        )
    return experience_entries


def _looks_like_experience(block: str) -> bool:
    lowered = block.lower()
    if "experience" in lowered or "responsibilities" in lowered:
        return True
    if any(char.isdigit() for char in block):  # often dates
        return True
    return any(block.lstrip().startswith(symbol) for symbol in ("-", "•", "*"))


def _parse_job_description(text: str) -> ParsedJD:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    role_title = lines[0] if lines else None
    responsibilities = _extract_section_lines(text, {"responsibilities", "what you'll do"})
    required_skills = _extract_section_lines(text, {"requirements", "required", "must have"})
    nice_to_have = _extract_section_lines(text, {"nice to have", "preferred", "bonus"})

    if not responsibilities:
        responsibilities = _fallback_bullets(lines)
    if not required_skills:
        required_skills = _fallback_keywords(lines)

    return ParsedJD(
        role_title=role_title,
        responsibilities=responsibilities,
        required_skills=required_skills,
        nice_to_have_skills=nice_to_have,
        raw_text=text,
    )


def _extract_section_lines(text: str, headers: Iterable[str]) -> List[str]:
    header_markers = [h.lower() for h in headers]
    lines = text.splitlines()
    collecting = False
    collected: List[str] = []
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            if collecting and collected:
                break
            continue
        if any(header in lowered for header in header_markers):
            collecting = True
            collected = []
            continue
        if collecting:
            if stripped.startswith(("-", "•", "*")):
                collected.append(stripped.lstrip("-•* "))
            else:
                collected.append(stripped)
    return collected


def _fallback_bullets(lines: List[str]) -> List[str]:
    bullets = [line.lstrip("-•* ") for line in lines if line.startswith(("-", "•", "*"))]
    return bullets[:8]


def _fallback_keywords(lines: List[str]) -> List[str]:
    keywords: List[str] = []
    for line in lines[:20]:
        if ":" in line:
            _, tail = line.split(":", 1)
            keywords.extend([item.strip() for item in tail.split(",") if item.strip()])
    return keywords[:10]


def _detect_missing_keywords(cv_skills: List[str], required_skills: List[str]) -> List[str]:
    cv_skill_set = {skill.lower() for skill in cv_skills}
    missing = [skill for skill in required_skills if skill.lower() not in cv_skill_set]
    return missing


def _estimate_match_level(required_skills: List[str], missing_skills: List[str]) -> str:
    if not required_skills:
        return "Unknown"
    coverage = 1 - (len(missing_skills) / len(required_skills))
    if coverage >= 0.75:
        return "High"
    if coverage >= 0.4:
        return "Medium"
    return "Low"


def _build_markdown_report(analysis: AnalysisReport, rewrites: RewrittenSections) -> str:
    lines = ["## CV Optimization Assistant"]

    lines.append("### Overall Match & ATS Readiness")
    lines.append(f"- Match level: {analysis.match_level or 'Unknown'}")
    lines.append(f"- ATS readiness: {analysis.ats_readiness or 'Unknown'}")
    if analysis.missing_keywords:
        lines.append("- Missing keywords: " + ", ".join(analysis.missing_keywords))
    if analysis.strengths:
        lines.append("- Strengths: " + "; ".join(analysis.strengths))
    if analysis.issues:
        lines.append("- Issues: " + "; ".join(analysis.issues))

    if analysis.improvement_opportunities:
        lines.append("")
        lines.append("**Improvement opportunities**")
        for tip in analysis.improvement_opportunities:
            lines.append(f"- {tip}")

    def _section(before: str | None, after: str | None, explanation: str | None, title: str) -> None:
        if not (before or after):
            return
        lines.append("")
        lines.append(f"### {title}")
        if before:
            lines.append("**Before**")
            lines.append(before.strip())
        if after:
            lines.append("")
            lines.append("**After**")
            lines.append(after.strip())
        if explanation:
            lines.append("")
            lines.append("_Why:_ " + explanation.strip())

    _section(rewrites.summary_before, rewrites.summary_after, rewrites.summary_explanation, "Summary")
    _section(rewrites.skills_before, rewrites.skills_after, rewrites.skills_explanation, "Skills")

    if rewrites.experience_items:
        lines.append("")
        lines.append("### Experience")
        for idx, item in enumerate(rewrites.experience_items, start=1):
            lines.append(f"#### Role {idx}")
            if item.before:
                lines.append("**Before**")
                lines.append(item.before.strip())
            if item.after:
                lines.append("")
                lines.append("**After**")
                lines.append(item.after.strip())
            if item.explanation:
                lines.append("")
                lines.append("_Why:_ " + item.explanation.strip())
            lines.append("")

    lines.append("_Generated by the CV Optimization Assistant._")
    return "\n".join(line for line in lines if line is not None)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_llm() -> ChatOpenAI:
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    return ChatOpenAI(temperature=0.3, model=model_name)


_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an ATS expert. Use the provided CV summary, skills, experience, job "
            "description details, and knowledge base tips to evaluate alignment. Respond with "
            "valid JSON matching the schema provided. You must respond with ONLY raw JSON. "
            "Do not wrap the JSON in ```json``` or any other Markdown formatting. Do not add any "
            "explanation text before or after the JSON.",
        ),
        (
            "human",
            "CV summary: {cv_summary}\n\nCV skills: {cv_skills}\n\nCV experience: {cv_experience}\n\n"
            "Job responsibilities: {jd_responsibilities}\n\nJob required skills: {jd_required_skills}\n\n"
            "ATS tips: {ats_tips}\n\nCV best practices: {cv_best_practices}\n\n"
            "Return JSON with keys match_level, ats_readiness, strengths, issues, missing_keywords, improvement_opportunities.",
        ),
    ]
)


async def _generate_analysis_summary(
    structured_cv: StructuredCV, parsed_jd: ParsedJD, ats_tips: str, cv_best: str
) -> Dict[str, Any] | None:
    llm = _get_llm()
    parser = StrOutputParser()
    chain = _ANALYSIS_PROMPT | llm | parser

    experience_text = _summarize_experience_blocks(structured_cv.experience)
    try:
        raw = await chain.ainvoke(
            {
                "cv_summary": structured_cv.summary or "",
                "cv_skills": ", ".join(structured_cv.skills) or "",
                "cv_experience": experience_text,
                "jd_responsibilities": "\n".join(parsed_jd.responsibilities) or "",
                "jd_required_skills": ", ".join(parsed_jd.required_skills) or "",
                "ats_tips": ats_tips,
                "cv_best_practices": cv_best,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Analysis LLM call failed: %s", exc)
        return None

    try:
        return parse_json_from_llm(raw)
    except ValueError:
        snippet = raw.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        logger.warning("LLM response was not valid JSON after cleaning, falling back: %s", snippet)
        return None


def _build_heuristic_report(
    structured_cv: StructuredCV, parsed_jd: ParsedJD, missing_keywords: List[str]
) -> AnalysisReport:
    strengths = []
    issues = []
    if structured_cv.summary:
        strengths.append("Summary present")
    else:
        issues.append("Summary section missing or empty.")
    if structured_cv.skills:
        strengths.append("Skills detected")
    else:
        issues.append("Skills section missing.")
    if structured_cv.experience:
        strengths.append("Experience entries detected")
    else:
        issues.append("Could not identify experience bullets.")
    if missing_keywords:
        issues.append("Some required skills are not reflected in the CV.")

    return AnalysisReport(
        match_level=_estimate_match_level(parsed_jd.required_skills, missing_keywords),
        ats_readiness="Basic" if not issues else "Needs work",
        missing_keywords=missing_keywords,
        strengths=strengths,
        issues=issues,
        improvement_opportunities=[
            "Tailor skills to highlight JD keywords.",
            "Add ATS-friendly headings and bullet points.",
        ],
    )


_REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You rewrite CV sections for ATS. Only rephrase information explicitly provided. "
            "Do NOT introduce new skills, roles, companies, or accomplishments. You must respond "
            "with ONLY raw JSON. Do not wrap the JSON in ```json``` or any other Markdown formatting. "
            "Do not add any explanation text before or after the JSON.",
        ),
        (
            "human",
            "CV summary: {cv_summary}\n\nCV skills: {cv_skills}\n\n"
            "Experience blocks (JSON): {experience_blocks}\n\n"
            "Job description focus: {job_focus}\n\nAnalysis focal points: {analysis_points}\n\n"
            "Bullet style inspiration: {bullet_examples}\n\n"
            "Return JSON with keys summary (before, after, explanation), skills (before, after, explanation),"
            " experience (list of objects with before, after, explanation).",
        ),
    ]
)


async def _generate_rewrites(
    structured_cv: StructuredCV,
    parsed_jd: ParsedJD,
    analysis: AnalysisReport,
    bullet_examples: str,
) -> Dict[str, Any] | None:
    llm = _get_llm()
    parser = StrOutputParser()
    chain = _REWRITE_PROMPT | llm | parser

    experience_payload = [
        {
            "role": entry.role,
            "raw_text": entry.raw_text,
            "bullets": entry.bullets or ([entry.raw_text] if entry.raw_text else []),
        }
        for entry in structured_cv.experience[:3]
    ]

    if not experience_payload and structured_cv.raw_text:
        experience_payload = [
            {"role": None, "raw_text": structured_cv.raw_text[:500], "bullets": []}
        ]

    try:
        raw = await chain.ainvoke(
            {
                "cv_summary": structured_cv.summary or "",
                "cv_skills": ", ".join(structured_cv.skills) or "",
                "experience_blocks": json.dumps(experience_payload, ensure_ascii=False),
                "job_focus": json.dumps(
                    {
                        "role": parsed_jd.role_title,
                        "required_skills": parsed_jd.required_skills,
                        "responsibilities": parsed_jd.responsibilities,
                    },
                    ensure_ascii=False,
                ),
                "analysis_points": json.dumps(
                    {
                        "strengths": analysis.strengths,
                        "issues": analysis.issues,
                        "missing_keywords": analysis.missing_keywords,
                    },
                    ensure_ascii=False,
                ),
                "bullet_examples": bullet_examples,
            }
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Rewriting LLM call failed: %s", exc)
        return None

    try:
        return parse_json_from_llm(raw)
    except ValueError:
        snippet = raw.strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        logger.warning("LLM response was not valid JSON after cleaning, falling back: %s", snippet)
        return None


def _payload_to_rewrites(payload: Dict[str, Any]) -> RewrittenSections:
    summary_block = payload.get("summary") or {}
    skills_block = payload.get("skills") or {}
    experience_blocks = payload.get("experience") or []

    experience_items = []
    for block in experience_blocks:
        experience_items.append(
            ExperienceRewrite(
                before=block.get("before"),
                after=block.get("after"),
                explanation=block.get("explanation"),
            )
        )

    return RewrittenSections(
        summary_before=summary_block.get("before"),
        summary_after=summary_block.get("after"),
        summary_explanation=summary_block.get("explanation"),
        skills_before=skills_block.get("before"),
        skills_after=skills_block.get("after"),
        skills_explanation=skills_block.get("explanation"),
        experience_items=experience_items,
    )


def _summarize_experience_blocks(experience: List[ExperienceEntry]) -> str:
    summaries = []
    for entry in experience[:5]:
        bullets = " | ".join(entry.bullets or [])
        summaries.append(f"Role: {entry.role or 'N/A'} — bullets: {bullets or entry.raw_text}")
    return "\n".join(summaries)

