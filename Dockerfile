FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m src.build_all
ENV REVIEW_DB_PATH=/data/reviews.sqlite3
ENV QA_DB_PATH=/data/qa_controls.sqlite3
EXPOSE 7860
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.port=7860", "--server.headless=true", "--browser.gatherUsageStats=false"]
