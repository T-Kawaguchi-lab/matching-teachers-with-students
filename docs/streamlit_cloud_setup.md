# Streamlit Community Cloud 設定

## 前提
- GitHub にこのプロジェクトが push 済み
- `generated/` に最新結果が入っている

## 作成手順
1. Streamlit Community Cloud にログイン
2. `New app`
3. Repository:
   `T-Kawaguchi-lab/matching-teachers-with-students`
4. Branch:
   `main`
5. Main file path:
   `streamlit_app.py`

## この運用での考え方
- 類似度計算はローカル PC 側で実行
- GitHub に `generated/` を push
- Streamlit Cloud 側はその結果を表示

## 注意
- `intfloat/multilingual-e5-large` は重いため、Cloud 側で再計算はさせず、表示専用にする方が安定します。
