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


def value_from_row(row: pd.Series | None, candidates: list[str], default: str = "") -> str:
    if row is None:
        return default
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


def get_fields_from_row(row: pd.Series | None) -> list[str]:
    if row is None:
        return []
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


def compute_exact_matches(base_fields: Iterable[str], other_fields: Iterable[str]) -> list[str]:
    other_map: dict[str, str] = {}
    for item in other_fields:
        key = normalize_text_token(item)
        if key and key not in other_map:
            other_map[key] = safe_str(item).strip()

    matches: list[str] = []
    seen = set()
    for item in base_fields:
        key = normalize_text_token(item)
        if key and key in other_map and key not in seen:
            matches.append(other_map[key] or safe_str(item).strip())
            seen.add(key)
    return matches


def render_tags(tags: list[str]) -> None:
    if not tags:
        st.markdown('<div class="value">なし</div>', unsafe_allow_html=True)
        return
    html = "".join(f'<span class="tag">{safe_str(tag)}</span>' for tag in tags)
    st.markdown(html, unsafe_allow_html=True)


def build_row_lookup(df: pd.DataFrame, name_col: str) -> dict[str, pd.Series]:
    lookup: dict[str, pd.Series] = {}
    if name_col not in df.columns:
        return lookup
    for _, row in df.iterrows():
        lookup[safe_str(row.get(name_col)).strip()] = row
    return lookup


def prepare_scores(
    score_df: pd.DataFrame,
    name_col: str,
    counterpart_lookup: dict[str, pd.Series],
    base_fields: list[str],
    weights_norm: dict[str, float],
    use_reweighted_total: bool,
) -> pd.DataFrame:
    out = score_df.copy()

    out["theme_score_f"] = ensure_numeric(out, "theme_score")
    out["field_score_f"] = ensure_numeric(out, "field_score")
    out["exact_bonus_f"] = ensure_numeric(out, "exact_bonus")

    out["total_score_reweighted"] = (
        out["theme_score_f"] * weights_norm["theme_score"]
        + out["field_score_f"] * weights_norm["field_score"]
        + out["exact_bonus_f"]
    )

    if use_reweighted_total:
        out["display_total_score"] = out["total_score_reweighted"]
    else:
        out["display_total_score"] = ensure_numeric(out, "total_score")

    matched_words_col: list[str] = []
    matched_count_col: list[int] = []
    for _, row in out.iterrows():
        counterpart_name = safe_str(row.get(name_col)).strip()
        counterpart_row = counterpart_lookup.get(counterpart_name)
        counterpart_fields = get_fields_from_row(counterpart_row)
        matched_words = compute_exact_matches(base_fields, counterpart_fields)
        matched_words_col.append(" / ".join(matched_words))
        matched_count_col.append(len(matched_words))

    out["matched_words"] = matched_words_col
    out["matched_count"] = matched_count_col

    sort_cols = ["display_total_score"]
    ascending = [False]
    if name_col in out.columns:
        sort_cols.append(name_col)
        ascending.append(True)

    out = out.sort_values(by=sort_cols, ascending=ascending).reset_index(drop=True)
    out["display_rank"] = out.index + 1
    return out


def get_teacher_role_in_committee(committee_row: pd.Series | None, teacher_name: str) -> str:
    if committee_row is None:
        return "委員会情報なし"
    teacher_name = safe_str(teacher_name).strip()
    if not teacher_name:
        return "なし"
    role_map = {
        "main_advisor": "主指導教員",
        "sub_advisor_1": "副指導教員1",
        "sub_advisor_2": "副指導教員2",
    }
    for col, label in role_map.items():
        if safe_str(committee_row.get(col)).strip() == teacher_name:
            return label
    return "委員会候補外"


