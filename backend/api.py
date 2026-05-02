"""
FastAPI backend serving BigQuery data for the frontend dashboard.
"""
import logging

from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from utils.bigquery_helper import BigQueryHelper
from auth import (
    verify_password, create_access_token, get_current_user, require_admin,
)
from models import (
    UserCreate, UserLogin, UserUpdate, TokenResponse, UserResponse,
    WatchlistAdd, PortfolioAdd, PortfolioUpdate, AlertCreate,
)
import user_service
import os

app = FastAPI(title="DSC Quant Analyst API", version="1.0.0")
logger = logging.getLogger(__name__)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_bq_instance = None

def get_bq():
    global _bq_instance
    if _bq_instance is None:
        _bq_instance = BigQueryHelper()
    return _bq_instance


class BigQueryProxy:
    def __getattr__(self, name):
        return getattr(get_bq(), name)


bq = BigQueryProxy()


# ─── Helper ───────────────────────────────────────────────────────────────────

def _run_query(sql):
    """Execute SQL and return list of dicts."""
    try:
        rows = bq.client.query(sql).result()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def health():
    return {"status": "ok", "project": bq.client.project}


@app.post("/api/auth/signup", response_model=TokenResponse)
def signup(data: UserCreate):
    """Register new user."""
    try:
        user = user_service.create_user(
            email=data.email,
            phone=data.phone,
            password=data.password,
            full_name=data.full_name,
        )
        token = create_access_token(user["id"], user["role"])
        return TokenResponse(
            access_token=token,
            user=UserResponse(**user),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Signup failed")
        raise HTTPException(status_code=500, detail="Signup failed due to internal server error")


@app.post("/api/auth/login", response_model=TokenResponse)
def login(data: UserLogin):
    """Login with email + password."""
    user = user_service.get_user_by_email(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["role"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            phone=user["phone"],
            full_name=user["full_name"],
            role=user["role"],
            created_at=str(user.get("created_at", "")),
        ),
    )


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user profile."""
    user = user_service.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=user["id"],
        email=user["email"],
        phone=user["phone"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=str(user.get("created_at", "")),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/admin/users")
def admin_list_users(admin: dict = Depends(require_admin)):
    """List all users (admin only)."""
    return user_service.list_users()


@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: str, data: UserUpdate, admin: dict = Depends(require_admin)):
    """Update user role/info (admin only)."""
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = user_service.update_user(user_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: str, admin: dict = Depends(require_admin)):
    """Delete user (admin only)."""
    user_service.delete_user(user_id)
    return {"message": "User deleted"}


@app.get("/api/admin/pipeline-status")
def pipeline_status(admin: dict = Depends(require_admin)):
    """Get last scrape timestamps for each table."""
    tables = ["lankabd_datamatrix", "lankabd_price_archive", "lankabd_announcements"]
    result = {}
    for t in tables:
        try:
            full_id = bq._get_full_table_id(t)
            sql = f"SELECT MAX(updated_at) as last_updated, COUNT(*) as row_count FROM `{full_id}`"
            rows = list(bq.client.query(sql).result())
            if rows:
                r = dict(rows[0])
                result[t] = {
                    "last_updated": str(r.get("last_updated", "")),
                    "row_count": r.get("row_count", 0),
                }
        except Exception:
            result[t] = {"last_updated": None, "row_count": 0}
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/datamatrix")
def get_datamatrix(
    sector: str = Query(None, description="Filter by sector"),
    limit: int = Query(500, ge=1, le=5000),
):
    """Current snapshot of all stocks."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"SELECT * FROM `{table}`"
    if sector:
        sql += f" WHERE Sector = '{sector}'"
    sql += f" LIMIT {limit}"
    return _run_query(sql)


@app.get("/api/sectors")
def get_sectors():
    """List distinct sectors."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"SELECT DISTINCT Sector FROM `{table}` WHERE Sector IS NOT NULL ORDER BY Sector"
    return _run_query(sql)


@app.get("/api/symbols")
def get_symbols(sector: str = Query(None)):
    """List distinct symbols."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"SELECT DISTINCT Symbol FROM `{table}` WHERE Symbol IS NOT NULL"
    if sector:
        sql += f" AND Sector = '{sector}'"
    sql += " ORDER BY Symbol"
    return _run_query(sql)


@app.get("/api/price-history/{symbol}")
def get_price_history(
    symbol: str,
    limit: int = Query(365, ge=1, le=5000),
):
    """Price archive for a specific symbol."""
    table = bq._get_full_table_id("lankabd_price_archive")
    sql = (
        f"SELECT * FROM `{table}` "
        f"WHERE Symbol = '{symbol}' "
        f"ORDER BY Date DESC LIMIT {limit}"
    )
    return _run_query(sql)


@app.get("/api/announcements")
def get_announcements(
    symbol: str = Query(None),
    limit: int = Query(100, ge=1, le=2000),
):
    """Recent announcements."""
    table = bq._get_full_table_id("lankabd_announcements")
    sql = f"SELECT * FROM `{table}`"
    if symbol:
        sql += f" WHERE Symbol = '{symbol}'"
    sql += f" ORDER BY Date DESC LIMIT {limit}"
    return _run_query(sql)


@app.get("/api/market-summary")
def market_summary():
    """Aggregated market stats."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    SELECT
        COUNT(*) as total_stocks,
        COUNT(DISTINCT Sector) as total_sectors,
        ROUND(AVG(SAFE_CAST(LTP AS FLOAT64)), 2) as avg_price,
        MAX(updated_at) as last_updated
    FROM `{table}`
    """
    rows = _run_query(sql)
    return rows[0] if rows else {}


@app.get("/api/top-gainers")
def top_gainers(limit: int = Query(10, ge=1, le=50)):
    """Top gaining stocks."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    SELECT Symbol, Sector, LTP, HIGH, LOW, CLOSEP, YCP, TRADE, VALUE, VOLUME
    FROM `{table}`
    WHERE SAFE_CAST(LTP AS FLOAT64) IS NOT NULL
    ORDER BY SAFE_CAST(LTP AS FLOAT64) - SAFE_CAST(YCP AS FLOAT64) DESC
    LIMIT {limit}
    """
    return _run_query(sql)


@app.get("/api/top-losers")
def top_losers(limit: int = Query(10, ge=1, le=50)):
    """Top losing stocks."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    SELECT Symbol, Sector, LTP, HIGH, LOW, CLOSEP, YCP, TRADE, VALUE, VOLUME
    FROM `{table}`
    WHERE SAFE_CAST(LTP AS FLOAT64) IS NOT NULL
    ORDER BY SAFE_CAST(LTP AS FLOAT64) - SAFE_CAST(YCP AS FLOAT64) ASC
    LIMIT {limit}
    """
    return _run_query(sql)


@app.get("/api/sector-performance")
def sector_performance():
    """Avg price per sector."""
    table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    SELECT
        Sector,
        COUNT(*) as stock_count,
        ROUND(AVG(SAFE_CAST(LTP AS FLOAT64)), 2) as avg_ltp,
        ROUND(SUM(SAFE_CAST(VALUE AS FLOAT64)), 2) as total_value,
        ROUND(SUM(SAFE_CAST(VOLUME AS FLOAT64)), 0) as total_volume
    FROM `{table}`
    WHERE Sector IS NOT NULL
    GROUP BY Sector
    ORDER BY total_value DESC
    """
    return _run_query(sql)


# ═══════════════════════════════════════════════════════════════════════════════
# WATCHLIST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_watchlist_table():
    full_id = bq._get_full_table_id("watchlists")
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{full_id}` (
        id STRING, user_id STRING, symbol STRING, added_at TIMESTAMP,
        is_deleted BOOL
    )
    """
    bq.client.query(sql).result()


@app.get("/api/watchlist")
def get_watchlist(current_user: dict = Depends(get_current_user)):
    """Get user's watchlist with current prices."""
    _ensure_watchlist_table()
    wl_table = bq._get_full_table_id("watchlists")
    dm_table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    WITH latest_wl AS (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY user_id, symbol ORDER BY added_at DESC) as rn
        FROM `{wl_table}`
    )
    SELECT w.symbol, w.added_at, d.LTP, d.High, d.Low, d.YCP, d.Close, d.Volume_Qty_ as VOLUME, d.Sector
    FROM latest_wl w
    LEFT JOIN `{dm_table}` d ON w.symbol = d.Symbol
    WHERE w.user_id = '{current_user["user_id"]}' 
    AND w.rn = 1 
    AND (w.is_deleted IS NOT TRUE)
    ORDER BY w.added_at DESC
    """
    return _run_query(sql)


@app.post("/api/watchlist")
def add_to_watchlist(data: WatchlistAdd, current_user: dict = Depends(get_current_user)):
    """Add symbol to watchlist."""
    import uuid
    import pandas as pd
    from datetime import datetime, timezone
    _ensure_watchlist_table()
    df = pd.DataFrame([{
        "id": str(uuid.uuid4()),
        "user_id": current_user['user_id'],
        "symbol": data.symbol,
        "added_at": datetime.now(timezone.utc),
        "is_deleted": False
    }])
    bq.upload_dataframe(df, 'watchlists', truncate=False)
    return {"message": f"{data.symbol} added to watchlist"}


@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str, current_user: dict = Depends(get_current_user)):
    """Remove symbol from watchlist (Soft Delete for Sandbox)."""
    import pandas as pd
    from datetime import datetime, timezone
    _ensure_watchlist_table()
    
    df = pd.DataFrame([{
        "id": "deleted-" + symbol,
        "user_id": current_user['user_id'],
        "symbol": symbol,
        "added_at": datetime.now(timezone.utc),
        "is_deleted": True
    }])
    
    bq.upload_dataframe(df, 'watchlists', truncate=False)
    return {"message": f"{symbol} removed from watchlist"}


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_portfolio_table():
    full_id = bq._get_full_table_id("portfolios")
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{full_id}` (
        id STRING, user_id STRING, symbol STRING,
        buy_price FLOAT64, quantity INT64, buy_date STRING,
        price_target FLOAT64, stop_loss FLOAT64, notes STRING,
        created_at TIMESTAMP, updated_at TIMESTAMP,
        is_deleted BOOL
    )
    """
    bq.client.query(sql).result()


