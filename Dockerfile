FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# אופציונלי: דיבג – בדקו שהתוכן הגיע באמת לתוך /app
RUN ls -al /app

# ENTRYPOINT ו-CMD מדויקים
ENTRYPOINT ["python3", "main.py"]
