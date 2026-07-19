def build_alert_message(symbol: str, ltp: float, target: float, direction: str) -> str:
    arrow = "▲" if direction == "above" else "▼"
    return (
        f"{arrow} Price Alert Triggered\n"
        f"Symbol: {symbol}\n"
        f"Current Price: {ltp:.2f}\n"
        f"Target: {target:.2f} ({direction})"
    )


def build_digest_message(portfolio_pnl: float, top_gainers: list, top_losers: list) -> str:
    lines = [f"📊 Daily Market Digest\nPortfolio P&L today: {portfolio_pnl:+.2f}\n"]
    if top_gainers:
        lines.append("Top Gainers:")
        for g in top_gainers[:5]:
            lines.append(f"  {g['Symbol']} +{g['ChangePct']:.1f}%")
    if top_losers:
        lines.append("Top Losers:")
        for l in top_losers[:5]:
            lines.append(f"  {l['Symbol']} {l['ChangePct']:.1f}%")
    return "\n".join(lines)
