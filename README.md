# 修論指導委員マッチングシステム

学生の修論テーマと、教員の

- TRIOS 情報
- 過去の修論テーマ
- 自動推定した研究分野

を使って、**主指導教員 1 名 + 副指導教員 2 名** を推薦するプロジェクトです。

## 今回の版で変えたこと
- `select_teacher_excel.bat` または `select_student_excel.bat` の**どちらか片方だけ更新**しても実行できます。
- 更新していない側は、`incoming/` に保存されている**前回の最新 Excel** をそのまま再利用します。
- `run_pipeline.bat` は使わない前提に整理しました。
- 類似度計算は bat から **`committee_matching.pipeline` を直接実行**します。
- GitHub は次のリポジトリを使う前提に更新しました。  
  `https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git`
- まずは **Streamlit Community Cloud** で結果閲覧する前提にしました。
- PDF から抽出したサンプル入力を `sample_inputs/` に追加しました。

## 最初にやること
### 1. zip を展開
任意のフォルダに展開してください。

### 2. 初回セットアップ
`setup_first_time.bat` を実行してください。  
Python 仮想環境 `.venv` を作成し、必要ライブラリを入れます。

### 3. GitHub の最初の push
この zip を展開したフォルダで、次のどちらかを行います。

#### 方法 A: bat でまとめて実行
`setup_github_first_push.bat`

#### 方法 B: 手動で実行
```bash
git init
git branch -M main
git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

## 日々の使い方
### 教員 Excel を更新したとき
`select_teacher_excel.bat`

- 選んだファイルは `incoming/teachers_latest.xlsx` に保存されます。
- `incoming/students_latest.xlsx` が既にあれば、**その前回版を再利用して**自動計算します。

### 学生 Excel を更新したとき
`select_student_excel.bat`

- 選んだファイルは `incoming/students_latest.xlsx` に保存されます。
- `incoming/teachers_latest.xlsx` が既にあれば、**その前回版を再利用して**自動計算します。

### 結果を GitHub / Streamlit Cloud に反映したいとき
`push_updates.bat`

## Streamlit Community Cloud で見る
- GitHub に push
- Streamlit Community Cloud でこのリポジトリを選択
- Main file path は `streamlit_app.py`

詳しくは `docs/streamlit_cloud_setup.md` を見てください。

## 入力
### 教員 Excel
最低限必要な列
- `teacher_name`

あると使う列
- `department`
- `position`
- `trios_url`
- `manual_research_fields`

### 学生 Excel
最低限必要な列
- `student_name`
- `thesis_title`

あると使う列
- `department`
- `manual_research_fields`

## 出力
`generated/` に次が出ます。
- `teachers_enriched.xlsx`
- `students_enriched.xlsx`
- `committee_recommendations.xlsx`
- `student_teacher_similarity_detailed.xlsx`
- `teacher_teacher_similarity.xlsx`
- `student_teacher_scores_long.csv`
- `pipeline_status.json`

## スコアの考え方
総合スコアは次を混ぜています。
- 研究分野同士の類似度
- 学生の修論テーマ vs 教員の TRIOS / 過去修論テーマ の意味類似度
- TF-IDF の文字 n-gram 類似度
- 研究分野ラベルの exact match 加点
- 同一専攻内で差がつきやすいようにする z-score 補正

さらに、推薦する 3 名が似すぎないように、教員間の類似度を使って副指導候補に多様化ペナルティを入れています。

## 同じ専攻で似た研究が多い場合への対策
E5 だけではなく、次を混ぜています。

- lexical 類似度
- exact match
- cohort 内正規化
- MMR による委員会多様化

理由は `docs/model_options.md` に整理しています。

## 差し替え箇所
検索しやすいように、未設定の箇所は次の形にしています。

```text
！！！！！！！！！！
ここに入れる
！！！！！！！！！！
```

## 注意
- TRIOS 側の HTML 構造が変わった場合は `committee_matching/trios.py` のセレクタを調整してください。
- 過去の修論テーマは `data_sources/masters_thesis_history.xlsx` または `data_sources/masters_thesis_history.csv` を置くと自動で使います。
- `sample_inputs/` には今回の PDF から抽出したサンプル Excel を入れています。
- Streamlit Cloud は **表示用** と割り切り、重い類似度計算はローカル PC 側で回す運用を想定しています。
