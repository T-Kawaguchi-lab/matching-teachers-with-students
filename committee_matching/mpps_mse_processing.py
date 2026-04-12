from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from .utils import normalize_name, normalize_text, unique_keep_order


GROUPS = ["MPPS", "MSE"]


def parse_groups(value: object) -> List[str]:
    text = normalize_text(value).upper()
    if not text:
        return []
    groups: List[str] = []
    if "MPPS" in text:
        groups.append("MPPS")
    if "MSE" in text:
        groups.append("MSE")
    return groups


def split_multi_value_text(value: object) -> List[str]:
    text = normalize_text(value)
    if not text:
        return []
    for sep in [";", "；", "/", "／", "|", "｜", "、", ","]:
        text = text.replace(sep, "\n")
    return unique_keep_order([normalize_text(v) for v in text.splitlines() if normalize_text(v)])


KEYWORD_RULES: List[Tuple[str, List[str], List[str]]] = [
    ("労働経済・就職マッチング", ["就活", "採用", "新卒", "選考", "内定", "求人", "職業", "労働", "賃金", "介護離職"], ["労働経済", "人的資本", "就職マッチング", "採用市場設計"]),
    ("家族・人口政策", ["結婚", "出生", "出産", "子育て", "独身税", "少子化", "人口"], ["家族の経済学", "少子化対策", "人口政策", "家計意思決定"]),
    ("保険・金融行動", ["保険", "投資", "株式", "PBR", "資産", "金融", "ESG", "ファイナンス", "証券"], ["行動ファイナンス", "金融市場分析", "ESG投資", "企業財務"]),
    ("意思決定分析", ["意思決定", "損失回避", "選好", "価値観", "行動変容", "ゲーミフィケーション"], ["行動意思決定", "実験・行動分析", "ナッジ", "意思決定支援"]),
    ("マッチング理論・ゲーム理論", ["matching", "マッチング", "ゲーム理論", "パレート", "均衡", "割当", "ライドシェア", "uniform rule"], ["安定マッチング", "資源配分", "メカニズムデザイン", "協力ゲーム・非協力ゲーム"]),
    ("都市・地域政策", ["都市", "東京", "住宅地", "不動産", "地籍", "自治体", "地域", "空港", "洪水", "公園", "居住", "創業支援"], ["都市経済", "地域政策", "土地利用", "公共政策評価"]),
    ("GIS・空間分析", ["地理空間", "居住パターン", "地籍", "23区", "空港", "洪水", "地図", "空間"], ["GIS", "空間計量", "地理情報分析", "立地分析"]),
    ("社会政策・福祉", ["介護", "産後", "福祉", "NPO", "アウトリーチ", "居場所", "コミュニティ"], ["社会福祉政策", "地域福祉", "子育て支援", "非営利組織論"]),
    ("オペレーションズリサーチ", ["最適化", "輸送", "スケジューリング", "負荷分散", "運行計画", "経路最適化", "工場", "multi", "マルチファクトリー"], ["数理最適化", "組合せ最適化", "オペレーションズリサーチ", "計画・スケジューリング"]),
    ("交通・モビリティ", ["電動バス", "ライドシェア", "道路", "歩車", "歩行者", "交通", "飛行経路", "シェアサイクル", "自転車", "水素ステーション", "FCV"], ["交通工学", "モビリティ設計", "交通需要分析", "ネットワーク設計"]),
    ("建築・空間設計", ["間取り", "住宅", "歩車共存空間", "建築", "空間", "舞台", "スタジアム", "アリーナ"], ["建築計画", "空間レイアウト生成", "居住空間設計", "都市空間デザイン"]),
    ("機械学習", ["機械学習", "アクティブラーニング", "factorization", "sparse", "スパース", "モデリング", "センチメント", "行動認識", "マルチモーダル", "異常"], ["機械学習", "統計的学習", "予測モデリング", "表現学習"]),
    ("画像・視覚情報処理", ["画像", "視線", "骨格", "関節角", "認識", "生体計測", "vision", "異常原因", "衛星", "リモートセンシング"], ["コンピュータビジョン", "画像認識", "行動認識", "マルチモーダル解析"]),
    ("ネットワーク・グラフ理論", ["グラフ", "コイン", "部分彩色", "連結性", "ネットワーク"], ["グラフ理論", "離散数学", "ネットワーク最適化", "組合せ構造"]),
    ("サービス・待ち行列", ["サーバ", "サービスシステム", "待ち行列", "性能解析"], ["待ち行列理論", "サービス工学", "システム性能評価"]),
    ("スポーツデータ分析", ["eスポーツ", "スポーツ", "チーム", "プレイスタイル", "スタジアム", "アリーナ"], ["スポーツアナリティクス", "戦術分析", "パフォーマンス分析"]),
    ("災害・防災研究", ["震災", "災害", "洪水", "記憶", "防災", "犯罪被害", "騒音"], ["災害社会学", "防災政策", "リスク評価"]),
    ("政策評価・計量分析", ["計量", "因果推論", "政策分析", "影響", "効果", "推移", "実証", "要請"], ["政策評価", "計量経済学", "統計的因果推論", "実証分析"]),
    ("会計・ファイナンス", ["会計", "仕訳", "財務", "監査"], ["会計データ分析", "財務会計", "管理会計", "会計情報システム"]),
    ("テキスト分析・NLP", ["テキスト", "言語", "SNS", "意見", "感情", "ワクチン"], ["テキストマイニング", "自然言語処理", "感情分析", "社会データ分析"]),
    ("医療・ヘルスデータ", ["医療", "生体", "ハザード比", "HPV", "ワクチン", "ヘルス"], ["医療データ分析", "生体情報解析", "ヘルスデータサイエンス", "統計解析"]),
    ("観光・マーケティング", ["観光", "セグメンテーション", "マーケティング", "需要"], ["観光データ分析", "マーケティング分析", "クラスタリング", "需要予測"]),
    ("環境・エネルギー", ["環境", "排出", "エネルギー", "グリーン", "気候", "CO2", "水素"], ["環境政策", "エネルギーシステム", "脱炭素分析", "持続可能性評価"]),
]