@app.get("/api/portfolio")
def get_portfolio(current_user: dict = Depends(get_current_user)):
    """Get user's portfolio with current prices and P&L (Soft Delete Support)."""
    _ensure_portfolio_table()
    pf_table = bq._get_full_table_id("portfolios")
    dm_table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    WITH latest_pf AS (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY id ORDER BY updated_at DESC) as rn
        FROM `{pf_table}`
    )
    SELECT
        p.id, p.symbol, p.buy_price, p.quantity, p.buy_date,
        p.price_target, p.stop_loss, p.notes, p.created_at,
        SAFE_CAST(d.LTP AS FLOAT64) as current_price,
        d.Sector,
        ROUND((SAFE_CAST(d.LTP AS FLOAT64) - p.buy_price) * p.quantity, 2) as pnl,
        ROUND(((SAFE_CAST(d.LTP AS FLOAT64) - p.buy_price) / p.buy_price) * 100, 2) as pnl_percent
    FROM latest_pf p
    LEFT JOIN `{dm_table}` d ON p.symbol = d.Symbol
    WHERE p.user_id = '{current_user["user_id"]}'
    AND p.rn = 1
    AND (p.is_deleted IS NOT TRUE)
    ORDER BY p.created_at DESC
    """
    return _run_query(sql)


@app.get("/api/portfolio/summary")
def portfolio_summary(current_user: dict = Depends(get_current_user)):
    """Portfolio summary: total invested, current value, P&L."""
    _ensure_portfolio_table()
    pf_table = bq._get_full_table_id("portfolios")
    dm_table = bq._get_full_table_id("lankabd_datamatrix")
    sql = f"""
    SELECT
        ROUND(SUM(p.buy_price * p.quantity), 2) as total_invested,
        ROUND(SUM(SAFE_CAST(d.LTP AS FLOAT64) * p.quantity), 2) as current_value,
        ROUND(SUM((SAFE_CAST(d.LTP AS FLOAT64) - p.buy_price) * p.quantity), 2) as total_pnl,
        COUNT(*) as total_holdings
    FROM `{pf_table}` p
    LEFT JOIN `{dm_table}` d ON p.symbol = d.Symbol
    WHERE p.user_id = '{current_user["user_id"]}'
    """
    rows = _run_query(sql)
    return rows[0] if rows else {}


@app.post("/api/portfolio")
def add_to_portfolio(data: PortfolioAdd, current_user: dict = Depends(get_current_user)):
    """Add holding to portfolio."""
    import uuid
    import pandas as pd
    from datetime import datetime, timezone
    _ensure_portfolio_table()
    
    now = datetime.now(timezone.utc)
    df = pd.DataFrame([{
        "id": str(uuid.uuid4()),
        "user_id": current_user["user_id"],
        "symbol": data.symbol,
        "buy_price": float(data.buy_price),
        "quantity": int(data.quantity),
        "buy_date": data.buy_date or now.strftime('%Y-%m-%d'),
        "price_target": float(data.price_target or 0),
        "stop_loss": float(data.stop_loss or 0),
        "notes": data.notes or "",
        "created_at": now,
        "updated_at": now,
        "is_deleted": False
    }])
    
    bq.upload_dataframe(df, 'portfolios', truncate=False)
    return {"message": f"{data.symbol} added to portfolio"}


@app.put("/api/portfolio/{holding_id}")
def update_holding(holding_id: str, data: PortfolioUpdate, current_user: dict = Depends(get_current_user)):
    """Update portfolio holding."""
    from datetime import datetime, timezone
    full_id = bq._get_full_table_id("portfolios")
    now = datetime.now(timezone.utc).isoformat()
    sets = [f"updated_at = '{now}'"]
    updates = data.model_dump(exclude_none=True)
    for k, v in updates.items():
        if k == "notes":
            sets.append(f"{k} = '{str(v).replace(chr(39), chr(39)+chr(39))}'")
        else:
            sets.append(f"{k} = {v}")
    sql = f"UPDATE `{full_id}` SET {', '.join(sets)} WHERE id = '{holding_id}' AND user_id = '{current_user['user_id']}'"
    bq.client.query(sql).result()
    return {"message": "Holding updated"}


@app.delete("/api/portfolio/{holding_id}")
def delete_holding(holding_id: str, current_user: dict = Depends(get_current_user)):
    """Delete portfolio holding (Soft Delete)."""
    import pandas as pd
    from datetime import datetime, timezone
    _ensure_portfolio_table()
    now = datetime.now(timezone.utc)
    df = pd.DataFrame([{
        "id": holding_id,
        "user_id": current_user['user_id'],
        "updated_at": now,
        "is_deleted": True
    }])
    bq.upload_dataframe(df, 'portfolios', truncate=False)
    return {"message": "Holding deleted"}


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_alerts_table():
    full_id = bq._get_full_table_id("price_alerts")
    sql = f"""
    CREATE TABLE IF NOT EXISTS `{full_id}` (
        id STRING, user_id STRING, symbol STRING,
        target_price FLOAT64, direction STRING,
        is_triggered BOOL, triggered_at TIMESTAMP,
        created_at TIMESTAMP
    )
    """
    bq.client.query(sql).result()


@app.get("/api/alerts")
def get_alerts(current_user: dict = Depends(get_current_user)):
    """Get user's price alerts."""
    _ensure_alerts_table()
    full_id = bq._get_full_table_id("price_alerts")
    sql = f"SELECT * FROM `{full_id}` WHERE user_id = '{current_user['user_id']}' ORDER BY created_at DESC"
    return _run_query(sql)


@app.post("/api/alerts")
def create_alert(data: AlertCreate, current_user: dict = Depends(get_current_user)):
    """Create price alert."""
    import uuid
    from datetime import datetime, timezone
    _ensure_alerts_table()
    full_id = bq._get_full_table_id("price_alerts")
    alert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
    INSERT INTO `{full_id}` (id, user_id, symbol, target_price, direction, is_triggered, triggered_at, created_at)
    VALUES ('{alert_id}', '{current_user["user_id"]}', '{data.symbol}', {data.target_price}, '{data.direction}', false, NULL, '{now}')
    """
    bq.client.query(sql).result()
    return {"message": "Alert created", "id": alert_id}


@app.delete("/api/alerts/{alert_id}")
def delete_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    """Delete price alert."""
    full_id = bq._get_full_table_id("price_alerts")
    sql = f"DELETE FROM `{full_id}` WHERE id = '{alert_id}' AND user_id = '{current_user['user_id']}'"
    bq.client.query(sql).result()
    return {"message": "Alert deleted"}


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
