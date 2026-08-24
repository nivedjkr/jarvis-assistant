import os
import pytest
from fastapi.testclient import TestClient
from jarvis.api import app, api_client
from jarvis.semantic_memory import SemanticMemory

def test_semantic_memory_prewarm():
    mem = SemanticMemory()
    mem.prewarm()
    assert mem.model is not None

def test_mobile_static_files():
    client = TestClient(app)
    
    res_index = client.get("/mobile/")
    assert res_index.status_code == 200
    assert "J.A.R.V.I.S." in res_index.text
    
    res_app = client.get("/mobile/app.js")
    assert res_app.status_code == 200
    assert "initOrbVisualizer" in res_app.text
    
    res_css = client.get("/mobile/styles.css")
    assert res_css.status_code == 200
    assert "orbCanvas" in res_css.text
    
    res_cfg = client.get("/mobile/config.json")
    assert res_cfg.status_code == 200
    assert "ws_token" in res_cfg.json()

def test_vitals_endpoint():
    client = TestClient(app)
    res = client.get("/vitals")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_usage" in data
    assert "ram_usage" in data
