"""Step 1.4 of the candidate pipeline: screen candidates with an LLM.

Every candidate from search_candidates.py gets a decision (include / unsure /
exclude) with a one-sentence reason, judged from title and abstract against
the definitions and exclusion criteria of the EarXplore paper (Section 3.1).
Each prompt also shows the most similar papers that are in EarXplore and the
most similar ones that were not included, as examples.

Nothing is deleted here: "exclude" only moves a paper to the collapsed part
of the weekly issue (step 1.5).

Usage:
  # weekly: candidates.csv from search_candidates.py
  python git_actions_scripts/screen_candidates.py candidates.csv --out screened.csv

  # once: build the pool of not-included example papers from an ACM backfill
  python git_actions_scripts/search_candidates.py --since 2022-01-21 --until 2026-04-10 --sources ACM-DL --raw backfill_raw.csv --out backfill_kept.csv
  python git_actions_scripts/screen_candidates.py --make-negatives backfill_raw.csv

  # measure recall / workload on the same backfill (--limit N: fewer negatives)
  python git_actions_scripts/screen_candidates.py --evaluate backfill_raw.csv --out eval.csv

  # look at the prompt for the first candidate without calling the LLM
  python git_actions_scripts/screen_candidates.py candidates.csv --show-prompt

  # LLM_MODEL is a KI-Toolbox model with its own system prompt: add --no-system-prompt
  # to any of the commands above (the examples are still sent in the user message)

  python git_actions_scripts/screen_candidates.py --selfcheck

LLM via an OpenAI-compatible chat completions endpoint (.env or environment):
  LLM_API_URL   full URL; KIT KI-Toolbox: https://ki-toolbox.scc.kit.edu/api/v1/chat/completions
                (Gemini: https://generativelanguage.googleapis.com/v1beta/openai/chat/completions)
  LLM_API_KEY   KI-Toolbox: Settings > Account > API key (KIT network or VPN required)
  LLM_MODEL     KI-Toolbox alias, e.g. alias.medium-local (local models are not budgeted);
                never standard-local / standard-external, they inject their own system prompt
"""
import argparse
import json
import os
import re
import sys
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

sys.path.insert(0, os.path.dirname(__file__))
import search_candidates as search  # noqa: E402  (shared filter, corpus and title helpers)

load_dotenv()

DATA_PATH = 'datasets/data.csv'
NEGATIVES_PATH = 'datasets/candidates/negatives.csv'
N_EXAMPLES = 3          # similar papers per side (included / not included)
EXAMPLE_CHARS = 600     # example abstracts are shortened to keep prompts small
DECISIONS = ('include', 'unsure', 'exclude')
ANSWER_COLUMNS = ['decision', 'reason', 'criterion', 'location_guess']

