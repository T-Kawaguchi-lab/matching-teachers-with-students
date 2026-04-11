import importlib
import sys
import streamlit as st

for name in ["app.app", "app"]:
    if name in sys.modules:
        del sys.modules[name]

try:
    app_module = importlib.import_module("app.app")
    app_module.main()
except Exception as exc:
    st.error("app.app の読み込みまたは main() 実行でエラーが発生しました。")
    st.exception(exc)