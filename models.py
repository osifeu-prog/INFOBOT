from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id        = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    phone     = Column(String, nullable=True)
    is_admin  = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Shop(Base):
    __tablename__ = "shops"
    id        = Column(Integer, primary_key=True)
    owner_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    name      = Column(String, unique=True, nullable=False)
    full_access = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    cards     = relationship("Card", back_populates="shop")

class Card(Base):
    __tablename__ = "cards"
    id        = Column(Integer, primary_key=True)
    shop_id   = Column(Integer, ForeignKey("shops.id"), nullable=False)
    title     = Column(String, nullable=False)
    image_file = Column(String, nullable=False)  # שבילה בדיסק/שירות ענן
    price     = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    shop      = relationship("Shop", back_populates="cards")

class Purchase(Base):
    __tablename__ = "purchases"
    id        = Column(Integer, primary_key=True)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_id   = Column(Integer, ForeignKey("cards.id"), nullable=False)
    token     = Column(String, unique=True, nullable=False)
    amount    = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Score(Base):
    __tablename__ = "scores"
    id        = Column(Integer, primary_key=True)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    kisses    = Column(Integer, default=0)
    hugs      = Column(Integer, default=0)
    contracts = Column(Integer, default=0)
    # ניתן להוסיף נוסחה לחישוב “ערך” כללי
