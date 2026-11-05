"""Steps 1.1-1.3 of the candidate pipeline: fetch new papers from ACM-DL,
IEEE Xplore and SpringerLink with the search terms of the EarXplore paper
(Section 3.1 / Appendix A), apply the paper's rules locally and drop papers
that are already known.

1.1 search: the APIs are queried broadly (a superset of the paper's query).
1.2 filter: search fields, content types, Springer disciplines/subjects and
    language are checked by the same code for all three sources.
1.3 dedupe: papers already in EarXplore (datasets/bibtexs.bib) or shown in an
    earlier run (datasets/candidates/seen.csv) are dropped; near-identical
    titles are flagged as possible alternative versions (column similar_to).

Usage:
  python git_actions_scripts/search_candidates.py --since 2026-04-10 --out candidates.csv
  python git_actions_scripts/search_candidates.py --input raw.csv --out candidates.csv   # filter only
  python git_actions_scripts/search_candidates.py ... --rejected rejected.csv           # inspect drops
  python git_actions_scripts/search_candidates.py ... --update-seen                     # remember results
  python git_actions_scripts/search_candidates.py --selfcheck

API keys via environment variables or the .env file in the repo root
(run from there). A source without its key is skipped;
OpenAlex also works without one but is heavily rate-limited.
  OPENALEX_API_KEY  https://openalex.org/settings/api      (ACM-DL substitute)
  IEEE_API_KEY      https://developer.ieee.org
  SPRINGER_API_KEY  https://dev.springernature.com
"""
import argparse
import datetime as dt
import difflib
import os
import re
import sys
import time

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()  # local .env; in GitHub Actions the keys come from repository secrets

# Search terms from the paper (Section 3.1 / Appendix A)
TERMS = ['earable', 'earables', 'hearable', 'hearables', 'ear-worn', 'ear worn',
         'earbud', 'earbuds', 'earphone', 'earphones', 'headphone', 'headphones',
         'earpiece', 'earpieces', 'ear-mounted', 'ear mounted', 'ear-attached',
         'ear attached', 'ear-based', 'ear based']
BOOLEAN_QUERY = ' OR '.join(f'"{t}"' for t in TERMS) + ' OR (ear AND (wearable OR wearables))'

# subjects: Springer only, needed for the paper's discipline filter (Computer
# Science, Engineering), which is a premium API feature and so done locally
COLUMNS = ['source', 'doi', 'title', 'abstract', 'keywords', 'date', 'type', 'venue', 'language',
           'subjects', 'url']


def get(url, params):
    """GET with a simple wait-and-retry on rate limits (HTTP 429)."""
    for attempt in range(4):
        r = requests.get(url, params=params, timeout=60)
        if r.status_code != 429 or attempt == 3:
            break
        # Retry-After may also be an HTTP date; fall back to 30 s then
        wait = r.headers.get('Retry-After', '')
        time.sleep(int(wait) if wait.isdigit() else 30)
    r.raise_for_status()
    return r.json()


def clean_doi(doi):
    return (doi or '').lower().removeprefix('https://doi.org/').strip()


