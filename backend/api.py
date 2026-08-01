import os

from fastapi import FastAPI, Depends, HTTPException, status, Query, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from .auth import (
    create_access_token, create_refresh_token, create_reset_token,
    decode_refresh_token, decode_reset_token, verify_reset_fingerprint,
    hash_password, verify_password, get_current_user, require_admin,
)
from .models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
    WatchlistAdd, PortfolioAdd, PortfolioUpdate, AlertCreate,
    ScreenerRequest, ScreenerResponse, ScreenerWatchlistAdd,
    SubscriptionCreate, BundleCreate, NotificationPreferences,
    InvestorProfile, ProfileUpdate, FitScore, PortfolioHealth, Recommendations,
)
from .user_service import (
    create_user, get_user_by_email, get_user_credentials,
    get_user_by_id, get_user_session, bump_token_version, reset_password,
    list_users, update_user, delete_user,
)
from . import account_recovery
from . import market_service, watchlist_service, portfolio_service, alerts_service
from . import fundamentals_service
from . import screener_service
from . import subscriptions_service
from . import notification_prefs_service
from . import profile_service
from . import fit_service
from . import portfolio_fit_service
from . import recommendation_service

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

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
    access = create_access_token(user)
    refresh = create_refresh_token(user.id, token_version=0)
    return TokenResponse(access_token=access, refresh_token=refresh, user=user)


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: UserLogin):
    user = get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cred = get_user_credentials(payload.email)
    if not cred or not verify_password(payload.password, cred.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access = create_access_token(user)
    refresh = create_refresh_token(user.id, token_version=cred["token_version"])
    return TokenResponse(access_token=access, refresh_token=refresh, user=user)


@app.get("/api/auth/me", response_model=UserResponse)
def read_me(current_user: UserResponse = Depends(get_current_user)):
    # /auth/me returns the full, fresh record (the token carries only a
    # lightweight identity) — the frontend loads this on mount, so a demoted
    # role or edited profile is reflected here without waiting for token expiry.
    fresh = get_user_by_id(current_user.id)
    return fresh or current_user


@app.post("/api/auth/refresh", response_model=TokenResponse)
def refresh_token_endpoint(payload: RefreshRequest):
    """Sliding-window refresh (#68): re-issues BOTH tokens on every call.

    The refresh token's token_version must match the user's current value —
    a mismatch means password-reset or logout-all happened since this refresh
    token was issued, and it is no longer honored.
    """
    claims = decode_refresh_token(payload.refresh_token)
    user_id = claims.get("sub")
    session = get_user_session(user_id) if user_id else None
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if claims.get("token_version") != session["token_version"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access = create_access_token(user)
    new_refresh = create_refresh_token(user_id, session["token_version"])
    return TokenResponse(access_token=access, refresh_token=new_refresh, user=user)


@app.post("/api/auth/logout", response_model=MessageResponse)
def logout(current_user: UserResponse = Depends(get_current_user)):
    """Client-discard contract: no token is revocable server-side short of a
    token_version bump, and a single-session logout does not warrant one —
    the client simply drops both tokens. This is a documented no-op.
    """
    return MessageResponse(message="Logged out. Discard your tokens.")


@app.post("/api/auth/logout-all", response_model=MessageResponse)
def logout_all(current_user: UserResponse = Depends(get_current_user)):
    """Bump token_version, invalidating every outstanding refresh token."""
    bump_token_version(current_user.id)
    return MessageResponse(message="Logged out of all sessions.")


@app.post("/api/auth/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest):
    """Always 200 — whether the account exists is never revealed (#68)."""
    user = get_user_by_email(payload.email)
    if user:
        session = get_user_session(user.id)
        reset_token = create_reset_token(user.id, session["password_hash"])
        reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
        account_recovery.send_reset_email(user.id, user.email, reset_link)
    return MessageResponse(message="If that email exists, a password reset link has been sent.")


@app.post("/api/auth/reset-password", response_model=MessageResponse)
def reset_password_endpoint(payload: ResetPasswordRequest):
    """Verify the reset token's signature, expiry, purpose, and single-use
    fingerprint (#68), then set the new password and bump token_version —
    which also signs the user out of every existing session.
    """
    claims = decode_reset_token(payload.token)
    user_id = claims.get("sub")
    session = get_user_session(user_id) if user_id else None
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid reset token")

    verify_reset_fingerprint(claims, session["password_hash"])

    new_hash = hash_password(payload.new_password)
    reset_password(user_id, new_hash)
    return MessageResponse(message="Password reset. Please log in again.")


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


# ── Dashboard leaderboards (PRD-12, #82) ─────────────────────────────────────

@app.get("/api/market/strength")
def market_strength():
    return market_service.market_strength()


@app.get("/api/market/sectors/breakdown")
def sectors_breakdown():
    return market_service.sector_breakdown()


@app.get("/api/market/leaderboard")
def leaderboard(
    metric: str = Query(pattern=market_service.metric_pattern(market_service.LEADERBOARD_METRICS)),
    limit: int = Query(default=10, le=50),
):
    return market_service.leaderboard(metric=metric, limit=limit)


@app.get("/api/market/extremes")
def extremes(
    metric: str = Query(pattern=market_service.metric_pattern(market_service.EXTREMES_METRICS)),
    limit: int = Query(default=10, le=50),
):
    return market_service.extremes_leaderboard(metric=metric, limit=limit)


@app.get("/api/market/technical-extremes")
def technical_extremes(
    metric: str = Query(pattern=market_service.metric_pattern(market_service.TECHNICAL_METRICS)),
    limit: int = Query(default=10, le=50),
):
    return market_service.technical_extremes(metric=metric, limit=limit)


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


@app.post("/api/market/screener", response_model=ScreenerResponse)
def screener(payload: ScreenerRequest):
    """Bulk-filter the ~414 symbols in one hybrid read (#71) — see
    screener_service for the native-SQL/derived-Python split and the
    whitelist that guards it.
    """
    try:
        results = screener_service.screen(
            preset=payload.preset,
            filters=[f.model_dump() for f in payload.filters] if payload.filters else None,
            limit=payload.limit,
        )
    except screener_service.InvalidFilter as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ScreenerResponse(count=len(results), results=results)


@app.post("/api/market/screener/export")
def screener_export(payload: ScreenerRequest):
    """CSV of the same result set /screener would return — reuses exports._csv
    (#71) rather than a second CSV-writing path.
    """
    from .exports import _csv
    try:
        results = screener_service.screen(
            preset=payload.preset,
            filters=[f.model_dump() for f in payload.filters] if payload.filters else None,
            limit=payload.limit,
        )
    except screener_service.InvalidFilter as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    content, media_type = _csv(results)
    return Response(content, media_type=media_type,
                     headers={"Content-Disposition": "attachment; filename=screener_results.csv"})


@app.post("/api/market/screener/watchlist")
def screener_add_to_watchlist(payload: ScreenerWatchlistAdd, current_user: UserResponse = Depends(get_current_user)):
    """Bulk-add a screener result set's symbols to the caller's watchlist —
    reuses watchlist_service.add_to_watchlist per symbol (#71), the same
    dedup-safe path a single manual add uses.
    """
    added = [watchlist_service.add_to_watchlist(current_user.id, symbol) for symbol in payload.symbols]
    return {"added": added}


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


# ── Investor profile (#85, personalization spine #84) ────────────────────────

@app.get("/api/profile/me", response_model=InvestorProfile)
def profile_me(current_user: UserResponse = Depends(get_current_user)):
    # Never 404s: an unset profile resolves to the neutral default (is_default),
    # which is what the onboarding nudge keys on.
    return profile_service.get_profile(current_user.id)


@app.put("/api/profile/me", response_model=InvestorProfile)
def profile_update(payload: ProfileUpdate, current_user: UserResponse = Depends(get_current_user)):
    # Enums are validated by Pydantic (422). Sectors are validated here against
    # the live universe so a typo can't silently store an un-scoreable preference.
    valid = set(profile_service.list_sector_names())
    unknown = [s for s in payload.sector_prefs if s not in valid]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown sectors: {', '.join(unknown)}")
    return profile_service.save_profile(current_user.id, payload.model_dump())


@app.get("/api/profile/sectors")
def profile_sectors(current_user: UserResponse = Depends(get_current_user)):
    return profile_service.list_sector_names()


@app.get("/api/fit/{symbol}", response_model=FitScore)
def fit_score(symbol: str, current_user: UserResponse = Depends(get_current_user)):
    # Explainable per-axis fit of a stock against the caller's profile (#88).
    return fit_service.fit_for(current_user.id, symbol)


@app.get("/api/recommendations", response_model=Recommendations)
def recommendations(current_user: UserResponse = Depends(get_current_user)):
    # Personalized 'for you' recs + strategy nudges — matches preferences, not advice (#93).
    return recommendation_service.recommend(current_user.id)


# ── Portfolio ────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio_list(current_user: UserResponse = Depends(get_current_user)):
    return portfolio_service.get_portfolio(current_user.id)


@app.get("/api/portfolio/health", response_model=PortfolioHealth)
def portfolio_health(current_user: UserResponse = Depends(get_current_user)):
    # Portfolio-level fit vs the caller's profile — observations, never advice (#91).
    return portfolio_fit_service.portfolio_health(current_user.id)


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


# ── Subscriptions & bundles (#77) ────────────────────────────────────────────

@app.post("/api/subscriptions")
def subscription_create(payload: SubscriptionCreate, current_user: UserResponse = Depends(get_current_user)):
    return subscriptions_service.create_subscription(current_user.id, payload.model_dump())


@app.post("/api/subscriptions/{subscription_id}/transaction")
def subscription_attach_transaction(subscription_id: str, body: dict, current_user: UserResponse = Depends(get_current_user)):
    txn_id = body.get("transaction_id")
    if not txn_id:
        raise HTTPException(status_code=400, detail="transaction_id is required")
    return subscriptions_service.attach_transaction_id(subscription_id, txn_id)


@app.get("/api/subscriptions/pricing")
def subscription_pricing():
    return subscriptions_service.get_pricing()


@app.get("/api/admin/subscriptions")
def admin_subscriptions_list(admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.list_subscriptions()


@app.post("/api/admin/subscriptions/{subscription_id}/approve")
def admin_approve_subscription(subscription_id: str, admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.decide_subscription(subscription_id, admin.id, approved=True)


@app.post("/api/admin/subscriptions/{subscription_id}/reject")
def admin_reject_subscription(subscription_id: str, admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.decide_subscription(subscription_id, admin.id, approved=False)


@app.post("/api/admin/bundles")
def admin_create_bundle(payload: BundleCreate, admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.create_bundle(admin.id, payload.model_dump())


@app.get("/api/admin/bundles")
def admin_list_bundles(admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.list_bundles()


@app.put("/api/admin/bundles/{bundle_id}")
def admin_update_bundle(bundle_id: str, payload: BundleCreate, admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.update_bundle(bundle_id, payload.model_dump())


@app.post("/api/admin/bundles/{bundle_id}/deactivate")
def admin_deactivate_bundle(bundle_id: str, admin: UserResponse = Depends(require_admin)):
    return subscriptions_service.deactivate_bundle(bundle_id)


# ── Notification preferences (#78) ───────────────────────────────────────────

@app.get("/api/settings/notifications")
def get_notification_prefs(current_user: UserResponse = Depends(get_current_user)):
    return notification_prefs_service.get_prefs(current_user.id) or {
        "channels_enabled": [], "telegram_chat_id": None, "whatsapp_number": None,
        "email": current_user.email, "web_push_subscription": None,
    }


@app.put("/api/settings/notifications")
def update_notification_prefs(payload: NotificationPreferences, current_user: UserResponse = Depends(get_current_user)):
    return notification_prefs_service.update_prefs(current_user.id, payload.model_dump())


# ── Internal (cron) ──────────────────────────────────────────────────────────

@app.post("/api/internal/run-alerts")
def run_alerts(authorization: str = Header(default="")):
    """Manual / backfill trigger for the edge-trigger alert sweep (#66).

    The scheduled sweep now runs as a step chained onto the market ETL on GitHub
    Actions (#80, ADR-0001) — LTP only refreshes there, so the sweep must run on
    the scrape's completion, not on a fixed-time cron that races it. The Vercel
    Cron that used to drive this endpoint is retired.

    This endpoint stays for manual and backfill runs (e.g. re-firing after a
    provider outage). Auth is `Authorization: Bearer $CRON_SECRET` — a missing or
    wrong secret is a 401, and an unset server-side secret fails closed (never
    open the endpoint to the world). It runs the same `check_alerts` engine the
    GH Actions step runs, so the two triggers can never diverge.
    """
    secret = os.environ.get("CRON_SECRET")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    from . import alert_checker
    result = alert_checker.check_alerts(alert_checker.build_notifier())
    return {
        "fired": len(result["fired"]),
        "undelivered": len(result["undelivered"]),
        "rebaselined": len(result["rebaselined"]),
    }


# ── Admin ────────────────────────────────────────────────────────────────────

@app.post("/api/admin/bootstrap-admin")
def bootstrap_admin(payload: dict):
    """First-run admin setup: promote an existing user to admin (ported from
    main, #81). Fail-hard — main's version fell back to a hardcoded default
    secret, which is the self-promote-to-admin vuln #68 killed for JWT. Here an
    unset ADMIN_BOOTSTRAP_SECRET disables the endpoint (500), never opens it.
    """
    secret = os.environ.get("ADMIN_BOOTSTRAP_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Admin bootstrap is disabled (no secret configured)")
    if payload.get("secret") != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    email = payload.get("email")
    user = get_user_by_email(email) if email else None
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_user(user.id, {"role": "admin"})
    return {"status": "ok", "email": email, "role": "admin"}


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