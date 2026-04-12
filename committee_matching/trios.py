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
    "User-Agent": "Mozilla/5.0 (compatible; thesis-committee-matcher/1.0)"
}
DEFAULT_RESEARCHMAP_BASE_URL = "https://researchmap.jp"
DEFAULT_RESEARCHMAP_API_URL = "https://api.researchmap.jp"
REQUEST_TIMEOUT = 20

RESEARCHMAP_RESERVED_SEGMENTS = {
    "",
    "researchers",
    "public",
    "login",
    "logout",
    "settings",
    "about",
    "faq",
    "manual",
    "help",
    "communities",
    "search",
    "advanced_search",
    "new",
    "ja",
    "en",
}

RESEARCHMAP_SUBPAGE_SUFFIXES = {
    "research_projects": "research_topics",
    "published_papers": "papers",
    "research_areas": "research_fields",
    "research_interests": "research_keywords",
}


def fetch_response(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    params: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    client = session or requests
    response = client.get(
        url,
        headers=DEFAULT_HEADERS,
        timeout=timeout,
        params=params,
        allow_redirects=True,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response


def fetch(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    params: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> str:
    return fetch_response(url, timeout=timeout, params=params, session=session).text


def fetch_json(
    url: str,
    timeout: int = REQUEST_TIMEOUT,
    params: Optional[Dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, object]:
    client = session or requests
    response = client.get(
        url,
        headers={
            **DEFAULT_HEADERS,
            "Accept": "application/ld+json, application/json;q=0.9, */*;q=0.1",
        },
        timeout=timeout,
        params=params,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def _iter_dt_dd_pairs(soup: BeautifulSoup) -> Iterable[Tuple[str, object]]:
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        label = normalize_text(dt.get_text(" ", strip=True))
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
        return ""
    if "さらに表示" in cleaned or lowered == "more..." or lowered.endswith(" more..."):
        return ""
    if cleaned in {"マイポータルへ", "My portal", "researchmap"}:
        return ""
    return cleaned


def _looks_like_section_heading(text: str) -> bool:
    value = normalize_text(text)
    if not value:
        return False

    heading_patterns = [
        r"^基本情報$",
        r"^所属$",
        r"^経歴$",
        r"^学歴$",
        r"^受賞$",
        r"^委員歴$",
        r"^論文$",
        r"^MISC$",
        r"^書籍等出版物$",
        r"^講演・口頭発表等$",
        r"^担当経験のある科目",
        r"^所属学協会$",
        r"^社会貢献活動$",
        r"^研究分野$",
        r"^研究キーワード$",
        r".*研究課題$",
        r"^Research fields?$",
        r"^Research keywords?$",
        r"^Research interests?$",
        r"^Research projects?$",
    ]
    return any(re.search(p, value, re.IGNORECASE) for p in heading_patterns)


def _extract_lines_from_dd(dd) -> List[str]:
    items: List[str] = []

    rows = dd.select("table tbody tr") or dd.select("table tr")
    if rows:
        for tr in rows:
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            title = _clean_item(tds[0].get_text(" ", strip=True))
            if title:
                items.append(title)
        return unique_keep_order(items)

    list_items = dd.select("ul > li")
    if list_items:
        for li in list_items:
            bold = li.find(["b", "strong", "a"])
            if bold:
                title = _clean_item(bold.get_text(" ", strip=True))
            else:
                strings = [_clean_item(s) for s in li.stripped_strings]
                strings = [s for s in strings if s]
                title = strings[0] if strings else ""
            if title:
                items.append(title)
        return unique_keep_order(items)

    for s in dd.stripped_strings:
        item = _clean_item(s)
        if item:
            items.append(item)
    return unique_keep_order(items)


def _extract_lines_from_container(node) -> List[str]:
    if node is None:
        return []

    rows = node.select("table tbody tr") or node.select("table tr")
    if rows:
        items: List[str] = []
        for tr in rows:
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            title = _clean_item(tds[0].get_text(" ", strip=True))
            if title:
                items.append(title)
        return unique_keep_order(items)

    list_items = node.select("ul > li") or node.select("ol > li")
    if list_items:
        items: List[str] = []
        for li in list_items:
            bold = li.find(["b", "strong", "a"])
            if bold:
                title = _clean_item(bold.get_text(" ", strip=True))
            else:
                strings = [_clean_item(s) for s in li.stripped_strings]
                strings = [s for s in strings if s]
                title = strings[0] if strings else ""
            if title:
                items.append(title)
        return unique_keep_order(items)

    items: List[str] = []
    for s in node.stripped_strings:
        item = _clean_item(s)
        if not item:
            continue
        if _looks_like_section_heading(item):
            continue
        items.append(item)
    return unique_keep_order(items)


def _iter_heading_blocks(soup: BeautifulSoup, patterns: Iterable[str]) -> Iterable[object]:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "div", "span", "p", "th", "a"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if any(p.search(text) for p in compiled):
            yield node


def _extract_by_heading_patterns(html: str, patterns: Iterable[str]) -> List[str]:
    soup = BeautifulSoup(html, "lxml")

    dd = _find_first_dd(soup, patterns)
    if dd is not None:
        dd_items = _extract_lines_from_dd(dd)
        if dd_items:
            return unique_keep_order(dd_items)

    values: List[str] = []
    for heading in _iter_heading_blocks(soup, patterns):
        siblings = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "get_text", None) is None:
                continue
            text = normalize_text(sibling.get_text(" ", strip=True))
            if text and _looks_like_section_heading(text):
                break
            siblings.append(sibling)
            if len(siblings) >= 6:
                break
        for sibling in siblings:
            values.extend(_extract_lines_from_container(sibling))
        if values:
            break

    if values:
        return unique_keep_order(values)

    body_lines: List[str] = []
    started = False
    for line in soup.get_text("\n", strip=True).splitlines():
        line = _clean_item(line)
        if not line:
            continue
        if not started and any(re.search(p, line, re.IGNORECASE) for p in patterns):
            started = True
            continue
        if started:
            if _looks_like_section_heading(line):
                break
            body_lines.append(line)
    return unique_keep_order(body_lines)


def extract_topics_and_papers_from_html(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "lxml")

    topics_dd = _find_first_dd(soup, [r"研究課題", r"^Research projects?$"])
    research_fields_dd = _find_first_dd(soup, [r"^研究分野$", r"^Research fields?$"])
    research_keywords_dd = _find_first_dd(soup, [r"^研究キーワード$", r"^Research keywords?$", r"^Research interests?$"])

    topics = _extract_lines_from_dd(topics_dd) if topics_dd else _extract_by_heading_patterns(html, [r"研究課題", r"^Research projects?$"])
    research_fields = _extract_lines_from_dd(research_fields_dd) if research_fields_dd else _extract_by_heading_patterns(html, [r"^研究分野$", r"^Research fields?$"])
    research_keywords = _extract_lines_from_dd(research_keywords_dd) if research_keywords_dd else _extract_by_heading_patterns(html, [r"^研究キーワード$", r"^Research keywords?$", r"^Research interests?$"])

    paper_sections = _find_all_dds(
        soup,
        [
            r"論文",
            r"paper",
            r"articles?",
        ],
    )
    papers: List[str] = []
    for dd in paper_sections:
        papers.extend(_extract_lines_from_dd(dd))
    if not papers:
        papers = _extract_by_heading_patterns(html, [r"論文", r"paper", r"articles?"])

    return {
        "research_topics": unique_keep_order(topics),
        "research_fields": unique_keep_order(research_fields),
        "research_keywords": unique_keep_order(research_keywords),
        "papers": unique_keep_order(papers),
    }


def search_candidates(base_url: str, name: str, per: int = 50) -> List[Dict[str, str]]:
    quoted = urllib.parse.quote(name)
    url = f"{base_url}/ja/researchers?q={quoted}&per={per}"
    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    candidates: List[Dict[str, str]] = []
    for link in soup.select('a[href*="/researcher/"], a[href*="/researchers/"]'):
        href = link.get("href")
        label = link.get_text(" ", strip=True)
        if not href or not label:
            continue
        if not re.search(r"/\d{6,}", href):
            continue
        candidates.append({
            "display_name": normalize_text(label),
            "url": urllib.parse.urljoin(base_url, href),
        })

    dedup: List[Dict[str, str]] = []
    seen = set()
    for row in candidates:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        dedup.append(row)
    return dedup


def _normalize_compact_name(value: object) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"[-‐‑‒–—―ー・･.,，、\s]+", "", text)
    return text


def _clean_display_name(value: object) -> str:
    text = normalize_text(value)
    text = re.sub(r"\s*[-|｜].*researchmap.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[-|｜].*マイポータル.*$", "", text)
    text = re.sub(r"\s*[-|｜].*My portal.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*researchmap\s*$", "", text, flags=re.IGNORECASE)
    return normalize_text(text)


def _extract_researchmap_permalink(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc and "researchmap.jp" not in parsed.netloc:
        return ""
    path = parsed.path.strip("/")
    if not path:
        return ""
    first = path.split("/")[0].strip()
    if not first:
        return ""
    if first.startswith("@"):
        first = first[1:]
    if first.lower() in RESEARCHMAP_RESERVED_SEGMENTS:
        return ""
    if not re.fullmatch(r"[0-9A-Za-z._-]+", first):
        return ""
    return first


def _extract_base_profile_url(url: str) -> str:
    permalink = _extract_researchmap_permalink(url)
    if not permalink:
        return normalize_text(url)
    return f"{DEFAULT_RESEARCHMAP_BASE_URL}/{permalink}"


def _parse_researchmap_candidates_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    candidates: List[Dict[str, str]] = []

    for link in soup.select("a[href]"):
        href = normalize_text(link.get("href"))
        label = _clean_display_name(link.get_text(" ", strip=True))
        if not href:
            continue

        url = urllib.parse.urljoin(base_url, href)
        permalink = _extract_researchmap_permalink(url)
        if not permalink:
            continue

        if label in {"一致した業績を検索", "researchmap", "Researcher Search", "研究者をさがす", "研究者検索"}:
            continue

        profile_url = f"{DEFAULT_RESEARCHMAP_BASE_URL}/{permalink}"
        candidates.append({
            "display_name": label or permalink,
            "url": profile_url,
            "permalink": permalink,
        })

    dedup: List[Dict[str, str]] = []
    seen = set()
    for row in candidates:
        key = row["url"]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    return dedup


def unique_keep_order_candidates(values: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for row in values:
        url = normalize_text(row.get("url", ""))
        if not url or url in seen:
            continue
        seen.add(url)
        payload = dict(row)
        payload["display_name"] = _clean_display_name(payload.get("display_name", ""))
        payload["url"] = url
        payload["permalink"] = normalize_text(payload.get("permalink", "")) or _extract_researchmap_permalink(url)
        out.append(payload)
    return out


def _build_researchmap_query_variants(name: str) -> List[str]:
    text = normalize_text(name)
    compact = _normalize_compact_name(name)
    variants = [text]
    if text.replace(" ", "") != text:
        variants.append(text.replace(" ", ""))
    if " " in text:
        variants.append(text.replace(" ", "　"))
    if compact and compact != text:
        variants.append(compact)
    return unique_keep_order(variants)


def _search_researchmap_via_internal_pages(base_url: str, name: str) -> Tuple[List[Dict[str, str]], str]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    search_urls = [
        f"{base_url.rstrip('/')}/researchers",
        f"{base_url.rstrip('/')}/researchers/",
    ]
    param_sets: List[Dict[str, str]] = []
    for query in _build_researchmap_query_variants(name):
        param_sets.extend(
            [
                {"q": query},
                {"q": query, "lang": "ja"},
                {"name": query, "op": "search"},
                {"name": query, "op": "search", "lang": "ja"},
                {"query": query, "op": "search", "lang": "ja"},
                {"search": query, "lang": "ja"},
                {"researcher_name": query, "lang": "ja"},
            ]
        )

    last_html = ""
    all_candidates: List[Dict[str, str]] = []
    seen_params = set()

    for search_url in search_urls:
        for params in param_sets:
            key = (search_url, tuple(sorted(params.items())))
            if key in seen_params:
                continue
            seen_params.add(key)
            try:
                html = fetch(search_url, params=params, session=session)
            except Exception:
                continue
            last_html = html
            parsed = _parse_researchmap_candidates_from_html(html, base_url)
            if parsed:
                all_candidates.extend(parsed)
                if len(parsed) >= 3:
                    break
        if all_candidates:
            break

    return unique_keep_order_candidates(all_candidates), last_html


def _parse_candidates_from_search_engine_html(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    candidates: List[Dict[str, str]] = []

    for link in soup.select("a[href]"):
        href = normalize_text(link.get("href"))
        label = _clean_display_name(link.get_text(" ", strip=True))
        if not href:
            continue
        if href.startswith("/l/?kh=1&uddg="):
            href = urllib.parse.unquote(href.split("uddg=", 1)[1])

        permalink = _extract_researchmap_permalink(href)
        if not permalink:
            continue

        profile_url = f"{DEFAULT_RESEARCHMAP_BASE_URL}/{permalink}"
        candidates.append({
            "display_name": label or permalink,
            "url": profile_url,
            "permalink": permalink,
        })

    return unique_keep_order_candidates(candidates)


def _search_researchmap_via_duckduckgo(name: str) -> List[Dict[str, str]]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    queries = [
        f'site:researchmap.jp "{normalize_text(name)}" researchmap',
        f"site:researchmap.jp {normalize_text(name)} researchmap",
    ]
    all_candidates: List[Dict[str, str]] = []

    for query in queries:
        try:
            html = fetch("https://duckduckgo.com/html/", params={"q": query}, session=session)
        except Exception:
            continue
        parsed = _parse_candidates_from_search_engine_html(html)
        if parsed:
            all_candidates.extend(parsed)
            break

    return unique_keep_order_candidates(all_candidates)


def search_researchmap_candidates(base_url: str, name: str) -> Tuple[List[Dict[str, str]], str]:
    internal_candidates, last_html = _search_researchmap_via_internal_pages(base_url, name)
    if internal_candidates:
        return internal_candidates, last_html

    ddg_candidates = _search_researchmap_via_duckduckgo(name)
    if ddg_candidates:
        return ddg_candidates, last_html

    return [], last_html


def choose_best(name: str, candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    target = _normalize_compact_name(name)
    best_row: Optional[Dict[str, str]] = None
    best_score = -1

    for row in candidates:
        label = _normalize_compact_name(row.get("display_name"))
        permalink = _normalize_compact_name(row.get("permalink"))
        score = 0
        if label:
            if label == target:
                score = 100
            elif label.startswith(target) or target.startswith(label):
                score = 90
            elif target and target in label:
                score = 80
        if permalink:
            if permalink == target:
                score = max(score, 75)
            elif target and target in permalink:
                score = max(score, 65)
        if score > best_score:
            best_score = score
            best_row = row

    return best_row or (candidates[0] if candidates else None)


def _score_researchmap_candidate(name: str, candidate: Dict[str, str]) -> int:
    target = _normalize_compact_name(name)
    label = _normalize_compact_name(candidate.get("display_name"))
    permalink = normalize_text(candidate.get("permalink", "")).lower()

    score = 0
    if label == target and target:
        score += 1000
    elif label.startswith(target) or target.startswith(label):
        score += 700
    elif target and target in label:
        score += 500

    if normalize_text(candidate.get("display_name", "")):
        score += 50

    if permalink:
        if target and target in permalink:
            score += 30
        if "-" in permalink or "_" in permalink:
            score += 10

    return score


def _rank_researchmap_candidates(name: str, candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
    dedup = unique_keep_order_candidates(candidates)
    return sorted(
        dedup,
        key=lambda row: (
            _score_researchmap_candidate(name, row),
            normalize_text(row.get("display_name", "")),
            normalize_text(row.get("url", "")),
        ),
        reverse=True,
    )


def _empty_result(status: str, matched_url: str = "", error: str = "", source: str = "") -> Dict[str, object]:
    payload: Dict[str, object] = {
        "status": status,
        "matched_url": matched_url,
        "profile_source": source,
        "research_topics": [],
        "research_fields": [],
        "research_keywords": [],
        "papers": [],
    }
    if error:
        payload["error"] = error
    return payload


def _has_profile_data(payload: Dict[str, object]) -> bool:
    for key in ("research_topics", "research_fields", "research_keywords", "papers"):
        values = payload.get(key, []) or []
        if isinstance(values, list) and any(normalize_text(v) for v in values):
            return True
    return False


def _localized_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        for item in value:
            text = _localized_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("ja", "en", "name", "label", "text", "title", "value"):
            if key in value:
                text = _localized_text(value.get(key))
                if text:
                    return text
        return ""
    return normalize_text(value)


def extract_profile_from_researchmap_json(payload: Dict[str, object]) -> Dict[str, List[str]]:
    research_topics: List[str] = []
    research_fields: List[str] = []
    research_keywords: List[str] = []
    papers: List[str] = []

    graph = payload.get("@graph", [])
    if not isinstance(graph, list):
        graph = []

    for node in graph:
        if not isinstance(node, dict):
            continue

        node_type = normalize_text(node.get("@type") or "")
        lower_type = node_type.lower()
        items = node.get("items", []) if isinstance(node.get("items", []), list) else []

        if "research_areas" in lower_type:
            for item in items:
                if not isinstance(item, dict):
                    continue
                discipline = _localized_text(item.get("discipline"))
                field = _localized_text(item.get("research_field"))
                if field:
                    research_fields.append(field)
                if discipline:
                    research_fields.append(discipline)
            continue

        if "research_interest" in lower_type:
            for item in items:
                if not isinstance(item, dict):
                    continue
                keyword = _localized_text(
                    item.get("research_interest")
                    or item.get("research_keyword")
                    or item.get("keyword")
                    or item.get("title")
                    or item.get("name")
                )
                if keyword:
                    research_keywords.append(keyword)
            continue

        if "research_project" in lower_type:
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = _localized_text(
                    item.get("research_project_title")
                    or item.get("project_title")
                    or item.get("title")
                    or item.get("name")
                )
                if title:
                    research_topics.append(title)
            continue

        if "paper" in lower_type:
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = _localized_text(
                    item.get("paper_title")
                    or item.get("article_title")
                    or item.get("title")
                    or item.get("name")
                )
                if title:
                    papers.append(title)
            continue

    return {
        "research_topics": unique_keep_order(research_topics),
        "research_fields": unique_keep_order(research_fields),
        "research_keywords": unique_keep_order(research_keywords),
        "papers": unique_keep_order(papers),
    }


def _fetch_researchmap_subpages(profile_url: str, cache_dir: Path) -> Dict[str, List[str]]:
    collected: Dict[str, List[str]] = {
        "research_topics": [],
        "research_fields": [],
        "research_keywords": [],
        "papers": [],
    }

    profile_url = _extract_base_profile_url(profile_url)
    cache_prefix = slugify(profile_url)

    for suffix, target_key in RESEARCHMAP_SUBPAGE_SUFFIXES.items():
        url = f"{profile_url.rstrip('/')}/{suffix}"
        cache_path = cache_dir / f"{cache_prefix}__{suffix}.html"

        try:
            response = fetch_response(url)
            html = response.text
            cache_path.write_text(html, encoding="utf-8")
        except Exception:
            if cache_path.exists():
                html = cache_path.read_text(encoding="utf-8")
            else:
                continue

        parsed = extract_topics_and_papers_from_html(html)

        if target_key == "research_topics":
            collected[target_key].extend(parsed.get("research_topics", []))
            if not parsed.get("research_topics"):
                collected[target_key].extend(_extract_by_heading_patterns(html, [r"研究課題", r"^Research projects?$"]))
        elif target_key == "research_fields":
            collected[target_key].extend(parsed.get("research_fields", []))
            if not parsed.get("research_fields"):
                collected[target_key].extend(_extract_by_heading_patterns(html, [r"^研究分野$", r"^Research fields?$"]))
        elif target_key == "research_keywords":
            collected[target_key].extend(parsed.get("research_keywords", []))
            if not parsed.get("research_keywords"):
                collected[target_key].extend(_extract_by_heading_patterns(html, [r"^研究キーワード$", r"^Research keywords?$", r"^Research interests?$"]))
        elif target_key == "papers":
            collected[target_key].extend(parsed.get("papers", []))
            if not parsed.get("papers"):
                collected[target_key].extend(_extract_by_heading_patterns(html, [r"論文", r"paper", r"articles?"]))

    return {key: unique_keep_order(values) for key, values in collected.items()}


def _collect_researchmap_profile(candidate: Dict[str, str], cache_dir: Path) -> Dict[str, object]:
    original_profile_url = normalize_text(candidate.get("url", ""))
    original_permalink = normalize_text(candidate.get("permalink", "")) or _extract_researchmap_permalink(original_profile_url)

    if not original_profile_url and original_permalink:
        original_profile_url = f"{DEFAULT_RESEARCHMAP_BASE_URL}/{original_permalink}"

    canonical_profile_url = _extract_base_profile_url(original_profile_url)
    canonical_permalink = _extract_researchmap_permalink(canonical_profile_url) or original_permalink
    cache_key = slugify(canonical_permalink or original_profile_url)

    root_html_cache = cache_dir / f"{cache_key}__researchmap_profile.html"
    json_cache = cache_dir / f"{cache_key}__researchmap.json"

    merged: Dict[str, List[str]] = {
        "research_topics": [],
        "research_fields": [],
        "research_keywords": [],
        "papers": [],
    }

    html = ""
    try:
        response = fetch_response(original_profile_url)
        html = response.text
        final_url = normalize_text(response.url) or original_profile_url
        canonical_profile_url = _extract_base_profile_url(final_url)
        canonical_permalink = _extract_researchmap_permalink(final_url) or canonical_permalink
        root_html_cache.write_text(html, encoding="utf-8")
    except Exception:
        if root_html_cache.exists():
            html = root_html_cache.read_text(encoding="utf-8")

    candidate_permalinks = unique_keep_order([canonical_permalink, original_permalink])

    for permalink in candidate_permalinks:
        if not permalink:
            continue
        api_url = f"{DEFAULT_RESEARCHMAP_API_URL.rstrip('/')}/{permalink}"
        try:
            time.sleep(0.1)
            payload = fetch_json(api_url, params={"format": "json"})
            json_cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            api_parsed = extract_profile_from_researchmap_json(payload)
            for key in merged:
                merged[key].extend(api_parsed.get(key, []))
            canonical_permalink = permalink
            canonical_profile_url = f"{DEFAULT_RESEARCHMAP_BASE_URL}/{permalink}"
            break
        except Exception:
            continue

    if not any(merged.values()) and json_cache.exists():
        try:
            payload = json.loads(json_cache.read_text(encoding="utf-8"))
            api_parsed = extract_profile_from_researchmap_json(payload)
            for key in merged:
                merged[key].extend(api_parsed.get(key, []))
        except Exception:
            pass

    if html:
        root_parsed = extract_topics_and_papers_from_html(html)
        for key in merged:
            merged[key].extend(root_parsed.get(key, []))

    subpage_parsed = _fetch_researchmap_subpages(canonical_profile_url, cache_dir)
    for key in merged:
        merged[key].extend(subpage_parsed.get(key, []))

    result = {
        "status": "ok_researchmap_fallback",
        "matched_url": canonical_profile_url,
        "matched_display_name": candidate.get("display_name", ""),
        "profile_source": "researchmap",
        "research_topics": unique_keep_order(merged["research_topics"]),
        "research_fields": unique_keep_order(merged["research_fields"]),
        "research_keywords": unique_keep_order(merged["research_keywords"]),
        "papers": unique_keep_order(merged["papers"]),
    }
    return result


def enrich_teacher_from_researchmap(name: str, cache_dir: str | Path) -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    search_cache_path = cache_dir / f"{slugify(name)}__researchmap_search.html"

    try:
        candidates, last_search_html = search_researchmap_candidates(DEFAULT_RESEARCHMAP_BASE_URL, name)
        if last_search_html:
            search_cache_path.write_text(last_search_html, encoding="utf-8")

        ranked_candidates = _rank_researchmap_candidates(name, candidates)
        if not ranked_candidates:
            return _empty_result("researchmap_not_found", source="researchmap")

        exact_name = _normalize_compact_name(name)
        exact_matches = [
            c for c in ranked_candidates
            if _normalize_compact_name(c.get("display_name", "")) == exact_name
        ]
        if exact_matches:
            trial_candidates = exact_matches + [
                c for c in ranked_candidates if c not in exact_matches
            ]
        else:
            trial_candidates = ranked_candidates

        tried_urls: List[str] = []
        last_result: Optional[Dict[str, object]] = None

        for candidate in trial_candidates[:10]:
            profile_result = _collect_researchmap_profile(candidate, cache_dir)
            tried_urls.append(normalize_text(profile_result.get("matched_url", "")) or normalize_text(candidate.get("url", "")))
            last_result = profile_result
            if _has_profile_data(profile_result):
                profile_result["status"] = "ok_researchmap_fallback"
                profile_result["tried_candidates"] = " | ".join([u for u in tried_urls if u])
                return profile_result

        if last_result is not None:
            last_result["status"] = "researchmap_profile_empty"
            last_result["tried_candidates"] = " | ".join([u for u in tried_urls if u])
            return last_result

        return _empty_result("researchmap_not_found", source="researchmap")

    except Exception as exc:
        return _empty_result("researchmap_error", error=str(exc), source="researchmap")


def enrich_teacher_from_trios(name: str, base_url: str, cache_dir: str | Path, trios_url: str = "") -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{slugify(name)}.html"

    try:
        if os.environ.get("TRIOS_DISABLE_FETCH", "") == "1":
            if cache_path.exists():
                parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding="utf-8"))
                if _has_profile_data(parsed):
                    return {
                        "status": "cache_only",
                        "matched_url": trios_url,
                        "profile_source": "trios",
                        **parsed,
                    }
            return enrich_teacher_from_researchmap(name, cache_dir)

        if trios_url:
            html = fetch(trios_url)
            cache_path.write_text(html, encoding="utf-8")
            parsed = extract_topics_and_papers_from_html(html)
            if _has_profile_data(parsed):
                return {
                    "status": "ok_direct_url",
                    "matched_url": trios_url,
                    "profile_source": "trios",
                    **parsed,
                }
            return enrich_teacher_from_researchmap(name, cache_dir)

        candidates = search_candidates(base_url, name)
        best = choose_best(name, candidates)
        if best:
            time.sleep(0.15)
            html = fetch(best["url"])
            cache_path.write_text(html, encoding="utf-8")
            parsed = extract_topics_and_papers_from_html(html)
            if _has_profile_data(parsed):
                return {
                    "status": "ok",
                    "matched_url": best["url"],
                    "matched_display_name": best["display_name"],
                    "profile_source": "trios",
                    **parsed,
                }

        return enrich_teacher_from_researchmap(name, cache_dir)

    except Exception as exc:
        if cache_path.exists():
            parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding="utf-8"))
            if _has_profile_data(parsed):
                return {
                    "status": "cache_fallback",
                    "matched_url": trios_url,
                    "profile_source": "trios",
                    "error": str(exc),
                    **parsed,
                }

        fallback = enrich_teacher_from_researchmap(name, cache_dir)
        if _has_profile_data(fallback):
            fallback["error"] = str(exc)
            return fallback

        return _empty_result("error", trios_url, str(exc), source="trios")