# MPPS / MSE 学生-教員 類似度マッチングシステム

この版は、元の zip の UI / GitHub 運用をベースにしつつ、次を追加した版です。

- MPPS と MSE を別グループとして扱う
- MPPS の学生は MPPS の教員、MSE の学生は MSE の教員だけと比較する
- `所属` が `MPPS / MSE` の教員は両グループに含める
- 学生入力は `M1_MPPS_MSE_2024.xlsx` 形式を直接使用
- 教員入力は `指導教員一覧_2025.xlsx` 形式を直接使用
- `MPPS_MSE_2021-2024.xlsx` を `data_sources/master_title.xlsx` として保持し、後から CSV / Excel を追記できる
- UI からファイルをアップロードして、その場で類似度計算を実行できる
- `incoming/` と `generated/` を GitHub に push する UI ボタンを追加

## 類似度計算

### 学生側入力
- タイトル
- 概要分野
- 研究内容
- 研究分野
- 細かい研究分野（タイトル / 研究内容から自動推定）

### 教員側入力
- TRIOS 情報
- 担当タイトル（`master_title.xlsx` から集約）
- 大まかな研究分野（TRIOS / 担当タイトルから推定）
- 細かい研究分野（TRIOS / 担当タイトルから推定）

### スコア分割
- 分野類似度: 学生の `概要分野 + 研究分野 + 細かい研究分野` と、教員の `大まかな研究分野 + 細かい研究分野`
- 研究内容類似度: 学生の `タイトル + 研究内容` と、教員の `TRIOS情報 + 担当タイトル`

`config/app_config.json` の既定値では、分野 0.5 / 研究内容 0.5 で合成します。

## 主なファイル

- `incoming/students_latest.xlsx`
- `incoming/teachers_latest.xlsx`
- `data_sources/master_title.xlsx`
- `generated/students_enriched.xlsx`
- `generated/teachers_enriched.xlsx`
- `generated/committee_recommendations.xlsx`
- `generated/student_teacher_similarity_detailed.xlsx`
- `generated/student_teacher_scores_long.csv`

## UI

`streamlit_app.py` を起動すると、次ができます。

- MPPS / MSE 切り替え表示
- 学生ファイル / 教員ファイルのアップロード
- `master_title` への追加ファイルアップロード
- アップロード内容で即時計算
- 生成結果の閲覧とダウンロード
- GitHub への commit / push 実行

## GitHub Actions

`.github/workflows/process_matching.yml` は次の更新で再計算します。

- `incoming/teachers_latest.xlsx`
- `incoming/students_latest.xlsx`
- `data_sources/master_title.xlsx`

## 補足

- TRIOS 取得は実行環境のネットワークに依存します。
- この環境では GitHub への実 push と Actions 実行確認まではしていません。
- TRIOS が取得できない場合でも、担当タイトルベースで継続できるようにしています。
