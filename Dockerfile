FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# לבדיקת העתקת כל הקבצים
RUN ls -al /app

# ENTRYPOINT להרצת כל שני הסקריפטים יחד
ENTRYPOINT ["sh", "-c", "python main.py & python bot_manager.py"]
