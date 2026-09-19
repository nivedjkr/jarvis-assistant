import os
import pytest
from pathlib import Path
from PIL import Image
from jarvis.vision_service import VisionService, get_vision_service
from jarvis.tools import ToolRegistry, validate_tool_schemas
from jarvis.cli import JarvisAssistant


def test_vision_service_singleton_and_init():
    vs = get_vision_service()
    assert vs is not None
    assert vs.vision_model == "meta/llama-3.2-11b-vision-instruct"


def test_vision_image_encoding(tmp_path):
    vs = get_vision_service()
    test_img = tmp_path / "test_color.png"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(test_img, format="PNG")
    
    b64_str, mime_type = vs._encode_image(str(test_img))
    assert len(b64_str) > 0
    assert mime_type == "image/jpeg"


def test_vision_tools_registered_and_validated():
    registry = ToolRegistry()
    assert validate_tool_schemas(registry) is True
    assert "analyze_image" in registry.tools
    assert "inspect_screen" in registry.tools


@pytest.mark.asyncio
async def test_analyze_image_sandboxing():
    registry = ToolRegistry()
    
    # Path outside allowed sandbox
    res = await registry.execute("analyze_image", {"path": "C:/Windows/System32/config/SAM"})
    assert "ACCESS DENIED" in res
    
    # Blocked pattern check
    res_env = await registry.execute("analyze_image", {"path": ".env.backup"})
    assert "ACCESS DENIED" in res_env


@pytest.mark.asyncio
async def test_analyze_image_execution(tmp_path):
    registry = ToolRegistry()
    
    # Create test image in jarvis/data/screenshots
    test_img = Path("jarvis/data/screenshots/test_unit_img.png")
    test_img.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (20, 20), color="green")
    img.save(test_img, format="PNG")
    
    try:
        res = await registry.execute("analyze_image", {
            "path": str(test_img),
            "prompt": "What color is this image?"
        })
        assert len(res) > 0
        assert "FAILED" not in res
    finally:
        if test_img.exists():
            test_img.unlink()


@pytest.mark.asyncio
async def test_cli_vision_slash_commands():
    app = JarvisAssistant()
    
    # /vision without args
    res = await app.process("/vision")
    assert "/vision <image_path>" in res
    
    # Check help includes vision
    res_help = await app.process("/help")
    assert "/screen" in res_help
    assert "/vision" in res_help
    assert "registered tools" in res_help