def text(value):
    """Springer returns abstracts as str, list or {'h1':..., 'p':...}."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(text(v) for v in value)
    if isinstance(value, dict):
        return text(value.get('p', ''))
    return ''


# --- ACM-DL via OpenAlex (ACM has no official search API) -------------------

def from_openalex(w):
    index = w.get('abstract_inverted_index') or {}
    words = {pos: word for word, positions in index.items() for pos in positions}
    location = w.get('primary_location') or {}
    return {
        'source': 'ACM-DL',
        'doi': clean_doi(w.get('doi')),
        'title': w.get('title') or '',
        'abstract': ' '.join(words[i] for i in sorted(words)),
        # OpenAlex keywords are machine-generated, not the author keywords the
        # paper searched, so they are deliberately left out
        'keywords': '',
        'date': w.get('publication_date') or '',
        'type': w.get('type') or '',
        'venue': (location.get('source') or {}).get('display_name') or '',
        'language': w.get('language') or '',
        'url': w.get('doi') or '',
    }


def search_acm(since, until):
    params = {
        # 10.1145 is ACM's DOI prefix; OpenAlex often lacks the publisher for proceedings
        'filter': f'title_and_abstract.search:{BOOLEAN_QUERY},doi_starts_with:10.1145,'
                  f'from_publication_date:{since},to_publication_date:{until}',
        'select': 'doi,title,publication_date,type,language,abstract_inverted_index,primary_location',
        'per-page': 200,
        'cursor': '*',
    }
    if os.getenv('OPENALEX_API_KEY'):
        params['api_key'] = os.getenv('OPENALEX_API_KEY')
    while params['cursor']:
        data = get('https://api.openalex.org/works', params)
        yield from map(from_openalex, data['results'])
        params['cursor'] = data['meta'].get('next_cursor')


# --- IEEE Xplore ------------------------------------------------------------

def from_ieee(a):
    terms = [t for group in (a.get('index_terms') or {}).values() for t in group.get('terms', [])]
    return {
        'source': 'IEEE-X',
        'doi': clean_doi(a.get('doi')),
        'title': a.get('title') or '',
        'abstract': a.get('abstract') or '',
        'keywords': ', '.join(terms),  # author keywords + IEEE terms = "Index Terms"
        'date': a.get('publication_date') or str(a.get('publication_year') or ''),
        'type': a.get('content_type') or '',
        'venue': a.get('publication_title') or '',
        'language': '',
        'url': a.get('html_url') or '',
    }


def search_ieee(since, until):
    params = {
        'apikey': os.environ['IEEE_API_KEY'],
        'querytext': BOOLEAN_QUERY,
        # start_date/end_date = date the record was INSERTED into Xplore,
        # so late-indexed papers are not missed
        'start_date': since.replace('-', ''),
        'end_date': until.replace('-', ''),
        'max_records': 200,
        'start_record': 1,
    }
    while True:
        data = get('https://ieeexploreapi.ieee.org/api/v1/search/articles', params)
        articles = data.get('articles', [])
        yield from map(from_ieee, articles)
        params['start_record'] += len(articles)
        if not articles or params['start_record'] > int(data.get('total_records', 0)):
            break


# --- SpringerLink -----------------------------------------------------------

def from_springer(r):
    urls = r.get('url') or [{}]
    return {
        'source': 'SpringerLink',
        'doi': clean_doi(r.get('doi')),
        'title': text(r.get('title')),
        'abstract': text(r.get('abstract')),
        'keywords': ', '.join(r.get('keyword') or []),
        'date': r.get('onlineDate') or r.get('publicationDate') or '',
        # genre separates research papers ("OriginalPaper ...") from reviews,
        # encyclopedia entries etc., which contentType alone does not
        # (genre is a str for chapters, a list for journal articles)
        'type': f"{r.get('contentType') or ''} | {text(r.get('genre'))}",
        'venue': r.get('publicationName') or '',
        'language': r.get('language') or '',
        # subjects = disciplines (e.g. "Computer Science"); sntsubjects = the newer
        # taxonomy SpringerLink's web filters use (e.g. "Virtual and Augmented Reality")
        'subjects': ', '.join((r.get('subjects') or []) +
                              [s.get('term', '') for s in r.get('sntsubjects') or []]),
        'url': urls[0].get('value', ''),
    }


def search_springer(since, until):
    # The free plan only allows full-text search (title:/subject: are premium),
    # so most hits are noise (~3% match in title/abstract/keywords); the filter
    # step removes them. ~50 hits per week, but ~46,000 for all years.
    params = {
        'api_key': os.environ['SPRINGER_API_KEY'],
        'q': f'({BOOLEAN_QUERY}) onlinedatefrom:{since} onlinedateto:{until}',
        's': 1,
        'p': 25,  # maximum page size on the free plan
    }
    while True:
        data = get('https://api.springernature.com/meta/v2/json', params)
        records = data.get('records', [])
        yield from map(from_springer, records)
        params['s'] += len(records)
        if not records or params['s'] > int(data['result'][0]['total']):
            break


SOURCES = {'ACM-DL': (search_acm, None), 'IEEE-X': (search_ieee, 'IEEE_API_KEY'),
           'SpringerLink': (search_springer, 'SPRINGER_API_KEY')}


def search_all(since, until, sources=tuple(SOURCES)):
    rows = []
    for name in sources:
        search, key = SOURCES[name]
        if key and not os.getenv(key):
            print(f'{name}: skipped, {key} not set', file=sys.stderr)
            continue
        try:
            found = list(search(since, until))
        except requests.RequestException as e:  # HTTP errors, timeouts, connection errors
            # one failing source must not block the other two
            print(f'{name}: failed ({e})', file=sys.stderr)
            continue
        print(f'{name}: {len(found)} results', file=sys.stderr)
        rows += found
    df = pd.DataFrame(rows, columns=COLUMNS).fillna('')
    # same paper from two sources: keep the first; papers without DOI are kept
    return pd.concat([df[df.doi == ''], df[df.doi != ''].drop_duplicates('doi')])


# --- 1.2 filter: the paper's rules ------------------------------------------

TERM_RE = re.compile(r'\b(?:' + '|'.join(map(re.escape, TERMS)) + r')\b')

# Paper: ACM "Research Article OR Short Paper". OpenAlex cannot tell the two
# apart, so only obvious non-papers (conference-abstract, editorial, ...) go.
ACM_TYPES = {'article', 'conference-paper', 'review'}
# Paper: IEEE "Conferences, Journals". Deviation: Early Access articles are
# peer-reviewed journal papers before issue assignment; keeping them means they
# are not lost if IEEE never re-inserts the final version. Remove to be strict.
IEEE_TYPES = {'Conferences', 'Journals', 'Early Access Articles'}
# Paper: Springer "Conference Paper, Research Article". Filtered via genre
# instead, because corpus paper [45] is a "Chapter" in a contributed volume.
SPRINGER_TYPES = {'Article', 'Chapter', 'Chapter ConferencePaper'}
# Springer facets: disciplines AND subjects (OR within each), see Appendix A URL
SPRINGER_DISCIPLINES = {'Computer Science', 'Engineering'}
SPRINGER_SUBJECTS = {'Interaction Design', 'Virtual and Augmented Reality', 'Human-Machine Interfaces',
                     'Wearable Technology', 'User Interfaces and Human Computer Interaction',
                     'Mobile Computing', 'Assistive Navigation Technologies for Visually Impaired Users'}


def field_matches(value):
    """True if the text contains a search term, or both 'wearable(s)' and 'ear'.

    The paper's query checks 'wearable AND ear' within one field. It is checked
    across title + abstract + keywords here: a slightly larger superset that makes
    up for the ACM author keywords OpenAlex lacks (corpus paper [101] has 'ear'
    only in the title and 'wearable' only in the abstract).
    """
    text = re.sub('[‐-―]', '-', value.lower())  # typographic hyphens -> '-'
    return bool(TERM_RE.search(text) or
                (re.search(r'\bwearables?\b', text) and re.search(r'\bear\b', text)))


def exclusion_reason(row):
    """'' if the paper passes all rules, otherwise the first rule it fails."""
    if not field_matches(f'{row.title} \n {row.abstract} \n {row.keywords}'):
        return 'no search term'
    if row.language and row.language != 'en':
        return 'language'
    if row.source == 'ACM-DL' and row.type not in ACM_TYPES:
        return 'content type'
    if row.source == 'IEEE-X' and row.type not in IEEE_TYPES:
        return 'content type'
    if row.source == 'SpringerLink':
        content, _, genre = row.type.partition(' | ')
        if content not in SPRINGER_TYPES or not genre.startswith('OriginalPaper'):
            return 'content type'
        subjects = {s.strip() for s in row.subjects.split(',')}
        if not subjects & SPRINGER_DISCIPLINES or not subjects & SPRINGER_SUBJECTS:
            return 'springer subject'
    return ''


def apply_filter(df):
    return df.assign(excluded=df.apply(exclusion_reason, axis=1))


# --- 1.3 dedupe: corpus and earlier runs ------------------------------------

BIBTEX_PATH = 'datasets/bibtexs.bib'
SEEN_PATH = 'datasets/candidates/seen.csv'
# decision: '' = not decided yet, later 'accepted' / 'rejected' (step 1.5)
SEEN_COLUMNS = ['doi', 'title', 'source', 'first_seen', 'decision']
# Corpus titles are at most 0.69 similar to each other, so 0.85 means
# "same paper, other version" (poster vs. full paper, journal extension, ...)
SIMILAR_TITLE = 0.85
DOI_RE = re.compile(r'10\.\d{4,9}/[^\s{}"]+')


def norm_title(title):
    t = re.sub(r'[{}\\]', '', title.lower())
    t = re.sub(r'^(poster|demo|wip|work in progress|late[- ]breaking work)\s*:\s*', '', t)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t).split())


def load_corpus(path=BIBTEX_PATH):
    """{study ID: (doi, normalised title)}. Some entries only have the DOI in their url."""
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    corpus = {}
    for study_id, body in re.findall(r'@\w+\{(\d+)_[^,]*,(.*?)\n\}', raw, re.S):
        fields = {k.lower(): v for k, v in re.findall(r'^\s*(\w+)\s*=\s*\{(.*)\}\s*,?\s*$', body, re.M)}
        doi = DOI_RE.search(fields.get('doi') or fields.get('url', ''))
        corpus[study_id] = (doi.group(0).lower() if doi else '', norm_title(fields.get('title', '')))
    return corpus


def load_seen(path=SEEN_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=SEEN_COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def apply_dedupe(df, corpus, seen):
    """Mark papers already in EarXplore or seen before; flag near-identical corpus titles."""
    corpus_dois = {doi for doi, _ in corpus.values()} - {''}
    corpus_titles = {title for _, title in corpus.values()} - {''}
    seen_dois = set(seen.doi) - {''}
    seen_titles = set(seen.title.map(norm_title)) - {''}

    def reason(row):
        title = norm_title(row.title)
        if row.excluded:
            return row.excluded
        if row.doi in corpus_dois or title in corpus_titles:
            return 'in corpus'
        if row.doi in seen_dois or title in seen_titles:
            return 'already seen'
        return ''

    def similar_to(row):
        title = norm_title(row.title)
        if row.excluded or not title:
            return ''
        score, study_id = max((difflib.SequenceMatcher(None, title, t).ratio(), i)
                              for i, (_, t) in corpus.items())
        return f'ID {study_id} ({score:.2f})' if score >= SIMILAR_TITLE else ''

    df = df.assign(excluded=df.apply(reason, axis=1))
    return df.assign(similar_to=df.apply(similar_to, axis=1))


def update_seen(kept, path=SEEN_PATH):
    """Remember this run's candidates so the next (overlapping) run skips them."""
    new = kept[['doi', 'title', 'source']].assign(first_seen=str(dt.date.today()), decision='')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.concat([load_seen(path), new])[SEEN_COLUMNS].to_csv(path, index=False)


