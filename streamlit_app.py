import streamlit as st
from pathlib import Path

st.set_page_config(page_title="debug", layout="wide")

p = Path(__file__).resolve().parent / "app" / "app.py"

st.write("debug mode")
st.write(f"app.py exists: {p.exists()}")
st.write(f"path: {p}")

if p.exists():
    text = p.read_text(encoding="utf-8", errors="replace")
    st.write("contains def main:", "def main" in text)
    st.code(text[:3000])