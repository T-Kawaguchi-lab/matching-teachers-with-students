from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Set

import pandas as pd
import streamlit as st

from committee_matching.config import get_config
from committee_matching.pipeline import run_pipeline, update_master_title_file

ROOT_DIR = Path(__file__).resolve().parents[1]
CFG = get_config()
GENERATED_DIR = ROOT_DIR / str(CFG["generated_dir"])
INCOMING_DIR = ROOT_DIR / "incoming"
DATA_DIR = ROOT_DIR / "data_sources"
TEACHER_FILE = ROOT_DIR / str(CFG["incoming_teacher_excel"])
STUDENT_FILE = ROOT_DIR / str(CFG["incoming_student_excel"])
MASTER_TITLE_FILE = ROOT_DIR / str(CFG["master_title_excel"])
STATUS_JSON = GENERATED_DIR / "pipeline_status.json"
SCORES_CSV = GENERATED_DIR / "student_teacher_scores_long.csv"
RECOMMEND_XLSX = GENERATED_DIR / "committee_recommendations.xlsx"
STUDENTS_XLSX = GENERATED_DIR / "students_enriched.xlsx"
TEACHERS_XLSX = GENERATED_DIR / "teachers_enriched.xlsx"


def save_upload(uploaded_file, target: Path) -> bool:
    if uploaded_file is None:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(uploaded_file.getbuffer())
    return True


def load_status() -> dict:
    if not STATUS_JSON.exists():
        return {}
    try:
        return json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_group_df_from_excel(path: Path, group: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        xls = pd.ExcelFile(path)
        if group in xls.sheet_names:
            return pd.read_excel(path, sheet_name=group)
        if xls.sheet_names:
            return pd.read_excel(path, sheet_name=xls.sheet_names[0])
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def safe_read_scores_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    required_cols = {"group", "student_name", "teacher_name"}
    if not required_cols.issubset(df.columns):
        return pd.DataFrame()

    return df


def filter_internal_columns_for_display(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    if df.empty:
        return df
    hidden = {"content_text", "field_text"}
    if kind == "teacher":
        hidden.add("trios_info")
    cols = [c for c in df.columns if c not in hidden]
    return df[cols].copy()


def run_git_push(message: str) -> str:
    if not (ROOT_DIR / ".git").exists():
        return "git リポジトリが見つかりません。"

    steps = [
        ["git", "add", "incoming", "generated", "data_sources/master_title.xlsx"],
        ["git", "commit", "-m", message],
        ["git", "push"],
    ]

    out = []
    for cmd in steps:
        result = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd)}\n{result.stdout}{result.stderr}".strip())
        if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr).lower():
            break

    return "\n\n".join(out)


def normalize_text_for_match(text: str) -> str:
    if pd.isna(text):
        return ""
    return str(text).replace("　", " ").strip()


def split_exact_match_tokens(text: str) -> Set[str]:
    """
    field_score 用テキストから完全一致判定に使う単語集合を作る。
    部分一致はせず、区切られた語だけを見る。
    """
    if not text:
        return set()

    separators = [",", "，", "、", ";", "；", "\n", "\r", "\t", "|", "/", "／"]
    s = normalize_text_for_match(text)
    for sep in separators:
        s = s.replace(sep, "\n")

    parts = []
    for line in s.split("\n"):
        token = line.strip()
        if token:
            parts.append(token)

    return set(parts)


def get_match_words(student_field_text: str, teacher_field_text: str) -> List[str]:
    """
    field_score に使った単語だけで完全一致を調べる。
    """
    s_tokens = split_exact_match_tokens(student_field_text)
    t_tokens = split_exact_match_tokens(teacher_field_text)

    if not s_tokens or not t_tokens:
        return []

    matched = sorted(s_tokens & t_tokens)
    return matched


