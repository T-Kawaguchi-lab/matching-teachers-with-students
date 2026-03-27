<<<<<<< HEAD
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
=======
# Streamlit Community Cloud の設定

## 1. New app を作成
- GitHub repository: `T-Kawaguchi-lab/matching-teachers-with-students`
- Branch: `main`
- Main file path: `streamlit_app.py`

## 2. URL をメモ
公開 URL が決まったら、プロジェクト直下に `.env` を作り、次を入れます。

```text
STREAMLIT_APP_URL=！！！！！！！！！！
ここに入れる
！！！！！！！！！！
```

## 3. 以後の流れ
- `select_teacher_excel.bat` または `select_student_excel.bat`
- GitHub に push
- GitHub Actions が `generated/` を更新して main に再push
- Streamlit Community Cloud が最新 commit を表示

## 注意
アプリを開いた直後に古い結果のことがあります。その場合は GitHub Actions の完了後に再読み込みしてください。
>>>>>>> 5379900 (Initial commit)
