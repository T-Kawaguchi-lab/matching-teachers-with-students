# GitHub / Streamlit Cloud の差し替え箇所

## 1. GitHub
この版では GitHub リポジトリ URL を次に固定しています。

- `https://github.com/T-Kawaguchi-lab/matching-teachers-with-students.git`

変更したくなった場合は、次を置き換えてください。

- `setup_github_first_push.bat`
- `.env.example`
- `docs/github_first_steps.md`

## 2. Streamlit Community Cloud
最初は Streamlit Community Cloud で表示する前提です。  
必要に応じて `.env.example` の次を置き換えてください。

- `STREAMLIT_APP_URL`
- `APP_BASE_URL`

## 3. 置き換える場所が分かるようにしている記号
未設定の箇所は次のようにしています。

```text
！！！！！！！！！！
ここに入れる
！！！！！！！！！！
```

この文字列で検索すれば、差し替え箇所をすぐ見つけられます。
