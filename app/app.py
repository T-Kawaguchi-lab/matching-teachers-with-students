from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

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

    .weight-box {
        border: 1px solid #dbe4f0;
        border-radius: 14px;
        padding: 14px 16px;
        background: #f8fbff;
        margin-bottom: 14px;
    }

    .tag {
        display: inline-block;
        padding: 0.22rem 0.55rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3;
        font-size: 0.82rem;
        font-weight: 700;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
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


def is_missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except Exception:
        return False


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


def ensure_numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)


def normalize_weights(weight_dict: dict[str, float]) -> dict[str, float]:
    clipped = {k: max(0.0, float(v)) for k, v in weight_dict.items()}
    total = sum(clipped.values())
    if total <= 0:
        return {k: 0.0 for k in clipped}
    return {k: v / total for k, v in clipped.items()}


def normalize_text_token(text: str) -> str:
    return " ".join(safe_str(text).strip().lower().split())


def parse_listlike(value: Any) -> list[str]:
    if is_missing(value):
        return []

    if isinstance(value, list):
        out = []
        for item in value:
            s = safe_str(item).strip()
            if s:
                out.append(s)
        return out

    s = safe_str(value).strip()
    if not s:
        return []

    if s.startswith("[") and s.endswith("]"):
        try:
            parsed = json.loads(s.replace("'", '"'))
            if isinstance(parsed, list):
                return [safe_str(x).strip() for x in parsed if safe_str(x).strip()]
        except Exception:
            pass

    seps = [" ; ", ";", "、", ",", "\n", " / ", "/"]
    tmp = [s]
    for sep in seps:
        next_tmp = []
        for piece in tmp:
            next_tmp.extend(piece.split(sep))
        tmp = next_tmp

    out = [p.strip() for p in tmp if p.strip()]
    return out


def get_fields_from_row(row: pd.Series) -> list[str]:
    candidates = [
        "research_fields",
        "research_fields_text",
        "research_field",
        "field",
    ]
    for c in candidates:
        if c in row.index:
            vals = parse_listlike(row[c])
            if vals:
                return vals
    return []


def compute_exact_matches(student_fields: Iterable[str], teacher_fields: Iterable[str]) -> list[str]:
    teacher_map: dict[str, str] = {}
    for t in teacher_fields:
        key = normalize_text_token(t)
        if key and key not in teacher_map:
            teacher_map[key] = safe_str(t).strip()

    matches: list[str] = []
    seen = set()
    for s in student_fields:
        key = normalize_text_token(s)
        if key and key in teacher_map and key not in seen:
            matches.append(teacher_map[key] or safe_str(s).strip())
            seen.add(key)
    return matches


def render_tags(tags: list[str]) -> None:
    if not tags:
        st.markdown('<div class="value">なし</div>', unsafe_allow_html=True)
        return
    html = "".join(f'<span class="tag">{safe_str(tag)}</span>' for tag in tags)
    st.markdown(html, unsafe_allow_html=True)


