from __future__ import annotations

import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .utils import normalize_name, normalize_text, slugify, unique_keep_order


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; thesis-committee-matcher/1.0)"
}
DEFAULT_JGLOBAL_BASE_URL = "https://jglobal.jst.go.jp"
REQUEST_TIMEOUT = 20

CONTROL_LINES = {
    "全件表示",
    "もっと見る",
    "前のページに戻る",
    "この研究者にコンタクトする",
    "J-GLOBAL 科学技術総合リンクセンター",
    "研究者",
    "TOP",
    "BOTTOM",
}

SECTION_PATTERNS: Dict[str, List[str]] = {
    "research_fields": [r"研究分野", r"Research field"],
    "research_keywords": [r"研究キーワード", r"keyword"],
    "research_topics": [r"研究課題"],
    "papers": [r"論文"],
}
STOP_SECTION_PATTERNS: List[str] = [
    r"研究分野",
    r"研究キーワード",
    r"研究課題",
    r"論文",
    r"^MISC",
    r"特許",
    r"書籍",
    r"講演",
    r"^Works",
    r"学位",
    r"所属学協会",
    r"経歴",
    r"学歴",
    r"委員歴",
    r"社会貢献活動",
    r"受賞",
    r"担当経験のある科目",
    r"研究者データベース",
]


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


def _clean_item(text: object) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^\[\d+\]\s*", "", cleaned)
    cleaned = re.sub(r"^[*•・\-]+\s*", "", cleaned)
    cleaned = normalize_text(cleaned)
    if cleaned in CONTROL_LINES:
        return ""
    lowered = cleaned.lower()
    if lowered in {"more...", "j-global", "researchmap"}:
        return ""
    if "さらに表示" in cleaned:
        return ""
    return cleaned


