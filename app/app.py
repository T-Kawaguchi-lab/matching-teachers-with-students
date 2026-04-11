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
        student_upload = st.file_uploader("M1_MPPS_MSE_2024 をアップロード", type=["xlsx"])
        teacher_upload = st.file_uploader("指導教員一覧_2025 をアップロード", type=["xlsx"])
        master_append = st.file_uploader("master_title に追加する CSV / Excel", type=["csv", "xlsx"])

        col1, col2 = st.columns(2)

        if col1.button("入力ファイルを保存", width="stretch"):
            saved = []
            if save_upload(student_upload, STUDENT_FILE):
                saved.append("students_latest.xlsx")
            if save_upload(teacher_upload, TEACHER_FILE):
                saved.append("teachers_latest.xlsx")

            if saved:
                st.success("保存: " + ", ".join(saved))
            else:
                st.info("保存するアップロードがありません。")

        if col2.button("master_title に追加", width="stretch"):
            if master_append is None:
                st.info("追加ファイルを選択してください。")
            else:
                try:
                    temp = GENERATED_DIR / f"_append_{master_append.name}"
                    save_upload(master_append, temp)
                    update_master_title_file(ROOT_DIR, temp)
                    st.success("master_title.xlsx に追加しました。")
                except Exception as exc:
                    st.error(f"master_title の更新に失敗しました: {exc}")
                    st.exception(exc)

        if st.button("アップロード内容で類似度を計算", width="stretch", type="primary"):
            try:
                if student_upload is not None:
                    save_upload(student_upload, STUDENT_FILE)
                if teacher_upload is not None:
                    save_upload(teacher_upload, TEACHER_FILE)
                if master_append is not None:
                    temp = GENERATED_DIR / f"_append_{master_append.name}"
                    save_upload(master_append, temp)
                    update_master_title_file(ROOT_DIR, temp)

                result = run_pipeline(ROOT_DIR)
                st.success("類似度計算が完了しました。")
                st.json(result)
            except Exception as exc:
                st.error(f"計算に失敗しました: {exc}")
                st.exception(exc)

        if st.button("incoming/generated を GitHub に push", width="stretch"):
            try:
                log = run_git_push("Update matching inputs and outputs from UI")
                st.text_area("git 実行ログ", log, height=220)
            except Exception as exc:
                st.error(f"git push に失敗しました: {exc}")
                st.exception(exc)

        st.markdown("---")
        st.caption(
            "注: GitHub push は実行環境に push 権限がある場合のみ動作します。"
            "GitHub Actions 実行確認まではこの環境ではできません。"
        )

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

        left, right = st.columns([1.1, 1])

        with left:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("推薦結果")
            rec_df = get_group_df_from_excel(RECOMMEND_XLSX, selected_group)
            if not rec_df.empty:
                st.dataframe(rec_df, width="stretch", hide_index=True)
            else:
                st.info("まだ推薦結果がありません。")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("詳細類似度")

            scores_df = safe_read_scores_csv(SCORES_CSV)
            if not scores_df.empty:
                scores_df = scores_df[scores_df["group"].astype(str) == str(selected_group)].copy()

                student_names = ["すべて"]
                if not scores_df.empty:
                    student_names += sorted(scores_df["student_name"].dropna().astype(str).unique().tolist())

                selected_student = st.selectbox(
                    "学生で絞り込み",
                    options=student_names,
                    key=f"student_filter_{selected_group}",
                )

                if selected_student != "すべて":
                    scores_df = scores_df[scores_df["student_name"].astype(str) == str(selected_student)].copy()

                st.dataframe(scores_df, width="stretch", hide_index=True)
            else:
                if SCORES_CSV.exists():
                    st.warning("詳細類似度ファイルは存在しますが、読み込みに失敗したか必要列が不足しています。")
                else:
                    st.info("まだ詳細類似度がありません。")

            st.markdown("</div>", unsafe_allow_html=True)

        with right:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("学生データ（加工後）")
            stu_df = get_group_df_from_excel(STUDENTS_XLSX, selected_group)
            if not stu_df.empty:
                st.dataframe(stu_df, width="stretch", hide_index=True)
            else:
                st.info("学生加工データがありません。")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("教員データ（加工後）")
            tea_df = get_group_df_from_excel(TEACHERS_XLSX, selected_group)
            if not tea_df.empty:
                st.dataframe(tea_df, width="stretch", hide_index=True)
            else:
                st.info("教員加工データがありません。")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("ダウンロード")

        col1, col2, col3 = st.columns(3)
        for col, path, label in [
            (col1, RECOMMEND_XLSX, "committee_recommendations.xlsx"),
            (col2, TEACHERS_XLSX, "teachers_enriched.xlsx"),
            (col3, STUDENTS_XLSX, "students_enriched.xlsx"),
        ]:
            if path.exists():
                col.download_button(
                    label=label,
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )

        if SCORES_CSV.exists():
            st.download_button(
                "student_teacher_scores_long.csv",
                SCORES_CSV.read_bytes(),
                file_name=SCORES_CSV.name,
                mime="text/csv",
                width="stretch",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    except Exception as exc:
        st.error("表示処理でエラーが発生しました。")
        st.exception(exc)


if __name__ == "__main__":
    main()