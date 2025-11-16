"""Pydantic models shared across the CV Optimization Assistant."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    """Represents a single role or position extracted from the CV."""

    role: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class StructuredCV(BaseModel):
    """Structured representation of the candidate CV."""

    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[ExperienceEntry] = Field(default_factory=list)
    raw_text: str = ""


class ParsedJD(BaseModel):
    """Structured version of the job description."""

    role_title: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    raw_text: str = ""


class AnalysisReport(BaseModel):
    """Summary of findings from the analysis/ATS agent."""

    match_level: Optional[str] = None
    ats_readiness: Optional[str] = None
    missing_keywords: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    improvement_opportunities: List[str] = Field(default_factory=list)


class ExperienceRewrite(BaseModel):
    """Captures before/after bullets and rationale for a single experience block."""

    before: Optional[str] = None
    after: Optional[str] = None
    explanation: Optional[str] = None


class RewrittenSections(BaseModel):
    """Holds rewritten sections returned by the rewriting agent."""

    summary_before: Optional[str] = None
    summary_after: Optional[str] = None
    summary_explanation: Optional[str] = None
    skills_before: Optional[str] = None
    skills_after: Optional[str] = None
    skills_explanation: Optional[str] = None
    experience_items: List[ExperienceRewrite] = Field(default_factory=list)
    final_markdown: Optional[str] = None