TEACHER_COARSE_HINTS: List[Tuple[str, List[str]]] = [
    ("公共政策・社会工学", ["政策", "社会", "自治体", "制度", "公共", "行政", "地域"]),
    ("経済・ファイナンス", ["経済", "市場", "賃金", "金融", "株式", "ESG", "投資", "企業"]),
    ("数理最適化・OR", ["最適化", "スケジューリング", "輸送", "計画", "ネットワーク", "待ち行列", "ゲーム理論"]),
    ("AI・データサイエンス", ["学習", "画像", "推定", "データ", "モデル", "認識", "センシング"]),
    ("都市・空間・交通", ["都市", "交通", "住宅", "不動産", "空港", "地理空間", "GIS"]),
    ("環境・エネルギー", ["環境", "排出", "エネルギー", "グリーン", "気候"]),
]


def infer_research_fields_from_texts(texts: Iterable[object], include_coarse: bool = True) -> Tuple[List[str], List[str]]:
    merged = "\n".join([normalize_text(t) for t in texts if normalize_text(t)])
    coarse: List[str] = []
    fine: List[str] = []
    if not merged:
        return coarse, fine

    lower = merged.lower()
    for coarse_name, keywords, fine_candidates in KEYWORD_RULES:
        if any(k.lower() in lower for k in keywords):
            coarse.append(coarse_name)
            fine.extend(fine_candidates)

    if include_coarse:
        for coarse_name, keywords in TEACHER_COARSE_HINTS:
            if any(k.lower() in lower for k in keywords):
                coarse.append(coarse_name)

    return unique_keep_order(coarse), unique_keep_order(fine)


