"""Step 2.3 of the update pipeline: categorise new studies with an LLM, panel by panel.

Input is proposed.csv from extract_studies.py (metadata + extracted full text).
For every panel, one LLM call gets the paper's full text and how the two most
similar EarXplore studies were categorised in that panel. The answer holds a
value and a verbatim evidence quote per column. Afterwards every value is
checked: known value? right format? quote really in the paper? consistent with
the other panels? Problems become flags for the review.

Panels: Interaction, Performance, Sensing, Study, Device, Motivations (incl. Intended Applications).

Models, per panel (.env or environment):
  LLM_MODEL_<PANEL>  e.g. LLM_MODEL_INTERACTION: a KI-Toolbox model that brings its own
                     system prompt for this panel; the script then sends no system prompt.
                     Panels: INTERACTION, PERFORMANCE, SENSING, STUDY, DEVICE, MOTIVATIONS
  LLM_MODEL_CATEGORISATION
                     plain model (e.g. alias.medium-local) for panels without their own, with
                     the script's own system prompt (generated from data.csv / explanations.csv).
                     Falls back to LLM_MODEL, which must then not carry a system prompt itself.
  LLM_API_URL, LLM_API_KEY as for screen_candidates.py.

Usage:
  python git_actions_scripts/categorise_studies.py proposed.csv --out categorised.csv
      -> categorised.csv (proposed rows + category columns) and categorised_review.csv
         (one line per study and column: value, evidence, flag)
  python git_actions_scripts/categorise_studies.py --evaluate 14 --out eval.csv [--panels Interaction,Study]
      -> categorise corpus studies whose text is in --work-dir and compare with data.csv
  python git_actions_scripts/categorise_studies.py proposed.csv --show-prompt
  python git_actions_scripts/categorise_studies.py --export-prompts toolbox_prompts
      -> one system prompt per panel to paste into the KI-Toolbox models (re-export
         after data.csv changed: the allowed values come from it)
  python git_actions_scripts/categorise_studies.py --selfcheck
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import extract_studies as extract  # noqa: E402  (text file names)
import screen_candidates as screen  # noqa: E402  (LLM call, similar-study finder)
import evaluate_extraction  # noqa: E402  (scores against data.csv)

load_dotenv()

DATA_PATH = 'datasets/data.csv'
EXPLANATIONS_PATH = 'datasets/explanations.csv'
MAX_TEXT = 60000        # characters of full text per call (~15k tokens)
N_EXAMPLES = 2

# Column kinds:
#   multi        values from a list, sorted alphabetically (as in data.csv)
#   list         values from a list, order kept (Motivations, Development Stage)
#   free         free text, order kept, no list (Device Model)
#   single       exactly one value from a list
#   number       an integer
#   performance  "94 (N=12)": percentage and number of participants
#   study        "No" or "Yes (N=18)"
PANELS = {
    'Interaction': {
        'Location': 'multi',
        'Input Body Part': 'multi',
        'Gesture': 'multi',
        'Interaction_PANEL_Number of Selected Gestures': 'number',
        'Interaction_PANEL_Resolution': 'multi',
        'Interaction_PANEL_Hands-Free': 'single',
        'Interaction_PANEL_Eyes-Free': 'single',
        'Interaction_PANEL_Possible on One Ear': 'single',
        'Interaction_PANEL_Adaptation of the Interaction Detection Algorithm to User': 'single',
    },
    'Performance': {
        'Interaction_PANEL_Accuracy of Interaction Detection (User-Dependent)': 'performance',
        'Interaction_PANEL_Accuracy of Interaction Detection (User-Independent)': 'performance',
        'Interaction_PANEL_F1-Score of Interaction Detection (User-Dependent)': 'performance',
        'Interaction_PANEL_F1-Score of Interaction Detection (User-Independent)': 'performance',
    },
    'Sensing': {
        'Sensing_PANEL_Sensors': 'multi',
        'Sensing_PANEL_No Additional Sensing': 'single',
    },
    'Study': {
        'Study_PANEL_Elicitation Study': 'study',
        'Study_PANEL_Usability Evaluations': 'study',
        'Study_PANEL_Cognitive Load Evaluations': 'study',
        'Study_PANEL_Social Acceptability of Interactions Evaluations': 'study',
        'Study_PANEL_Evaluation of Settings': 'multi',
        'Study_PANEL_Evaluation of User-Related Conditions': 'multi',
        'Study_PANEL_Evaluation of Environment-Related Conditions': 'multi',
        'Study_PANEL_Evaluation of Device-Related Conditions': 'multi',
    },
    'Device': {
        'Device_PANEL_Earphone Type': 'multi',
        'Device_PANEL_Development Stage': 'list',
        'Device_PANEL_Device Model': 'free',
        'Device_PANEL_Real-Time Processing': 'single',
        'Device_PANEL_On-Device Processing': 'single',
    },
    'Motivations': {
        'Motivations_PANEL_Motivations': 'list',
        'Applications_PANEL_Intended Applications': 'multi',
    },
}

# Corpus conventions the column definitions do not spell out. Same content as
# the system prompts of the KI-Toolbox panel models.
PANEL_NOTES = {
    'Interaction': """\
