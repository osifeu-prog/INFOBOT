FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# אתחול DB + הפעלת שירים במקביל
CMD ["sh", "-c", "python -c 'import database, asyncio; asyncio.run(database.init_db())' && uvicorn dashboard:app --host 0.0.0.0 --port 8000 & python bot.py"]