def _suggest_taxonomy_fields(field_matcher, texts: Iterable[object], top_k: int = 4) -> List[str]:
    if field_matcher is None:
        return []
    normalized_texts = [normalize_text(t) for t in texts if normalize_text(t)]
    if not normalized_texts:
        return []
    try:
        return field_matcher.suggest_fields(
            normalized_texts,
            top_k=top_k,
            min_score=0.18,
            additional_min_score=0.16,
            relative_score_floor=0.82,
        )
    except Exception:
        return []


def load_master_title(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["指導教員", "担当タイトル", "所属", "年度"])
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    else:
        df = pd.read_excel(p)
    rename_map = {}
    for src, dst in [("teacher_name", "指導教員"), ("title", "担当タイトル"), ("thesis_title", "担当タイトル"), ("department", "所属"), ("group", "所属"), ("year", "年度")]:
        if src in df.columns and dst not in df.columns:
            rename_map[src] = dst
    df = df.rename(columns=rename_map)
    for col in ["指導教員", "担当タイトル", "所属", "年度"]:
        if col not in df.columns:
            df[col] = ""
    df["指導教員"] = df["指導教員"].map(normalize_text)
    df["担当タイトル"] = df["担当タイトル"].map(normalize_text)
    df["所属"] = df["所属"].map(normalize_text)
    df = df[(df["指導教員"] != "") & (df["担当タイトル"] != "")].copy()
    return df[["指導教員", "担当タイトル", "所属", "年度"]].reset_index(drop=True)