# =========================================================
# Header
# =========================================================
st.markdown('<div class="main-title">修論テーマ × 教員マッチング UI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">全候補教員を表示し、重み変更・一致ワード表示に対応した版です。</div>',
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
    show_full_data = st.checkbox("全体データを表示", value=False)

    st.markdown("---")
    st.subheader("重み変更")
    st.caption("theme / field のみを重み変更します。一致ボーナスは重み対象に含めず、そのまま加点します。")

    weight_theme = st.number_input(
        "テーマ類似重み (theme_score)",
        min_value=0.0,
        max_value=10.0,
        value=0.45,
        step=0.05,
        format="%.2f",
    )
    weight_field = st.number_input(
        "分野類似重み (field_score)",
        min_value=0.0,
        max_value=10.0,
        value=0.25,
        step=0.05,
        format="%.2f",
    )

    use_reweighted_total = st.checkbox(
        "この画面では再計算した total_score を使う",
        value=True,
    )


# =========================================================
# Selected student
# =========================================================
student_scores = scores[scores[score_student_col] == selected_student].copy()

if student_scores.empty:
    st.warning("この学生の候補データがありません。")
    st.stop()

student_info_df = students_df[students_df[student_name_col] == selected_student]
committee_key_col = first_existing(committee_df, ["student_name", "name"], "student_name")
committee_info_df = committee_df[committee_df[committee_key_col] == selected_student]

if student_info_df.empty or committee_info_df.empty:
    st.warning("学生情報または委員会情報が見つかりません。")
    st.stop()

student_info = student_info_df.iloc[0]
committee_info = committee_info_df.iloc[0]


# =========================================================
# Recompute total score
# =========================================================
weights_raw = {
    "theme_score": float(weight_theme),
    "field_score": float(weight_field),
}
weights_norm = normalize_weights(weights_raw)

student_scores["theme_score_f"] = ensure_numeric(student_scores, "theme_score")
student_scores["field_score_f"] = ensure_numeric(student_scores, "field_score")
student_scores["exact_bonus_f"] = ensure_numeric(student_scores, "exact_bonus")

student_scores["total_score_reweighted"] = (
    student_scores["theme_score_f"] * weights_norm["theme_score"]
    + student_scores["field_score_f"] * weights_norm["field_score"]
    + student_scores["exact_bonus_f"]
)

if use_reweighted_total:
    student_scores["display_total_score"] = student_scores["total_score_reweighted"]
else:
    student_scores["display_total_score"] = ensure_numeric(student_scores, "total_score")

student_scores = student_scores.sort_values(
    by=["display_total_score", score_teacher_col] if score_teacher_col in student_scores.columns else ["display_total_score"],
    ascending=[False, True] if score_teacher_col in student_scores.columns else [False],
).reset_index(drop=True)

student_scores["display_rank"] = student_scores.index + 1


# =========================================================
# Exact matched words
# =========================================================
student_fields = get_fields_from_row(student_info)

teacher_lookup: dict[str, pd.Series] = {}
for _, row in teachers_df.iterrows():
    teacher_lookup[safe_str(row.get(teacher_name_col)).strip()] = row

matched_words_col: list[str] = []
matched_count_col: list[int] = []

for _, srow in student_scores.iterrows():
    teacher_name = safe_str(srow.get(score_teacher_col)).strip()
    teacher_row = teacher_lookup.get(teacher_name)
    teacher_fields = get_fields_from_row(teacher_row) if teacher_row is not None else []
    matched_words = compute_exact_matches(student_fields, teacher_fields)
    matched_words_col.append(" / ".join(matched_words))
    matched_count_col.append(len(matched_words))

student_scores["matched_words"] = matched_words_col
student_scores["matched_count"] = matched_count_col


# =========================================================
# Top metrics
# =========================================================
total_students = len(student_names)
total_teachers = (
    teachers_df[teacher_name_col].dropna().astype(str).nunique()
    if teacher_name_col in teachers_df.columns
    else len(teachers_df)
)
candidate_count = len(student_scores)

m1, m2, m3 = st.columns(3)
with m1:
    render_metric_card("学生数", total_students, "推薦対象の学生")
with m2:
    render_metric_card("教員数", total_teachers, "候補教員データ")
with m3:
    render_metric_card("表示候補数", candidate_count, f"{selected_student} さん向け（全件表示）")


# =========================================================
# Weight summary
# =========================================================
st.markdown('<div class="weight-box">', unsafe_allow_html=True)
st.markdown('<div class="section-title" style="margin-top:0;">現在の重み / Current Weights</div>', unsafe_allow_html=True)
st.write(
    f"theme = **{weights_norm['theme_score']:.3f}** / "
    f"field = **{weights_norm['field_score']:.3f}**"
)
st.write("一致ボーナスは **重み付けせずにそのまま加点** します。")
st.caption("再計算式: weighted(theme, field) + exact_bonus")
st.markdown("</div>", unsafe_allow_html=True)


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

    st.markdown('<div class="label">研究分野タグ</div>', unsafe_allow_html=True)
    render_tags(student_fields)

    st.markdown("</div>", unsafe_allow_html=True)

with right_top:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">Recommended Committee</div>', unsafe_allow_html=True)

    render_field("主指導教員", value_from_row(committee_info, ["main_advisor"]))
    render_field("副指導教員1", value_from_row(committee_info, ["sub_advisor_1"]))
    render_field("副指導教員2", value_from_row(committee_info, ["sub_advisor_2"]))

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Results list
# =========================================================
st.markdown('<div class="section-title">候補一覧 / Results List（全件表示）</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="small-note">一致ワード列を追加しています。一致ボーナスは重み付けせず、そのまま加点しています。</div>',
    unsafe_allow_html=True,
)

display_df = student_scores.copy()
display_df["total_score"] = display_df["display_total_score"]

display_cols = [
    "display_rank",
    "teacher_name",
    "total_score",
    "theme_score",
    "field_score",
    "exact_bonus",
    "matched_count",
    "matched_words",
]
existing_cols = [c for c in display_cols if c in display_df.columns]

column_config = {}
if "display_rank" in existing_cols:
    column_config["display_rank"] = st.column_config.NumberColumn("順位", format="%d")
if "teacher_name" in existing_cols:
    column_config["teacher_name"] = st.column_config.TextColumn("教員名", width="medium")
if "total_score" in existing_cols:
    column_config["total_score"] = st.column_config.NumberColumn("総合スコア", format="%.4f")
if "theme_score" in existing_cols:
    column_config["theme_score"] = st.column_config.NumberColumn("テーマ類似", format="%.4f")
if "field_score" in existing_cols:
    column_config["field_score"] = st.column_config.NumberColumn("分野類似", format="%.4f")
if "exact_bonus" in existing_cols:
    column_config["exact_bonus"] = st.column_config.NumberColumn("一致ボーナス", format="%.4f")
if "matched_count" in existing_cols:
    column_config["matched_count"] = st.column_config.NumberColumn("一致数", format="%d")
if "matched_words" in existing_cols:
    column_config["matched_words"] = st.column_config.TextColumn("一致ワード", width="large")

st.dataframe(
    display_df[existing_cols],
    use_container_width=True,
    hide_index=True,
    height=720,
    column_config=column_config,
)

csv_download = display_df[existing_cols].to_csv(index=False).encode("utf-8-sig")
st.download_button(
    label="この学生の全候補一覧をCSVでダウンロード",
    data=csv_download,
    file_name=f"{selected_student}_all_candidates.csv",
    mime="text/csv",
)


# =========================================================
# Teacher detail selector
# =========================================================
st.markdown('<div class="section-title">候補教員の詳細 / Teacher Detail</div>', unsafe_allow_html=True)

teacher_options = display_df[score_teacher_col].dropna().astype(str).tolist()
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
teacher_fields_selected = get_fields_from_row(teacher_info)
matched_words_selected = compute_exact_matches(student_fields, teacher_fields_selected)

selected_teacher_score_df = display_df[display_df[score_teacher_col].astype(str) == str(selected_teacher)]
selected_teacher_score = selected_teacher_score_df.iloc[0] if not selected_teacher_score_df.empty else None


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

    st.markdown('<div class="label">研究分野タグ</div>', unsafe_allow_html=True)
    render_tags(teacher_fields_selected)

    st.markdown("</div>", unsafe_allow_html=True)

with detail_right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="pill">Score Breakdown</div>', unsafe_allow_html=True)

    if selected_teacher_score is not None:
        render_field("順位", int(selected_teacher_score["display_rank"]))
        render_field("総合スコア", f'{float(selected_teacher_score["display_total_score"]):.4f}')
        render_field("テーマ類似", f'{float(selected_teacher_score["theme_score_f"]):.4f}')
        render_field("分野類似", f'{float(selected_teacher_score["field_score_f"]):.4f}')
        render_field("一致ボーナス", f'{float(selected_teacher_score["exact_bonus_f"]):.4f}')
        render_field("一致ワード", " / ".join(matched_words_selected) if matched_words_selected else "なし")
    else:
        render_field("順位", "なし")
        render_field("総合スコア", "なし")

    st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="card-soft">', unsafe_allow_html=True)
st.markdown('<div class="section-title" style="margin-top:0;">External / TRIOS-based Information</div>', unsafe_allow_html=True)

info_col1, info_col2 = st.columns(2)
with info_col1:
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
    render_field("研究課題", value_from_row(teacher_info, ["trios_topics"]))

with info_col2:
    render_field("論文タイトル", value_from_row(teacher_info, ["trios_papers"]))
    render_field("過去修論テーマ", value_from_row(teacher_info, ["past_thesis_titles"]))

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