def selfcheck():
    w = {'doi': 'https://doi.org/10.1145/3706598.3714133', 'title': 'BudsID',
         'abstract_inverted_index': {'Finger': [0], 'input': [2], 'identification': [1]},
         'primary_location': {'source': None}}
    row = from_openalex(w)
    assert row['doi'] == '10.1145/3706598.3714133'
    assert row['abstract'] == 'Finger identification input'
    assert row['venue'] == ''

    a = {'doi': '10.1109/X', 'index_terms': {'author_terms': {'terms': ['Earables']},
                                             'ieee_terms': {'terms': ['Ear', 'Sensors']}}}
    assert from_ieee(a)['keywords'] == 'Earables, Ear, Sensors'
    assert from_ieee({})['keywords'] == ''

    r = {'doi': '10.1007/Y', 'abstract': {'h1': 'Abstract', 'p': ['First.', 'Second.']},
         'url': [{'format': 'html', 'value': 'https://link.springer.com/Y'}],
         'subjects': ['Computer Science'], 'sntsubjects': [{'id': '1', 'term': 'Mobile Computing'}]}
    assert from_springer(r)['abstract'] == 'First. Second.'
    assert from_springer(r)['subjects'] == 'Computer Science, Mobile Computing'
    assert from_springer(r)['url'] == 'https://link.springer.com/Y'
    assert from_springer({'contentType': 'Article', 'genre': ['OriginalPaper', 'Research']})['type'] == \
        'Article | OriginalPaper Research'

    assert field_matches('Tap gestures on EARBUDS')
    assert field_matches('an ear‑worn device')            # non-breaking hyphen
    assert field_matches('a wearable sensor behind the ear')
    assert not field_matches('wearable sensors for the eye')  # 'ear' missing
    assert not field_matches('a linear model in recent years')
    assert not field_matches('Did you hear that?')            # OpenAlex stemming noise

    def row(**kw):
        base = dict(source='IEEE-X', title='Earable input', abstract='', keywords='',
                    type='Conferences', language='', subjects='')
        return pd.Series({**base, **kw})
    assert exclusion_reason(row()) == ''
    assert exclusion_reason(row(title='Can you ear me?', abstract='a wearable')) == ''  # across fields
    assert exclusion_reason(row(title='Wearable', abstract='on the eye')) == 'no search term'
    assert exclusion_reason(row(type='Magazines')) == 'content type'
    assert exclusion_reason(row(source='ACM-DL', type='conference-abstract')) == 'content type'
    assert exclusion_reason(row(source='ACM-DL', type='article', language='fr')) == 'language'
    springer = dict(source='SpringerLink', type='Chapter | OriginalPaper Contributed volume')
    assert exclusion_reason(row(**springer, subjects='Engineering, Wearable Technology')) == ''
    assert exclusion_reason(row(**springer, subjects='Medicine, Wearable Technology')) == 'springer subject'
    assert exclusion_reason(row(**springer, subjects='Computer Science, Artificial Intelligence')) == 'springer subject'
    assert exclusion_reason(row(source='SpringerLink', type='Chapter ReferenceWorkEntry | ReferenceWork',
                                subjects='Engineering, Wearable Technology')) == 'content type'

    assert norm_title('Poster: {EarX}: Ear-Based Input!') == 'earx ear based input'
    corpus = {'7': ('10.1145/a', 'earx ear based input'), '8': ('', 'tap control for headphones')}
    assert load_corpus()['136'][0] == '10.1007/978-3-032-12392-3_23'  # DOI taken from url
    seen = pd.DataFrame({'doi': ['10.1109/s'], 'title': ['Old one'], 'source': [''],
                         'first_seen': [''], 'decision': ['']})
    df = pd.DataFrame({'doi': ['10.1145/a', '', '10.1109/s', '10.1/new', '10.1/v', '10.1/x'],
                       'title': ['EarX', 'Tap Control for Headphones', 'x', 'New paper',
                                 'Poster: EarX: Ear based input.', 'y'],
                       'excluded': ['', '', '', '', '', 'no search term']})
    out = apply_dedupe(df, corpus, seen)
    assert list(out.excluded) == ['in corpus', 'in corpus', 'already seen', '', 'in corpus', 'no search term']
    df.loc[4, 'title'] = 'EarX: Ear-based inputs'  # other version, other DOI
    out = apply_dedupe(df, corpus, seen)
    assert out.excluded[4] == '' and out.similar_to[4] == 'ID 7 (0.98)'
    assert out.similar_to[3] == ''
    print('self-check ok')


