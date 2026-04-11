import importlib
import streamlit as st

st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

st.write("streamlit_app.py は起動しています")

try:
    importlib.import_module("app.app")
    st.success("app.app の import は成功しました")
except Exception as exc:
    st.error("app/app.py の import でエラーが発生しました。")
    st.exception(exc)