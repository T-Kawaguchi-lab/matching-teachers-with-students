import streamlit as st

st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

try:
    from app.app import *
except Exception as exc:
    st.error("app/app.py の import でエラーが発生しました。")
    st.exception(exc)