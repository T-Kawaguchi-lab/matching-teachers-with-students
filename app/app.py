from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# =========================================================
# Paths
# =========================================================
ROOT_DIR = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT_DIR / "generated"

SCORES_CSV = GENERATED_DIR / "student_teacher_scores_long.csv"
COMMITTEE_XLSX = GENERATED_DIR / "committee_recommendations.xlsx"
TEACHERS_XLSX = GENERATED_DIR / "teachers_enriched.xlsx"
STUDENTS_XLSX = GENERATED_DIR / "students_enriched.xlsx"
STATUS_JSON = GENERATED_DIR / "pipeline_status.json"


# =========================================================
# Page config
# =========================================================
st.set_page_config(
    page_title="修論テーマ × 教員マッチング",
    layout="wide",
)


# =========================================================
# Styles
# =========================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    .main-title {
        font-size: 2.1rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #0f172a;
    }

    .sub-title {
        color: #475569;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }

    .section-title {
        font-size: 1.2rem;
        font-weight: 700;
        margin-top: 0.2rem;
        margin-bottom: 0.8rem;
        color: #0f172a;
    }

    .card {
        border: 1px solid #dbe4f0;
        border-radius: 16px;
        padding: 18px 18px 14px 18px;
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        margin-bottom: 16px;
    }

    .card-soft {
        border: 1px solid #e5edf6;
        border-radius: 16px;
        padding: 16px 18px;
        background: #fbfdff;
        margin-bottom: 14px;
    }

    .metric-card {
        border: 1px solid #dbe4f0;
        border-radius: 16px;
        padding: 16px 18px;
        background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
        min-height: 110px;
    }

    .metric-label {
        color: #64748b;
        font-size: 0.95rem;
        margin-bottom: 0.4rem;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
    }

    .metric-sub {
        color: #64748b;
        font-size: 0.9rem;
        margin-top: 0.3rem;
    }

    .label {
        color: #64748b;
        font-size: 0.9rem;
        margin-bottom: 0.15rem;
        font-weight: 600;
    }

    .value {
        color: #0f172a;
        font-size: 1rem;
        margin-bottom: 0.9rem;
        line-height: 1.6;
        word-break: break-word;
    }

    .pill {
        display: inline-block;
        padding: 0.3rem 0.7rem;
        border-radius: 999px;
        background: #e8f1ff;
        color: #1d4ed8;
        font-size: 0.85rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }

    .small-note {
        color: #64748b;
        font-size: 0.88rem;
    }

    div[data-baseweb="select"] > div {
        border-radius: 12px !important;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid #e5edf6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# Helpers
# =========================================================
def safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v)
    return "" if s.lower() == "nan" else s


def first_existing(df: pd.DataFrame, candidates: list[str], default: str = "") -> str:
    for c in candidates:
        if c in df.columns:
            return c
    return default


def value_from_row(row: pd.Series, candidates: list[str], default: str = "") -> str:
    for c in candidates:
        if c in row.index:
            return safe_str(row.get(c, default))
    return default


def format_multiline_text(text: str) -> str:
    text = safe_str(text).strip()
    if not text:
        return "なし"
    return text.replace("\n", "<br>")


def render_field(label: str, value: Any) -> None:
    st.markdown(
        f"""
        <div class="label">{label}</div>
        <div class="value">{format_multiline_text(safe_str(value))}</div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: Any, sub: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{safe_str(value)}</div>
            <div class="metric-sub">{safe_str(sub)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_status() -> dict:
    if not STATUS_JSON.exists():
        return {}
    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


# =========================================================
# Header
# =========================================================
st.markdown('<div class="main-title">修論テーマ × 教員マッチング UI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">GitHub Actions が生成した最新の教員・学生データと推薦結果を、右側アプリに近いカード型 UI で表示します。</div>',
    unsafe_allow_html=True,
)


# =========================================================
# Load status
# =========================================================
status = load_status()

if status:
    with st.expander("最新実行情報 / Pipeline Status", expanded=False):
        st.json(status)


# =========================================================
# File existence checks
# =========================================================
if not SCORES_CSV.exists():
    st.warning(
        "まだ推薦結果がありません。教員入力と学生入力の両方が GitHub に push されると、GitHub Actions が自動で推薦結果を生成します。"
    )
    if status:
        st.info(status.get("message", "現在は待機中です。"))
    st.stop()

committee_exists = COMMITTEE_XLSX.exists()
teachers_exists = TEACHERS_XLSX.exists()
students_exists = STUDENTS_XLSX.exists()

if not (committee_exists and teachers_exists and students_exists):
    st.error("generated フォルダ内の必要ファイルが不足しています。GitHub Actions の完了を確認してください。")
    st.stop()


# =========================================================
# Load data
# =========================================================
scores = pd.read_csv(SCORES_CSV)
committee_df = pd.read_excel(COMMITTEE_XLSX)
teachers_df = pd.read_excel(TEACHERS_XLSX)
students_df = pd.read_excel(STUDENTS_XLSX)

student_name_col = first_existing(students_df, ["student_name", "name"], "student_name")
teacher_name_col = first_existing(teachers_df, ["teacher_name", "name"], "teacher_name")
score_student_col = first_existing(scores, ["student_name"], "student_name")
score_teacher_col = first_existing(scores, ["teacher_name"], "teacher_name")

if score_student_col not in scores.columns:
    st.error("scores データに student_name 列が見つかりません。")
    st.stop()

student_names = sorted(scores[score_student_col].dropna().astype(str).unique().tolist())
if not student_names:
    st.warning("推薦対象の学生データがまだありません。")
    st.stop()


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.header("表示設定")
    selected_student = st.selectbox("学生を選択", student_names)
    rank_limit = st.slider("表示件数", 3, 20, 10)
    show_full_data = st.checkbox("全体データを表示", value=False)
    st.caption("右側アプリのように、選択対象ごとに結果をカード表示します。")


# =========================================================
# Filter selected student
# =========================================================
student_scores = (
    scores[scores[score_student_col] == selected_student]
    .sort_values("rank" if "rank" in scores.columns else scores.columns[0])
    .head(rank_limit)
    .copy()
)

if student_scores.empty:
    st.warning("この学生の候補データがありません。")
    st.stop()

student_info_df = students_df[students_df[student_name_col] == selected_student]
committee_info_df = committee_df[committee_df[first_existing(committee_df, ["student_name", "name"], "student_name")] == selected_student]

if student_info_df.empty or committee_info_df.empty:
    st.warning("学生情報または委員会情報が見つかりません。")
    st.stop()

student_info = student_info_df.iloc[0]
committee_info = committee_info_df.iloc[0]


# =========================================================
# Top metrics
# =========================================================
total_students = len(student_names)
total_teachers = teachers_df[teacher_name_col].dropna().astype(str).nunique() if teacher_name_col in teachers_df.columns else len(teachers_df)
candidate_count = len(student_scores)

m1, m2, m3 = st.columns(3)
with m1:
    render_metric_card("学生数", total_students, "推薦対象の学生")
with m2:
    render_metric_card("教員数", total_teachers, "候補教員データ")
with m3:
    render_metric_card("表示候補数", candidate_count, f"{selected_student} さん向け")


# =========================================================
# Main selector area
# =========================================================
st.markdown('<div class="section-title">学生入力データ / Input Data</div>', unsafe_allow_html=True)

left_top, right_top = st.columns([1.45, 1.0])

with left_top:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">Student Profile</div>', unsafe_allow_html=True)

    render_field("学生名", value_from_row(student_info, ["student_name", "name"]))
    render_field("修論テーマ", value_from_row(student_info, ["thesis_title", "theme", "title"]))
    render_field("研究分野候補", value_from_row(student_info, ["research_fields", "research_field", "field"]))

    st.markdown("</div>", unsafe_allow_html=True)

with right_top:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">Recommended Committee</div>', unsafe_allow_html=True)

    render_field("主指導教員", value_from_row(committee_info, ["main_advisor"]))
    render_field("副指導教員1", value_from_row(committee_info, ["sub_advisor_1"]))
    render_field("副指導教員2", value_from_row(committee_info, ["sub_advisor_2"]))

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Ranking table
# =========================================================
st.markdown('<div class="section-title">上位候補ランキング / Results List</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-note">右側アプリの結果一覧に寄せて、主要スコアを先頭にまとめて表示しています。</div>',
    unsafe_allow_html=True,
)

display_cols = [
    "rank",
    "teacher_name",
    "total_score",
    "theme_score",
    "field_score",
    "lexical_score",
    "exact_bonus",
]
existing_cols = [c for c in display_cols if c in student_scores.columns]

column_config = {}
if "rank" in existing_cols:
    column_config["rank"] = st.column_config.NumberColumn("順位", format="%d")
if "teacher_name" in existing_cols:
    column_config["teacher_name"] = st.column_config.TextColumn("教員名")
if "total_score" in existing_cols:
    column_config["total_score"] = st.column_config.NumberColumn("総合スコア", format="%.4f")
if "theme_score" in existing_cols:
    column_config["theme_score"] = st.column_config.NumberColumn("テーマ類似", format="%.4f")
if "field_score" in existing_cols:
    column_config["field_score"] = st.column_config.NumberColumn("分野類似", format="%.4f")
if "lexical_score" in existing_cols:
    column_config["lexical_score"] = st.column_config.NumberColumn("語彙スコア", format="%.4f")
if "exact_bonus" in existing_cols:
    column_config["exact_bonus"] = st.column_config.NumberColumn("一致ボーナス", format="%.4f")

st.dataframe(
    student_scores[existing_cols],
    use_container_width=True,
    hide_index=True,
    height=420,
    column_config=column_config,
)


# =========================================================
# Teacher detail selector
# =========================================================
st.markdown('<div class="section-title">候補教員の詳細 / Teacher Detail</div>', unsafe_allow_html=True)

teacher_options = student_scores[score_teacher_col].dropna().astype(str).tolist()
selected_teacher = st.selectbox(
    "教員を選択",
    teacher_options,
    key="selected_teacher_detail",
)

teacher_info_df = teachers_df[teachers_df[teacher_name_col] == selected_teacher]
if teacher_info_df.empty:
    st.warning("教員詳細が見つかりません。")
    st.stop()

teacher_info = teacher_info_df.iloc[0]


# =========================================================
# Teacher detail cards
# =========================================================
detail_left, detail_right = st.columns(2)

with detail_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">Basic Information</div>', unsafe_allow_html=True)

    render_field("教員名", value_from_row(teacher_info, ["teacher_name", "name"]))
    render_field("所属", value_from_row(teacher_info, ["department", "affiliation"]))
    render_field("職名", value_from_row(teacher_info, ["position", "title"]))
    render_field("研究分野候補", value_from_row(teacher_info, ["research_fields", "research_field"]))

    st.markdown("</div>", unsafe_allow_html=True)

with detail_right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">External / Metadata</div>', unsafe_allow_html=True)

    trios_url = value_from_row(teacher_info, ["trios_url"])
    if trios_url:
        st.markdown(
            f"""
            <div class="label">TRIOS URL</div>
            <div class="value"><a href="{trios_url}" target="_blank">{trios_url}</a></div>
            """,
            unsafe_allow_html=True,
        )
    else:
        render_field("TRIOS URL", "なし")

    render_field("TRIOS 取得状態", value_from_row(teacher_info, ["trios_status"]))
    render_field("過去修論テーマ", value_from_row(teacher_info, ["past_thesis_titles"]))

    st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="card-soft">', unsafe_allow_html=True)
st.markdown('<div class="section-title" style="margin-top:0;">TRIOS由来の情報 / TRIOS-based Information</div>', unsafe_allow_html=True)

info_col1, info_col2 = st.columns(2)
with info_col1:
    render_field("研究課題", value_from_row(teacher_info, ["trios_topics"]))
with info_col2:
    render_field("論文タイトル", value_from_row(teacher_info, ["trios_papers"]))

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Optional raw data area
# =========================================================
if show_full_data:
    st.markdown('<div class="section-title">全体データ / Full Data</div>', unsafe_allow_html=True)

    with st.expander("教員データ", expanded=False):
        st.dataframe(teachers_df, use_container_width=True, hide_index=True)

    with st.expander("学生データ", expanded=False):
        st.dataframe(students_df, use_container_width=True, hide_index=True)

    with st.expander("推薦スコアデータ", expanded=False):
        st.dataframe(scores, use_container_width=True, hide_index=True)