def render_teacher_external_info(teacher_info: pd.Series) -> None:
    st.markdown('<div class="card-soft">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title" style="margin-top:0;">External / TRIOS-based Information</div>',
        unsafe_allow_html=True,
    )

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
# Header
# =========================================================
st.markdown('<div class="main-title">修論テーマ × 教員マッチング UI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">学生→教員推薦と、教員→学生一覧の両方に対応した版です。</div>',
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
committee_key_col = first_existing(committee_df, ["student_name", "name"], "student_name")

if score_student_col not in scores.columns:
    st.error("scores データに student_name 列が見つかりません。")
    st.stop()
if score_teacher_col not in scores.columns:
    st.error("scores データに teacher_name 列が見つかりません。")
    st.stop()

student_names = sorted(scores[score_student_col].dropna().astype(str).unique().tolist())
teacher_names = sorted(scores[score_teacher_col].dropna().astype(str).unique().tolist())

if not student_names:
    st.warning("推薦対象の学生データがまだありません。")
    st.stop()
if not teacher_names:
    st.warning("推薦対象の教員データがまだありません。")
    st.stop()

student_lookup = build_row_lookup(students_df, student_name_col)
teacher_lookup = build_row_lookup(teachers_df, teacher_name_col)
committee_lookup = build_row_lookup(committee_df, committee_key_col)


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.header("表示設定")

    view_mode = st.radio(
        "表示モード",
        ["学生から教員を探す", "教員から学生を探す"],
        index=0,
    )

    selected_student = st.selectbox(
        "学生を選択",
        student_names,
        disabled=view_mode != "学生から教員を探す",
    )
    selected_teacher_sidebar = st.selectbox(
        "教員を選択",
        teacher_names,
        disabled=view_mode != "教員から学生を探す",
    )

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

weights_raw = {
    "theme_score": float(weight_theme),
    "field_score": float(weight_field),
}
weights_norm = normalize_weights(weights_raw)


# =========================================================
# Top metrics
# =========================================================
total_students = len(student_names)
total_teachers = len(teacher_names)

m1, m2, m3 = st.columns(3)
with m1:
    render_metric_card("学生数", total_students, "推薦対象の学生")
with m2:
    render_metric_card("教員数", total_teachers, "候補教員データ")
with m3:
    render_metric_card(
        "表示モード",
        "学生→教員" if view_mode == "学生から教員を探す" else "教員→学生",
        "表示対象をサイドバーで切替可能",
    )


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
# Student -> Teacher mode
# =========================================================
if view_mode == "学生から教員を探す":
    student_scores = scores[scores[score_student_col].astype(str) == str(selected_student)].copy()

    if student_scores.empty:
        st.warning("この学生の候補データがありません。")
        st.stop()

    student_info = student_lookup.get(selected_student)
    committee_info = committee_lookup.get(selected_student)

    if student_info is None:
        st.warning("学生情報が見つかりません。")
        st.stop()

    student_fields = get_fields_from_row(student_info)
    student_scores = prepare_scores(
        score_df=student_scores,
        name_col=score_teacher_col,
        counterpart_lookup=teacher_lookup,
        base_fields=student_fields,
        weights_norm=weights_norm,
        use_reweighted_total=use_reweighted_total,
    )

    candidate_count = len(student_scores)
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
        render_field("表示候補数", candidate_count)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">候補一覧 / Results List（教員を全件表示）</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">選択した学生に対して、教員を類似度順に並べています。</div>',
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
        file_name=f"{selected_student}_all_teachers.csv",
        mime="text/csv",
    )

    st.markdown('<div class="section-title">候補教員の詳細 / Teacher Detail</div>', unsafe_allow_html=True)

    teacher_options = display_df[score_teacher_col].dropna().astype(str).tolist()
    selected_teacher_detail = st.selectbox(
        "教員を選択",
        teacher_options,
        key="selected_teacher_detail",
    )

    teacher_info = teacher_lookup.get(selected_teacher_detail)
    if teacher_info is None:
        st.warning("教員詳細が見つかりません。")
        st.stop()

    teacher_fields_selected = get_fields_from_row(teacher_info)
    matched_words_selected = compute_exact_matches(student_fields, teacher_fields_selected)

    selected_teacher_score_df = display_df[
        display_df[score_teacher_col].astype(str) == str(selected_teacher_detail)
    ]
    selected_teacher_score = (
        selected_teacher_score_df.iloc[0] if not selected_teacher_score_df.empty else None
    )

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

    render_teacher_external_info(teacher_info)


