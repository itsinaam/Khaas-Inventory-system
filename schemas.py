from pydantic import BaseModel, computed_field
from datetime import datetime
from typing import Optional

class InventoryBase(BaseModel):
    name: str
    category: str
    quantity_received: int
    units: Optional[str] = None
    cost: Optional[str] = None
    expiry_date: Optional[datetime] = None

class InventoryCreate(InventoryBase):
    pass

class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity_received: Optional[int] = None
    units: Optional[str] = None
    cost: Optional[str] = None
    expiry_date: Optional[datetime] = None

class InventoryResponse(InventoryBase):
    id: int
    created_at: datetime

    @computed_field
    @property
    def status(self) -> str:
        """Calculate stock status based on quantity"""
        if self.quantity_received == 0:
            return "Out of Stock"
        elif self.quantity_received < 10:
            return "Low Stock"
        else:
            return "In Stock"

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserCreateRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: str = "user"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreateResponse(UserResponse):
    generated_password: str
