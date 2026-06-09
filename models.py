from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()



class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    category = Column(String(255), nullable=False, default="")
    quantity_received = Column(Integer, nullable=False, default=0)
    units = Column(String(255))
    cost = Column(String(255))
    expiry_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(255), nullable=False)
    product_photo = Column(String(1000), nullable=True)  # URL to Supabase image
    product_category = Column(String(255), nullable=False)
    product_price = Column(Float, nullable=False)
    initial_stock = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)