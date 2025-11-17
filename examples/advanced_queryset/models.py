"""Modelos con relaciones para ejemplo avanzado."""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    """Modelo de usuario con referidos."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación con referidos
    referidos = relationship("Referral", back_populates="user", lazy="dynamic")


class Referral(Base):
    """Modelo de referido."""

    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_email = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación con usuario
    user = relationship("User", back_populates="referidos")


class Order(Base):
    """Modelo de orden."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Integer, nullable=False)  # En centavos
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación con usuario
    user = relationship("User")

