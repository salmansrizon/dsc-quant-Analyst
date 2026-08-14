"""Behaviour tables against the real dataset (#86).

The DDL that makes behaviour_events a partition-expiring table can't be asserted
offline — this checks the live table is actually partitioned by event_date with
the 8-day expiry, so the storage lifecycle (which replaces a DELETE) is real.
"""
import pytest

from backend import db

pytestmark = pytest.mark.integration


def test_behaviour_events_is_partitioned_with_expiry():
    tbl = db.client().get_table(db.qualified_name("behaviour_events"))
    assert tbl.time_partitioning is not None
    assert tbl.time_partitioning.field == "event_date"
    # 8 days, expressed in ms by the API.
    assert tbl.time_partitioning.expiration_ms == 8 * 24 * 60 * 60 * 1000


def test_behaviour_summary_has_a_current_view():
    # Versioned table -> _current view exists (unlike the raw event log).
    view = db.client().get_table(db.qualified_name("behaviour_summary_current"))
    assert view is not None
