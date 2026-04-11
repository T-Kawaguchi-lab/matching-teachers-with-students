import streamlit as st
import traceback

st.set_page_config(page_title="MPPS / MSE 類似度マッチング", layout="wide")

st.write("streamlit_app.py は起動しています")

try:
    from app.app import main
    st.success("app.app の import は成功しました")
except Exception as exc:
    st.error("app.app の import で失敗しました")
    st.code(traceback.format_exc())
    raise

main()