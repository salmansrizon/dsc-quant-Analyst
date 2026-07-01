from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import create_access_token, verify_password, get_current_user, require_admin
from .models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    WatchlistAdd, PortfolioAdd, PortfolioUpdate, AlertCreate,
    SubscriptionCreate, NotificationPreferences, BundleCreate,
)
from .user_service import (
    create_user, get_user_by_email, get_user_credentials,
    get_user_by_id, list_users, update_user, delete_user,
)
from . import bq_service
from .repositories import watchlist_repo, portfolio_repo, alert_repo, NotFoundError

app = FastAPI(title="DSC Quant Analyst API", version="1.0.0")


@app.exception_handler(NotFoundError)
def not_found_handler(request, exc):
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and "authorization" not in request.headers:
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
        return response


app.add_middleware(CacheControlMiddleware)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(payload: UserCreate):
    try:
        user = create_user(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, user=user)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cred = get_user_credentials(payload.email)
    if not cred or not verify_password(payload.password, cred.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(cred["id"], cred.get("role", "user"))
    return TokenResponse(access_token=token, user=user)


@app.get("/api/auth/me", response_model=UserResponse)
def read_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user


# ── Market Data ──────────────────────────────────────────────────────────────

@app.get("/api/market/summary")
def market_summary():
    return bq_service.market_summary()


@app.get("/api/market/sectors")
def sectors():
    return bq_service.list_sectors()


@app.get("/api/market/sectors/breakdown")
def sectors_breakdown():
    return bq_service.sector_breakdown()


@app.get("/api/market/strength")
def market_strength():
    return bq_service.market_strength()


@app.get("/api/market/extremes")
def extremes(
    metric: str = Query(pattern="^(pe_low|pe_high|director_holding_low|director_holding_high|nav_price_low|nav_price_high)$"),
    limit: int = Query(default=10, le=50),
):
    return bq_service.extremes_leaderboard(metric=metric, limit=limit)


@app.get("/api/market/technical-extremes")
def technical_extremes(
    metric: str = Query(pattern="^(rsi_low|rsi_high|macd_low|macd_high|stochastic_low|stochastic_high)$"),
    limit: int = Query(default=10, le=50),
):
    return bq_service.technical_extremes(metric=metric, limit=limit)


@app.get("/api/market/stocks")
def stocks(sector: str = None, search: str = None, limit: int = Query(default=500, le=5000)):
    return bq_service.list_stocks(sector=sector, search=search, limit=limit)


@app.get("/api/market/stocks/{symbol}")
def stock_detail(symbol: str):
    result = bq_service.get_stock(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return result


@app.get("/api/market/top-movers")
def top_movers(limit: int = Query(default=10, le=50)):
    return bq_service.top_movers(limit=limit)


@app.get("/api/market/leaderboard")
def leaderboard(metric: str = Query(pattern="^(value|gainer|loser|volume|trade)$"), limit: int = Query(default=10, le=50)):
    return bq_service.leaderboard(metric=metric, limit=limit)


@app.get("/api/market/price-history/{symbol}")
def price_history(symbol: str, days: int = Query(default=365, le=1095)):
    return bq_service.price_history(symbol.upper(), days=days)


@app.get("/api/market/announcements")
def announcements(symbol: str = None, limit: int = Query(default=50, le=200)):
    return bq_service.list_announcements(symbol=symbol, limit=limit)


# ── Watchlist ────────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
def watchlist_list(current_user: UserResponse = Depends(get_current_user)):
    return bq_service.get_watchlist(current_user.id)


@app.post("/api/watchlist")
def watchlist_add(payload: WatchlistAdd, current_user: UserResponse = Depends(get_current_user)):
    return bq_service.add_to_watchlist(current_user.id, payload.symbol)


@app.delete("/api/watchlist/{symbol}")
def watchlist_remove(symbol: str, current_user: UserResponse = Depends(get_current_user)):
    watchlist_repo.remove(current_user.id, symbol.upper())
    return {"status": "removed"}


# ── Portfolio ────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio_list(current_user: UserResponse = Depends(get_current_user)):
    return bq_service.get_portfolio(current_user.id)


@app.get("/api/portfolio/summary")
def portfolio_summary(current_user: UserResponse = Depends(get_current_user)):
    return bq_service.portfolio_summary(current_user.id)


@app.post("/api/portfolio")
def portfolio_add(payload: PortfolioAdd, current_user: UserResponse = Depends(get_current_user)):
    return bq_service.add_to_portfolio(current_user.id, payload.model_dump())


@app.put("/api/portfolio/{portfolio_id}")
def portfolio_update(portfolio_id: str, payload: PortfolioUpdate, current_user: UserResponse = Depends(get_current_user)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    portfolio_repo.update(portfolio_id, current_user.id, data)
    return {"status": "updated"}


@app.delete("/api/portfolio/{portfolio_id}")
def portfolio_delete(portfolio_id: str, current_user: UserResponse = Depends(get_current_user)):
    portfolio_repo.delete(portfolio_id, current_user.id)
    return {"status": "deleted"}


# ── Alerts ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def alerts_list(current_user: UserResponse = Depends(get_current_user)):
    return bq_service.get_alerts(current_user.id)


@app.post("/api/alerts")
def alerts_create(payload: AlertCreate, current_user: UserResponse = Depends(get_current_user)):
    return bq_service.create_alert(current_user.id, payload.model_dump())


@app.delete("/api/alerts/{alert_id}")
def alerts_delete(alert_id: str, current_user: UserResponse = Depends(get_current_user)):
    alert_repo.delete(alert_id, current_user.id)
    return {"status": "deleted"}


# ── Subscriptions ────────────────────────────────────────────────────────────

@app.post("/api/subscriptions")
def subscription_create(payload: SubscriptionCreate, current_user: UserResponse = Depends(get_current_user)):
    return bq_service.create_subscription(current_user.id, payload.model_dump())


@app.post("/api/subscriptions/{subscription_id}/transaction")
def subscription_attach_transaction(subscription_id: str, body: dict, current_user: UserResponse = Depends(get_current_user)):
    txn_id = body.get("transaction_id", "").strip()
    if not txn_id:
        raise HTTPException(status_code=400, detail="transaction_id is required")
    return bq_service.attach_transaction_id(subscription_id, txn_id)


@app.get("/api/subscriptions/pricing")
def subscription_pricing():
    return bq_service.get_pricing()


@app.get("/api/admin/subscriptions")
def admin_subscriptions_list(admin: UserResponse = Depends(require_admin)):
    return bq_service.list_subscriptions()


@app.post("/api/admin/bundles")
def admin_create_bundle(payload: BundleCreate, admin: UserResponse = Depends(require_admin)):
    return bq_service.create_bundle(admin.id, payload.model_dump())


@app.get("/api/admin/bundles")
def admin_list_bundles(admin: UserResponse = Depends(require_admin)):
    return bq_service.list_bundles()


@app.put("/api/admin/bundles/{bundle_id}")
def admin_update_bundle(bundle_id: str, payload: BundleCreate, admin: UserResponse = Depends(require_admin)):
    return bq_service.update_bundle(bundle_id, payload.model_dump())


@app.post("/api/admin/bundles/{bundle_id}/deactivate")
def admin_deactivate_bundle(bundle_id: str, admin: UserResponse = Depends(require_admin)):
    return bq_service.deactivate_bundle(bundle_id)


@app.post("/api/admin/subscriptions/{subscription_id}/approve")
def admin_approve_subscription(subscription_id: str, admin: UserResponse = Depends(require_admin)):
    return bq_service.decide_subscription(subscription_id, admin.id, approved=True)


@app.post("/api/admin/subscriptions/{subscription_id}/reject")
def admin_reject_subscription(subscription_id: str, admin: UserResponse = Depends(require_admin)):
    return bq_service.decide_subscription(subscription_id, admin.id, approved=False)


# ── Settings ─────────────────────────────────────────────────────────────────

@app.get("/api/settings/notifications")
def get_notification_prefs(current_user: UserResponse = Depends(get_current_user)):
    return bq_service.get_notification_preferences(current_user.id)


@app.put("/api/settings/notifications")
def update_notification_prefs(payload: NotificationPreferences, current_user: UserResponse = Depends(get_current_user)):
    return bq_service.update_notification_preferences(current_user.id, payload.model_dump())


# ── Admin ────────────────────────────────────────────────────────────────────

@app.get("/api/admin/ping")
def admin_ping(admin: UserResponse = Depends(require_admin)):
    return {"msg": "admin access confirmed"}


@app.get("/api/admin/users")
def admin_users(admin: UserResponse = Depends(require_admin)):
    return list_users()


@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: dict, admin: UserResponse = Depends(require_admin)):
    update_user(user_id, payload)
    return {"status": "updated"}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, admin: UserResponse = Depends(require_admin)):
    delete_user(user_id)
    return {"status": "deleted"}


# ── Bootstrap ────────────────────────────────────────────────────────────────

@app.post("/api/admin/bootstrap-admin")
def bootstrap_admin(email: str, secret: str):
    import os
    expected = os.environ.get("ADMIN_BOOTSTRAP_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_user(user.id, {"role": "admin"})
    return {"status": "promoted", "email": email}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}