- Record only the interactions the paper actually implements, demonstrates or evaluates, not interactions it merely calls possible. A sensing platform that is evaluated only for eye movements gets only eye-related values, even if it could also sense EEG or jaw movements.
- Pure elicitation studies (gestures are only proposed by participants, no system detects them): Gesture, Input Body Part, Resolution, Hands-Free, Eyes-Free, Possible on One Ear and Adaptation are "N/A", and Number of Selected Gestures is 0. Location is still filled in.
- Actuation papers (the earable gives non-auditory output such as vibration or heat): Location is "Actuation", Gesture names the actuation type (e.g. "Vibration (Actuation)"), Input Body Part is "N/A".
- Use the gesture names of the list including the part in brackets, which says where the gesture is performed: "(Earable)" on the device, "(Ear)" on the ear, "(Face)" on the face, "(Mid-Air)" in the air. "Tap" is a short touch, "Touch" a contact without a tapping motion.
- Number of Selected Gestures follows its definition and can differ from the number of Gesture values (e.g. "Ekman 7" stands for seven facial expressions).
- Resolution: give the resolution of the main interaction. Give several values only if the paper's interactions clearly differ in resolution.
- Adaptation: "Yes" only if the paper shows that a trained detection model is adapted, calibrated or fine-tuned to a new individual user. Training or evaluating per user (user-dependent models) alone is "No".
- Possible on One Ear: "Yes" if the interaction works with a device on one ear; "No" if the system needs both ears (e.g. it compares signals from left and right); "Yes (Performance Loss)" only if the paper reports that one ear works but worse.""",
    'Performance': """\
- Value format: the percentage as a whole number, then the number of participants the result is based on in brackets, e.g. "94 (N=12)". Convert fractions to percent (0.943 -> 94) and round half up.
- Only report what the paper reports as accuracy or as F1-score. Do not derive or convert other metrics (precision, recall, error rate, EER, AUC); those fields are "N/A".
- Consider only the most basic reported condition and setting (e.g. sitting in a lab, no noise, no motion), the full gesture set, and the paper's own proposed method (not baselines). Take the result of the main evaluation, not the best result of an ablation, a subset of gestures or a single participant.
- Decide User-Dependent vs. User-Independent from how the test users relate to the training data:
  - User-Independent: leave-one-user-out, leave-one-subject-out, cross-user, "unseen users", "new users", models trained on some participants and tested on others.
  - User-Dependent: within-user, per-user, user-specific, personalised models, "trained and tested on data of the same participants", k-fold or random splits over the pooled data of all participants.
  - If the paper reports both, fill both fields with their own values. Never put the same result into both fields.
  - If the data split cannot be determined, use User-Dependent.""",
    'Sensing': """\
