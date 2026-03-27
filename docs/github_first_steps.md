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