def recompute_weighted_scores(
    df: pd.DataFrame,
    field_weight: float,
    content_weight: float,
    per_match_bonus: float = 0.005,
) -> pd.DataFrame:
    out = df.copy()

    fw = float(field_weight)
    cw = float(content_weight)
    weight_sum = fw + cw
    if weight_sum <= 0:
        fw, cw = 0.5, 0.5
    else:
        fw /= weight_sum
        cw /= weight_sum

    field_score = pd.to_numeric(out.get("field_score", 0.0), errors="coerce").fillna(0.0)
    content_score = pd.to_numeric(out.get("content_score", 0.0), errors="coerce").fillna(0.0)

    out["weighted_score_base"] = fw * field_score + cw * content_score

    match_words_list: List[str] = []
    match_bonus_list: List[float] = []

    if "student_field_text" in out.columns and "teacher_field_text" in out.columns:
        for _, row in out.iterrows():
            matched_words = get_match_words(
                str(row.get("student_field_text", "")),
                str(row.get("teacher_field_text", "")),
            )
            match_words_list.append(", ".join(matched_words) if matched_words else "")
            match_bonus_list.append(len(matched_words) * per_match_bonus)
    else:
        match_words_list = [""] * len(out)
        match_bonus_list = [0.0] * len(out)

    out["match_word"] = match_words_list
    out["match_word_bonus"] = match_bonus_list
    out["total_score"] = out["weighted_score_base"] + pd.to_numeric(
        out["match_word_bonus"], errors="coerce"
    ).fillna(0.0)

    return out


def extract_teacher_title_append_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["指導教員", "担当タイトル"])

    if path.suffix.lower() == ".csv":
        src = pd.read_csv(path)
    else:
        src = pd.read_excel(path)

    if src.empty:
        return pd.DataFrame(columns=["指導教員", "担当タイトル"])

    teacher_candidates = ["指導教員", "教員", "担当教員", "teacher_name", "teacher"]
    title_candidates = ["担当タイトル", "タイトル", "修論タイトル", "title"]

    teacher_col = next((c for c in teacher_candidates if c in src.columns), None)
    title_col = next((c for c in title_candidates if c in src.columns), None)

    if teacher_col is None or title_col is None:
        return pd.DataFrame(columns=["指導教員", "担当タイトル"])

    out = src[[teacher_col, title_col]].copy()
    out.columns = ["指導教員", "担当タイトル"]
    out["指導教員"] = out["指導教員"].astype(str).str.strip()
    out["担当タイトル"] = out["担当タイトル"].astype(str).str.strip()
    out = out[(out["指導教員"] != "") & (out["担当タイトル"] != "")]
    out = out.drop_duplicates().reset_index(drop=True)
    return out


def build_student_to_teacher_table(df: pd.DataFrame, selected_student: str) -> pd.DataFrame:
    display_df = df[df["student_name"].astype(str) == str(selected_student)].copy()
    display_df = display_df.sort_values("total_score", ascending=False).reset_index(drop=True)
    display_df.insert(0, "順位", range(1, len(display_df) + 1))

    keep_cols = [
        "順位",
        "teacher_name",
        "total_score",
        "field_score",
        "content_score",
        "match_word",
        "match_word_bonus",
    ]
    display_df = display_df[keep_cols].copy()
    display_df = display_df.rename(
        columns={
            "teacher_name": "教員名",
            "total_score": "total_score",
            "field_score": "field_score",
            "content_score": "content_score",
            "match_word": "match_word",
            "match_word_bonus": "match_word_bonus",
        }
    )
    return display_df