- Sensors: only sensors that are part of the earable AND that the presented system actually uses to detect the interaction. Do not list sensors the device merely has (e.g. an IMU in an earbud whose method uses only the microphone). Most studies list one or two sensors.
- A speaker counts only if the earable's own speaker emits the sensing signal (e.g. ultrasound, active acoustic sensing). A signal emitted by a smartphone or another device does not make "Speaker" a sensor of the earable. A physical button counts as "Button".
- Papers without sensing for interaction (pure elicitation studies, actuation-only devices): Sensors is "N/A" and No Additional Sensing is "N/A".
- No Additional Sensing: "Yes" if the earable alone senses the interaction; "No" if another device senses part of it (e.g. a ring, wristband, camera, smartphone sensors). A smartphone that only processes or displays data does not count as sensing. "Partly" if only some of the interactions need additional sensing devices.""",
    'Study': """\
- The four study fields are "No", or "Yes (N=<number of participants>)", e.g. "Yes (N=18)". Use "Yes" without a number only if the paper does not report it. If several such studies were run, use the participants of the main one.
- Usability Evaluations: participants rated or commented on using the interactions, e.g. SUS, UEQ, ratings of ease of use, comfort, fatigue or preference, or interviews about the interaction. A recognition or accuracy experiment with participants is NOT a usability evaluation, even if participants performed the gestures.
- Cognitive Load Evaluations: only explicit workload measures of the interactions, e.g. NASA-TLX or a dual-task design.
- Social Acceptability of Interactions Evaluations: participants rated how acceptable it is to perform the interactions in front of others or in public places.
- Elicitation Study: participants proposed gestures or interactions for given commands or scenarios.
- Settings and conditions describe the evaluation of the interactions (e.g. the recognition experiment). Write "N/A" when the paper does not evaluate the interactions.
- User-Related Conditions: what the participants did during the evaluation; a seated lab study is "Sitting".
- Environment-Related Conditions: only conditions deliberately induced to test robustness (e.g. played noise), not conditions that are simply part of the setting.
- Device-Related Conditions: only device conditions deliberately varied in the evaluation (e.g. re-wearing the device, different device models, music playing).""",
    'Device': """\
- Earphone Type: "Earbud" for in-ear earphones and earbuds; "Headphone" for on-ear and over-ear headphones; "Custom Device" for self-built ear-worn devices that are not shaped like standard earphones (e.g. earmolds, behind-the-ear electrodes, ear-mounted frames). Several types are possible.
- Development Stage:
  - "Commercial": an off-the-shelf product is used as it is.
  - "Research Prototype": the device was built by the researchers (including research platforms such as eSense or OpenEarable).
  - "Commercial, Research Prototype": an off-the-shelf product was modified, e.g. sensors, electrodes or other hardware were added to it. This is also the value when the study uses both a commercial and a self-built device.
- Device Model: the exact product names as written in the paper, separated by ", ", in the order the paper names them. Whenever the paper adds hardware to a product or changes it, add " (Adapted)" to that model, e.g. "Bose QC45 (Adapted)". "N/A" for self-built devices without a model name.
- Real-Time Processing: "Yes" only if the system is shown to detect and respond to interactions live; "No" if the data is analysed offline; "N/A" if there is no detection (e.g. elicitation or actuation-only papers).
- On-Device Processing: "Yes" only if detection runs on the earable itself; processing on a smartphone, computer or connected microcomputer is "No"; "N/A" if there is no detection.""",
    'Motivations': """\
- Use only what the authors explicitly state, typically in the abstract, introduction, discussion or conclusion. Do not infer motivations or applications yourself.
- Intended Applications: only applications the authors explicitly propose as uses of THEIR system or interaction (e.g. "our system can be used for ..."). Do not list applications mentioned only in the related work, as general background or as distant future work. Most studies have one to three.
- Motivations: use only the six listed values. List them in the order of how prominent they are in the paper, most prominent first. Most studies have two to four.
  - Proof-of-Concept: demonstrating the feasibility of a novel idea, technology, or interaction modality.
  - Novel Interaction Technique: creating and/or validating a new input or output method enabled by earable technologies.
  - System Extension: enhancing an existing system or concept, such as by adding new sensing modalities or features.
  - Performance Optimization: improving existing solutions by increasing accuracy, robustness, efficiency, or responsiveness.
  - User-Centered Design: developing the system or interaction approach based on explicitly identified user needs or user research.
  - Societal Impact: motivated by a larger societal goal, such as improving accessibility or health.""",
}

SYSTEM_PROMPT = """\
You categorise a research paper for EarXplore, a curated database of research on interaction with earables, \
exactly the way the existing studies in EarXplore were categorised. You fill the fields of the {panel} panel.