# Same text as the KI-Toolbox model's system prompt; {locations} is filled from
# LOCATIONS below, {{ }} are literal braces for str.format.
SYSTEM_PROMPT = """\
You screen scientific publications for EarXplore, a curated database of research on interaction with earables. As in the title and abstract screening of a systematic literature review, you decide from the title, abstract, keywords and venue alone whether a paper should be included in EarXplore.

## Definitions (from the EarXplore paper)
- Earables are devices that attach in, on, or in the immediate vicinity of the ear to offer functionalities beyond basic audio in- and output.
- Interaction with Earables is the engagement between a user and devices that attach in, on, or in the immediate vicinity of the ear through intentional control inputs and/or non-auditory feedback modalities.

## How the definition is interpreted in the existing corpus
The corpus interprets the definition broadly. A paper is included if the earable does at least one of the following:

1. It captures movements, signals or states that a person produces and that can serve as input, even if the paper presents this as tracking, recognition or monitoring and does not build an explicit control interface. Input sources in the corpus:
   - Head: nodding, turning, tilting, head posture
   - Eyes: gaze direction, blinking, eye movements (including during sleep)
   - Face: facial expressions, touching the face
   - Mouth: tongue, teeth, jaw, silent speech
   - Hand: gestures at the ear, at the face or in mid-air, touching the device
   - Brain activity (e.g., EEG), tensor tympani
   - Wearable state of the device: inserting, removing, fit, configuration
2. It provides non-auditory feedback at the ear: vibration, heat, pressure, shape change, poking, electrical stimulation, light, a display or similar.
3. It enables authentication or identification through an intentional action (tapping, gestures, teeth, thoughts).
4. It provides hardware, platforms or technical foundations (e.g., sensor calibration) that enable such input.

In addition:
- Elicitation studies are included, even without any sensing (e.g., simulated input to a conceptual device).
- It is sufficient if the earable is one of several devices or body locations studied.
- Systems that combine an earable with other devices (e.g., smartphone, smart glasses) count as long as input is captured or feedback is given at the ear.
- The application context (health, safety, driving, accessibility, VR, entertainment) does not matter. What matters is which signal is captured or which feedback is given.

Interaction locations in the corpus:
{locations}

## Exclusion criteria
Exclude a paper only if at least one of the following criteria clearly applies:
1. Not peer-reviewed: workshop proposals and workshop summaries, theses, patents, technical reports, industry white papers, preprints. Posters, demos, extended abstracts, work-in-progress papers and short papers count as peer-reviewed. Never exclude a paper only because its venue or type is missing.
2. Larger head-worn or off-body systems (e.g., VR headsets) in which neither input is captured nor feedback is given at the ear itself.
3. Purely technical development of audio earphones (e.g., transducers, active noise cancellation, sound quality).
4. Not written in English.
5. No interaction: the earable only captures signals that are not an action of the person, such as vital signs (heart rate, oxygen saturation, body temperature, blood pressure), breathing or coughing (unless used as deliberate input), hearing tests or general body activity such as walking and step counting, and it gives no non-auditory feedback. Head, eye, face, mouth, hand and brain signals do not fall under this criterion, not even in a health context.
6. No earable: the system is not located in, on, or in the immediate vicinity of the ear.
7. Purely conceptual work (e.g., position papers, visions) without a prototype and without a user study. Elicitation studies are exempt from this criterion.

## Examples
With each paper you receive similar papers that were included in EarXplore and similar papers that were not included. For the papers that were not included, the reason is unknown. The examples are for orientation only. The definitions and criteria above are decisive.

## Decision
- "include": the paper is clearly within the scope of EarXplore.
- "unsure": the paper is possibly within scope, or the abstract is missing or too vague to decide. When in doubt, choose "unsure": a missed paper is worse than an extra one to check.
- "exclude": an exclusion criterion clearly applies. Name its number.

## Answer format
Answer with JSON only, without any other text:
{{"decision": "include|unsure|exclude", "reason": "one sentence", "criterion": "number of the exclusion criterion, or empty", "location_guess": "one of the locations above, or empty"}}"""

# What each Location of the EarXplore taxonomy covers, derived from the input
# body parts and gestures coded in data.csv. A new Location in data.csv needs a
# line here (location_overview fails otherwise).
LOCATIONS = {
    'Ear and Earable': 'input on the ear or the device itself, e.g. touching, tapping, pressing, covering or '
                       'deforming the ear or earable, inserting or removing the earbud (wearable state), '
                       'contracting the tensor tympani muscle',
    'Hand Gestures and Location': 'hand gestures near the ear, on the face or in mid-air, and touching the face',
    'Head Gestures and Pointing': 'head movements and orientation, e.g. nodding, shaking, tilting, turning, '
                                  'head posture, pointing with the head',
    'Face': 'facial expressions and facial muscle activity, e.g. smiling, eyebrow or nose movements, '
            'emotion recognition',
    'Mouth': 'tongue, teeth and jaw movements, e.g. teeth clicks, jaw clenching, tongue gestures, silent speech',
    'Eye-Tracking': 'gaze direction, blinks and eye movements, e.g. via EOG electrodes at the ear',
    'Brain': 'brain activity measured at the ear, e.g. EEG, mental commands, thought-based authentication',
    'Actuation': 'output to the user at the ear, e.g. vibration, heat, pressure, shape change, poking, '
                 'electrotactile stimulation, light or a display',
}


