"""Behaviour-driven affinity seam (#93 → #96).

The exact re-weighting formula is the fog ticket #107; the behaviour substrate it
reads (`user_affinity`, #86) is not on this trunk yet. This module fixes the
*interface* now so recommendations/feed rank through a stable seam — and ships a
neutral placeholder so the fit-driven spine works today. When #86 lands these
read `user_affinity`; when #107 lands the formula sharpens. Neither touches the
callers.
"""


def engaged_sectors(user_id: str) -> list[str]:
    """Sectors the user has revealed interest in (visits, watchlist, screener).
    Placeholder: empty until the #86 substrate lands — the behaviour-driven
    candidate generator simply contributes nothing until then."""
    return []


def affinity_score(user_id: str, symbol: str) -> float:
    """A bounded interest tilt for `symbol`, in [0, 1] — multiplied into a small
    ranking bonus so affinity can re-rank but never dominate fit (#93 decision).
    Placeholder: neutral 0.0 until the #107 formula lands."""
    return 0.0