## Input
The user message contains: (1) similar EarXplore studies with the values they received for this panel, as \
examples of how the corpus is coded; (2) the paper to categorise: title, abstract and full text.

## Rules
- Follow the definition of each field.
- Use the allowed values, written exactly as listed. Separate several values with ", ".
- Only if no listed value fits, write a new value in the same style. It will be reviewed by a human.
- Write "N/A" if the paper gives no information or the field does not apply.
- Evidence: for every field, copy ONE continuous passage from the paper, word for word (at most 30 words), \
that supports the value. Do not join passages with "...", do not paraphrase and do not describe the paper in \
your own words; the passage is checked against the paper. Leave the evidence empty ("") for "N/A", for "No" \
and whenever the value follows from something the paper does not do.

## Corpus conventions
{notes}

## Fields

{fields}
## Answer format
Answer with JSON only, without any other text:
{{{schema}}}"""

ALLOWED_TEXT = {
    'number': 'an integer',
    'performance': 'the percentage as a whole number and the number of participants, e.g. "94 (N=12)"; or N/A',
    'study': '"No", or "Yes (N=<number of participants>)", e.g. "Yes (N=18)"',
}
LIST_KINDS = {'multi', 'list', 'single'}


def short(column):
    """'Interaction_PANEL_Hands-Free' -> 'Hands-Free' (the JSON keys the LLM sees)."""
    return column.split('_PANEL_')[-1]


def panel_model(panel):
    """The KI-Toolbox model of this panel, or '' to use the fallback model with the script's prompt."""
    return os.getenv(f'LLM_MODEL_{panel.upper()}', '')


def fallback_model():
    """Plain model for panels without their own. LLM_MODEL may be the screening's toolbox
    model with its own system prompt, so LLM_MODEL_CATEGORISATION comes first."""
    return os.getenv('LLM_MODEL_CATEGORISATION') or os.getenv('LLM_MODEL', '')


# --- vocabulary and prompt ------------------------------------------------------

def load_vocabulary(data):
    """{column: [values, most frequent first]} from the existing studies."""
    vocab = {}
    for panel in PANELS.values():
        for column, kind in panel.items():
            if kind in LIST_KINDS or kind == 'free':
                values = data[column].str.split(', ').explode().str.strip()
                vocab[column] = values[~values.isin(['', 'Nan', 'nan'])].value_counts().index.tolist()
    return vocab


def field_block(panel, vocab, explanations):
    lines = []
    for column, kind in PANELS[panel].items():
        lines += [f'### {short(column)}', f'Definition: {explanations.get(column, "")}']
        if kind in ALLOWED_TEXT:
            lines.append(f'Allowed values: {ALLOWED_TEXT[kind]}')
        elif kind == 'free':
            lines.append(f'Allowed values: names as written in the paper, e.g. {"; ".join(vocab[column][1:7])}; or N/A')
        else:
            how = {'multi': 'one or more', 'list': 'one or more', 'single': 'exactly one'}[kind]
            lines.append(f'Allowed values ({how}): {"; ".join(vocab[column])}')
        lines.append('')
    return '\n'.join(lines)


def system_prompt(panel, vocab, explanations):
    schema = ', '.join(f'"{short(c)}": {{"value": "...", "evidence": "..."}}' for c in PANELS[panel])
    return SYSTEM_PROMPT.format(panel=panel.upper(), notes=PANEL_NOTES.get(panel, '-'),
                                fields=field_block(panel, vocab, explanations), schema=schema)


