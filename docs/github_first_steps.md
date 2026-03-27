
# GitHub 最初の設定手順

## 使うリポジトリ
- `https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git`

## いちばん簡単な流れ
1. この zip を展開
2. `setup_first_time.bat`
3. `setup_github_first_push.bat`

## 手動でやる場合
```bash
git init
git branch -M main
git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

## 2回目以降
Excel 更新 → bat で再計算 → `push_updates.bat`

# GitHub の最初の設定

## 1. この zip を展開
任意の作業フォルダに置きます。OneDrive 外の短いパスを推奨します。

## 2. GitHub リポジトリへ最初の push
まだ空リポジトリなら `setup_github_first_push.bat` を実行します。

内部では次を実行します。
- `git init`
- `git branch -M main`
- `git remote add origin https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git`
- `git add .`
- `git commit -m "Initial commit"`
- `git push -u origin main`

## 3. GitHub Actions を確認
push 後に `Actions` タブで `Process matching inputs and refresh Streamlit outputs` が動くことを確認します。

## 4. 以後の更新
- 教員更新: `select_teacher_excel.bat`
- 学生更新: `select_student_excel.bat`

どちらも **Excel選択 → commit → push** まで自動です。
GitHub Actions がその push を拾って加工と推薦結果生成を行います。