import os

from fastapi import FastAPI, Depends, HTTPException, status, Query, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from .auth import create_access_token, verify_password, get_current_user, require_admin
from .models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    WatchlistAdd, PortfolioAdd, PortfolioUpdate, AlertCreate,
)
from .user_service import (
    create_user, get_user_by_email, get_user_credentials,
    get_user_by_id, list_users, update_user, delete_user,
)
from . import market_service, watchlist_service, portfolio_service, alerts_service
from . import fundamentals_service

app = FastAPI(title="DSC Quant Analyst API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(payload: UserCreate):
    try:
        user = create_user(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=user)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cred = get_user_credentials(payload.email)
    if not cred or not verify_password(payload.password, cred.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=user)


@app.get("/api/auth/me", response_model=UserResponse)
def read_me(current_user: UserResponse = Depends(get_current_user)):
    # /auth/me returns the full, fresh record (the token carries only a
    # lightweight identity) — the frontend loads this on mount, so a demoted
    # role or edited profile is reflected here without waiting for token expiry.
    fresh = get_user_by_id(current_user.id)
    return fresh or current_user


# ── Market Data ──────────────────────────────────────────────────────────────

@app.get("/api/market/summary")
def market_summary():
    return market_service.market_summary()


@app.get("/api/market/sectors")
def sectors():
    return market_service.list_sectors()


@app.get("/api/market/stocks")
def stocks(sector: str = None, search: str = None, limit: int = Query(default=500, le=5000)):
    return market_service.list_stocks(sector=sector, search=search, limit=limit)


@app.get("/api/market/stocks/{symbol}")
def stock_detail(symbol: str):
    result = market_service.get_stock(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return result


@app.get("/api/market/top-movers")
def top_movers(limit: int = Query(default=10, le=50)):
    return market_service.top_movers(limit=limit)


@app.get("/api/market/price-history/{symbol}")
def price_history(symbol: str, days: int = Query(default=365, le=1095)):
    return market_service.price_history(symbol.upper(), days=days)


@app.get("/api/market/technical/{symbol}")
def technical_indicators(symbol: str, days: int = Query(default=365, le=1095)):
    return market_service.technical_indicators(symbol.upper(), days=days)


@app.get("/api/market/fundamentals/{symbol}")
def fundamentals(symbol: str):
    result = fundamentals_service.get_fundamentals(symbol.upper())
    if not result:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return result


@app.get("/api/market/announcements")
def announcements(symbol: str = None, limit: int = Query(default=50, le=200)):
    return market_service.list_announcements(symbol=symbol, limit=limit)


# ── Watchlist ────────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
def watchlist_list(current_user: UserResponse = Depends(get_current_user)):
    return watchlist_service.get_watchlist(current_user.id)


@app.post("/api/watchlist")
def watchlist_add(payload: WatchlistAdd, current_user: UserResponse = Depends(get_current_user)):
    return watchlist_service.add_to_watchlist(current_user.id, payload.symbol)


@app.delete("/api/watchlist/{symbol}")
def watchlist_remove(symbol: str, current_user: UserResponse = Depends(get_current_user)):
    watchlist_service.remove_from_watchlist(current_user.id, symbol.upper())
    return {"status": "removed"}


# ── Portfolio ────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio_list(current_user: UserResponse = Depends(get_current_user)):
    return portfolio_service.get_portfolio(current_user.id)


@app.get("/api/portfolio/summary")
def portfolio_summary(current_user: UserResponse = Depends(get_current_user)):
    return portfolio_service.portfolio_summary(current_user.id)


@app.post("/api/portfolio")
def portfolio_add(payload: PortfolioAdd, current_user: UserResponse = Depends(get_current_user)):
    return portfolio_service.add_to_portfolio(current_user.id, payload.model_dump())


@app.put("/api/portfolio/{portfolio_id}")
def portfolio_update(portfolio_id: str, payload: PortfolioUpdate, current_user: UserResponse = Depends(get_current_user)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    portfolio_service.update_portfolio(portfolio_id, current_user.id, data)
    return {"status": "updated"}


@app.delete("/api/portfolio/{portfolio_id}")
def portfolio_delete(portfolio_id: str, current_user: UserResponse = Depends(get_current_user)):
    portfolio_service.delete_portfolio(portfolio_id, current_user.id)
    return {"status": "deleted"}


# ── Alerts ───────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def alerts_list(current_user: UserResponse = Depends(get_current_user)):
    return alerts_service.get_alerts(current_user.id)


@app.post("/api/alerts")
def alerts_create(payload: AlertCreate, current_user: UserResponse = Depends(get_current_user)):
    return alerts_service.create_alert(current_user.id, payload.model_dump())


@app.delete("/api/alerts/{alert_id}")
def alerts_delete(alert_id: str, current_user: UserResponse = Depends(get_current_user)):
    alerts_service.delete_alert(alert_id, current_user.id)
    return {"status": "deleted"}


# ── Internal (cron) ──────────────────────────────────────────────────────────

@app.post("/api/internal/run-alerts")
def run_alerts(authorization: str = Header(default="")):
    """The edge-trigger alert sweep, triggered by Vercel Cron (#66, from #34).

    Serverless has no in-process scheduler, so an external trigger drives the
    sweep. Auth is the platform-signed `Authorization: Bearer $CRON_SECRET`
    header Vercel Cron sends — a missing or wrong secret is a 401, and an unset
    server-side secret fails closed (never open the endpoint to the world).

    **Scale-out (#34 dec.6):** this runs synchronously inside the function
    budget, fine at v1 scale (single-digit users, ms sweeps). When a crossing
    batch × ~300ms/email approaches the Vercel function timeout, move the sweep
    to a standalone GitHub Actions script (the ETL already runs there, #55) and
    keep this endpoint only for manual runs.
    """
    secret = os.environ.get("CRON_SECRET")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from . import alert_checker
    result = alert_checker.check_alerts(alert_checker.build_email_notifier())
    return {
        "fired": len(result["fired"]),
        "undelivered": len(result["undelivered"]),
        "rebaselined": len(result["rebaselined"]),
    }


# ── Admin ────────────────────────────────────────────────────────────────────

@app.get("/api/admin/ping")
def admin_ping(admin: UserResponse = Depends(require_admin)):
    return {"msg": "admin access confirmed"}


@app.get("/api/admin/users")
def admin_users(admin: UserResponse = Depends(require_admin)):
    return list_users()


@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, payload: dict, admin: UserResponse = Depends(require_admin)):
    # Report what actually happened: this used to answer "updated" even though
    # the write was a silent no-op (ticket #50).
    if not update_user(user_id, payload):
        raise HTTPException(status_code=404, detail="User not found, or no editable fields supplied")
    return {"status": "updated"}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, admin: UserResponse = Depends(require_admin)):
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}


@app.get("/api/admin/export/announcements")
def admin_export_announcements(admin: UserResponse = Depends(require_admin)):
    from .exports import export_announcements
    content, media_type = export_announcements()
    return Response(content, media_type=media_type, headers={"Content-Disposition": "attachment; filename=announcements.csv"})


@app.get("/api/admin/export/price_archive")
def admin_export_prices(admin: UserResponse = Depends(require_admin)):
    from .exports import export_price_archive
    content, media_type = export_price_archive()
    return Response(content, media_type=media_type, headers={"Content-Disposition": "attachment; filename=price_archive.csv"})


@app.get("/api/admin/export/data_grid")
def admin_export_full(admin: UserResponse = Depends(require_admin)):
    from .exports import export_master_dataset
    content, media_type = export_master_dataset()
    return Response(content, media_type=media_type, headers={"Content-Disposition": "attachment; filename=full_dataset.json"})


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}