def user_prompt(panel, study, text, examples):
    parts = ['How similar EarXplore studies were categorised:']
    for _, values in examples.iterrows():
        parts.append(f'- "{values["title"]}"')
        parts += [f'    {short(c)}: {values[c]}' for c in PANELS[panel]]
    parts += ['', 'PAPER TO CATEGORISE', f'Title: {study["Title"]}', f'Abstract: {study["Abstract"]}', '',
              'Full text:', text[:MAX_TEXT] if text else '(no full text available, use title and abstract)']
    return '\n'.join(parts)


# --- answer checking ------------------------------------------------------------

def squash(text):
    """For finding quotes: letters and digits only, so PDF artefacts (line-break hyphens,
    curly quotes, ligatures, spacing around citations) do not hide a real quote."""
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKC', text).lower())


def clean_value(column, kind, raw, vocab):
    """Normalise one value; returns (value, flags)."""
    raw = ' '.join(str(raw).split()) or 'N/A'
    if raw.lower() in ('n/a', 'na', 'none'):
        return 'N/A', ['no number given'] if kind == 'number' else []

    if kind == 'number':
        return raw, [] if raw.isdigit() else [f'not a number: {raw!r}']

    if kind == 'performance':
        m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*%?\s*(?:\(\s*N\s*=\s*(\d+)\s*\))?', raw, re.I)
        if not m:
            return raw, [f'unexpected format: {raw!r}']
        percent = float(m.group(1))
        percent = percent * 100 if percent <= 1 and '.' in m.group(1) else percent
        value = str(int(percent + 0.5))
        flags = [] if 0 <= percent <= 100 else ['percentage outside 0-100']
        if m.group(2):
            return f'{value} (N={m.group(2)})', flags
        return value, flags + ['number of participants missing']

    if kind == 'study':
        m = re.fullmatch(r'(no|yes)\s*(?:\(\s*N\s*=\s*(\d+)\s*\))?', raw, re.I)
        if not m:
            return raw, [f'unexpected format: {raw!r}']
        if m.group(1).lower() == 'no':
            return 'No', []
        return (f'Yes (N={m.group(2)})', []) if m.group(2) else ('Yes', ['number of participants missing'])

    values = list(dict.fromkeys(v.strip() for v in raw.split(',') if v.strip()))
    if len(values) > 1 and 'N/A' in values:
        values.remove('N/A')
    if kind == 'multi':
        values.sort()
    flags = []
    if kind in LIST_KINDS:
        new = [v for v in values if v not in vocab[column] and v != 'N/A']
        if new:
            flags.append(f'new value: {", ".join(new)}')
    if kind == 'single' and len(values) > 1:
        flags.append('several values for a single-value column')
    return ', '.join(values), flags


def parse_answer(panel, answer_text, text, vocab):
    """LLM JSON -> {column: (value, evidence, flags)}. Missing or broken answers become N/A + flag."""
    match = re.search(r'\{.*\}', answer_text or '', re.S)
    try:
        answer = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        answer = {}
    result = {}
    for column, kind in PANELS[panel].items():
        item = answer.get(short(column))
        if not isinstance(item, dict):
            result[column] = ('N/A', '', ['no answer from the LLM'])
            continue
        value, flags = clean_value(column, kind, item.get('value', ''), vocab)
        evidence = str(item.get('evidence') or '').strip()
        if evidence and text and squash(evidence) not in squash(text):
            flags.append('quote not found in the paper')
        result[column] = (value, evidence, flags)
    return result


def consistency_flags(row):
    """Rules across panels that hold in data.csv; returns {column: flag}."""
    flags = {}
    sensors, extra = row.get('Sensing_PANEL_Sensors'), row.get('Sensing_PANEL_No Additional Sensing')
    if sensors is not None and extra is not None and (sensors == 'N/A') != (extra == 'N/A'):
        msg = 'Sensors and No Additional Sensing should both be N/A or both be filled'
        flags['Sensing_PANEL_Sensors'] = flags['Sensing_PANEL_No Additional Sensing'] = msg
    count, gesture = row.get('Interaction_PANEL_Number of Selected Gestures'), row.get('Gesture')
    if count == '0' and gesture not in (None, 'N/A'):
        flags['Gesture'] = flags['Interaction_PANEL_Number of Selected Gestures'] = \
            '0 gestures but Gesture is filled'
    return flags


