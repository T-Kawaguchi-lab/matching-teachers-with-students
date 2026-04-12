from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .utils import normalize_text, slugify, unique_keep_order


DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; thesis-committee-matcher/1.0)'
}
DEFAULT_RESEARCHMAP_BASE_URL = 'https://researchmap.jp'
DEFAULT_RESEARCHMAP_API_URL = 'https://api.researchmap.jp'
REQUEST_TIMEOUT = 20


def _iter_dt_dd_pairs(soup: BeautifulSoup) -> Iterable[Tuple[str, object]]:
    for dt in soup.find_all('dt'):
        dd = dt.find_next_sibling('dd')
        if not dd:
            continue
        label = normalize_text(dt.get_text(' ', strip=True))
        if not label:
            continue
        yield label, dd


def _find_first_dd(soup: BeautifulSoup, patterns: Iterable[str]):
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    for label, dd in _iter_dt_dd_pairs(soup):
        if any(p.search(label) for p in compiled):
            return dd
    return None


def _find_all_dds(soup: BeautifulSoup, patterns: Iterable[str]) -> List[object]:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    matched = []
    for label, dd in _iter_dt_dd_pairs(soup):
        if any(p.search(label) for p in compiled):
            matched.append(dd)
    return matched


def _clean_item(text: object) -> str:
    cleaned = normalize_text(text)
    lowered = cleaned.lower()
    if not cleaned:
        return ''
    if 'さらに表示' in cleaned or lowered == 'more...' or lowered.endswith(' more...'):
        return ''
    return cleaned


def _extract_lines_from_dd(dd) -> List[str]:
    items: List[str] = []

    rows = dd.select('table tbody tr') or dd.select('table tr')
    if rows:
        for tr in rows:
            tds = tr.find_all('td', recursive=False)
            if not tds:
                continue
            title = _clean_item(tds[0].get_text(' ', strip=True))
            if title:
                items.append(title)
        return unique_keep_order(items)

    list_items = dd.select('ul > li')
    if list_items:
        for li in list_items:
            bold = li.find('b')
            if bold:
                title = _clean_item(bold.get_text(' ', strip=True))
            else:
                strings = [_clean_item(s) for s in li.stripped_strings]
                strings = [s for s in strings if s]
                title = strings[0] if strings else ''
            if title:
                items.append(title)
        return unique_keep_order(items)

    for s in dd.stripped_strings:
        item = _clean_item(s)
        if item:
            items.append(item)
    return unique_keep_order(items)


def extract_topics_and_papers_from_html(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, 'lxml')

    topics_dd = _find_first_dd(soup, [r'^研究課題$', r'^Research projects?$'])
    research_fields_dd = _find_first_dd(soup, [r'^研究分野$', r'^Research fields?$'])
    research_keywords_dd = _find_first_dd(soup, [r'^研究キーワード$', r'^Research keywords?$'])

    topics = _extract_lines_from_dd(topics_dd) if topics_dd else []
    research_fields = _extract_lines_from_dd(research_fields_dd) if research_fields_dd else []
    research_keywords = _extract_lines_from_dd(research_keywords_dd) if research_keywords_dd else []

    paper_sections = _find_all_dds(
        soup,
        [
            r'論文',
            r'paper',
            r'articles?',
        ],
    )
    papers: List[str] = []
    for dd in paper_sections:
        papers.extend(_extract_lines_from_dd(dd))

    return {
        'research_topics': unique_keep_order(topics),
        'research_fields': unique_keep_order(research_fields),
        'research_keywords': unique_keep_order(research_keywords),
        'papers': unique_keep_order(papers),
    }


