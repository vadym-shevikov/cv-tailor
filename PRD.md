
---

# PRD: Multi-Agent CV Optimization Assistant

## 1. Overview

The **CV Optimization Assistant** is a local, multi-agent AI tool that takes as input:

* A **candidate CV** (PDF, English only)
* A **job description** (text, English only)

and returns:

* **Rewritten CV sections** (e.g., Summary, Skills, Experience bullets)
* **Explanations** of *why* each change is recommended, explicitly referencing the job description and ATS best practices.

The system must:

* Be built with **LangChain 1.x** and **LangGraph 1.x**
* Use **GPT-4o-mini** (or similar) as the primary LLM via LangChain
* Use a **ready-made MCP server** (e.g., filesystem MCP server) to access a small local knowledge base with ATS/CV best practices
* Run **locally**, with a **minimal web UI**:

  * Form: upload CV (PDF) + paste/enter job description text
  * Output: rendered **Markdown** with recommendations and rewritten blocks

This project is intentionally **small and simple** to make it easy to understand the basics of LangChain, LangGraph, MCP, and multi-agent architectures.

---

## 2. Goals & Non-Goals

### 2.1 Goals

1. **Improve CV for a specific job**

   * Analyze CV and job description
   * Identify gaps and misalignment
   * Propose rewritten text tailored to the job

2. **Optimize for ATS checks**

   * Ensure presence of relevant keywords from the job description
   * Improve structure and formatting so it’s ATS-friendly (headings, bullet points, consistent dates, etc.)

3. **Provide human-readable explanations**

   * For each rewritten section, explain:

     * What was changed
     * Why this is better for this job and for ATS

4. **Demonstrate multi-agent orchestration**

   * At least **3 agents** coordinated via **LangGraph**
   * Clear separation of responsibilities per agent

5. **Use a ready-made MCP server as a knowledge layer**

   * Use **filesystem MCP** (or similar) to expose local Markdown knowledge files (ATS tips, CV best practices, example bullet points) as tools to the agents.

6. **Minimal, understandable codebase**

   * Single small repository
   * A handful of Python modules
   * Easy to run locally with simple commands

### 2.2 Non-Goals

* No multi-language support (English only).
* No RAG / vector databases in the initial version.
* No production-grade security, scalability, or multi-user architecture.
* No integration with external ATS APIs.
* No complex front-end SPA; UI is intentionally minimal.

---

## 3. Target Users & Use Cases

### 3.1 Users

* **Job seekers / developers** who want to tailor their CV to a specific job.
* **Technical users** exploring LangChain / LangGraph / MCP who want a concrete example.

### 3.2 Primary Use Cases

1. **Single CV + Job Description Optimization**

   * User uploads a PDF CV and pastes a job description.
   * System returns:

     * Summary of CV–JD match
     * ATS-related issues
     * Rewritten Summary, Skills, and selected Experience bullets

2. **“Before/After” View for Learning**

   * User can quickly see original vs improved text and understand reasoning behind changes.

---

## 4. Functional Requirements

### 4.1 Input

* **CV file**:

  * Format: **PDF**
  * Language: English
* **Job description**:

  * Text area input (plain text, English)

### 4.2 Processing

1. **PDF extraction**

   * Extract readable text from the PDF CV.
   * Basic cleanup (remove obvious noise like page numbers, repeated headers/footers when possible).

2. **CV structuring**

   * Attempt to identify and segment:

     * Summary / Profile
     * Skills / Technologies
     * Experience sections (per job)
   * If sections are ambiguous, degrade gracefully (fall back to generic text chunks).

3. **Job description analysis**

   * Extract:

     * Required skills / technologies / tools
     * Key responsibilities
     * Nice-to-have skills (if clearly stated)
   * Identify **key keywords and phrases** relevant for ATS matching.

4. **ATS-oriented checks**

   * Evaluate:

     * Presence of job-specific keywords in the CV
     * Clarity of headings and structure
     * Bullet point style (action verbs, impact, metrics)
     * Consistency of dates and formatting (basic checks)
   * Produce a **high-level ATS readiness assessment** (e.g., Low / Medium / High) and a short explanation.

5. **Rewriting & recommendations**

   * For at least these sections:

     * **Summary / Profile**
     * **Skills / Tech stack**
     * **Selected Experience bullets** (e.g., 1–3 most relevant roles)
   * Output for each section:

     * **Original text** (short excerpt or block)
     * **New proposed version** (Markdown)
     * **Explanation** describing:

       * Which JD requirements this addresses
       * Why it is more ATS-friendly