# --- example papers ----------------------------------------------------------

def load_corpus_papers(path=DATA_PATH):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return df.rename(columns={'Title': 'title', 'Abstract': 'abstract', 'Location': 'location'})


def location_overview(corpus):
    """One line per Location with what it covers, for the {locations} slot of the prompt."""
    used = set(corpus.location.str.split(', ').explode()) - {'', 'N/A'}
    undescribed = used - set(LOCATIONS)
    if undescribed:
        # a new taxonomy category the model would otherwise never hear about
        raise ValueError(f'add a description to LOCATIONS for: {sorted(undescribed)}')
    return '\n'.join(f'- {name}: {text}' for name, text in LOCATIONS.items())


def load_negatives(path=NEGATIVES_PATH):
    # ponytail: pseudo-negatives from the ACM backfill; add 'rejected' papers
    # from seen.csv (step 1.5) once it holds enough decisions with abstracts
    if not os.path.exists(path):
        print(f'warning: {path} missing, prompts get no not-included examples '
              f'(build it with --make-negatives)', file=sys.stderr)
        return pd.DataFrame(columns=['doi', 'title', 'abstract'])
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def make_example_finder(corpus, negatives):
    """Return find(row) -> (similar included papers, similar not-included papers)."""
    pools = {'included': corpus, 'not included': negatives}
    texts = pd.concat([p.title + ' ' + p.abstract for p in pools.values()])
    vectorizer = TfidfVectorizer(stop_words='english', sublinear_tf=True).fit(texts)
    matrices = {name: vectorizer.transform(p.title + ' ' + p.abstract) for name, p in pools.items() if len(p)}

    def find(row):
        query = vectorizer.transform([row.title + ' ' + row.abstract])
        own_title = search.norm_title(row.title)
        found = []
        for name, pool in pools.items():
            if pool.empty:
                found.append(pool)
                continue
            scores = linear_kernel(query, matrices[name])[0]
            ranked = pool.iloc[scores.argsort()[::-1]]
            # never show the paper itself as its own example (matters in --evaluate)
            same = ranked.title.map(search.norm_title) == own_title
            if 'doi' in ranked:
                same |= (ranked.doi == row.get('doi', '')) & (ranked.doi != '')
            found.append(ranked[~same].head(N_EXAMPLES))
        return found

    return find


# --- prompt and answer ------------------------------------------------------

def shorten(text, limit=EXAMPLE_CHARS):
    return text if len(text) <= limit else text[:limit].rsplit(' ', 1)[0] + ' ...'


def build_prompt(row, system, find_examples):
    included, not_included = find_examples(row)
    parts = []
    for label, examples in (('Similar papers that ARE in EarXplore', included),
                            ('Similar papers that were NOT included', not_included)):
        if len(examples):
            parts.append(label + ':')
            parts += [f'- {e.title}\n  {shorten(e.abstract)}' for e in examples.itertuples()]
            parts.append('')
    parts += ['PAPER TO SCREEN',
              f'Title: {row.title}',
              f'Venue: {row.get("venue", "")} ({row.get("type", "")})',
              f'Keywords: {row.get("keywords", "") or "-"}',
              f'Abstract: {row.abstract or "(no abstract available)"}']
    return system, '\n'.join(parts)


def ask_llm(system, user, max_tokens=1000, model=None):
    """One chat completion against an OpenAI-compatible endpoint.

    system=None sends no system message, for a KI-Toolbox model that brings its own.
    model overrides LLM_MODEL (categorise_studies.py uses one model per panel).
    """
    messages = ([{'role': 'system', 'content': system}] if system else []) + [{'role': 'user', 'content': user}]
    for _ in range(4):
        r = requests.post(
            os.environ['LLM_API_URL'],
            headers={'Authorization': f'Bearer {os.environ["LLM_API_KEY"]}'},
            json={'model': model or os.environ['LLM_MODEL'], 'temperature': 0,
                  # generous: "thinking" models spend tokens before answering
                  'max_tokens': max_tokens,
                  'messages': messages},
            timeout=120)
        if r.status_code != 429:
            break
        time.sleep(int(r.headers.get('Retry-After', 30)))
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content'] or ''