def build_teacher_to_student_table(df: pd.DataFrame, selected_teacher: str) -> pd.DataFrame:
    display_df = df[df["teacher_name"].astype(str) == str(selected_teacher)].copy()
    display_df = display_df.sort_values("total_score", ascending=False).reset_index(drop=True)
    display_df.insert(0, "順位", range(1, len(display_df) + 1))

    keep_cols = [
        "順位",
        "student_name",
        "title",
        "total_score",
        "field_score",
        "content_score",
        "match_word",
        "match_word_bonus",
    ]
    display_df = display_df[keep_cols].copy()
    display_df = display_df.rename(
        columns={
            "student_name": "学生名",
            "title": "学生タイトル",
            "total_score": "total_score",
            "field_score": "field_score",
            "content_score": "content_score",
            "match_word": "match_word",
            "match_word_bonus": "match_word_bonus",
        }
    )
    return display_df


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def main() -> None:
    st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

    st.markdown(
        """
<style>
.block-container {max-width: 1600px; padding-top: 1.2rem;}
.card {border: 1px solid #dde7f3; border-radius: 16px; padding: 16px; background: #fbfdff; margin-bottom: 14px;}
.metric {border: 1px solid #dde7f3; border-radius: 16px; padding: 14px; background: white;}
.small {color:#64748b; font-size:0.9rem;}
.title {font-size:2rem; font-weight:800; margin-bottom:.25rem;}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="title">MPPS / MSE 類似度マッチング UI</div>', unsafe_allow_html=True)
    st.markdown(
        "タイトル・概要分野・研究内容・研究分野・細かい研究分野を使って学生側を作成し、"
        "TRIOS情報・TRIOS研究分野・TRIOS研究キーワード・担当タイトルから教員側を作成します。"
        "MPPS と MSE は UI 上で切り替えて確認できます。"
    )

    status = load_status()
    selected_group = st.segmented_control("表示グループ", options=["MPPS", "MSE"], default="MPPS")

    with st.sidebar:
        st.header("入力ファイルの更新")

        student_upload = st.file_uploader("M1_MPPS_MSE_2024", type=["xlsx"])
        teacher_upload = st.file_uploader("指導教員一覧_2025", type=["xlsx"])
        master_append = st.file_uploader(
            "master_title に追加する CSV / Excel（指導教員・担当タイトル）",
            type=["csv", "xlsx"],
        )

        if st.button("保存", width="stretch"):
            saved = []
            if save_upload(student_upload, STUDENT_FILE):
                saved.append("students_latest.xlsx")
            if save_upload(teacher_upload, TEACHER_FILE):
                saved.append("teachers_latest.xlsx")

            if saved:
                st.success("保存: " + ", ".join(saved))
            else:
                st.info("保存するアップロードがありません。")

        if st.button("master_title に追加", width="stretch"):
            if master_append is None:
                st.info("追加ファイルを選択してください。")
            else:
                try:
                    temp = GENERATED_DIR / f"_append_{master_append.name}"
                    save_upload(master_append, temp)

                    append_df = extract_teacher_title_append_df(temp)
                    if append_df.empty:
                        st.warning("追加対象の列（指導教員・担当タイトル）を読み取れませんでした。")
                    else:
                        append_df.to_excel(temp, index=False)
                        update_master_title_file(ROOT_DIR, temp)
                        st.success(f"master_title.xlsx に {len(append_df)} 件追加しました。")
                except Exception as exc:
                    st.error(f"master_title の更新に失敗しました: {exc}")
                    st.exception(exc)

        if st.button("類似度計算", width="stretch", type="primary"):
            try:
                if student_upload is not None:
                    save_upload(student_upload, STUDENT_FILE)
                if teacher_upload is not None:
                    save_upload(teacher_upload, TEACHER_FILE)
                if master_append is not None:
                    temp = GENERATED_DIR / f"_append_{master_append.name}"
                    save_upload(master_append, temp)

                    append_df = extract_teacher_title_append_df(temp)
                    if not append_df.empty:
                        append_df.to_excel(temp, index=False)
                        update_master_title_file(ROOT_DIR, temp)

                result = run_pipeline(ROOT_DIR)
                st.success("完了")
                st.json(result)
            except Exception as e:
                st.exception(e)

        if st.button("incoming/generated を GitHub に push", width="stretch"):
            try:
                log = run_git_push("Update matching inputs and outputs from UI")
                st.text_area("git 実行ログ", log, height=220)
            except Exception as exc:
                st.error(f"git push に失敗しました: {exc}")
                st.exception(exc)

    try:
        metric_cols = st.columns(4)
        metric_cols[0].markdown(
            f'<div class="metric"><div class="small">現在の表示グループ</div>'
            f'<div style="font-size:1.8rem;font-weight:800">{selected_group}</div></div>',
            unsafe_allow_html=True,
        )
        metric_cols[1].markdown(
            f'<div class="metric"><div class="small">学生数</div>'
            f'<div style="font-size:1.8rem;font-weight:800">{status.get("groups", {}).get(selected_group, {}).get("students", 0)}</div></div>',
            unsafe_allow_html=True,
        )
        metric_cols[2].markdown(
            f'<div class="metric"><div class="small">教員数</div>'
            f'<div style="font-size:1.8rem;font-weight:800">{status.get("groups", {}).get(selected_group, {}).get("teachers", 0)}</div></div>',
            unsafe_allow_html=True,
        )
        metric_cols[3].markdown(
            f'<div class="metric"><div class="small">最終更新</div>'
            f'<div style="font-size:1.1rem;font-weight:700">{status.get("updated_at", "未実行")}</div></div>',
            unsafe_allow_html=True,
        )

        scores_df = safe_read_scores_csv(SCORES_CSV)
        scores_df = (
            scores_df[scores_df["group"].astype(str) == str(selected_group)].copy()
            if not scores_df.empty
            else pd.DataFrame()
        )

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("重み設定")

        colw1, colw2 = st.columns(2)
        field_weight = colw1.slider(
            "field_score の重み",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
        )
        content_weight = colw2.slider(
            "content_score の重み",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
        )

        st.caption("※ 完全一致する語1語につき、総合類似度に +0.005 されます。")
        st.caption("※ 完全一致判定は field_score に使った単語同士のみで行います。")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("類似度計算結果")

        current_display_df = pd.DataFrame()
        current_selected_name = ""
        current_selected_kind = ""

        if not scores_df.empty:
            weighted_scores_df = recompute_weighted_scores(
                scores_df,
                field_weight=field_weight,
                content_weight=content_weight,
                per_match_bonus=0.005,
            )

            display_mode = st.segmented_control(
                "表示方法",
                options=["学生を選んで教員順位を見る", "教員を選んで学生順位を見る"],
                default="学生を選んで教員順位を見る",
                key=f"display_mode_{selected_group}",
            )

            if display_mode == "学生を選んで教員順位を見る":
                student_names = sorted(
                    weighted_scores_df["student_name"].dropna().astype(str).unique().tolist()
                )

                if student_names:
                    selected_student = st.selectbox(
                        "表示する学生を選択",
                        options=student_names,
                        key=f"student_filter_{selected_group}",
                    )

                    display_df = build_student_to_teacher_table(weighted_scores_df, selected_student)
                    current_display_df = display_df.copy()
                    current_selected_name = str(selected_student)
                    current_selected_kind = "student"

                    st.dataframe(
                        display_df,
                        width="stretch",
                        hide_index=True,
                        height=700,
                    )
                else:
                    st.info("表示できる学生がいません。")

            else:
                teacher_names = sorted(
                    weighted_scores_df["teacher_name"].dropna().astype(str).unique().tolist()
                )

                if teacher_names:
                    selected_teacher = st.selectbox(
                        "表示する教員を選択",
                        options=teacher_names,
                        key=f"teacher_filter_{selected_group}",
                    )

                    display_df = build_teacher_to_student_table(weighted_scores_df, selected_teacher)
                    current_display_df = display_df.copy()
                    current_selected_name = str(selected_teacher)
                    current_selected_kind = "teacher"

                    st.dataframe(
                        display_df,
                        width="stretch",
                        hide_index=True,
                        height=700,
                    )
                else:
                    st.info("表示できる教員がいません。")
        else:
            weighted_scores_df = pd.DataFrame()
            st.info("まだ類似度計算結果がありません。")

        st.markdown("</div>", unsafe_allow_html=True)

        lower_left, lower_right = st.columns(2)

        with lower_left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("学生データ（加工後）")
            stu_df = get_group_df_from_excel(STUDENTS_XLSX, selected_group)
            if not stu_df.empty:
                st.dataframe(filter_internal_columns_for_display(stu_df, "student"), width="stretch", hide_index=True)
            else:
                st.info("学生加工データがありません。")
            st.markdown("</div>", unsafe_allow_html=True)

        with lower_right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("教員データ（加工後）")
            tea_df = get_group_df_from_excel(TEACHERS_XLSX, selected_group)
            if not tea_df.empty:
                st.dataframe(filter_internal_columns_for_display(tea_df, "teacher"), width="stretch", hide_index=True)
            else:
                st.info("教員加工データがありません。")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("ダウンロード")

        col1, col2 = st.columns(2)

        if not weighted_scores_df.empty:
            all_csv_bytes = dataframe_to_csv_bytes(weighted_scores_df)
            col1.download_button(
                f"{selected_group} 全件ダウンロード",
                all_csv_bytes,
                file_name=f"{selected_group}_weighted_scores_all.csv",
                mime="text/csv",
                width="stretch",
            )

        if not current_display_df.empty and current_selected_name:
            single_csv_bytes = dataframe_to_csv_bytes(current_display_df)

            if current_selected_kind == "student":
                button_label = f"{current_selected_name} ダウンロード"
                file_name = f"{selected_group}_{current_selected_name}_teachers_ranking.csv"
            else:
                button_label = f"{current_selected_name} ダウンロード"
                file_name = f"{selected_group}_{current_selected_name}_students_ranking.csv"

            col2.download_button(
                button_label,
                single_csv_bytes,
                file_name=file_name,
                mime="text/csv",
                width="stretch",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as e:
        st.error("表示のエラー")
        st.exception(e)


if __name__ == "__main__":
    main()