6. **Knowledge base usage via MCP**

   * Use a ready-made **filesystem MCP server** (or similar) to access a small local knowledge base, e.g.:

     ```text
     kb/
       ats_tips.md
       cv_best_practices.md
       bullet_examples.md
     ```

   * The MCP server exposes tools that allow the agents to:

     * Retrieve ATS guidelines
     * Retrieve CV best practices
     * Retrieve example bullet points

   * This knowledge influences the analysis and rewriting, so suggestions reflect established CV/ATS best practices.

### 4.3 Output

* Rendered as **Markdown** in the UI, including sections like:

  ````md
  # CV Optimization Report

  ## 1. Overall Match & ATS Readiness
  - Job match: Medium–High
  - ATS readiness: Medium
  - Key missing keywords: Kubernetes, Terraform

  ## 2. Summary (Before / After)

  **Original:**
  > ...

  **Suggested:**
  ```markdown
  ...
  ````

  **Why this is better:**

  * Adds keywords: "payment systems", "high-load", "Kubernetes"
  * Mirrors key responsibilities from the job description

  ```
  ```
* Sections:

  * Overall summary
  * ATS readiness & keyword coverage
  * Summary rewrite
  * Skills rewrite
  * Experience rewrite
  * Optional “Next steps” (e.g. “adapt this CV for similar roles with X/Y focus”).

---

## 5. Multi-Agent Design (LangGraph)

### 5.1 Agent Roles

Minimum set of **3 agents**:

1. **Document Parsing & Structuring Agent**

   * Input: raw PDF bytes, JD text
   * Responsibilities:

     * Extract text from the PDF CV
     * Segment CV into structured components (summary, skills, experience)
     * Normalize text into a structured representation (Python dict / Pydantic model)
   * Tools:

     * PDF parsing utility
   * Outputs:

     * `StructuredCV`
     * `ParsedJD` (key responsibilities and skills lists)

2. **Analysis & ATS Checker Agent**

   * Input: `StructuredCV`, `ParsedJD`, and content from the MCP knowledge base
   * Responsibilities:

     * Compare CV vs JD
     * Evaluate ATS-friendliness using guidelines from the knowledge base (via MCP)
     * Identify gaps, missing keywords, and structural issues
   * Tools:

     * MCP tools (e.g. `get_cv_guidelines`, `get_ats_tips`, or generic filesystem read tools adapted via LangChain MCP adapters)
   * Outputs:

     * `AnalysisReport` with:

       * Match summary
       * ATS readiness level
       * List of specific issues and opportunities for improvement

3. **Rewriting & Explanation Agent**

   * Input: `StructuredCV`, `ParsedJD`, `AnalysisReport`
   * Responsibilities:

     * Generate rewritten Summary, Skills, and selected Experience bullets
     * Ensure alignment with JD and ATS guidelines
     * Provide human-readable explanations for each change
   * Tools:

     * LLM via LangChain (GPT-4o-mini by default)
   * Outputs:

     * `RewrittenSections` (Markdown)
     * `Explanations` attached to each section

### 5.2 Orchestration (LangGraph)

* Define a simple **LangGraph workflow**:

  1. **Start → ParsingAgent**
  2. **ParsingAgent → AnalysisAgent**
  3. **AnalysisAgent → RewritingAgent**
  4. **RewritingAgent → Final Output Node (Markdown assembly)**

* Basic error paths:

  * If PDF parsing fails → error node returns a user-friendly message.
  * If JD is missing or too short → analysis agent returns a warning and limited recommendations.

---

## 6. Knowledge Layer via MCP

### 6.1 MCP Choice

* Use a **ready-made MCP server**, preferably a **filesystem MCP** that:

  * Exposes read-only access to a specific local directory (e.g. `kb/`).
  * Provides tools to read content of the Markdown files.

* Example knowledge files:

  * `kb/ats_tips.md`
  * `kb/cv_best_practices.md`
  * `kb/bullet_examples.md`

* The backend application will:

  * Connect to the MCP server using **LangChain MCP adapters**
  * Wrap MCP tools into LangChain tools for use by the **Analysis & ATS Checker Agent**

### 6.2 Usage Pattern

* When the Analysis agent runs:

  * It calls MCP tools to fetch relevant knowledge snippets (ATS tips, structure guidelines, example bullets).
  * Injects this content into the LLM prompt as “ground truth” guidance.
* This ensures:

  * Recommendations are consistent with the same, explicit CV/ATS guidelines.
  * Behavior is easy to tune by editing local Markdown files without touching code.

---

## 7. System Architecture & Tech Stack

### 7.1 High-Level Architecture

* **Frontend**:

  * Minimal web page with:

    * File upload field (PDF)
    * Text area for job description
    * Submit button
  * Displays Markdown result (converted to HTML or rendered with a Markdown component).

* **Backend**:

  * Python web app (e.g. FastAPI or similar) serving:

    * `GET /` – upload form
    * `POST /analyze` – handle submissions
  * On `/analyze`:

    * Parse inputs
    * Invoke LangGraph workflow with:

      * `cv_pdf_bytes`
      * `job_description_text`
    * Return Markdown report.

* **AI / Orchestration**:

  * LangChain 1.x:

    * LLM wrapper for GPT-4o-mini (or equivalent)
    * MCP tools integrated via MCP adapter
  * LangGraph 1.x:

    * Graph definition of agents and state
  * MCP server:

    * Filesystem-based server serving `kb/` content

### 7.2 Suggested Folder Structure

```bash
cv-tailor/
  PRD.md
  README.md
  requirements.txt
  app/
    main.py            # web server + endpoints
    graph.py           # LangGraph definition
    agents.py          # agent node functions
    models.py          # simple data models (StructuredCV, ParsedJD, etc.)
    pdf_utils.py       # PDF parsing helper
    mcp_client.py      # MCP integration (filesystem MCP adapter)
    templates/
      index.html       # minimal form UI
  kb/
    ats_tips.md
    cv_best_practices.md
    bullet_examples.md
