import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.api_client import JarvisAPIClient
from jarvis.awareness import GlobalAwarenessManager, detect_stock_velocity_anomaly

def test_system_prompt_proactive_persona():
    """Verify that system prompt contains proactive persona rules and guardrails."""
    client = JarvisAPIClient()
    prompt = client._load_system_prompt()
    
    assert "Ask, don't pepper — one well-placed question beats three reflexive ones." in prompt
    assert "Clarifying ambiguous requests" in prompt
    assert "Action confirmation" in prompt
    assert "Post-completion next steps" in prompt
    assert "Mild observations" in prompt
    assert "Shall I go with the usual, sir" in prompt
    assert "Might I suggest reviewing this before it goes out, sir?" in prompt
    assert "Might I ask if that's intentional, sir?" in prompt

def test_awareness_question_phrasing():
    """Verify that velocity anomaly alert in awareness module is question-phrased."""
    import tempfile
    from jarvis.memory import Memory, close_shared_db_connections
    from datetime import datetime, timedelta

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            db_path = os.path.join(tmp_dir, "test_jarvis.db")
            mem = Memory(db_path=db_path)
            now = datetime.now()
            sku = "SKU-SPIKE"
            item_name = "Mechanical Keyboard"

            # Baseline: low sales
            for day in range(14, 7, -1):
                ts = (now - timedelta(days=day)).isoformat()
                mem.log_inventory_event(
                    sku=sku, item_name=item_name, quantity_changed=-2,
                    event_type="sale", reorder_threshold=10, timestamp=ts
                )

            # Spike: high sales
            for day in range(7, 0, -1):
                ts = (now - timedelta(days=day)).isoformat()
                mem.log_inventory_event(
                    sku=sku, item_name=item_name, quantity_changed=-15,
                    event_type="sale", reorder_threshold=10, timestamp=ts
                )

            alerts = detect_stock_velocity_anomaly(
                db_path=db_path, anomaly_threshold=1.8, cooldown_minutes=0, data_dir=tmp_dir
            )

            assert len(alerts) == 1
            alert_text = alerts[0]["alert_text"]
            assert alert_text.startswith("Sir,")
            assert "running low faster than usual" in alert_text
            assert "Shall I place a reorder?" in alert_text
        finally:
            close_shared_db_connections()