def parse_answer(text, has_abstract):
    """LLM text -> answer dict. Anything unreadable becomes 'unsure', never 'exclude'."""
    match = re.search(r'\{.*\}', text, re.S)
    try:
        answer = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        answer = {}
    answer = {c: str(answer.get(c) or '').strip() for c in ANSWER_COLUMNS}
    answer['decision'] = answer['decision'].lower()
    if answer['decision'] not in DECISIONS:
        answer.update(decision='unsure', reason=f'unreadable LLM answer: {text[:200]!r}')
    if answer['decision'] == 'exclude' and not has_abstract:
        # title alone is not enough to rule a paper out
        answer['decision'] = 'unsure'
        answer['reason'] = '(no abstract, so at most unsure) ' + answer['reason']
    return answer


def screen(df, system, find_examples, llm=ask_llm):
    answers = []
    for i, (_, row) in enumerate(df.iterrows(), 1):
        try:
            answer = parse_answer(llm(*build_prompt(row, system, find_examples)), bool(row.abstract.strip()))
        except requests.RequestException as e:
            # one failing call must not stop the weekly run
            answer = dict(decision='unsure', reason=f'LLM call failed: {e}', criterion='', location_guess='')
        answers.append(answer)
        print(f'[{i}/{len(df)}] {answer["decision"]:8} {row.title[:70]}', file=sys.stderr)
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(answers, columns=ANSWER_COLUMNS)], axis=1)


# --- backfill: negatives and evaluation ----------------------------------------

def backfill_candidates(raw_path):
    """Filtered backfill with label: True = in EarXplore, False = seen by the authors, not included."""
    raw = pd.read_csv(raw_path, dtype=str, keep_default_na=False).reindex(columns=search.COLUMNS, fill_value='')
    kept = search.apply_filter(raw).query('excluded == ""').drop(columns='excluded')
    corpus = search.load_corpus()
    dois = {doi for doi, _ in corpus.values()} - {''}
    titles = {title for _, title in corpus.values()} - {''}
    return kept.assign(label=kept.doi.isin(dois) | kept.title.map(search.norm_title).isin(titles))


def make_negatives(raw_path, path=NEGATIVES_PATH):
    negatives = backfill_candidates(raw_path).query('not label')[['doi', 'title', 'abstract']]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    negatives.to_csv(path, index=False)
    print(f'{len(negatives)} not-included papers written to {path}', file=sys.stderr)


def evaluate(raw_path, system, find_examples, limit=None, llm=ask_llm):
    data = backfill_candidates(raw_path)
    positives, negatives = data[data.label], data[~data.label]
    if limit:
        negatives = negatives.sample(min(limit, len(negatives)), random_state=0)
    result = screen(pd.concat([positives, negatives]), system, find_examples, llm)

    kept = result.decision != 'exclude'
    pos, neg = result[result.label], result[~result.label]
    print('\n' + pd.crosstab(result.label.map({True: 'in EarXplore', False: 'not included'}),
                             result.decision).to_string())
    print(f'\nrecall (include+unsure on EarXplore papers): {kept[result.label].sum()}/{len(pos)}')
    print(f'workload (include+unsure on not-included):   {kept[~result.label].sum()}/{len(neg)}')
    for title, reason in pos[pos.decision == 'exclude'][['title', 'reason']].itertuples(index=False):
        print(f'  MISSED: {title[:70]}\n          {reason}')
    for title, reason in neg[neg.decision == 'include'][['title', 'reason']].itertuples(index=False):
        print(f'  CHECK (maybe missed by the paper?): {title[:70]}\n          {reason}')
    return result


# --- self-check ---------------------------------------------------------------

