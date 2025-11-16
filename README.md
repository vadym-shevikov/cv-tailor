# CV Optimization Assistant

Multi-agent, local-first AI assistant that takes your **CV (PDF)** and a **job description** (text), then:

- Analyzes how well your CV matches the role  
- Checks basic **ATS readiness**  
- Rewrites key sections (Summary, Skills, Experience bullets)  
- Explains **why** each change helps for this specific job

---

## Features

- 🧠 **Multi-agent architecture** with LangGraph:
  - Parsing & structuring agent
  - Analysis & ATS checker agent
  - Rewriting & explanation agent
- 📄 **Input**: CV as PDF (English only)
- 📋 **Input**: Job description as plain text (English)
- 🔍 **ATS-oriented analysis** based on a small knowledge base:
  - `kb/ats_tips.md`
  - `kb/cv_best_practices.md`
  - `kb/bullet_examples.md`
- 🤖 **LLM-powered rewriting** (e.g. GPT-4o-mini via LangChain)
- 📑 **Output**: Rich Markdown report (before/after + explanations)
- 💾 Uses a **ready-made filesystem MCP server** to expose the local `kb/` folder as a knowledge layer

---

## Tech Stack

- **Python** (3.11+ recommended)
- **LangChain 1.x**
- **LangGraph 1.x**
- **MCP** – filesystem MCP server
- Web backend:
  - Minimal API (e.g. FastAPI / similar) – see `app/main.py`
- Frontend:
  - Simple HTML form template in `app/templates/index.html`

Exact libraries and versions are recorded in `requirements.txt`.

---

## Project Structure

```bash
cv-tailor/
  PRD.md             # Product Requirements Document
  AGENT.md           # Agent / architecture description
  README.md          # This file
  requirements.txt   # Python dependencies

  kb/                # Local knowledge base used via MCP
    ats_tips.md
    cv_best_practices.md
    bullet_examples.md

  app/
    main.py          # Web server + endpoints
    graph.py         # LangGraph definition
    agents.py        # Agent node functions
    models.py        # Simple data models (StructuredCV, ParsedJD, etc.)
    pdf_utils.py     # PDF parsing helper
    mcp_client.py    # MCP integration (filesystem MCP adapter)
    templates/
      index.html     # Minimal upload form UI
````

For more details on the behavior of each agent, see **`AGENT.md`**.
For product-level requirements, see **`PRD.md`**.

---

## Requirements

* Python **3.11+**
* An OpenAI-compatible API key (e.g. `OPENAI_API_KEY`)

  * Default model (suggested): **gpt-4o-mini** (can be changed)
* A running **filesystem MCP server** that exposes the `kb/` directory

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>.git
cd <your-repo-folder>
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Prepare the knowledge base

The folder `kb/` should already contain:

* `ats_tips.md`
* `cv_best_practices.md`
* `bullet_examples.md`

You can edit these files to customize the guidance and examples the agents use.

### 5. Configure environment variables

Create a `.env` file (or export env vars in your shell). See `.env.example` for a starter template:

```bash
OPENAI_API_KEY=your_api_key_here
LLM_MODEL_NAME=gpt-4o-mini   # or another model name if you prefer
MCP_ENABLED=true             # set to false to fall back to direct kb/ reads
MCP_COMMAND="mcp-server-filesystem ./kb"   # override the filesystem MCP command if needed
```

> All KB content lives under the repo-local `kb/` directory. MCP access is restricted to this folder so no global paths (e.g., `/tmp` or `~`) are touched by the knowledge layer.

### 6. Run the MCP server

Run your **filesystem MCP server** pointing at the `kb/` directory.

Conceptually:

```bash
# Example command for the official MCP filesystem server
mcp-server-filesystem ./kb
```

Check your MCP server docs for the exact command and configuration.
The important part: the server should expose read-only access to `kb/` and be reachable by the Python app (see `mcp_client.py`).

---

## MCP filesystem integration

- The backend uses the **official MCP Python SDK** to communicate with a filesystem MCP server over stdio. By default it launches `mcp-server-filesystem` with the `./kb` directory, keeping all knowledge reads confined to this repo.
- The MCP server binary should be installed globally (via npm):

  ```bash
  npm install -g @modelcontextprotocol/server-filesystem
  ```

- Environment variables control how the client connects:
  - `MCP_ENABLED=true|false` — disable to force direct `kb/` reads.
  - `MCP_COMMAND="mcp-server-filesystem ./kb"` — override the launch command.
- All KB files (`ats_tips.md`, `cv_best_practices.md`, `bullet_examples.md`) live under `kb/` in this repository. The MCP client enforces that scope, so no system directories or `/tmp` paths are touched.
- If the MCP server fails to start or initialize, the app automatically disables MCP for the current process and keeps serving requests via on-disk `kb/` reads (equivalent to setting `MCP_ENABLED=false`).
- Set `CV_TAILOR_DEBUG=true` while running the server to see detailed MCP logs. When it works, you'll see log lines like `MCP: fetched ats_tips via MCP` instead of `using disk`.

---

### 7. Run the backend

For example, if using FastAPI + Uvicorn:

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://localhost:8000
```

You should see a simple web page with:

* File input (upload CV PDF)
* Text area (job description)
* Submit button

---

## Usage

1. Open the app in your browser (e.g. `http://localhost:8000`).
2. Upload your **CV (PDF, English)**.
3. Paste the **job description** (English).
4. Click **Submit**.
5. Wait for the analysis to complete.
6. View the **Markdown report**, which includes:

   * Overall job match & ATS readiness
   * Summary (before / after + explanation)
   * Skills (before / after + explanation)
   * Selected Experience bullets (before / after + explanation)

You can copy the suggested text directly into your CV and adapt it further if needed.

---

## How It Works (Short Version)

1. **Document Parsing & Structuring Agent**

   * Extracts text from your PDF CV.
   * Heuristically splits it into Summary, Skills, Experience, etc.
   * Parses the job description into responsibilities and skills.

2. **Analysis & ATS Checker Agent**

   * Uses MCP to read:

     * `kb/ats_tips.md`
     * `kb/cv_best_practices.md`
   * Compares your CV against the job description and best practices.
   * Produces an `AnalysisReport` with match level, ATS readiness, missing keywords, and improvement ideas.

3. **Rewriting & Explanation Agent**

   * Uses `AnalysisReport` and structured documents to:

     * Rewrite Summary, Skills, and selected Experience bullets.
     * Output both **before/after** and **why this is better**.

4. **Final Output Node**

   * Assembles a human-readable **Markdown report**.
   * The backend renders this Markdown in the browser.

For deeper details, see **`AGENT.md`**.

---

## Development Notes

* This project is designed to be **easy to hack on**:

  * Agents are implemented in `app/agents.py`.
  * The LangGraph workflow is defined in `app/graph.py`.
  * MCP integration logic lives in `app/mcp_client.py`.
* You can:

  * Add more knowledge files under `kb/`.
  * Adjust prompts for each agent.
  * Swap out the LLM model using environment variables.

---

## Roadmap / Ideas

Potential future improvements:

* Support additional input formats (DOCX, plain text).
* Multi-language support (e.g. Ukrainian ↔ English).
* Extra agents:

  * Cover letter generator
  * LinkedIn profile summary generator
* Integration with LangSmith for tracing and debugging.
* More advanced ATS scoring with structured rules.

---

## Disclaimer

This tool is an **educational project** and does **not guarantee** that your CV will pass any specific ATS or result in interviews.
Always review and adjust the generated content yourself before using it in real applications.