if __name__ == '__main__':
    today = dt.date.today()
    parser = argparse.ArgumentParser()
    # 30 days overlap by default: databases index late, duplicates are removed later
    parser.add_argument('--since', default=str(today - dt.timedelta(days=30)))
    parser.add_argument('--until', default=str(today))
    # e.g. a backfill without Springer, whose free full-text search returns ~14,000 hits for 2022-2026
    parser.add_argument('--sources', default=','.join(SOURCES), help=f'comma-separated subset of {list(SOURCES)}')
    parser.add_argument('--out', default='candidates.csv')
    parser.add_argument('--input', help='filter an existing raw CSV instead of querying the APIs')
    parser.add_argument('--raw', help='also save the unfiltered search results here')
    parser.add_argument('--rejected', help='also save the dropped papers with their reason here')
    parser.add_argument('--seen', default=SEEN_PATH, help='papers shown in earlier runs')
    parser.add_argument('--update-seen', action='store_true', help='add this run\'s candidates to --seen')
    parser.add_argument('--selfcheck', action='store_true')
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        raise SystemExit

    if args.input:
        raw = pd.read_csv(args.input, dtype=str, keep_default_na=False).reindex(columns=COLUMNS, fill_value='')
    else:
        raw = search_all(args.since, args.until, args.sources.split(','))
        if args.raw:
            raw.to_csv(args.raw, index=False)

    result = apply_dedupe(apply_filter(raw), load_corpus(), load_seen(args.seen))
    kept = result[result.excluded == '']
    print(pd.crosstab(result.source, result.excluded.replace('', 'KEPT')).to_string(), file=sys.stderr)
    kept.drop(columns='excluded').to_csv(args.out, index=False)
    if args.rejected:
        result[result.excluded != ''].to_csv(args.rejected, index=False)
    if args.update_seen:
        update_seen(kept, args.seen)
    print(f'{len(kept)} of {len(raw)} papers kept, written to {args.out}', file=sys.stderr)
