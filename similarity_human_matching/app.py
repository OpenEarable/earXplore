"""
Similarity Human Rating Tool
======================================
Authors rate 20 pairs on a Visual Analog Scale (0 = Opposite, 100 = Equal).
Two tasks are supported:
  - abstract  : rate abstract text similarity (seed 42)
  - document  : rate document/database criteria similarity (seed 43)

Pair assignments are drawn globally without replacement, so no pair is ever
shown to more than one author within the same task.

Run with:  python app.py
Then open:  http://localhost:5001
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', 'datasets')
ASSIGNMENTS_FILE      = os.path.join(BASE_DIR, 'pair_assignments.json')
ABSTRACT_RATINGS_FILE = os.path.join(BASE_DIR, 'ratings.json')
DOCUMENT_RATINGS_FILE = os.path.join(BASE_DIR, 'ratings_document.json')
DRAFTS_DIR            = os.path.join(BASE_DIR, 'drafts')

# ── constants ──────────────────────────────────────────────────────────────────
AUTHORS          = ['author_1', 'author_2', 'author_3', 'author_4', 'author_5']
PAIRS_PER_AUTHOR = 20
TEASER_LEN       = 200   # chars shown in the review summary per abstract
ABSTRACT_SEED    = 42
DOCUMENT_SEED    = 43
TASKS            = ('abstract', 'document')
TASK_LABELS      = {'abstract': 'Abstract Similarity', 'document': 'Document Similarity'}

# Columns excluded from the document view
DOC_EXCLUDED_COLS = {'ID', 'Title', 'Abstract', 'Main Author', 'Authors', 'Year', 'Study Link'}

# Ordered panel groups for the document view (mirrors earXplore modal)
DOC_GROUP_ORDER = [
    'General Information', 'Interaction', 'Sensing',
    'Study', 'Device', 'Motivations', 'Applications', 'Keywords',
]

# ── app setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'earXplore-human-rating-2026')


# ── pair assignment ────────────────────────────────────────────────────────────

def _draw_pairs(sim_csv_path: str, seed: int) -> dict:
    """Draw PAIRS_PER_AUTHOR * n_authors globally-unique (i<j) pairs."""
    sim_df    = pd.read_csv(sim_csv_path, index_col=0)
    paper_ids = [int(x) for x in sim_df.index]

    all_pairs = [
        [paper_ids[i], paper_ids[j]]
        for i in range(len(paper_ids))
        for j in range(i + 1, len(paper_ids))
    ]

    total_needed = PAIRS_PER_AUTHOR * len(AUTHORS)
    rng          = np.random.default_rng(seed)
    chosen       = rng.choice(len(all_pairs), size=total_needed, replace=False)
    selected     = [all_pairs[int(idx)] for idx in chosen]

    return {
        author: selected[k * PAIRS_PER_AUTHOR:(k + 1) * PAIRS_PER_AUTHOR]
        for k, author in enumerate(AUTHORS)
    }


def load_assignments() -> dict:
    """Return {'abstract': {...}, 'document': {...}}, migrating old format if needed."""
    abs_sim_path = os.path.join(DATA_DIR, 'abstract_similarity', 'abstract_similarity.csv')
    doc_sim_path = os.path.join(DATA_DIR, 'database_similarity', 'normalized_database_similarity.csv')

    if not os.path.exists(ASSIGNMENTS_FILE):
        assignments = {
            'abstract': _draw_pairs(abs_sim_path, ABSTRACT_SEED),
            'document': _draw_pairs(doc_sim_path, DOCUMENT_SEED),
        }
        with open(ASSIGNMENTS_FILE, 'w') as fh:
            json.dump(assignments, fh, indent=2)
        return assignments

    with open(ASSIGNMENTS_FILE) as fh:
        data = json.load(fh)

    # Detect old format: top-level keys are author names, not task names
    if any(k in data for k in AUTHORS):
        data = {
            'abstract': data,
            'document': _draw_pairs(doc_sim_path, DOCUMENT_SEED),
        }
        with open(ASSIGNMENTS_FILE, 'w') as fh:
            json.dump(data, fh, indent=2)
        return data

    # Add document block if missing (e.g. file only had abstract)
    if 'document' not in data:
        data['document'] = _draw_pairs(doc_sim_path, DOCUMENT_SEED)
        with open(ASSIGNMENTS_FILE, 'w') as fh:
            json.dump(data, fh, indent=2)

    return data


# ── paper data ─────────────────────────────────────────────────────────────────

def load_abstracts() -> dict:
    """Return {str(id): abstract_text} for all papers."""
    df     = pd.read_csv(os.path.join(DATA_DIR, 'data.csv'))
    result = {}
    for _, row in df.iterrows():
        abstract = row.get('Abstract', '')
        result[str(int(row['ID']))] = str(abstract) if pd.notna(abstract) else ''
    return result


def _panel_name(col: str) -> str:
    """Map column name to its display panel group."""
    if '_PANEL_' in col:
        return col.split('_PANEL_')[0]
    return 'General Information'


def _field_label(col: str) -> str:
    """Derive display label — last underscore segment, matching earXplore modal."""
    return col.split('_')[-1]


def load_document_panels() -> dict:
    """
    Return {str(id): [{'panel': name, 'fields': [{'label': l, 'value': v}]}]}
    Groups are ordered like the earXplore modal. Excluded columns are skipped.
    """
    df     = pd.read_csv(os.path.join(DATA_DIR, 'data.csv'))
    result = {}

    for _, row in df.iterrows():
        pid    = str(int(row['ID']))
        groups = {g: [] for g in DOC_GROUP_ORDER}

        for col in df.columns:
            if col in DOC_EXCLUDED_COLS:
                continue
            val = str(row[col]) if pd.notna(row[col]) else 'N/A'
            if col == 'Keywords':
                groups['Keywords'].append({'label': 'Keywords', 'value': val})
            else:
                grp = _panel_name(col)
                if grp not in groups:
                    groups[grp] = []
                groups[grp].append({'label': _field_label(col), 'value': val})

        result[pid] = [
            {'panel': g, 'fields': groups[g]}
            for g in DOC_GROUP_ORDER if groups[g]
        ]

    return result


# ── ratings / draft storage ────────────────────────────────────────────────────

def _ratings_file(task: str) -> str:
    return ABSTRACT_RATINGS_FILE if task == 'abstract' else DOCUMENT_RATINGS_FILE


def _draft_path(task: str, author: str) -> str:
    suffix = '' if task == 'abstract' else '_document'
    return os.path.join(DRAFTS_DIR, f'{author}{suffix}_draft.json')


def load_ratings(task: str) -> dict:
    path = _ratings_file(task)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def save_ratings(task: str, ratings: dict) -> None:
    with open(_ratings_file(task), 'w') as fh:
        json.dump(ratings, fh, indent=2)


def load_draft(task: str, author: str) -> dict:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = _draft_path(task, author)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def save_draft(task: str, author: str, draft: dict) -> None:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    with open(_draft_path(task, author), 'w') as fh:
        json.dump(draft, fh, indent=2)


def delete_draft(task: str, author: str) -> None:
    path = _draft_path(task, author)
    if os.path.exists(path):
        os.remove(path)


def clamp_rating(raw) -> int:
    try:
        return max(0, min(100, int(float(raw))))
    except (ValueError, TypeError):
        return 50


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    submitted = {task: list(load_ratings(task).keys()) for task in TASKS}
    return render_template(
        'index.html',
        authors=AUTHORS, submitted=submitted,
        tasks=TASKS, task_labels=TASK_LABELS,
    )


@app.route('/start', methods=['POST'])
def start():
    author = request.form.get('author', '').strip()
    task   = request.form.get('task', 'abstract').strip()
    if author not in AUTHORS or task not in TASKS:
        return redirect(url_for('index'))

    if author in load_ratings(task):
        return redirect(url_for('done', task=task, author=author))

    draft = load_draft(task, author)
    for i in range(PAIRS_PER_AUTHOR):
        if str(i) not in draft:
            return redirect(url_for('rate', task=task, author=author, pair_index=i))

    return redirect(url_for('review', task=task, author=author))


@app.route('/rate/<task>/<author>/<int:pair_index>', methods=['GET'])
def rate(task, author, pair_index):
    if author not in AUTHORS or task not in TASKS:
        return redirect(url_for('index'))
    if author in load_ratings(task):
        return redirect(url_for('done', task=task, author=author))

    all_assignments = load_assignments()
    pairs = all_assignments[task][author]
    if pair_index >= len(pairs):
        return redirect(url_for('review', task=task, author=author))

    draft          = load_draft(task, author)
    pair           = pairs[pair_index]
    current_rating = clamp_rating(draft.get(str(pair_index), 50))

    if task == 'abstract':
        abstracts = load_abstracts()
        return render_template(
            'rate.html',
            task=task, task_label=TASK_LABELS[task],
            author=author, pair_index=pair_index, total=len(pairs),
            abstract_a=abstracts.get(str(pair[0]), '(Abstract not available)'),
            abstract_b=abstracts.get(str(pair[1]), '(Abstract not available)'),
            current_rating=current_rating,
        )
    else:
        doc_panels = load_document_panels()
        return render_template(
            'rate.html',
            task=task, task_label=TASK_LABELS[task],
            author=author, pair_index=pair_index, total=len(pairs),
            panels_a=doc_panels.get(str(pair[0]), []),
            panels_b=doc_panels.get(str(pair[1]), []),
            current_rating=current_rating,
        )


@app.route('/rate/<task>/<author>/<int:pair_index>', methods=['POST'])
def rate_post(task, author, pair_index):
    if author not in AUTHORS or task not in TASKS:
        return redirect(url_for('index'))

    rating = clamp_rating(request.form.get('rating', '50'))
    draft  = load_draft(task, author)
    draft[str(pair_index)] = rating
    save_draft(task, author, draft)

    all_assignments = load_assignments()
    next_i = pair_index + 1
    if next_i < len(all_assignments[task][author]):
        return redirect(url_for('rate', task=task, author=author, pair_index=next_i))
    return redirect(url_for('review', task=task, author=author))


@app.route('/review/<task>/<author>', methods=['GET'])
def review(task, author):
    if author not in AUTHORS or task not in TASKS:
        return redirect(url_for('index'))
    if author in load_ratings(task):
        return redirect(url_for('done', task=task, author=author))

    all_assignments = load_assignments()
    pairs  = all_assignments[task][author]
    draft  = load_draft(task, author)

    pair_data = []
    if task == 'abstract':
        papers = load_abstracts()
        for i, pair in enumerate(pairs):
            a = papers.get(str(pair[0]), '')
            b = papers.get(str(pair[1]), '')
            pair_data.append({
                'index': i,
                'teaser_a': (a[:TEASER_LEN] + '\u2026') if len(a) > TEASER_LEN else a,
                'teaser_b': (b[:TEASER_LEN] + '\u2026') if len(b) > TEASER_LEN else b,
                'rating': clamp_rating(draft.get(str(i), 50)),
            })
    else:
        doc_panels = load_document_panels()
        for i, pair in enumerate(pairs):
            pair_data.append({
                'index': i,
                'panels_a': doc_panels.get(str(pair[0]), []),
                'panels_b': doc_panels.get(str(pair[1]), []),
                'rating': clamp_rating(draft.get(str(i), 50)),
            })

    return render_template(
        'review.html',
        task=task, task_label=TASK_LABELS[task],
        author=author, pairs=pair_data, total=len(pairs),
    )


@app.route('/submit/<task>/<author>', methods=['POST'])
def submit(task, author):
    if author not in AUTHORS or task not in TASKS:
        return redirect(url_for('index'))

    all_assignments = load_assignments()
    pairs = all_assignments[task][author]

    final_ratings = []
    for i, pair in enumerate(pairs):
        final_ratings.append({
            'pair_index': i,
            'paper_a': pair[0],
            'paper_b': pair[1],
            'rating': clamp_rating(request.form.get(f'rating_{i}', '50')),
        })

    all_ratings = load_ratings(task)
    all_ratings[author] = {
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'ratings': final_ratings,
    }
    save_ratings(task, all_ratings)
    delete_draft(task, author)

    return redirect(url_for('done', task=task, author=author))


@app.route('/done/<task>/<author>')
def done(task, author):
    other_task       = 'document' if task == 'abstract' else 'abstract'
    other_submitted  = author in load_ratings(other_task)
    return render_template(
        'done.html',
        task=task, task_label=TASK_LABELS[task],
        author=author,
        other_task=other_task, other_task_label=TASK_LABELS[other_task],
        other_submitted=other_submitted,
    )


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5001)
