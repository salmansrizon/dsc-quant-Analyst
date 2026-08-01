"""
Pydantic models for request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional
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
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class MessageResponse(BaseModel):
    message: str


# ─── Watchlist ────────────────────────────────────────────────────────────────

class WatchlistAdd(BaseModel):
    symbol: str


class WatchlistItem(BaseModel):
    symbol: str
    added_at: Optional[str] = None


# ─── Portfolio ────────────────────────────────────────────────────────────────

class PortfolioAdd(BaseModel):
    symbol: str
    # buy_price must be > 0: portfolio_service computes pnl as (LTP - buy_price)
    # / buy_price, so 0 is a division by zero in SQL and a negative price is a
    # nonsense P&L (#62). Reject it at the interface, not deep in a query.
    buy_price: float = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    buy_date: Optional[str] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None


class PortfolioUpdate(BaseModel):
    buy_price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
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


# ─── Subscriptions & bundles (#77, ported from main) ─────────────────────────

class SubscriptionCreate(BaseModel):
    medium: list[str]
    alert_channel: bool
    digest_channel: bool
    alert_cap: int = Field(..., ge=0)
    digest_cadence: str = Field(..., pattern="^(daily|alternate|weekly)$")
    bundle_id: Optional[str] = None


class BundleCreate(BaseModel):
    name: str
    medium: list[str]
    alert_channel: bool
    digest_channel: bool
    alert_cap: int = Field(..., ge=0)
    digest_cadence: str = Field(..., pattern="^(daily|alternate|weekly)$")
    price: float = Field(..., ge=0)


# ─── Notification preferences (#78, ported from main) ────────────────────────

class NotificationPreferences(BaseModel):
    telegram_chat_id: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    web_push_subscription: Optional[str] = None
    channels_enabled: list[str] = []


# ─── Investor profile (#85, personalization spine #84) ───────────────────────

Goal = Literal["income", "growth", "preservation"]
Risk = Literal["low", "med", "high"]
Horizon = Literal["short", "medium", "long"]


class InvestorProfile(BaseModel):
    """The resolved, engine-ready profile the #88 fit engine + #93 recs consume.

    Always non-null: an absent profile resolves to the neutral cold-start object
    (is_default=True), so the engine never branches on None. sector_prefs is the
    parsed rank-ordered list ([0] = top choice), never the stored JSON string.
    """
    goal: Goal
    risk: Risk
    horizon: Horizon
    sector_prefs: list[str] = []
    is_default: bool = False


class ProfileUpdate(BaseModel):
    """What the onboarding quiz / profile editor submits. Enums are validated by
    Pydantic (422 on a bad value); sector_prefs is checked against the live
    sector universe at the route (400)."""
    goal: Goal
    risk: Risk
    horizon: Horizon
    sector_prefs: list[str] = []


# ─── Fit engine (#88, personalization spine #84) ─────────────────────────────

class FitAxis(BaseModel):
    """One explainable dimension of the fit scorecard. `score` is null when the
    metric is missing or meaningless (e.g. negative-equity ROE) — a null axis is
    dropped from the composite, never scored 0 (which would fake-penalize)."""
    axis: str
    score: Optional[float] = None      # 0..100, higher = better on this dimension
    reason: str                        # mandatory human sentence
    weight: float                      # this axis's share of the composite


class FitScore(BaseModel):
    """A stock scored against an investor profile (#88). Framing is always
    'matches your preferences', never advice — the disclaimer rides here.

    `composite` is computed for downstream ranking (feed #89 / recs #91 / nudges
    #93) but is NOT a user-facing headline — the frontend renders axes + reasons
    only (decision C). `scorable` is False below the 2-axis coverage floor, when
    `composite` is None and the scorecard should say so. `weight_caption` is the
    only place the profile->weight tilt surfaces, since the composite is hidden."""
    symbol: str
    composite: Optional[float] = None  # weighted mean over scored axes, 0..100 — internal-only
    scorable: bool = True              # False when <2 axes scored (composite floored to None)
    weight_caption: str = ""           # e.g. "Weighted toward Growth & Stability, from your profile."
    axes: list[FitAxis]
    is_default_profile: bool
    disclaimer: str


# ─── Screener (#71) ───────────────────────────────────────────────────────────

class ScreenerFilter(BaseModel):
    field: str
    op: str
    value: float | str


class ScreenerRequest(BaseModel):
    preset: Optional[str] = None
    filters: Optional[list[ScreenerFilter]] = None
    limit: int = Field(default=500, gt=0, le=500)


class ScreenerResult(BaseModel):
    symbol: str
    sector: Optional[str] = None
    price: Optional[float] = None
    volume: Optional[float] = None
    market_cap: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    dividend_yield: Optional[float] = None


class ScreenerResponse(BaseModel):
    count: int
    results: list[ScreenerResult]


class ScreenerWatchlistAdd(BaseModel):
    symbols: list[str]


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
