from fastapi import FastAPI, Depends
from database import AsyncSessionLocal
from models import User, Shop, Card, Purchase, Score
from sqlalchemy.future import select

app = FastAPI(title="NFTII Exchange Dashboard")

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/admin/shops")
async def list_shops(session=Depends(get_session)):
    result = await session.execute(select(Shop))
    shops = result.scalars().all()
    return [{"id": s.id, "name": s.name, "owner_id": s.owner_id} for s in shops]

@app.get("/admin/purchases")
async def list_purchases(session=Depends(get_session)):
    result = await session.execute(select(Purchase))
    ps = result.scalars().all()
    return [{"user_id": p.user_id, "card_id":p.card_id, "token":p.token, "amount":p.amount} for p in ps]

@app.get("/leaderboard")
async def leaderboard(session=Depends(get_session)):
    result = await session.execute(select(User))
    users = result.scalars().all()
    # בניית דירוג על פי סכום הרכישות
    ranking = []
    for u in users:
        total = await session.execute(select(Purchase).where(Purchase.user_id==u.id))
        amt = sum(p.amount for p in total.scalars().all())
        ranking.append({"user_id":u.telegram_id, "total_spent":amt})
    ranking.sort(key=lambda x: x["total_spent"], reverse=True)
    return ranking
