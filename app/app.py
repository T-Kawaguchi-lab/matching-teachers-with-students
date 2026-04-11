from __future__ import annotations

import json
import subprocess
from pathlib import Path

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

    required_cols = {"group", "student_name"}
    if not required_cols.issubset(df.columns):
        return pd.DataFrame()

    return df


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


def main() -> None:
    st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

    st.markdown(
        """
<style>
.block-container {max-width: 1500px; padding-top: 1.2rem;}
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
        "TRIOS情報・担当タイトル・研究分野から教員側を作成します。"
        "MPPS と MSE は UI 上で切り替えて確認できます。"
    )

    status = load_status()
    selected_group = st.segmented_control("表示グループ", options=["MPPS", "MSE"], default="MPPS")

    with st.sidebar:
        st.header("入力ファイルの更新")

        student_upload = st.file_uploader("M1_MPPS_MSE_2024", type=["xlsx"])
        teacher_upload = st.file_uploader("指導教員一覧_2025", type=["xlsx"])

        if st.button("保存", width="stretch"):
            save_upload(student_upload, STUDENT_FILE)
            save_upload(teacher_upload, TEACHER_FILE)
            st.success("保存しました")

        if st.button("類似度計算", width="stretch", type="primary"):
            try:
                result = run_pipeline(ROOT_DIR)
                st.success("完了")
                st.json(result)
            except Exception as e:
                st.exception(e)

    try:
        rec_df = get_group_df_from_excel(RECOMMEND_XLSX, selected_group)
        if not rec_df.empty:
            st.dataframe(rec_df, width="stretch")

        scores_df = safe_read_scores_csv(SCORES_CSV)
        if not scores_df.empty:
            scores_df = scores_df[scores_df["group"] == selected_group]
            st.dataframe(scores_df, width="stretch")

    except Exception as e:
        st.error("表示エラー")
        st.exception(e)


if __name__ == "__main__":
    main()