```

---

## 8. LLM & Configuration

* Default model: **GPT-4o-mini** (or similar small, cost-effective model).

* Key parameters:

  * Temperature: ~0.2–0.5 (more deterministic suggestions).
  * Max tokens: sufficient for CV + JD + knowledge + generated output.

* Configuration:

  * Load API keys from environment variables.
  * Model name configurable in one place (e.g. `config.py`).

* Optional:

  * **LangSmith** tracing, behind a simple config flag (off by default for simplicity).

---

## 9. UX Requirements

* **Landing / main page:**

  * Title: “CV Optimization Assistant”
  * Short explanation: “Upload your CV and paste a job description to get ATS-oriented improvements.”
  * Form:

    * File input: “Upload CV (PDF)”
    * Text area: “Job description”
    * Submit button

* **Result view:**

  * Show:

    * High-level summary at the top
    * Then sections, in Markdown style:

      * Overall Match & ATS Readiness
      * Summary (before / after + explanation)
      * Skills (before / after + explanation)
      * Experience (before / after + explanation)

* **Errors & validation:**

  * If no file is provided → “Please upload a PDF CV.”
  * If invalid file type → “Only PDF CVs are supported in this version.”
  * If job description is empty → “Please paste a job description so the system can tailor your CV.”

---

## 10. Success Criteria

* **Functional:**

  * User can run the app locally and open the UI in a browser.
  * Uploads a real CV (2–3 pages PDF) and a real job description.
  * Gets a coherent report with clear “before/after” examples and ATS-oriented explanations.

* **Technical:**

  * Uses **LangChain 1.x**, **LangGraph 1.x**, and a **ready-made MCP server**.
  * Multi-agent orchestration is implemented via LangGraph.
  * MCP is the only knowledge layer; no RAG/vector DB.

* **Usability:**

  * Setup is simple: install dependencies, start MCP server, run backend.
  * Output is understandable and actionable without reading the code.

---

## 11. Risks & Open Questions

* **PDF parsing quality**

  * Some CV designs may parse poorly.
  * Acceptable for MVP; limitations will be documented.

* **Knowledge coverage**

  * The small local knowledge base might be limited in scope.
  * Can be extended easily by editing/adding Markdown files in `kb/`.

* **Model hallucinations**

  * The LLM may invent skills or responsibilities.
  * Prompts must clearly instruct the model:

    * Not to add experience or skills not present in the original CV.
    * Only to rephrase and emphasize what is already there, aligned with the JD.

* **MCP setup complexity**

  * Requires running an additional MCP process.
  * Mitigation: provide simple README instructions and minimal config.

---