# EarXplore

![Paper Teaser Figure](./teaser_figure_interactive.pdf)

EarXplore is an interactive research database for earable interaction studies. It combines a Flask backend with four synchronized exploration views and configurable filtering logic driven by YAML and CSV data.

Live instance: [earxplore.teco.edu](https://earxplore.teco.edu/)  
Paper: [arXiv:2507.20656](https://arxiv.org/abs/2507.20656)

---

## Table of Contents

1. [What This Repository Contains](#what-this-repository-contains)
2. [Quick Start](#quick-start)
3. [Environment Variables (.env)](#environment-variables-env)
4. [Configuration via YAML](#configuration-via-yaml)
5. [Dataset and File Conventions](#dataset-and-file-conventions)
6. [Recomputing Similarity and Connection Matrices](#recomputing-similarity-and-connection-matrices)
7. [Views and Main Features](#views-and-main-features)
8. [Usage Walkthrough](#usage-walkthrough)
9. [Contributing](#contributing)
10. [License](#license)
11. [Contact](#contact)

---

## What This Repository Contains

```text
earXplore/
├── app.py                                # Flask app (all routes and server-side data prep)
├── configs/
│   └── earXplore_interaction.yaml        # Main runtime configuration
├── datasets/
│   ├── data.csv                          # Core study dataset
│   ├── explanations.csv                  # Column descriptions shown in UI tooltips
│   ├── abstract_similarity/
│   │   ├── data_with_embeddings.csv
│   │   └── normalized_abstract_similarity.csv
│   ├── database_similarity/
│   │   └── normalized_database_similarity.csv
│   ├── interconnections/
│   │   ├── citation_matrix.csv
│   │   └── coauthor_matrix.csv
│   └── usage_logs/                       # Optional study logs exported by participants
├── computation_notebooks/                # Data prep and analysis notebooks
├── git_actions_scripts/
│   ├── update_similarity_matrices.py
│   └── update_similarity_matrices_and_author_connections.py
├── static/                               # Frontend JS/CSS/assets
├── templates/                            # Main Flask templates
└── similarity_human_matching/            # Separate rating/annotation mini-app
```

---

## Quick Start

Recommended Python version: **3.11+** (project is currently run with modern Flask/pandas/numpy stack).

### 1) Create and activate a virtual environment

Windows (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Create `.env`

At minimum, set `SECRET_KEY`. If you use forms and chatbot features, configure SMTP and LLM variables too (see full section below).

### 4) Run the app

```bash
python app.py
```

Open: [http://localhost:888](http://localhost:888)

Optional dev mode:

```bash
flask run --debug
```

---

## Environment Variables (.env)

The app reads environment variables via `python-dotenv` on startup.

### Core / Security

```bash
SECRET_KEY="a-long-random-secret"
FLASK_DEBUG=false
BEHIND_PROXY=false
```

- `SECRET_KEY`: Required for stable CSRF/session behavior.
- `BEHIND_PROXY=true`: Enables `ProxyFix` so rate limiting uses client IP behind reverse proxies.

### Mail (Add Study / Report Mistake forms)

```bash
MAIL_SERVER="your-smtp-server.example.com"
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER="default-sender@example.com"
MAIL_USERNAME="your-email@example.com"
MAIL_PASSWORD="your-password"
RECIPIENTS="reviewer@example.com"
```

### Chatbot (EarBot)

```bash
LLM_API_URL="https://your-llm-endpoint"
LLM_API_KEY="your-key"
LLM_MODEL="your-model-name"
```

If these are missing, `/api/chat` responds with a configuration error message instead of crashing.

### Similarity recomputation (embeddings)

```bash
GEMINI_API_KEY="your-gemini-api-key"
```

Used by the update scripts and workflows that generate abstract embeddings/similarity matrices.

---

## Configuration via YAML

Runtime behavior is no longer hardcoded in `app.py`; it is loaded from `configs/earXplore_interaction.yaml`.

Important keys:

| Key | Purpose |
|---|---|
| `database-path` | Path to the main CSV dataset used by the views. |
| `explanations-path` | Path to the CSV with tooltip explanations. |
| `excluded-sidebar-categories` | Columns hidden from normal sidebar filter generation. |
| `metadata-sidebar-categories` | Columns grouped into the metadata panel. |
| `slider-categories` | Numeric columns rendered as range sliders. |
| `select-deselect-all-categories` | Columns with per-category select/deselect-all controls. |
| `exclusive-filtering-categories` | Columns that support exclusive matching mode. |
| `select-deselect-all-panels` | Panels with panel-level bulk selection controls. |
| `initially-hidden-panels` | Panels collapsed by default. |
| `parenthical-columns` | Columns using `Value (details)` where filtering should use only `Value`. |
| `start-category-filters` | Default visible columns/categories in table/chart views. |
| `performance-metrics-columns` | Performance metric columns merged into one dedicated filter block. |
| `device-model-column` | Column used by the custom Device Model keyword filter block. |
| `device-model-options` | Fixed Device Model options shown in UI (e.g., OpenEarable, AirPods, Other, N/A). |
| `other-threshold-columns` | Columns where rare values are grouped into `Other`. |
| `token-search-columns` | Columns rendered with token-search UI (opt-in filtering). |

Notes:

- Performance metric columns are automatically treated as parenthetical and excluded from regular checkbox rendering.
- Token-search columns use selected tokens as filters; empty selection means no constraint for that column.
- The app computes rare-value sets and token options at startup from the current dataset.

---

## Dataset and File Conventions

### Required base data

- `datasets/data.csv`
- `datasets/explanations.csv` with at least `Column` and `Explanation` headers

### Naming convention for grouping in sidebar panels

Columns containing `_PANEL_` are grouped by the prefix before `_PANEL_` (for example `Interaction_PANEL_...` goes to panel `Interaction`).

### Similarity and timeline artifacts used by views

- `datasets/abstract_similarity/normalized_abstract_similarity.csv`
- `datasets/database_similarity/normalized_database_similarity.csv`
- `datasets/interconnections/citation_matrix.csv`
- `datasets/interconnections/coauthor_matrix.csv`

If citation/coauthor matrices are missing, timeline view falls back to zero matrices so the page can still render.

---

## Recomputing Similarity and Connection Matrices

You can update derived matrices either manually or via GitHub Actions.

### Manual (local)

Run from repository root:

```bash
python git_actions_scripts/update_similarity_matrices_and_author_connections.py
```

This script updates:

- database similarity (`datasets/database_similarity/normalized_database_similarity.csv`)
- abstract embeddings + similarity (`datasets/abstract_similarity/data_with_embeddings.csv`, `datasets/abstract_similarity/abstract_similarity.csv`, `datasets/abstract_similarity/normalized_abstract_similarity.csv`)
- coauthor matrix (`datasets/interconnections/coauthor_matrix.csv`)

### Automated (GitHub Actions)

Workflow: `.github/workflows/update-matrices.yml`

- Triggers when a PR into `main` is closed and merged.
- Runs `git_actions_scripts/update_similarity_matrices_and_author_connections.py`.
- Requires repository secret `GEMINI_API_KEY`.
- Commits generated changes back to the repository.

---

## Views and Main Features

EarXplore offers four synchronized views sharing one filter state (persisted in session storage):

1. **Tabular Overview (`/`)**
2. **Distribution Charts (`/bar-chart`)**
3. **Study Similarity (`/similarity`)**
4. **Study Timeline (`/timeline`)**

Additional features:

- **Add Study / Report Mistake (`/add_study`)** with CSRF protection, honeypot spam check, and mail dispatch.
- **EarBot chatbot (`/api/chat`)** with rate limiting (`20/day/IP`), max input length checks, and sanitized markdown rendering on frontend.
- **Usage study logger (frontend-only)** that records interactions in `sessionStorage` and exports JSON logs (no server-side tracking required).

---

## Usage Walkthrough

The following media show the main interaction flow on the hosted instance.

### View Selection Menu

Navigate between tabular, chart, similarity, timeline, and contribution entry points.

![navbar_demonstration gif](https://github.com/user-attachments/assets/35882867-cc68-4fb3-a751-a620af3d7141)

### Filter Sidebar

Use panel/category controls, sliders, token filters, and bulk select actions.

![sidebar_demonstration gif](https://github.com/user-attachments/assets/ebfe356d-436f-4bb1-b6f5-89214b0ef8a2)

### Display Customization

Toggle visible columns/charts and color mappings while preserving active filters across views.

![filter_demonstration gif](https://github.com/user-attachments/assets/b41978e1-dd71-4031-ab6a-c6ee65fe1129)

### Modal Overlays

Open full study details and relation-specific overlays from charts/nodes.

![modal_demonstration gif](https://github.com/user-attachments/assets/d4f809e5-bd01-49d7-857a-8685bd7ce8bd)

### Screenshots of the Four Views

#### Tabular View

<img width="2513" height="969" alt="Tabular View" src="https://github.com/user-attachments/assets/afe5826d-585a-4bb2-b476-8557143a3df4" />

#### Graphical View

<img width="2507" height="968" alt="Graphical View" src="https://github.com/user-attachments/assets/a2d7f7aa-c1a5-4c09-92e5-5aebf63a8aab" />

#### Similarity View

<img width="2493" height="935" alt="Similarity View" src="https://github.com/user-attachments/assets/cb998750-08e0-404e-bbe1-2a3738c1f4d7" />

#### Timeline View

<img width="2506" height="915" alt="Timeline View" src="https://github.com/user-attachments/assets/38d581a1-4386-4466-b338-990198b6af20" />

---

## Contributing

Contributions are welcome in two ways:

1. Use the in-app form (`/add_study`) to suggest new papers or report mistakes.
2. Open pull requests with dataset/config/script improvements.

For dataset updates, keep generated similarity/connection artifacts in sync (locally or via the workflow).

---

## License

This project is licensed under the [MIT License](./LICENSE).

---

## Contact

- GitHub: [98JoHu](https://github.com/98JoHu)
- E-mail: jonas.hummel@kit.edu
