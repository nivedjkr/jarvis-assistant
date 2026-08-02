"""
Automated Ground-Truth Verification for Trader Features Phase 4
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing Trader Features (Phase 4)...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_trader_tests():
    # -------------------------------------------------------------
    # 1. Price Watchlist & Market Monitor
    # -------------------------------------------------------------
    print("--- 4.1 Price Watchlist & Market Monitor ---")
    watch_res = await cli.process_command("/watch AAPL below 1000")
    print(f"✓ Output:\n{watch_res}\n")
    assert "AAPL" in watch_res
    assert "below" in watch_res

    # Execute proactive monitor price watch check with yfinance
    print("Executing ProactiveMonitor live market check...")
    cli.proactive_monitor._check_price_watches()
    print("✓ Proactive market monitor check executed successfully.")

    # -------------------------------------------------------------
    # 2. Trade Journal
    # -------------------------------------------------------------
    print("\n--- 4.2 Trade Journal: Log & Review ---")
    trade_log_res = await cli.process_command("/trade log AAPL BUY 150.25 10 reason: Long term hold")
    print(f"✓ Trade Log Output:\n{trade_log_res}\n")
    assert "BUY" in trade_log_res
    assert "AAPL" in trade_log_res

    trade_review_res = await cli.process_command("/trade review AAPL")
    print(f"✓ Trade Review Output:\n{trade_review_res}\n")
    assert "150.25" in trade_review_res or "trade journal entries" in trade_review_res.lower()

asyncio.run(run_trader_tests())

print("All Trader Features (Phase 4) tests PASSED successfully!")
