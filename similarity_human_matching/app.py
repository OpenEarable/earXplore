"""
Abstract Similarity Human Rating Tool
======================================
Authors rate 20 abstract pairs each on a Visual Analog Scale (0 = Opposite, 100 = Equal).
Pair assignments are drawn globally without replacement using random_state = 42,
so no pair is ever shown to more than one author.

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
ASSIGNMENTS_FILE = os.path.join(BASE_DIR, 'pair_assignments.json')
RATINGS_FILE = os.path.join(BASE_DIR, 'ratings.json')
DRAFTS_DIR = os.path.join(BASE_DIR, 'drafts')

# ── constants ──────────────────────────────────────────────────────────────────
AUTHORS = ['author_1', 'author_2', 'author_3', 'author_4', 'author_5']
PAIRS_PER_AUTHOR = 20
TEASER_LEN = 200          # chars shown in the review summary per abstract
RANDOM_SEED = 42

# ── app setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'earXplore-human-rating-2026-abstract')


# ── pair assignment ────────────────────────────────────────────────────────────

def generate_pair_assignments() -> dict:
    """
    Build all unique (i < j) pairs from the abstract similarity matrix,
    draw PAIRS_PER_AUTHOR * len(AUTHORS) of them globally without replacement
    using RANDOM_SEED, and assign consecutive blocks to each author.
    Written to ASSIGNMENTS_FILE once; never regenerated.
    """
    sim_path = os.path.join(DATA_DIR, 'abstract_similarity', 'abstract_similarity.csv')
    sim_df = pd.read_csv(sim_path, index_col=0)
    paper_ids = [int(x) for x in sim_df.index]

    all_pairs: list[list[int]] = [
        [paper_ids[i], paper_ids[j]]
        for i in range(len(paper_ids))
        for j in range(i + 1, len(paper_ids))
    ]

    total_needed = PAIRS_PER_AUTHOR * len(AUTHORS)
    rng = np.random.default_rng(RANDOM_SEED)
    chosen_indices = rng.choice(len(all_pairs), size=total_needed, replace=False)
    selected = [all_pairs[int(idx)] for idx in chosen_indices]

    assignments = {
        author: selected[k * PAIRS_PER_AUTHOR:(k + 1) * PAIRS_PER_AUTHOR]
        for k, author in enumerate(AUTHORS)
    }

    with open(ASSIGNMENTS_FILE, 'w') as fh:
        json.dump(assignments, fh, indent=2)

    return assignments


def load_assignments() -> dict:
    if not os.path.exists(ASSIGNMENTS_FILE):
        return generate_pair_assignments()
    with open(ASSIGNMENTS_FILE) as fh:
        return json.load(fh)


# ── paper data ─────────────────────────────────────────────────────────────────

def load_papers() -> dict[str, str]:
    """Return {str(id): abstract_text} for all papers."""
    df = pd.read_csv(os.path.join(DATA_DIR, 'data.csv'))
    result = {}
    for _, row in df.iterrows():
        abstract = row.get('Abstract', '')
        result[str(int(row['ID']))] = str(abstract) if pd.notna(abstract) else ''
    return result


# ── ratings / draft storage ────────────────────────────────────────────────────

def load_ratings() -> dict:
    if not os.path.exists(RATINGS_FILE):
        return {}
    with open(RATINGS_FILE) as fh:
        return json.load(fh)


def save_ratings(ratings: dict) -> None:
    with open(RATINGS_FILE, 'w') as fh:
        json.dump(ratings, fh, indent=2)


def load_draft(author: str) -> dict:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = os.path.join(DRAFTS_DIR, f'{author}_draft.json')
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def save_draft(author: str, draft: dict) -> None:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = os.path.join(DRAFTS_DIR, f'{author}_draft.json')
    with open(path, 'w') as fh:
        json.dump(draft, fh, indent=2)


def delete_draft(author: str) -> None:
    path = os.path.join(DRAFTS_DIR, f'{author}_draft.json')
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
    submitted = set(load_ratings().keys())
    return render_template('index.html', authors=AUTHORS, submitted=submitted)


@app.route('/start', methods=['POST'])
def start():
    author = request.form.get('author', '').strip()
    if author not in AUTHORS:
        return redirect(url_for('index'))

    if author in load_ratings():
        return redirect(url_for('done', author=author))

    draft = load_draft(author)
    for i in range(PAIRS_PER_AUTHOR):
        if str(i) not in draft:
            return redirect(url_for('rate', author=author, pair_index=i))

    # All pairs already in draft — go straight to review
    return redirect(url_for('review', author=author))


@app.route('/rate/<author>/<int:pair_index>', methods=['GET'])
def rate(author, pair_index):
    if author not in AUTHORS:
        return redirect(url_for('index'))
    if author in load_ratings():
        return redirect(url_for('done', author=author))

    assignments = load_assignments()
    pairs = assignments[author]
    if pair_index >= len(pairs):
        return redirect(url_for('review', author=author))

    papers = load_papers()
    draft = load_draft(author)
    pair = pairs[pair_index]

    return render_template(
        'rate.html',
        author=author,
        pair_index=pair_index,
        total=len(pairs),
        abstract_a=papers.get(str(pair[0]), '(Abstract not available)'),
        abstract_b=papers.get(str(pair[1]), '(Abstract not available)'),
        current_rating=clamp_rating(draft.get(str(pair_index), 50)),
    )


@app.route('/rate/<author>/<int:pair_index>', methods=['POST'])
def rate_post(author, pair_index):
    if author not in AUTHORS:
        return redirect(url_for('index'))

    rating = clamp_rating(request.form.get('rating', '50'))
    draft = load_draft(author)
    draft[str(pair_index)] = rating
    save_draft(author, draft)

    assignments = load_assignments()
    next_i = pair_index + 1
    if next_i < len(assignments[author]):
        return redirect(url_for('rate', author=author, pair_index=next_i))
    return redirect(url_for('review', author=author))


@app.route('/review/<author>', methods=['GET'])
def review(author):
    if author not in AUTHORS:
        return redirect(url_for('index'))
    if author in load_ratings():
        return redirect(url_for('done', author=author))

    assignments = load_assignments()
    pairs = assignments[author]
    papers = load_papers()
    draft = load_draft(author)

    pair_data = []
    for i, pair in enumerate(pairs):
        a = papers.get(str(pair[0]), '')
        b = papers.get(str(pair[1]), '')
        pair_data.append({
            'index': i,
            'teaser_a': (a[:TEASER_LEN] + '\u2026') if len(a) > TEASER_LEN else a,
            'teaser_b': (b[:TEASER_LEN] + '\u2026') if len(b) > TEASER_LEN else b,
            'rating': clamp_rating(draft.get(str(i), 50)),
        })

    return render_template('review.html', author=author, pairs=pair_data, total=len(pairs))


@app.route('/submit/<author>', methods=['POST'])
def submit(author):
    if author not in AUTHORS:
        return redirect(url_for('index'))

    assignments = load_assignments()
    pairs = assignments[author]

    final_ratings = []
    for i, pair in enumerate(pairs):
        final_ratings.append({
            'pair_index': i,
            'paper_a': pair[0],
            'paper_b': pair[1],
            'rating': clamp_rating(request.form.get(f'rating_{i}', '50')),
        })

    all_ratings = load_ratings()
    all_ratings[author] = {
        'submitted_at': datetime.now(timezone.utc).isoformat(),
        'ratings': final_ratings,
    }
    save_ratings(all_ratings)
    delete_draft(author)

    return redirect(url_for('done', author=author))


@app.route('/done/<author>')
def done(author):
    return render_template('done.html', author=author)


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True, port=5001)
