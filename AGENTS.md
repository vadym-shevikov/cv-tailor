# AGENT.md – CV Optimization Assistant

## Summary

This repository implements a **local multi-agent CV optimization assistant**.

Input:
- CV as a **PDF** (English)
- **Job description** as plain text (English)

Output:
- Rewritten CV sections (Summary, Skills, selected Experience bullets)
- Explanations why each change improves **job match** and **ATS readiness**

The system is built with:

- **LangChain 1.x**
- **LangGraph 1.x**
- A **ready-made MCP server** (filesystem MCP) to access local Markdown knowledge files:
  - `kb/ats_tips.md`
  - `kb/cv_best_practices.md`
  - `kb/bullet_examples.md`

The primary LLM is **GPT-4o-mini** (or similar), configured via environment variables.

This is intentionally a **small, educational project** that demonstrates:
- Multi-agent orchestration with LangGraph
- Integrating MCP as a knowledge layer
- Practical CV + ATS optimization logic

---

## High-Level Flow

1. User uploads a **PDF CV** and pastes a **job description** via a minimal web UI.
2. Backend calls the **LangGraph workflow** with:
   - `cv_pdf_bytes`
   - `job_description_text`
3. The graph coordinates three agents:
   1. **Document Parsing & Structuring Agent**
   2. **Analysis & ATS Checker Agent**
   3. **Rewriting & Explanation Agent**
4. The final node assembles a **Markdown report**, which the UI renders.

---

## Agents

### 1. Document Parsing & Structuring Agent

**Goal:** Convert unstructured inputs (PDF CV + job description) into a structured representation that other agents can use.

**Inputs:**
- Raw PDF bytes of the CV
- Job description text

**Responsibilities:**
- Extract text from the PDF
- Perform basic cleanup (remove obvious noise like page numbers where possible)
- Heuristically segment the CV into:
  - Summary / Profile
  - Skills / Tech stack
  - Experience (per job)
- Parse the job description into:
  - Core responsibilities
  - Required skills / tools / technologies
  - Nice-to-have skills (if detectable)

**Outputs:**
- `StructuredCV` – structured Python object (e.g. Pydantic model) with:
  - `summary: str | None`
  - `skills: list[str] | None`
  - `experience: list[ExperienceEntry]`
  - `raw_text: str` (fallback)
- `ParsedJD` – structured job description:
  - `role_title: str | None`
  - `responsibilities: list[str]`
  - `required_skills: list[str]`
  - `nice_to_have_skills: list[str]`
  - `raw_text: str`

**Tools:**
- Local PDF parsing utility (`pdf_utils.py`)

**Constraints:**
- If segmentation fails, the agent should return best-effort extraction and mark fields as `None` or empty, rather than failing the whole pipeline.

---

### 2. Analysis & ATS Checker Agent

**Goal:** Evaluate how well the CV matches the job description and how ATS-friendly it is, using the knowledge base exposed by MCP.

**Inputs:**
- `StructuredCV`
- `ParsedJD`
- Knowledge content fetched from MCP (`ats_tips.md`, `cv_best_practices.md`, `bullet_examples.md` as needed)

**Responsibilities:**
- Compare CV content with job requirements:
  - Check presence/absence of **required skills** in CV
  - Detect potential relevance of experience to the job responsibilities
- Assess **ATS readiness**, based on knowledge from:
  - `ats_tips.md`
  - `cv_best_practices.md`
- Identify:
  - Missing or weak keywords
  - Structural issues (unclear headings, lack of bullet points, etc.)
  - Stylistic issues (weak verbs, lack of impact/metrics)

**Outputs:**
- `AnalysisReport`:
  - `match_level: str` (e.g. "Low", "Medium", "High")
  - `ats_readiness: str`
  - `missing_keywords: list[str]`
  - `strengths: list[str]`
  - `issues: list[str]` (plain language)
  - `improvement_opportunities: list[str]` (what to target in rewriting)

**Tools:**
- MCP client / MCP tools:
  - Filesystem MCP server exposing:
    - `kb/ats_tips.md`
    - `kb/cv_best_practices.md`
    - `kb/bullet_examples.md`
- LLM via LangChain for reasoning over CV + JD + KB content

**Constraints:**
- Use knowledge from the MCP KB as **guidance**, not as strict rules.
- Provide concise, actionable findings (avoid very long essays).

---