def fetch(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    params: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> str:
    client = session or requests
    response = client.get(url, headers=DEFAULT_HEADERS, timeout=timeout, params=params, allow_redirects=True)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def fetch_json(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    params: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, object]:
    client = session or requests
    response = client.get(
        url,
        headers={**DEFAULT_HEADERS, 'Accept': 'application/ld+json, application/json;q=0.9, */*;q=0.1'},
        timeout=timeout,
        params=params,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def search_candidates(base_url: str, name: str, per: int = 50) -> List[Dict[str, str]]:
    quoted = urllib.parse.quote(name)
    url = f'{base_url}/ja/researchers?q={quoted}&per={per}'
    html = fetch(url)
    soup = BeautifulSoup(html, 'lxml')

    candidates: List[Dict[str, str]] = []
    for link in soup.select('a[href*="/researcher/"], a[href*="/researchers/"]'):
        href = link.get('href')
        label = link.get_text(' ', strip=True)
        if not href or not label:
            continue
        if not re.search(r'/\d{6,}', href):
            continue
        candidates.append({
            'display_name': normalize_text(label),
            'url': urllib.parse.urljoin(base_url, href),
        })

    dedup: List[Dict[str, str]] = []
    seen = set()
    for row in candidates:
        if row['url'] in seen:
            continue
        seen.add(row['url'])
        dedup.append(row)
    return dedup


def choose_best(name: str, candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    target = re.sub(r'\s+', '', normalize_text(name))
    for row in candidates:
        label = re.sub(r'\s+', '', normalize_text(row.get('display_name')))
        if label == target or label.startswith(target):
            return row
    return candidates[0] if candidates else None


def _empty_result(status: str, matched_url: str = '', error: str = '', source: str = '') -> Dict[str, object]:
    payload: Dict[str, object] = {
        'status': status,
        'matched_url': matched_url,
        'profile_source': source,
        'research_topics': [],
        'research_fields': [],
        'research_keywords': [],
        'papers': [],
    }
    if error:
        payload['error'] = error
    return payload


def _has_profile_data(payload: Dict[str, object]) -> bool:
    for key in ('research_topics', 'research_fields', 'research_keywords', 'papers'):
        values = payload.get(key, []) or []
        if isinstance(values, list) and any(normalize_text(v) for v in values):
            return True
    return False


def _localized_text(value: object) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        for item in value:
            text = _localized_text(item)
            if text:
                return text
        return ''
    if isinstance(value, dict):
        for key in ('ja', 'en', 'name', 'label', 'text', 'title', 'value'):
            if key in value:
                text = _localized_text(value.get(key))
                if text:
                    return text
        return ''
    return normalize_text(value)


def _extract_researchmap_permalink(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc and 'researchmap.jp' not in parsed.netloc:
        return ''
    path = parsed.path.strip('/')
    if not path:
        return ''
    first = path.split('/')[0].strip()
    if not first:
        return ''
    if first in {'researchers', 'public', 'login', 'logout', 'communities', 'support', 'about', 'faq', 'en', 'ja'}:
        return ''
    if first.startswith('@'):
        first = first[1:]
    if not re.match(r'^[A-Za-z0-9._\-]+$', first):
        return ''
    return first


def _parse_researchmap_candidates_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, 'lxml')
    candidates: List[Dict[str, str]] = []

    for link in soup.select('a[href]'):
        href = normalize_text(link.get('href'))
        label = normalize_text(link.get_text(' ', strip=True))
        if not href or not label:
            continue
        url = urllib.parse.urljoin(base_url, href)
        permalink = _extract_researchmap_permalink(url)
        if not permalink:
            continue
        if label in {'一致した業績を検索', 'researchmap', 'Researcher Search', '研究者をさがす'}:
            continue
        candidates.append({
            'display_name': label,
            'url': url,
            'permalink': permalink,
        })

    dedup: List[Dict[str, str]] = []
    seen = set()
    for row in candidates:
        key = row['url']
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    return dedup


def _build_researchmap_search_param_candidates(session: requests.Session, base_url: str, name: str) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    search_url = f'{base_url.rstrip("/")}/researchers/'
    try:
        landing_html = fetch(search_url, session=session, params={'lang': 'ja'})
        soup = BeautifulSoup(landing_html, 'lxml')
        for form in soup.find_all('form'):
            action = normalize_text(form.get('action'))
            if action and 'researchers' not in action:
                continue
            hidden_params: Dict[str, str] = {}
            for inp in form.select('input[name]'):
                name_attr = normalize_text(inp.get('name'))
                if not name_attr:
                    continue
                input_type = normalize_text(inp.get('type')).lower()
                if input_type == 'hidden':
                    hidden_params[name_attr] = normalize_text(inp.get('value'))
            for field_name in ['name', 'q', 'query', 'search', 'researcher_name', 'full_name']:
                params = dict(hidden_params)
                params[field_name] = name
                params.setdefault('op', 'search')
                params.setdefault('lang', 'ja')
                candidates.append(params)
    except Exception:
        pass

    candidates.extend(
        [
            {'name': name, 'op': 'search', 'lang': 'ja'},
            {'q': name, 'op': 'search', 'lang': 'ja'},
            {'query': name, 'op': 'search', 'lang': 'ja'},
            {'search': name, 'op': 'search', 'lang': 'ja'},
            {'name': name, 'lang': 'ja'},
            {'q': name, 'lang': 'ja'},
        ]
    )

    dedup: List[Dict[str, str]] = []
    seen = set()
    for params in candidates:
        key = tuple(sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(params)
    return dedup


def search_researchmap_candidates(base_url: str, name: str) -> Tuple[List[Dict[str, str]], str]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    search_url = f'{base_url.rstrip("/")}/researchers/'

    param_candidates = _build_researchmap_search_param_candidates(session, base_url, name)
    all_candidates: List[Dict[str, str]] = []
    last_html = ''

    for params in param_candidates:
        try:
            html = fetch(search_url, params=params, session=session)
            last_html = html
            parsed = _parse_researchmap_candidates_from_html(html, base_url)
            if parsed:
                all_candidates.extend(parsed)
                if len(parsed) >= 3:
                    break
        except Exception:
            continue

    dedup: List[Dict[str, str]] = []
    seen = set()
    for row in all_candidates:
        key = row['url']
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    return dedup, last_html


def choose_best_researchmap(name: str, candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not candidates:
        return None

    target = re.sub(r'\s+', '', normalize_text(name)).lower()
    best_row: Optional[Dict[str, str]] = None
    best_score = -1

    for row in candidates:
        label = re.sub(r'\s+', '', normalize_text(row.get('display_name'))).lower()
        if not label:
            continue
        score = 0
        if label == target:
            score = 100
        elif label.startswith(target) or target.startswith(label):
            score = 90
        elif target in label or label in target:
            score = 80
        elif label[:2] and label[:2] in target:
            score = 60
        if score > best_score:
            best_score = score
            best_row = row

    return best_row or candidates[0]


def _items_from_graph_node(node: Dict[str, object]) -> List[Dict[str, object]]:
    items = node.get('items', [])
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def extract_profile_from_researchmap_json(payload: Dict[str, object]) -> Dict[str, List[str]]:
    research_topics: List[str] = []
    research_fields: List[str] = []
    research_keywords: List[str] = []
    papers: List[str] = []

    graph = payload.get('@graph', [])
    if not isinstance(graph, list):
        graph = []

    for node in graph:
        if not isinstance(node, dict):
            continue
        node_type = normalize_text(node.get('@type') or '')
        lower_type = node_type.lower()
        items = _items_from_graph_node(node)

        if 'research_areas' in lower_type:
            for item in items:
                discipline = _localized_text(item.get('discipline'))
                field = _localized_text(item.get('research_field'))
                if field:
                    research_fields.append(field)
                if discipline:
                    research_fields.append(discipline)
            continue

        if 'research_interest' in lower_type:
            for item in items:
                keyword = _localized_text(
                    item.get('research_interest')
                    or item.get('research_keyword')
                    or item.get('keyword')
                    or item.get('title')
                    or item.get('name')
                )
                if keyword:
                    research_keywords.append(keyword)
            continue

        if 'research_project' in lower_type:
            for item in items:
                title = _localized_text(
                    item.get('research_project_title')
                    or item.get('project_title')
                    or item.get('title')
                    or item.get('name')
                )
                if title:
                    research_topics.append(title)
            continue

        if 'paper' in lower_type:
            for item in items:
                title = _localized_text(
                    item.get('paper_title')
                    or item.get('article_title')
                    or item.get('title')
                    or item.get('name')
                )
                if title:
                    papers.append(title)
            continue

    return {
        'research_topics': unique_keep_order(research_topics),
        'research_fields': unique_keep_order(research_fields),
        'research_keywords': unique_keep_order(research_keywords),
        'papers': unique_keep_order(papers),
    }


def _fallback_extract_research_projects_from_html(html: str) -> List[str]:
    soup = BeautifulSoup(html, 'lxml')
    matched_dds = _find_all_dds(soup, [r'研究課題'])
    topics: List[str] = []
    for dd in matched_dds:
        topics.extend(_extract_lines_from_dd(dd))
    return unique_keep_order(topics)


def enrich_teacher_from_researchmap(name: str, cache_dir: str | Path) -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    search_cache_path = cache_dir / f'{slugify(name)}__researchmap_search.html'
    json_cache_path = cache_dir / f'{slugify(name)}__researchmap.json'
    profile_cache_path = cache_dir / f'{slugify(name)}__researchmap_profile.html'

    try:
        candidates, last_search_html = search_researchmap_candidates(DEFAULT_RESEARCHMAP_BASE_URL, name)
        if last_search_html:
            search_cache_path.write_text(last_search_html, encoding='utf-8')

        best = choose_best_researchmap(name, candidates)
        if not best:
            return _empty_result('researchmap_not_found', source='researchmap')

        permalink = normalize_text(best.get('permalink')) or _extract_researchmap_permalink(best.get('url', ''))
        if not permalink:
            return _empty_result('researchmap_permalink_not_found', matched_url=best.get('url', ''), source='researchmap')

        api_url = f'{DEFAULT_RESEARCHMAP_API_URL.rstrip("/")}/{permalink}'
        time.sleep(0.15)
        payload = fetch_json(api_url, params={'format': 'json'})
        json_cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        parsed = extract_profile_from_researchmap_json(payload)

        if not parsed['research_topics']:
            try:
                profile_html = fetch(best['url'])
                profile_cache_path.write_text(profile_html, encoding='utf-8')
                parsed['research_topics'] = unique_keep_order(
                    parsed['research_topics'] + _fallback_extract_research_projects_from_html(profile_html)
                )
            except Exception:
                pass

        return {
            'status': 'ok_researchmap_fallback',
            'matched_url': best['url'],
            'matched_display_name': best.get('display_name', ''),
            'profile_source': 'researchmap',
            **parsed,
        }
    except Exception as exc:
        if json_cache_path.exists():
            try:
                payload = json.loads(json_cache_path.read_text(encoding='utf-8'))
                parsed = extract_profile_from_researchmap_json(payload)
                return {
                    'status': 'researchmap_cache_fallback',
                    'matched_url': '',
                    'profile_source': 'researchmap',
                    'error': str(exc),
                    **parsed,
                }
            except Exception:
                pass
        if profile_cache_path.exists():
            try:
                cached_html = profile_cache_path.read_text(encoding='utf-8')
                parsed = extract_topics_and_papers_from_html(cached_html)
                parsed['research_topics'] = unique_keep_order(
                    parsed.get('research_topics', []) + _fallback_extract_research_projects_from_html(cached_html)
                )
                return {
                    'status': 'researchmap_html_cache_fallback',
                    'matched_url': '',
                    'profile_source': 'researchmap',
                    'error': str(exc),
                    **parsed,
                }
            except Exception:
                pass
        return _empty_result('researchmap_error', error=str(exc), source='researchmap')


def enrich_teacher_from_trios(name: str, base_url: str, cache_dir: str | Path, trios_url: str = '') -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f'{slugify(name)}.html'

    try:
        if os.environ.get('TRIOS_DISABLE_FETCH', '') == '1':
            if cache_path.exists():
                parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding='utf-8'))
                if _has_profile_data(parsed):
                    return {'status': 'cache_only', 'matched_url': trios_url, 'profile_source': 'trios', **parsed}
            return enrich_teacher_from_researchmap(name, cache_dir)

        if trios_url:
            html = fetch(trios_url)
            cache_path.write_text(html, encoding='utf-8')
            parsed = extract_topics_and_papers_from_html(html)
            if _has_profile_data(parsed):
                return {
                    'status': 'ok_direct_url',
                    'matched_url': trios_url,
                    'profile_source': 'trios',
                    **parsed,
                }
            return enrich_teacher_from_researchmap(name, cache_dir)

        candidates = search_candidates(base_url, name)
        best = choose_best(name, candidates)
        if best:
            time.sleep(0.15)
            html = fetch(best['url'])
            cache_path.write_text(html, encoding='utf-8')
            parsed = extract_topics_and_papers_from_html(html)
            if _has_profile_data(parsed):
                return {
                    'status': 'ok',
                    'matched_url': best['url'],
                    'matched_display_name': best['display_name'],
                    'profile_source': 'trios',
                    **parsed,
                }

        return enrich_teacher_from_researchmap(name, cache_dir)
    except Exception as exc:
        if cache_path.exists():
            parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding='utf-8'))
            if _has_profile_data(parsed):
                return {
                    'status': 'cache_fallback',
                    'matched_url': trios_url,
                    'profile_source': 'trios',
                    'error': str(exc),
                    **parsed,
                }
        fallback = enrich_teacher_from_researchmap(name, cache_dir)
        if _has_profile_data(fallback):
            fallback['error'] = str(exc)
            return fallback
        return _empty_result('error', trios_url, str(exc), source='trios')