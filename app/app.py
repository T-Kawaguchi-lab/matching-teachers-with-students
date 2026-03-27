from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT_DIR / 'generated'
SCORES_CSV = GENERATED_DIR / 'student_teacher_scores_long.csv'
COMMITTEE_XLSX = GENERATED_DIR / 'committee_recommendations.xlsx'
TEACHERS_XLSX = GENERATED_DIR / 'teachers_enriched.xlsx'
STUDENTS_XLSX = GENERATED_DIR / 'students_enriched.xlsx'
STATUS_JSON = GENERATED_DIR / 'pipeline_status.json'

st.set_page_config(page_title='修論 指導教員マッチング', layout='wide')
st.title('修論テーマ × 教員マッチング UI')
<<<<<<< HEAD
st.caption('学生の修論テーマ、教員の TRIOS・過去修論テーマ・研究分野を使って主指導 1 名＋副指導 2 名を推薦します。')

if not SCORES_CSV.exists():
    st.warning('まだ generated/student_teacher_scores_long.csv がありません。先に select_teacher_excel.bat または select_student_excel.bat を実行してください。')
    st.stop()

scores = pd.read_csv(SCORES_CSV)
committee_df = pd.read_excel(COMMITTEE_XLSX)
teachers_df = pd.read_excel(TEACHERS_XLSX)
students_df = pd.read_excel(STUDENTS_XLSX)
=======
st.caption('GitHub Actions が生成した最新の教員・学生データと推薦結果を表示します。')
>>>>>>> 5379900 (Initial commit)

status = {}
if STATUS_JSON.exists():
    try:
        status = json.loads(STATUS_JSON.read_text(encoding='utf-8'))
    except Exception:
        status = {}

if status:
<<<<<<< HEAD
    with st.expander('最新実行情報'):
        st.json(status)

=======
    with st.expander('最新実行情報', expanded=True):
        st.json(status)

if not SCORES_CSV.exists():
    st.warning('まだ推薦結果がありません。教員入力と学生入力の両方が GitHub に push されると、GitHub Actions が自動で推薦結果を生成します。')
    if status:
        st.info(status.get('message', '現在は待機中です。'))
    st.stop()

scores = pd.read_csv(SCORES_CSV)
committee_df = pd.read_excel(COMMITTEE_XLSX)
teachers_df = pd.read_excel(TEACHERS_XLSX)
students_df = pd.read_excel(STUDENTS_XLSX)

>>>>>>> 5379900 (Initial commit)
student_names = sorted(scores['student_name'].dropna().unique().tolist())
selected_student = st.sidebar.selectbox('学生を選択', student_names)
rank_limit = st.sidebar.slider('表示件数', 3, 20, 10)

student_scores = scores[scores['student_name'] == selected_student].sort_values('rank').head(rank_limit).copy()
student_info = students_df[students_df['student_name'] == selected_student].iloc[0]
committee_info = committee_df[committee_df['student_name'] == selected_student].iloc[0]

col1, col2 = st.columns([1.3, 1])
with col1:
    st.subheader('学生情報')
    st.write(f"**学生名**: {student_info['student_name']}")
    st.write(f"**修論テーマ**: {student_info['thesis_title']}")
    st.write(f"**研究分野候補**: {student_info['research_fields']}")

    st.subheader('推薦された委員会')
    st.write(f"**主指導教員**: {committee_info['main_advisor']}")
    st.write(f"**副指導教員1**: {committee_info['sub_advisor_1']}")
    st.write(f"**副指導教員2**: {committee_info['sub_advisor_2']}")

with col2:
    st.subheader('上位候補ランキング')
    st.dataframe(
        student_scores[[
            'rank', 'teacher_name', 'total_score', 'theme_score', 'field_score', 'lexical_score', 'exact_bonus'
        ]],
        use_container_width=True,
        hide_index=True,
    )

st.subheader('候補教員の詳細')
selected_teacher = st.selectbox('教員を選択', student_scores['teacher_name'].tolist())
teacher_info = teachers_df[teachers_df['teacher_name'] == selected_teacher].iloc[0]

left, right = st.columns(2)
with left:
    st.write(f"**教員名**: {teacher_info['teacher_name']}")
    st.write(f"**所属**: {teacher_info.get('department', '')}")
    st.write(f"**職名**: {teacher_info.get('position', '')}")
    st.write(f"**研究分野候補**: {teacher_info.get('research_fields', '')}")
with right:
    st.write(f"**TRIOS URL**: {teacher_info.get('trios_url', '')}")
    st.write(f"**TRIOS 取得状態**: {teacher_info.get('trios_status', '')}")
    st.write(f"**過去修論テーマ**: {teacher_info.get('past_thesis_titles', '')}")

st.subheader('TRIOS由来の情報')
st.write(f"**研究課題**: {teacher_info.get('trios_topics', '')}")
st.write(f"**論文タイトル**: {teacher_info.get('trios_papers', '')}")

with st.expander('全体データを確認する'):
    st.write('教員データ')
    st.dataframe(teachers_df, use_container_width=True)
    st.write('学生データ')
    st.dataframe(students_df, use_container_width=True)
