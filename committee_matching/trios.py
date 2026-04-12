from __future__ import annotations

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


def fetch(url: str, timeout: int = 20) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


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


def _empty_result(status: str, matched_url: str = '', error: str = '') -> Dict[str, object]:
    payload: Dict[str, object] = {
        'status': status,
        'matched_url': matched_url,
        'research_topics': [],
        'research_fields': [],
        'research_keywords': [],
        'papers': [],
    }
    if error:
        payload['error'] = error
    return payload


def enrich_teacher_from_trios(name: str, base_url: str, cache_dir: str | Path, trios_url: str = '') -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f'{slugify(name)}.html'

    try:
        if os.environ.get('TRIOS_DISABLE_FETCH', '') == '1':
            if cache_path.exists():
                parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding='utf-8'))
                return {'status': 'cache_only', 'matched_url': trios_url, **parsed}
            return _empty_result('disabled', trios_url)
        if trios_url:
            html = fetch(trios_url)
            cache_path.write_text(html, encoding='utf-8')
            parsed = extract_topics_and_papers_from_html(html)
            return {
                'status': 'ok_direct_url',
                'matched_url': trios_url,
                **parsed,
            }

        candidates = search_candidates(base_url, name)
        best = choose_best(name, candidates)
        if not best:
            return _empty_result('not_found')

        time.sleep(0.15)
        html = fetch(best['url'])
        cache_path.write_text(html, encoding='utf-8')
        parsed = extract_topics_and_papers_from_html(html)
        return {
            'status': 'ok',
            'matched_url': best['url'],
            'matched_display_name': best['display_name'],
            **parsed,
        }
    except Exception as exc:
        if cache_path.exists():
            parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding='utf-8'))
            return {
                'status': 'cache_fallback',
                'matched_url': trios_url,
                'error': str(exc),
                **parsed,
            }
        return _empty_result('error', trios_url, str(exc))