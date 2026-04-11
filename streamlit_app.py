import importlib
import sys
import streamlit as st

# ここでは set_page_config を呼ばない
# app/app.py 側の main() の中で呼ぶ

for name in ["app.app", "app"]:
    if name in sys.modules:
        del sys.modules[name]

try:
    app_module = importlib.import_module("app.app")

    st.write("loaded module:", app_module)
    st.write("module file:", getattr(app_module, "__file__", "no file"))
    st.write("has main:", hasattr(app_module, "main"))
    st.write("dir contains main:", "main" in dir(app_module))

    if not hasattr(app_module, "main"):
        st.error("app.app は読めていますが、main が見つかりません。")
        st.code("\n".join(sorted([x for x in dir(app_module) if not x.startswith("__")])[:200]))
    else:
        app_module.main()

except Exception as exc:
    st.error("app.app の読み込みまたは main() 実行でエラーが発生しました。")
    st.exception(exc)