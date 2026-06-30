import pytest
from backend.repositories import WatchlistRepo, PortfolioRepo, AlertRepo, NotFoundError


class FakeQueryJob:
    def __init__(self, affected_rows):
        self.num_dml_affected_rows = affected_rows

    def result(self):
        return self


class FakeBQClient:
    def __init__(self, affected_rows=1):
        self.affected_rows = affected_rows
        self.last_sql = None
        self.last_params = None

    def query(self, sql, job_config=None):
        self.last_sql = sql
        self.last_params = (
            {p.name: p.value for p in job_config.query_parameters} if job_config else {}
        )
        return FakeQueryJob(self.affected_rows)


# ── WatchlistRepo.remove ───────────────────────────────────────────────────────

def test_remove_existing_item_sends_scoped_update():
    client = FakeBQClient(affected_rows=1)
    repo = WatchlistRepo(client)

    repo.remove(user_id="user-1", symbol="ABBANK")

    assert "UPDATE" in client.last_sql
    assert "watchlists" in client.last_sql
    assert client.last_params["uid"] == "user-1"
    assert client.last_params["symbol"] == "ABBANK"


def test_remove_missing_item_raises_not_found():
    client = FakeBQClient(affected_rows=0)
    repo = WatchlistRepo(client)

    with pytest.raises(NotFoundError):
        repo.remove(user_id="user-1", symbol="GHOST")


# ── PortfolioRepo.update ────────────────────────────────────────────────────────

def test_update_partial_fields_only_sets_given_keys():
    client = FakeBQClient(affected_rows=1)
    repo = PortfolioRepo(client)

    repo.update(portfolio_id="pf-1", user_id="user-1", fields={"notes": "trimmed position"})

    assert "notes" in client.last_params
    assert client.last_params["notes"] == "trimmed position"
    assert "buy_price" not in client.last_params
    assert "quantity" not in client.last_params
    assert client.last_params["pid"] == "pf-1"
    assert client.last_params["uid"] == "user-1"


def test_update_rejects_unknown_field():
    client = FakeBQClient(affected_rows=1)
    repo = PortfolioRepo(client)

    with pytest.raises(ValueError):
        repo.update(portfolio_id="pf-1", user_id="user-1", fields={"is_deleted": True})

    assert client.last_sql is None  # never reached BigQuery


def test_update_missing_item_raises_not_found():
    client = FakeBQClient(affected_rows=0)
    repo = PortfolioRepo(client)

    with pytest.raises(NotFoundError):
        repo.update(portfolio_id="ghost", user_id="user-1", fields={"notes": "x"})


# ── PortfolioRepo.delete ────────────────────────────────────────────────────────

def test_delete_existing_item_sends_scoped_soft_delete():
    client = FakeBQClient(affected_rows=1)
    repo = PortfolioRepo(client)

    repo.delete(portfolio_id="pf-1", user_id="user-1")

    assert "UPDATE" in client.last_sql
    assert "portfolios" in client.last_sql
    assert client.last_params["pid"] == "pf-1"
    assert client.last_params["uid"] == "user-1"


def test_delete_missing_item_raises_not_found():
    client = FakeBQClient(affected_rows=0)
    repo = PortfolioRepo(client)

    with pytest.raises(NotFoundError):
        repo.delete(portfolio_id="ghost", user_id="user-1")


# ── AlertRepo.delete ─────────────────────────────────────────────────────────────

def test_alert_delete_existing_item_sends_scoped_hard_delete():
    client = FakeBQClient(affected_rows=1)
    repo = AlertRepo(client)

    repo.delete(alert_id="al-1", user_id="user-1")

    assert "DELETE" in client.last_sql
    assert "price_alerts" in client.last_sql
    assert client.last_params["aid"] == "al-1"
    assert client.last_params["uid"] == "user-1"


def test_alert_delete_missing_item_raises_not_found():
    client = FakeBQClient(affected_rows=0)
    repo = AlertRepo(client)

    with pytest.raises(NotFoundError):
        repo.delete(alert_id="ghost", user_id="user-1")