# --- running ----------------------------------------------------------------------

def read_text(doi, work_dir):
    path = os.path.join(work_dir, 'text', extract.slug(doi) + '.txt')
    if not os.path.exists(path):
        return ''
    with open(path, encoding='utf-8') as f:
        return f.read()


def make_context(data):
    explanations = pd.read_csv(EXPLANATIONS_PATH, dtype=str, keep_default_na=False).set_index('Column').Explanation
    corpus = screen.load_corpus_papers(DATA_PATH)
    finder = screen.make_example_finder(corpus, pd.DataFrame(columns=['doi', 'title', 'abstract']))
    return load_vocabulary(data), explanations.to_dict(), finder


def similar_studies(finder, study):
    examples = finder(pd.Series({'title': study['Title'], 'abstract': study['Abstract'], 'doi': ''}))[0]
    # the finder returns data.csv rows with Location renamed; give back the real name
    return examples.assign(Location=examples['location']).head(N_EXAMPLES)


def categorise(studies, work_dir, data, llm=screen.ask_llm, panels=tuple(PANELS)):
    """Returns (rows with category columns, review lines)."""
    vocab, explanations, finder = make_context(data)
    rows, review = [], []
    for i, (_, study) in enumerate(studies.iterrows(), 1):
        text = read_text(study['doi'], work_dir)
        examples = similar_studies(finder, study)
        row, lines = study.to_dict(), []
        for panel in panels:
            model = panel_model(panel)
            system = None if model else system_prompt(panel, vocab, explanations)
            try:
                answer = llm(system, user_prompt(panel, study, text, examples), 3000, model or fallback_model() or None)
            except requests.RequestException as e:
                answer = ''
                print(f'  {panel}: LLM call failed: {e}', file=sys.stderr)
            for column, (value, evidence, flags) in parse_answer(panel, answer, text, vocab).items():
                if not text:
                    flags = ['no full text, only title and abstract'] + flags
                row[column] = value
                lines.append({'ID': study['ID'], 'Title': study['Title'], 'panel': panel, 'column': column,
                              'field': short(column), 'value': value, 'evidence': evidence, 'flag': flags})
        extra = consistency_flags(row)
        for line in lines:
            if line['column'] in extra:
                line['flag'].append(extra[line['column']])
            line['flag'] = '; '.join(line.pop('flag'))
            line.pop('column')
        review += lines
        rows.append(row)
        flagged = sum(1 for line in lines if line['flag'])
        print(f'[{i}/{len(studies)}] ID {study["ID"]}: {flagged} flagged fields  {study["Title"][:60]}',
              file=sys.stderr)
    return pd.DataFrame(rows), pd.DataFrame(review)


def evaluate(n, work_dir, out, panels):
    """Categorise n corpus studies that have a full text and compare with data.csv."""
    data = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
    dois = {sid: doi for sid, (doi, _) in screen.search.load_corpus().items()}
    data = data.assign(doi=data.ID.map(dois).fillna(''))
    with_text = data[data.doi.map(lambda d: bool(d) and bool(read_text(d, work_dir)))]
    sample = with_text.sample(min(n, len(with_text)), random_state=0)
    print(f'{len(with_text)} corpus studies have a full text, evaluating {len(sample)}', file=sys.stderr)
    # only the metadata goes in; the categories are what is being predicted
    rows, review = categorise(sample[['ID', 'Title', 'Abstract', 'doi']], work_dir, data, panels=panels)
    rows.to_csv(out, index=False)
    review.to_csv(os.path.splitext(out)[0] + '_review.csv', index=False)
    scores = evaluate_extraction.evaluate(evaluate_extraction.read(out), evaluate_extraction.read(DATA_PATH))
    print('\n' + scores.rename(index=short).round(2).to_string())
    print(f'\nmean: {scores.mean():.2f}   flagged fields: {(review.flag != "").mean():.0%}')


# --- self-check ---------------------------------------------------------------

