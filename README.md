# 修論指導委員マッチングシステム

学生の修論テーマと、教員の

- TRIOS 情報
- 過去の修論テーマ
- 自動推定した研究分野

を使って、**主指導教員 1 名 + 副指導教員 2 名** を推薦するプロジェクトです。

## 今回の版で変えたこと
- `select_teacher_excel.bat` / `select_student_excel.bat` が **Excel選択 → GitHubへcommit/push** までを一気に行い、GitHub Actions は **対象Excelが更新されたときだけ** 起動します。
- GitHub Actions が、更新された Excel を使って **TRIOS 情報追加・研究分野推定・加工済み Excel 保存** を行います。
- もう片方の入力 Excel が既にリポジトリ内にあれば、そのまま **類似度計算まで自動実行** します。
- GitHub Actions が `generated/` を更新して main に commit するため、**Streamlit Community Cloud はリポジトリ更新後の結果をそのまま表示** できます。
- `run_ui.bat` は **Streamlit Cloud の公開URLを開く** 方式を優先し、URL未設定時のみローカル起動にフォールバックします。
- GitHub リポジトリは次を前提に設定済みです。  
  `https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git`

## 最初にやること
### 1. zip を展開
任意のフォルダに展開してください。

### 2. 初回セットアップ
`setup_first_time.bat` を実行してください。  
Python 仮想環境 `.venv` を作成し、必要ライブラリを入れます。

### 3. GitHub の最初の push
まだリポジトリが空なら、展開したフォルダで `setup_github_first_push.bat` を実行します。

### 4. Streamlit Community Cloud を作成
- GitHub 連携後、このリポジトリを選ぶ
- Main file path は `streamlit_app.py`
- App URL が決まったら `.env` を作って `STREAMLIT_APP_URL=` に入れる

詳しくは `docs/github_first_steps.md` と `docs/streamlit_cloud_setup.md` を見てください。

## 日々の使い方
### 教員 Excel を更新したとき
`select_teacher_excel.bat`

- 教員 Excel を選択
- `incoming/teachers_latest.xlsx` に保存
- GitHub に commit / push
- GitHub Actions が教員の TRIOS 情報・研究分野を更新
- 既に `incoming/students_latest.xlsx` があれば、学生側加工済みデータも使って類似度計算
- Streamlit Cloud で結果確認

### 学生 Excel を更新したとき
`select_student_excel.bat`

- 学生 Excel を選択
- `incoming/students_latest.xlsx` に保存
- GitHub に commit / push
- GitHub Actions が学生の研究分野を更新（修論テーマから本当に当てはまるものだけを厳しめに付与）
- 既に `incoming/teachers_latest.xlsx` があれば、教員側加工済みデータも使って類似度計算
- Streamlit Cloud で結果確認

### 結果を見る
`run_ui.bat`

- `.env` に `STREAMLIT_APP_URL` が入っていれば、そのURLを開きます。
- 未設定ならローカル Streamlit を起動します。

## 処理モード
GitHub Actions は `python -m committee_matching.pipeline --mode auto` を使います。

- 教員だけある → 教員加工だけ実行
- 学生だけある → 学生加工だけ実行
- 両方ある → 推薦結果まで実行

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
- 研究分野ラベルの exact match 加点

さらに、推薦する 3 名が似すぎないように、教員間の類似度を使って副指導候補に多様化ペナルティを入れています。

## 注意
- GitHub Actions で高速に回しやすいように、既定の埋め込みモデルは `intfloat/multilingual-e5-base` にしています。必要なら `config/app_config.json` で変更できます。
- TRIOS 側の HTML 構造が変わった場合は `committee_matching/trios.py` のセレクタを調整してください。
- 過去の修論テーマは `data_sources/masters_thesis_history.xlsx` または `data_sources/masters_thesis_history.csv` を置くと自動で使います。
- Streamlit Cloud は **表示専用**、重い計算は GitHub Actions 側で行う運用です。