### 3. Rewriting & Explanation Agent

**Goal:** Generate **rewritten CV sections** that better match the job and follow ATS best practices, with explanations.

**Inputs:**
- `StructuredCV`
- `ParsedJD`
- `AnalysisReport`
- (Optionally) relevant snippets from MCP KB

**Responsibilities:**
- Rewrite at least:
  - **Summary / Profile**
  - **Skills / Tech stack**
  - **Selected experience bullets** (1–3 most relevant roles)
- For each section:
  - Provide `original` text (or a concise excerpt)
  - Provide `suggested` rewritten text (in Markdown)
  - Explain **why** this change is beneficial:
    - Which job requirements or skills are now reflected
    - How the wording/structure helps with ATS

**Outputs:**
- `RewrittenSections`:
  - `summary_before: str | None`
  - `summary_after: str | None`
  - `summary_explanation: str | None`
  - `skills_before: str | None`
  - `skills_after: str | None`
  - `skills_explanation: str | None`
  - `experience_items: list[ExperienceRewrite]` (`before`, `after`, `explanation`)
- Final **Markdown report** assembled from:
  - `AnalysisReport`
  - `RewrittenSections`

**Tools:**
- LLM via LangChain (GPT-4o-mini or compatible)

**Constraints:**
- **No hallucinations of experience**:
  - Do not invent new roles, companies, or responsibilities that are not present in the CV.
  - You may adjust wording, emphasize certain aspects, merge or split bullets, but the underlying facts must stay true.
- Prefer **concise, impact-oriented** rewrites:
  - Action verb + what you did + how you did it + measurable/clear result where possible.

---

## Orchestration (LangGraph)

The graph is linear and simple for clarity:

1. **Start → Parsing & Structuring Agent**
2. **Parsing & Structuring Agent → Analysis & ATS Checker Agent**
3. **Analysis & ATS Checker Agent → Rewriting & Explanation Agent**
4. **Rewriting & Explanation Agent → Final Output Node**

### State

The LangGraph state should contain:

- `cv_pdf_bytes: bytes`
- `job_description_text: str`
- `structured_cv: StructuredCV | None`
- `parsed_jd: ParsedJD | None`
- `analysis_report: AnalysisReport | None`
- `rewritten_sections: RewrittenSections | None`
- `final_markdown: str | None`

### Error Handling

- If PDF parsing fails:
  - Set an error flag and produce a simple markdown message explaining the issue.
- If the job description is missing or too short:
  - Produce a warning in the markdown output and limit recommendations to general ATS improvements.

---

## Knowledge Layer via MCP

The assistant uses a **filesystem MCP server** to access the local `kb/` directory.

### Knowledge Files

- `kb/ats_tips.md`
- `kb/cv_best_practices.md`
- `kb/bullet_examples.md`

These files contain human-written guidance on:
- ATS formatting and keyword strategies
- Recommended CV sections and styles
- Examples of strong bullet points

### Usage Pattern

- The Analysis & ATS Checker agent:
  - Calls MCP tools to read the relevant knowledge files.
  - Uses them as context to evaluate CV structure and ATS readiness.
- The Rewriting agent:
  - May optionally request examples from `bullet_examples.md` to inspire better wording patterns (not copy verbatim).

---

## Interface

### Web UI

- Minimal HTML form:
  - File input: CV (PDF, required)
  - Textarea: job description (required)
  - Submit button
- Results page:
  - Renders `final_markdown` as HTML
  - Sections:
    - Overall Match & ATS Readiness
    - Summary (Before / After / Why)
    - Skills (Before / After / Why)
    - Experience (Before / After / Why)

### Backend

- Endpoints (example):
  - `GET /` – serves the HTML form
  - `POST /analyze` – accepts form data, invokes LangGraph, returns rendered markdown

---

## Configuration

Environment variables (example):

- `OPENAI_API_KEY` – for GPT-4o-mini (or equivalent)
- `LLM_MODEL_NAME` – optional override for the model
- `MCP_SERVER_URI` – MCP server address/config (if needed)

Defaults should be simple for local development.

---

## Extension Ideas (Future)

- Support for additional CV formats (DOCX, plain text).
- Multi-language support (e.g., Ukrainian ↔ English).
- Additional agents:
  - Cover letter generator
  - LinkedIn summary generator
- Optional integration with LangSmith for tracing and debugging.

