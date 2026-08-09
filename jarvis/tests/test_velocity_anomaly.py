import pytest
import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.memory import Memory, close_shared_db_connections
from jarvis.awareness import detect_stock_velocity_anomaly


def test_steady_consumption_no_anomaly():
    """Steady consumption rate should NOT trigger a velocity anomaly alert."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            db_path = os.path.join(tmp_dir, "test_jarvis.db")
            mem = Memory(db_path=db_path)

            now = datetime.now()
            sku = "SKU-STEADY"
            item_name = "Wireless Mouse"

            # Log steady 5 units per day over past 14 days
            for day in range(14, 0, -1):
                ts = (now - timedelta(days=day)).isoformat()
                mem.log_inventory_event(
                    sku=sku,
                    item_name=item_name,
                    quantity_changed=-5,
                    event_type="sale",
                    reorder_threshold=10,
                    timestamp=ts
                )

            alerts = detect_stock_velocity_anomaly(
                db_path=db_path,
                anomaly_threshold=1.8,
                cooldown_minutes=0,
                data_dir=tmp_dir
            )
            assert len(alerts) == 0, f"Expected 0 alerts for steady consumption, got: {alerts}"
        finally:
            close_shared_db_connections()


def test_consumption_spike_triggers_velocity_anomaly():
    """Sales spike burst (e.g. 4x faster) SHOULD trigger a velocity anomaly alert."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            db_path = os.path.join(tmp_dir, "test_jarvis.db")
            mem = Memory(db_path=db_path)

            now = datetime.now()
            sku = "SKU-SPIKE"
            item_name = "Mechanical Keyboard"

            # Baseline: days 14-8, 2 units per day (low consumption)
            for day in range(14, 7, -1):
                ts = (now - timedelta(days=day)).isoformat()
                mem.log_inventory_event(
                    sku=sku,
                    item_name=item_name,
                    quantity_changed=-2,
                    event_type="sale",
                    reorder_threshold=10,
                    timestamp=ts
                )

            # Spike: days 7-1, 15 units per day (high consumption burst!)
            for day in range(7, 0, -1):
                ts = (now - timedelta(days=day)).isoformat()
                mem.log_inventory_event(
                    sku=sku,
                    item_name=item_name,
                    quantity_changed=-15,
                    event_type="sale",
                    reorder_threshold=10,
                    timestamp=ts
                )

            alerts = detect_stock_velocity_anomaly(
                db_path=db_path,
                anomaly_threshold=1.8,
                cooldown_minutes=0,
                data_dir=tmp_dir
            )

            assert len(alerts) == 1, f"Expected 1 anomaly alert, got {len(alerts)}"
            alert = alerts[0]
            assert alert["sku"] == "SKU-SPIKE"
            assert alert["ratio"] >= 1.8
            assert "selling roughly" in alert["alert_text"]
            assert "faster than usual" in alert["alert_text"]
        finally:
            close_shared_db_connections()