def selfcheck():
    assert parse_answer('```json\n{"decision": "Include", "reason": "Tap input."}\n```', True)['decision'] == 'include'
    assert parse_answer('I think it is fine.', True)['decision'] == 'unsure'
    assert parse_answer('{"decision": "maybe"}', True)['decision'] == 'unsure'
    assert parse_answer('{"decision": "exclude", "reason": "x"}', False)['decision'] == 'unsure'
    assert parse_answer('{"decision": "exclude", "criterion": 5}', True)['criterion'] == '5'

    corpus = load_corpus_papers()
    assert '- Mouth: tongue' in location_overview(corpus)
    try:
        location_overview(pd.DataFrame({'location': ['Mouth, Knee']}))
        assert False, 'undescribed location must fail'
    except ValueError:
        pass
    negatives = pd.DataFrame({'doi': ['10.1/n1', '10.1/n2'],
                              'title': ['Heart rate from earbuds', 'Noise cancelling headphones'],
                              'abstract': ['We monitor heart rate passively.', 'A new ANC circuit.']})
    find = make_example_finder(corpus, negatives)
    first = corpus.iloc[0]
    included, not_included = find(pd.Series({'doi': '', 'title': first.title, 'abstract': first.abstract}))
    assert first.title not in set(included.title)          # never its own example
    assert len(included) == N_EXAMPLES and len(not_included) == 2

    system = SYSTEM_PROMPT.format(locations=location_overview(corpus))
    row = pd.Series({'doi': '10.1/c', 'title': 'Teeth clicks on earbuds', 'abstract': '',
                     'venue': 'CHI', 'type': 'conference-paper', 'keywords': ''})
    _, user = build_prompt(row, system, find)
    assert '(no abstract available)' in user and 'ARE in EarXplore' in user

    fake_llm = lambda s, u: '{"decision": "exclude", "reason": "passive", "criterion": "5"}'
    out = screen(pd.DataFrame([row]), system, find, fake_llm)
    assert out.decision[0] == 'unsure'  # no abstract

    sent = []
    screen(pd.DataFrame([row]), None, find, lambda s, u: sent.append(s) or '{"decision": "include"}')
    assert sent == [None]  # --no-system-prompt: no system message reaches the LLM
    print('self-check ok')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('candidates', nargs='?', help='candidates.csv from search_candidates.py')
    parser.add_argument('--out', default='screened.csv')
    parser.add_argument('--evaluate', metavar='RAW_CSV', help='measure on a raw backfill instead')
    parser.add_argument('--limit', type=int, help='--evaluate: use only N not-included papers')
    parser.add_argument('--make-negatives', metavar='RAW_CSV', help='build the not-included example pool')
    parser.add_argument('--show-prompt', action='store_true', help='print the first prompt, no LLM call')
    parser.add_argument('--no-system-prompt', action='store_true',
                        help='send no system prompt: LLM_MODEL is a KI-Toolbox model with its own')
    parser.add_argument('--selfcheck', action='store_true')
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        raise SystemExit
    if args.make_negatives:
        make_negatives(args.make_negatives)
        raise SystemExit

    corpus = load_corpus_papers()
    system = None if args.no_system_prompt else SYSTEM_PROMPT.format(locations=location_overview(corpus))
    find_examples = make_example_finder(corpus, load_negatives())

    if args.show_prompt:
        first = pd.read_csv(args.candidates or args.evaluate, dtype=str, keep_default_na=False).iloc[0]
        for part in build_prompt(first.reindex(search.COLUMNS, fill_value=''), system, find_examples):
            print(part or '(no system prompt: the KI-Toolbox model uses its own)', end='\n\n' + '=' * 80 + '\n\n')
        raise SystemExit

    missing = [v for v in ('LLM_API_URL', 'LLM_API_KEY', 'LLM_MODEL') if not os.getenv(v)]
    if missing:
        sys.exit(f'set {", ".join(missing)} in .env first (see the docstring at the top)')

    if args.evaluate:
        evaluate(args.evaluate, system, find_examples, args.limit).to_csv(args.out, index=False)
    else:
        candidates = pd.read_csv(args.candidates, dtype=str, keep_default_na=False)
        screen(candidates, system, find_examples).to_csv(args.out, index=False)
    print(f'written to {args.out}', file=sys.stderr)