# =========================================================
# Teacher -> Student mode
# =========================================================
else:
    teacher_scores = scores[scores[score_teacher_col].astype(str) == str(selected_teacher_sidebar)].copy()

    if teacher_scores.empty:
        st.warning("この教員に対応する学生データがありません。")
        st.stop()

    teacher_info = teacher_lookup.get(selected_teacher_sidebar)
    if teacher_info is None:
        st.warning("教員情報が見つかりません。")
        st.stop()

    teacher_fields = get_fields_from_row(teacher_info)
    teacher_scores = prepare_scores(
        score_df=teacher_scores,
        name_col=score_student_col,
        counterpart_lookup=student_lookup,
        base_fields=teacher_fields,
        weights_norm=weights_norm,
        use_reweighted_total=use_reweighted_total,
    )

    candidate_count = len(teacher_scores)
    st.markdown('<div class="section-title">教員入力データ / Teacher Profile</div>', unsafe_allow_html=True)

    left_top, right_top = st.columns([1.2, 1.25])

    with left_top:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="pill">Teacher Profile</div>', unsafe_allow_html=True)

        render_field("教員名", value_from_row(teacher_info, ["teacher_name", "name"]))
        render_field("所属", value_from_row(teacher_info, ["department", "affiliation"]))
        render_field("職名", value_from_row(teacher_info, ["position", "title"]))
        render_field("研究分野候補", value_from_row(teacher_info, ["research_fields", "research_field"]))

        st.markdown('<div class="label">研究分野タグ</div>', unsafe_allow_html=True)
        render_tags(teacher_fields)

        st.markdown("</div>", unsafe_allow_html=True)

    with right_top:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="pill">Overview</div>', unsafe_allow_html=True)

        render_field("表示学生数", candidate_count)
        render_field("テーマ類似重み", f"{weights_norm['theme_score']:.3f}")
        render_field("分野類似重み", f"{weights_norm['field_score']:.3f}")
        render_field("スコア表示", "再計算 total_score" if use_reweighted_total else "元の total_score")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">学生一覧 / Results List（学生を全件表示）</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="small-note">選択した教員に対して、学生を類似度順に並べています。</div>',
        unsafe_allow_html=True,
    )

    display_df = teacher_scores.copy()
    display_df["total_score"] = display_df["display_total_score"]

    display_cols = [
        "display_rank",
        "student_name",
        "thesis_title",
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
    if "student_name" in existing_cols:
        column_config["student_name"] = st.column_config.TextColumn("学生名", width="medium")
    if "thesis_title" in existing_cols:
        column_config["thesis_title"] = st.column_config.TextColumn("修論テーマ", width="large")
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
        label="この教員に対する全学生一覧をCSVでダウンロード",
        data=csv_download,
        file_name=f"{selected_teacher_sidebar}_all_students.csv",
        mime="text/csv",
    )

    st.markdown('<div class="section-title">候補学生の詳細 / Student Detail</div>', unsafe_allow_html=True)

    student_options = display_df[score_student_col].dropna().astype(str).tolist()
    selected_student_detail = st.selectbox(
        "学生を選択",
        student_options,
        key="selected_student_detail",
    )

    student_info = student_lookup.get(selected_student_detail)
    committee_info = committee_lookup.get(selected_student_detail)

    if student_info is None:
        st.warning("学生詳細が見つかりません。")
        st.stop()

    student_fields = get_fields_from_row(student_info)
    matched_words_selected = compute_exact_matches(teacher_fields, student_fields)

    selected_student_score_df = display_df[
        display_df[score_student_col].astype(str) == str(selected_student_detail)
    ]
    selected_student_score = (
        selected_student_score_df.iloc[0] if not selected_student_score_df.empty else None
    )

    detail_left, detail_right = st.columns(2)

    with detail_left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="pill">Student Information</div>', unsafe_allow_html=True)

        render_field("学生名", value_from_row(student_info, ["student_name", "name"]))
        render_field("所属", value_from_row(student_info, ["department", "affiliation"]))
        render_field("修論テーマ", value_from_row(student_info, ["thesis_title", "theme", "title"]))
        render_field("研究分野候補", value_from_row(student_info, ["research_fields", "research_field", "field"]))

        st.markdown('<div class="label">研究分野タグ</div>', unsafe_allow_html=True)
        render_tags(student_fields)

        st.markdown("</div>", unsafe_allow_html=True)

    with detail_right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="pill">Score Breakdown</div>', unsafe_allow_html=True)

        if selected_student_score is not None:
            render_field("順位", int(selected_student_score["display_rank"]))
            render_field("総合スコア", f'{float(selected_student_score["display_total_score"]):.4f}')
            render_field("テーマ類似", f'{float(selected_student_score["theme_score_f"]):.4f}')
            render_field("分野類似", f'{float(selected_student_score["field_score_f"]):.4f}')
            render_field("一致ボーナス", f'{float(selected_student_score["exact_bonus_f"]):.4f}')
            render_field("一致ワード", " / ".join(matched_words_selected) if matched_words_selected else "なし")
            render_field("委員会での位置づけ", get_teacher_role_in_committee(committee_info, selected_teacher_sidebar))
        else:
            render_field("順位", "なし")
            render_field("総合スコア", "なし")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card-soft">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title" style="margin-top:0;">Selected Student Committee / Recommendation Context</div>',
        unsafe_allow_html=True,
    )
    ctx_col1, ctx_col2 = st.columns(2)
    with ctx_col1:
        render_field("主指導教員", value_from_row(committee_info, ["main_advisor"]))
        render_field("副指導教員1", value_from_row(committee_info, ["sub_advisor_1"]))
        render_field("副指導教員2", value_from_row(committee_info, ["sub_advisor_2"]))
    with ctx_col2:
        render_field("この教員の位置づけ", get_teacher_role_in_committee(committee_info, selected_teacher_sidebar))
        render_field("選択中の教員", selected_teacher_sidebar)
    st.markdown("</div>", unsafe_allow_html=True)

    render_teacher_external_info(teacher_info)


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