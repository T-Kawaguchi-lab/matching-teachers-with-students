from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .utils import normalize_text, slugify


DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; thesis-committee-matcher/1.0)'
}


def _find_dd_by_dt(soup: BeautifulSoup, dt_text: str):
    dt = soup.find('dt', string=lambda s: s and s.strip() == dt_text)
    if not dt:
        return None
    return dt.find_next_sibling('dd')


def extract_topics_and_papers_from_html(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, 'lxml')
    topics: List[str] = []
    papers: List[str] = []

    dd_topics = _find_dd_by_dt(soup, '研究課題')
    if dd_topics:
        for tr in dd_topics.select('table tbody tr'):
            tds = tr.find_all('td', recursive=False)
            if not tds:
                continue
            title = tds[0].get_text(' ', strip=True)
            if title and 'さらに表示' not in title:
                topics.append(normalize_text(title))

    dd_papers = _find_dd_by_dt(soup, '論文')
    if dd_papers:
        for li in dd_papers.select('ul > li'):
            bold = li.find('b')
            if not bold:
                continue
            title = bold.get_text(' ', strip=True)
            if title and 'さらに表示' not in title:
                papers.append(normalize_text(title))

    return {
        'research_topics': topics,
        'papers': papers,
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


def enrich_teacher_from_trios(name: str, base_url: str, cache_dir: str | Path, trios_url: str = '') -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f'{slugify(name)}.html'

    try:
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
            return {'status': 'not_found', 'matched_url': '', 'research_topics': [], 'papers': []}

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
        return {
            'status': 'error',
            'matched_url': trios_url,
            'error': str(exc),
            'research_topics': [],
            'papers': [],
        }