def selfcheck():
    data = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
    vocab, explanations, finder = make_context(data)
    assert 'Mouth' in vocab['Location'] and 'Nan' not in vocab['Study_PANEL_Evaluation of Device-Related Conditions']
    for panel in PANELS:  # every panel has notes and a valid prompt
        prompt = system_prompt(panel, vocab, explanations)
        assert panel in PANEL_NOTES and all(f'### {short(c)}' in prompt for c in PANELS[panel])
    assert 'Tap (Earable)' in system_prompt('Interaction', vocab, explanations)
    assert '"94 (N=12)"' in system_prompt('Performance', vocab, explanations)

    # formats
    perf = 'Interaction_PANEL_Accuracy of Interaction Detection (User-Dependent)'
    assert clean_value(perf, 'performance', '94.5% (N=12)', vocab) == ('95 (N=12)', [])
    assert clean_value(perf, 'performance', '0.943 (n = 8)', vocab) == ('94 (N=8)', [])
    assert clean_value(perf, 'performance', '91', vocab) == ('91', ['number of participants missing'])
    assert clean_value(perf, 'performance', 'high', vocab)[1] == ["unexpected format: 'high'"]
    study = 'Study_PANEL_Usability Evaluations'
    assert clean_value(study, 'study', 'yes (n=18)', vocab) == ('Yes (N=18)', [])
    assert clean_value(study, 'study', 'No', vocab) == ('No', [])
    assert clean_value(study, 'study', 'Yes', vocab) == ('Yes', ['number of participants missing'])
    motiv = 'Motivations_PANEL_Motivations'
    assert clean_value(motiv, 'list', 'System Extension, Proof-of-Concept', vocab)[0] == \
        'System Extension, Proof-of-Concept'  # order kept
    assert clean_value('Device_PANEL_Device Model', 'free', 'Sony X1, AirPods Pro', vocab) == ('Sony X1, AirPods Pro', [])

    text = 'We detect taps on the ear-\nbud and head nods with an IMU in both earbuds.'
    answer = json.dumps({
        'Location': {'value': 'Head Gestures and Pointing, Ear and Earable', 'evidence': 'taps on the earbud'},
        'Gesture': {'value': 'Tap (Earable), Nodding Wildly', 'evidence': 'head nods with an IMU'},
        'Number of Selected Gestures': {'value': 'two', 'evidence': ''},
        'Hands-Free': {'value': 'No', 'evidence': 'invented quote'},
        'Eyes-Free': {'value': 'Yes, No', 'evidence': ''},
    })
    out = parse_answer('Interaction', 'Sure!\n' + answer, text, vocab)
    assert out['Location'] == ('Ear and Earable, Head Gestures and Pointing', 'taps on the earbud', [])  # sorted
    assert out['Gesture'][2] == ['new value: Nodding Wildly']
    assert out['Interaction_PANEL_Number of Selected Gestures'][2] == ["not a number: 'two'"]
    assert out['Interaction_PANEL_Hands-Free'][2] == ['quote not found in the paper']
    assert out['Interaction_PANEL_Eyes-Free'][2] == ['several values for a single-value column']
    assert out['Interaction_PANEL_Resolution'] == ('N/A', '', ['no answer from the LLM'])
    assert squash('recog- nition with leave-one-user-\nout, the user’s ﬁngers [ 7, 12]') == \
        squash("recognition with leave-one-userout, the user's fingers [7,12]")

    assert consistency_flags({'Sensing_PANEL_Sensors': 'N/A', 'Sensing_PANEL_No Additional Sensing': 'Yes'})
    assert not consistency_flags({'Sensing_PANEL_Sensors': 'IMU', 'Sensing_PANEL_No Additional Sensing': 'Yes'})
    assert consistency_flags({'Interaction_PANEL_Number of Selected Gestures': '0', 'Gesture': 'Tap (Ear)'})

    # per-panel models: a panel with its own model gets no system prompt
    saved = {k: os.environ.get(k) for k in ('LLM_MODEL_INTERACTION', 'LLM_MODEL_SENSING')}
    os.environ['LLM_MODEL_INTERACTION'] = ''  # independent of the models set in .env
    os.environ['LLM_MODEL_SENSING'] = 'toolbox-sensing'
    calls = []
    def fake(system, user, max_tokens, model):
        calls.append((system is None, model))
        return json.dumps({'Sensors': {'value': 'N/A', 'evidence': ''},
                           'No Additional Sensing': {'value': 'Yes', 'evidence': ''}})
    one = pd.Series({'ID': '142', 'Title': data.Title[0], 'Abstract': data.Abstract[0], 'doi': '10.1/none'})
    try:
        rows, review = categorise(pd.DataFrame([one]), 'no_such_dir', data, fake, panels=('Interaction', 'Sensing'))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    assert calls == [(False, fallback_model() or None), (True, 'toolbox-sensing')]
    assert review.flag.str.startswith('no full text').all()
    assert 'both be N/A' in review.set_index('field').at['Sensors', 'flag']
    example_part = user_prompt('Interaction', one, '', similar_studies(finder, one)).split('PAPER TO CATEGORISE')[0]
    assert data.Title[0] not in example_part  # never its own example
    print('self-check ok')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('proposed', nargs='?', help='proposed.csv from extract_studies.py')
    parser.add_argument('--out', default='categorised.csv')
    parser.add_argument('--work-dir', default='extraction_work', help='where extract_studies.py put the texts')
    parser.add_argument('--panels', default=','.join(PANELS), help=f'comma-separated subset of {list(PANELS)}')
    parser.add_argument('--evaluate', type=int, metavar='N', help='categorise N corpus studies and compare')
    parser.add_argument('--show-prompt', action='store_true', help='print the prompts for the first study')
    parser.add_argument('--export-prompts', metavar='DIR',
                        help='write the system prompt of every panel to DIR/<panel>.txt (for the KI-Toolbox models)')
    parser.add_argument('--selfcheck', action='store_true')
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        raise SystemExit
    panels = [p.strip() for p in args.panels.split(',')]
    unknown = set(panels) - set(PANELS)
    if unknown:
        parser.error(f'unknown panels {sorted(unknown)}, choose from {list(PANELS)}')
    if args.export_prompts:
        # value lists come from data.csv: re-export after new studies were added
        vocab, explanations, _ = make_context(pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False))
        os.makedirs(args.export_prompts, exist_ok=True)
        for panel in panels:
            path = os.path.join(args.export_prompts, f'{panel.lower()}.txt')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(system_prompt(panel, vocab, explanations) + '\n')
            print(f'{panel}: {path}', file=sys.stderr)
        raise SystemExit

    if not args.show_prompt:
        missing = [v for v in ('LLM_API_URL', 'LLM_API_KEY') if not os.getenv(v)]
        if not fallback_model() and not all(panel_model(p) for p in panels):
            missing.append('LLM_MODEL_CATEGORISATION (or a LLM_MODEL_<PANEL> for every panel)')
        if missing:
            sys.exit(f'set {", ".join(missing)} in .env first (see the docstring at the top)')
    if args.evaluate:
        evaluate(args.evaluate, args.work_dir, args.out, panels)
        raise SystemExit
    if not args.proposed:
        parser.error('give proposed.csv, or use --evaluate')

    proposed = pd.read_csv(args.proposed, dtype=str, keep_default_na=False)
    data = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
    if args.show_prompt:
        vocab, explanations, finder = make_context(data)
        study = proposed.iloc[0]
        for panel in panels:
            model = panel_model(panel)
            print(f'#### {panel}  (model: {model or fallback_model() or "no model set"})')
            print(f'(KI-Toolbox model "{model}" brings its own system prompt)' if model
                  else system_prompt(panel, vocab, explanations))
            print('\n' + '-' * 80)
            print(user_prompt(panel, study, read_text(study['doi'], args.work_dir), similar_studies(finder, study))[:2500],
                  '\n...\n' + '=' * 80 + '\n')
        raise SystemExit

    rows, review = categorise(proposed, args.work_dir, data, panels=panels)
    rows.to_csv(args.out, index=False)
    review_path = os.path.splitext(args.out)[0] + '_review.csv'
    review.to_csv(review_path, index=False)
    print(f'written to {args.out} and {review_path}', file=sys.stderr)
