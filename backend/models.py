"""
Pydantic models for request/response schemas.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ─── Auth ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str = Field(..., min_length=5)
    phone: str = Field(..., min_length=6)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    phone: str
    full_name: str
    role: str
    created_at: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─── Watchlist ────────────────────────────────────────────────────────────────

class WatchlistAdd(BaseModel):
    symbol: str


class WatchlistItem(BaseModel):
    symbol: str
    added_at: Optional[str] = None


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioAdd(BaseModel):
    symbol: str
    buy_price: float
    quantity: int
    buy_date: Optional[str] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


class PortfolioUpdate(BaseModel):
    buy_price: Optional[float] = None
    quantity: Optional[int] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


class PortfolioItem(BaseModel):
    id: str
    symbol: str
    buy_price: float
    quantity: int
    buy_date: Optional[str] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None


# ─── Alerts ───────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    symbol: str
    target_price: float
    direction: str = Field(..., pattern="^(above|below)$")


class AlertItem(BaseModel):
    id: str
    symbol: str
    target_price: float
    direction: str
    is_triggered: bool = False
    triggered_at: Optional[str] = None
    created_at: Optional[str] = None


# ─── Subscriptions ────────────────────────────────────────────────────────────

class SubscriptionCreate(BaseModel):
    medium: list[str]
    alert_channel: bool
    digest_channel: bool
    alert_cap: int
    digest_cadence: str = Field(..., pattern="^(daily|alternate|weekly)$")
    bundle_id: Optional[str] = None


class BundleCreate(BaseModel):
    name: str
    medium: list[str]
    alert_channel: bool
    digest_channel: bool
    alert_cap: int
    digest_cadence: str = Field(..., pattern="^(daily|alternate|weekly)$")
    price: float


# ─── Notification Preferences ─────────────────────────────────────────────────

class NotificationPreferences(BaseModel):
    telegram_chat_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    web_push_subscription: Optional[str] = None
    channels_enabled: list[str] = []
