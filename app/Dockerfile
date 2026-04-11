# 今回の版では Streamlit Community Cloud を先に使うため、Dockerfile は予備として残しています。
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]