def merge_master_title(base_df: pd.DataFrame, append_df: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([base_df, append_df], ignore_index=True)
    merged["teacher_key"] = merged["指導教員"].map(normalize_name)
    merged["title_key"] = merged["担当タイトル"].map(normalize_text).str.lower()
    merged = merged.drop_duplicates(subset=["teacher_key", "title_key"], keep="last")
    merged = merged.drop(columns=["teacher_key", "title_key"])
    return merged.reset_index(drop=True)


@dataclass
class PreparedData:
    students: pd.DataFrame
    teachers: pd.DataFrame
    master_title: pd.DataFrame


def prepare_students(df: pd.DataFrame, field_matcher=None) -> pd.DataFrame:
    rename_map = {"名前": "student_name", "タイトル": "title", "所属": "group", "概要分野": "overview_field", "研究内容": "research_content", "研究分野": "research_field"}
    out = df.rename(columns=rename_map).copy()
    required = ["student_name", "title", "group"]
    for col in required:
        if col not in out.columns:
            raise ValueError(f"学生ファイルに必須列がありません: {col}")
    for col in ["overview_field", "research_content", "research_field"]:
        if col not in out.columns:
            out[col] = ""

    rows: List[Dict[str, object]] = []
    for _, row in out.iterrows():
        title = normalize_text(row.get("title"))
        content = normalize_text(row.get("research_content"))
        overview_fields = split_multi_value_text(row.get("overview_field"))
        base_fields = split_multi_value_text(row.get("research_field"))
        coarse, detailed = infer_research_fields_from_texts(
            [title, content, row.get("overview_field"), row.get("research_field")],
            include_coarse=False,
        )
        taxonomy_fields = _suggest_taxonomy_fields(
            field_matcher,
            [title, content, row.get("overview_field"), row.get("research_field")],
            top_k=3,
        )

        research_fields = unique_keep_order((base_fields if base_fields else overview_fields) + coarse)
        detailed_fields = unique_keep_order(detailed + taxonomy_fields)
        if not detailed_fields:
            detailed_fields = unique_keep_order(base_fields + overview_fields)
        field_text_values = unique_keep_order(overview_fields + research_fields + detailed_fields)

        rows.append({
            "student_name": normalize_text(row.get("student_name")),
            "group": normalize_text(row.get("group")).upper(),
            "title": title,
            "overview_field": " ; ".join(overview_fields),
            "research_content": content,
            "research_field": " ; ".join(research_fields),
            "detailed_research_field": " ; ".join(detailed_fields),
            "field_text": "\n".join(field_text_values),
            "content_text": "\n".join([v for v in [title, content] if v]),
        })
    result = pd.DataFrame(rows)
    result = result[(result["student_name"] != "") & (result["title"] != "") & (result["group"].isin(GROUPS))].copy()
    return result.reset_index(drop=True)


def prepare_teachers(
    df: pd.DataFrame,
    master_title_df: pd.DataFrame,
    trios_lookup: Dict[str, Dict[str, object]] | None = None,
    field_matcher=None,
) -> pd.DataFrame:
    trios_lookup = trios_lookup or {}
    rename_map = {"指導教員": "teacher_name", "所属": "group_text", "No.": "no"}
    out = df.rename(columns=rename_map).copy()
    if "teacher_name" not in out.columns:
        raise ValueError("指導教員一覧ファイルに必須列がありません: 指導教員")
    if "group_text" not in out.columns:
        out["group_text"] = ""

    history_by_teacher: Dict[str, List[str]] = {}
    for _, row in master_title_df.iterrows():
        key = normalize_name(row.get("指導教員"))
        history_by_teacher.setdefault(key, []).append(normalize_text(row.get("担当タイトル")))

    rows: List[Dict[str, object]] = []
    for _, row in out.iterrows():
        teacher_name = normalize_text(row.get("teacher_name"))
        groups = parse_groups(row.get("group_text"))
        if not groups:
            continue
        profile = trios_lookup.get(normalize_name(teacher_name), {})
        profile_topics = unique_keep_order(profile.get("research_topics", []) or [])
        profile_research_fields = unique_keep_order(profile.get("research_fields", []) or [])
        profile_research_keywords = unique_keep_order(profile.get("research_keywords", []) or [])
        profile_papers = unique_keep_order(profile.get("papers", []) or [])
        profile_info_values = unique_keep_order([
            *profile_topics,
            *profile_research_fields,
            *profile_research_keywords,
            *profile_papers,
        ])
        titles = unique_keep_order(history_by_teacher.get(normalize_name(teacher_name), []))

        field_source_texts = [*profile_topics, *profile_research_fields]
        coarse_fields, detailed_fields = infer_research_fields_from_texts(field_source_texts, include_coarse=True)
        taxonomy_fields = _suggest_taxonomy_fields(field_matcher, field_source_texts, top_k=4)

        coarse_fields = unique_keep_order(profile_research_fields + coarse_fields)
        detailed_fields = unique_keep_order(detailed_fields + taxonomy_fields)
        if not detailed_fields:
            detailed_fields = unique_keep_order(profile_research_fields + profile_research_keywords)

        field_text_values = unique_keep_order(
            profile_research_fields + profile_research_keywords + coarse_fields + detailed_fields
        )
        content_text_values = unique_keep_order(titles + profile_topics + profile_papers)

        for group in groups:
            rows.append({
                "teacher_name": teacher_name,
                "group": group,
                "group_text": normalize_text(row.get("group_text")),
                "trios_url": normalize_text(profile.get("matched_url", "")),
                "trios_status": normalize_text(profile.get("status", "")),
                "profile_source": normalize_text(profile.get("profile_source", "trios")),
                "trios_info": "\n".join(profile_info_values),
                "trios_topics_text": " / ".join(profile_topics),
                "trios_research_fields_text": " / ".join(profile_research_fields),
                "trios_research_keywords_text": " / ".join(profile_research_keywords),
                "trios_papers_text": " / ".join(profile_papers),
                "master_title_text": " / ".join(titles),
                "coarse_research_field": " ; ".join(coarse_fields),
                "detailed_research_field": " ; ".join(detailed_fields),
                "field_text": "\n".join(field_text_values),
                "content_text": "\n".join(content_text_values),
            })
    result = pd.DataFrame(rows)
    return result.reset_index(drop=True)