def _iter_dt_dd_pairs(soup: BeautifulSoup) -> Iterable[Tuple[str, object]]:
    for dt in soup.find_all("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        label = normalize_text(dt.get_text(" ", strip=True))
        if not label:
            continue
        yield label, dd


def _find_first_dd_like(soup: BeautifulSoup, patterns: Iterable[str]):
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    for label, dd in _iter_dt_dd_pairs(soup):
        if any(p.search(label) for p in compiled):
            return dd
    return None


def _find_all_dd_like(soup: BeautifulSoup, patterns: Iterable[str]) -> List[object]:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    matched = []
    for label, dd in _iter_dt_dd_pairs(soup):
        if any(p.search(label) for p in compiled):
            matched.append(dd)
    return matched


def _extract_lines_from_dd(dd, *, split_inline: bool = False, kind: str = "generic") -> List[str]:
    items: List[str] = []

    rows = dd.select("table tbody tr") or dd.select("table tr")
    if rows:
        for tr in rows:
            tds = tr.find_all("td", recursive=False)
            if not tds:
                continue
            title = _clean_item(tds[0].get_text(" ", strip=True))
            if title:
                items.append(_postprocess_section_item(title, kind=kind))
        return unique_keep_order([v for v in items if v])

    list_items = dd.select("ul > li") or dd.select("ol > li")
    if list_items:
        for li in list_items:
            text = _clean_item(li.get_text(" ", strip=True))
            if not text:
                continue
            if split_inline:
                items.extend(_split_inline_items(text))
            else:
                items.append(_postprocess_section_item(text, kind=kind))
        return unique_keep_order([v for v in items if v])

    block_text = _clean_item(dd.get_text("\n", strip=True))
    if block_text:
        lines = [_clean_item(x) for x in block_text.splitlines()]
        lines = [x for x in lines if x]
        if split_inline:
            for line in lines:
                items.extend(_split_inline_items(line))
        else:
            items.extend(_postprocess_section_item(line, kind=kind) for line in lines)
    return unique_keep_order([v for v in items if v])


def _parse_label_and_rest(line: str) -> Tuple[str, str]:
    m = re.match(r"^(.*?)(?:\s*\([^)]*\))?\s*[：:]\s*(.*)$", line)
    if m:
        return normalize_text(m.group(1)), normalize_text(m.group(2))
    return normalize_text(line), ""


def _split_inline_items(text: str) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    for sep in ["，", "、", ";", "；", "|", "｜"]:
        text = text.replace(sep, "\n")
    items = [normalize_text(x) for x in text.splitlines() if normalize_text(x)]
    return unique_keep_order(items)


def _line_has_heading_shape(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return False
    return ("：" in line or ":" in line or bool(re.search(r"\(\d+件\)", line)) or len(line) <= 30)


def _looks_like_section_start(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return False
    if line in CONTROL_LINES:
        return False
    if not _line_has_heading_shape(line):
        return False
    for pattern in STOP_SECTION_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False


def _postprocess_section_item(text: str, *, kind: str) -> str:
    value = _clean_item(text)
    if not value:
        return ""
    if kind == "research_topics":
        value = re.sub(r"^\d{4}\s*[-–−]\s*\d{4}\s*", "", value)
        value = re.sub(r"^\d{4}\s*[-–−]\s*", "", value)
        value = normalize_text(value)
    return value


def _plain_text_lines(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    lines = []
    for line in soup.get_text("\n", strip=True).splitlines():
        cleaned = _clean_item(line)
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_section_from_lines(lines: List[str], patterns: Iterable[str], *, split_inline: bool, kind: str) -> List[str]:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    results: List[str] = []

    for idx, line in enumerate(lines):
        if not _line_has_heading_shape(line):
            continue
        if not any(p.search(line) for p in compiled):
            continue

        label, inline_rest = _parse_label_and_rest(line)
        if any(p.search(label) for p in compiled) and inline_rest:
            if split_inline:
                results.extend(_split_inline_items(inline_rest))
            else:
                results.append(_postprocess_section_item(inline_rest, kind=kind))

        for nxt in lines[idx + 1:]:
            if nxt in CONTROL_LINES:
                continue
            if _looks_like_section_start(nxt):
                break
            if split_inline:
                results.extend(_split_inline_items(nxt))
            else:
                results.append(_postprocess_section_item(nxt, kind=kind))
        if results:
            break

    return unique_keep_order([v for v in results if v])


def extract_topics_and_papers_from_html(html: str) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "lxml")
    lines = _plain_text_lines(html)

    fields_dd = _find_first_dd_like(soup, SECTION_PATTERNS["research_fields"])
    keywords_dd = _find_first_dd_like(soup, SECTION_PATTERNS["research_keywords"])
    topics_dd = _find_first_dd_like(soup, SECTION_PATTERNS["research_topics"])
    paper_dds = _find_all_dd_like(soup, SECTION_PATTERNS["papers"])

    research_fields = _extract_lines_from_dd(fields_dd, split_inline=True, kind="research_fields") if fields_dd else []
    research_keywords = _extract_lines_from_dd(keywords_dd, split_inline=True, kind="research_keywords") if keywords_dd else []
    research_topics = _extract_lines_from_dd(topics_dd, split_inline=False, kind="research_topics") if topics_dd else []
    papers: List[str] = []
    for dd in paper_dds:
        papers.extend(_extract_lines_from_dd(dd, split_inline=False, kind="papers"))

    if not research_fields:
        research_fields = _extract_section_from_lines(lines, SECTION_PATTERNS["research_fields"], split_inline=True, kind="research_fields")
    if not research_keywords:
        research_keywords = _extract_section_from_lines(lines, SECTION_PATTERNS["research_keywords"], split_inline=True, kind="research_keywords")
    if not research_topics:
        research_topics = _extract_section_from_lines(lines, SECTION_PATTERNS["research_topics"], split_inline=False, kind="research_topics")
    if not papers:
        papers = _extract_section_from_lines(lines, SECTION_PATTERNS["papers"], split_inline=False, kind="papers")

    return {
        "research_topics": unique_keep_order(research_topics),
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


def choose_best(name: str, candidates: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    target = normalize_name(name)
    best: Optional[Dict[str, str]] = None
    best_score = -1
    for row in candidates:
        label = normalize_name(row.get("display_name"))
        score = 0
        if label == target:
            score = 100
        elif label.startswith(target) or target.startswith(label):
            score = 80
        elif target in label or label in target:
            score = 60
        if score > best_score:
            best = row
            best_score = score
    return best or (candidates[0] if candidates else None)


def _score_candidate_for_name(name: str, display_name: str) -> int:
    target = normalize_name(name)
    label = normalize_name(display_name)
    if not label:
        return 0
    if label == target:
        return 100
    if label.startswith(target) or target.startswith(label):
        return 80
    if target in label or label in target:
        return 60
    return 0


def _parse_jglobal_display_name(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag_name in ["h1", "title"]:
        tag = soup.find(tag_name)
        if tag:
            text = normalize_text(tag.get_text(" ", strip=True))
            if text and "J-GLOBAL" not in text:
                if tag_name == "title":
                    text = re.sub(r"\s*[|｜-].*$", "", text)
                return text

    lines = _plain_text_lines(html)
    for idx, line in enumerate(lines):
        if "J-GLOBAL ID" in line:
            for nxt in lines[idx + 1: idx + 6]:
                if not nxt:
                    continue
                if _looks_like_section_start(nxt):
                    break
                if any(key in nxt for key in ["更新日", "所属", "職名", "URL", "コンタクト"]):
                    continue
                return nxt
    return ""


def _has_profile_data(payload: Dict[str, object]) -> bool:
    for key in ("research_topics", "research_fields", "research_keywords", "papers"):
        values = payload.get(key, []) or []
        if isinstance(values, list) and any(normalize_text(v) for v in values):
            return True
    return False


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


def _search_jglobal_via_duckduckgo(name: str) -> List[Dict[str, str]]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    queries = [
        f'site:jglobal.jst.go.jp/detail?JGLOBAL_ID= "{normalize_text(name)}"',
        f"site:jglobal.jst.go.jp/detail?JGLOBAL_ID= {normalize_text(name)}",
    ]
    candidates: List[Dict[str, str]] = []
    seen = set()

    for query in queries:
        try:
            html = fetch("https://duckduckgo.com/html/", params={"q": query}, session=session)
        except Exception:
            continue

        soup = BeautifulSoup(html, "lxml")
        for link in soup.select("a[href]"):
            href = normalize_text(link.get("href"))
            if not href:
                continue
            if href.startswith("/l/?kh=1&uddg="):
                href = urllib.parse.unquote(href.split("uddg=", 1)[1])
            if "jglobal.jst.go.jp/detail" not in href:
                continue

            if href in seen:
                continue
            seen.add(href)

            candidates.append({
                "display_name": normalize_text(link.get_text(" ", strip=True)),
                "url": href,
                "source": "duckduckgo",
            })

        if candidates:
            break

    return candidates


def _search_jglobal_first_results(name: str) -> List[Dict[str, str]]:
    """
    TRIOS と同じ発想で:
    名前検索して、検索結果に出た detail?JGLOBAL_ID=... のリンクを上から順に使う。
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    queries = [
        normalize_text(name),
        normalize_text(name).replace(" ", ""),
    ]
    search_urls = [
        f"{DEFAULT_JGLOBAL_BASE_URL}/search/researchers",
        f"{DEFAULT_JGLOBAL_BASE_URL}/search/anythings",
    ]

    candidates: List[Dict[str, str]] = []
    seen = set()

    for query in queries:
        for search_url in search_urls:
            try:
                html = fetch(search_url, params={"q": query}, session=session)
            except Exception:
                continue

            soup = BeautifulSoup(html, "lxml")
            links = soup.select('a[href*="detail?JGLOBAL_ID="]')

            for link in links:
                href = normalize_text(link.get("href"))
                if not href:
                    continue
                abs_url = urllib.parse.urljoin(DEFAULT_JGLOBAL_BASE_URL, href)
                if abs_url in seen:
                    continue
                seen.add(abs_url)

                label = normalize_text(link.get_text(" ", strip=True))
                if not label:
                    parent = link.parent.get_text(" ", strip=True) if link.parent else ""
                    label = normalize_text(parent)

                candidates.append({
                    "display_name": label,
                    "url": abs_url,
                    "source": "jglobal_search",
                })

            if candidates:
                return candidates

    return []


def search_jglobal_candidates(name: str) -> List[Dict[str, str]]:
    candidates = _search_jglobal_first_results(name)
    if candidates:
        return candidates

    return _search_jglobal_via_duckduckgo(name)


def enrich_teacher_from_jglobal(name: str, cache_dir: str | Path) -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = slugify(name)

    try:
        candidates = search_jglobal_candidates(name)
        if not candidates:
            return _empty_result("jglobal_not_found", source="jglobal")

        tried_urls: List[str] = []
        best_nonempty: Optional[Dict[str, object]] = None
        best_score = -1

        for idx, candidate in enumerate(candidates[:10], start=1):
            url = normalize_text(candidate.get("url"))
            if not url:
                continue

            tried_urls.append(url)
            cache_path = cache_dir / f"{cache_key}__jglobal_{idx}.html"

            try:
                time.sleep(0.15)
                response = fetch_response(url)
                html = response.text
                final_url = normalize_text(response.url) or url
                cache_path.write_text(html, encoding="utf-8")
            except Exception:
                if not cache_path.exists():
                    continue
                html = cache_path.read_text(encoding="utf-8")
                final_url = url

            parsed = extract_topics_and_papers_from_html(html)
            display_name = _parse_jglobal_display_name(html) or normalize_text(candidate.get("display_name"))
            score = _score_candidate_for_name(name, display_name)

            result = {
                "status": "ok_jglobal_fallback",
                "matched_url": final_url,
                "matched_display_name": display_name,
                "profile_source": "jglobal",
                "research_topics": parsed.get("research_topics", []),
                "research_fields": parsed.get("research_fields", []),
                "research_keywords": parsed.get("research_keywords", []),
                "papers": parsed.get("papers", []),
            }

            if _has_profile_data(result) and score >= 100:
                return result

            if _has_profile_data(result) and score > best_score:
                best_nonempty = result
                best_score = score

        if best_nonempty is not None:
            best_nonempty["tried_candidates"] = " | ".join(tried_urls)
            return best_nonempty

        return {
            **_empty_result("jglobal_profile_empty", source="jglobal"),
            "tried_candidates": " | ".join(tried_urls),
        }

    except Exception as exc:
        return _empty_result("jglobal_error", error=str(exc), source="jglobal")


def enrich_teacher_from_trios(name: str, base_url: str, cache_dir: str | Path, trios_url: str = "") -> Dict[str, object]:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{slugify(name)}.html"

    try:
        if os.environ.get("TRIOS_DISABLE_FETCH", "") == "1":
            if cache_path.exists():
                parsed = extract_topics_and_papers_from_html(cache_path.read_text(encoding="utf-8"))
                if _has_profile_data(parsed):
                    return {"status": "cache_only", "matched_url": trios_url, "profile_source": "trios", **parsed}
            return enrich_teacher_from_jglobal(name, cache_dir)

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
            return enrich_teacher_from_jglobal(name, cache_dir)

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

        return enrich_teacher_from_jglobal(name, cache_dir)

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

        fallback = enrich_teacher_from_jglobal(name, cache_dir)
        if _has_profile_data(fallback):
            fallback["error"] = str(exc)
            return fallback

        return _empty_result("error", trios_url, str(exc), source="trios")