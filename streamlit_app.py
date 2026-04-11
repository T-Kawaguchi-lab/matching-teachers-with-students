import importlib
import streamlit as st

st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

try:
    app_module = importlib.import_module("app.app")
    app_module.main()
except Exception as exc:
    st.error("app.app の読み込みまたは main() 実行でエラーが発生しました。")
    st.exception(exc)