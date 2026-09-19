"""
VisionService for JARVIS (Mark 5.3.0 Cross-Modal Vision Architecture)
Provides desktop and browser screen capture, image preprocessing, and multimodal
visual analysis using NVIDIA NIM's meta/llama-3.2-11b-vision-instruct.
"""

import os
import io
import time
import base64
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image

from jarvis.llm_provider import get_shared_http_client
from openai import AsyncOpenAI


class VisionService:
    """Handles screen capture, image optimization, and multimodal LLM inspection."""

    def __init__(self):
        self.data_dir = Path("jarvis/data/screenshots")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vision_model = "meta/llama-3.2-11b-vision-instruct"
        
        api_key = os.getenv("NVIDIA_NIM_API_KEY") or "mock_key"
        self.client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            http_client=get_shared_http_client()
        )

    def capture_screen(self, output_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        Captures the primary desktop screen using native Windows .NET System.Drawing.
        Saves as PNG and returns (success, file_path_or_error).
        """
        if not output_path:
            timestamp = int(time.time() * 1000)
            target = self.data_dir / f"screen_{timestamp}.png"
        else:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)

        target_abs = str(target.resolve())

        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save('{target_abs}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False
            )
            if res.returncode != 0:
                return False, f"PowerShell screen capture failed: {res.stderr}"
            if not os.path.exists(target_abs):
                return False, f"Screen capture file '{target_abs}' was not generated."
            return True, target_abs
        except Exception as e:
            return False, f"Screen capture exception: {str(e)}"

    def _encode_image(self, file_path: str, max_dimension: int = 1600) -> Tuple[str, str]:
        """Reads, resizes, and base64 encodes an image. Returns (base64_str, mime_type)."""
        with Image.open(file_path) as img:
            # Convert RGBA to RGB for standard JPEG/PNG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Downscale large screenshots to optimize latency and token limit
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            return b64_str, "image/jpeg"

    async def analyze_image(
        self,
        image_path: str,
        prompt: Optional[str] = None
    ) -> str:
        """
        Sends an image to meta/llama-3.2-11b-vision-instruct for detailed visual inspection.
        """
        if not os.path.exists(image_path):
            return f"FAILED: Image file '{image_path}' does not exist."

        default_prompt = (
            "Analyze this screen capture/image in detail. "
            "Report: 1) Active windows, apps, or UI layouts; "
            "2) Visible text, buttons, or controls; "
            "3) Any visible UI bugs, overlapping elements, broken formatting, or visual glitches."
        )
        user_prompt = prompt.strip() if prompt and prompt.strip() else default_prompt

        try:
            b64_str, mime_type = self._encode_image(image_path)
            data_uri = f"data:{mime_type};base64,{b64_str}"

            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}}
                    ]
                }],
                max_tokens=1024,
                temperature=0.2
            )
            analysis = response.choices[0].message.content or "No visual analysis returned."
            return analysis.strip()
        except Exception as e:
            return f"Vision Model Error: {str(e)}"

    async def inspect_screen(self, query: Optional[str] = None) -> str:
        """One-shot capture of the desktop screen followed by vision analysis."""
        ok, path_or_err = self.capture_screen()
        if not ok:
            return f"Screen inspection failed: {path_or_err}"
        
        prompt = query or "Describe what is currently on screen, identifying active applications, layout, and visual bugs."
        analysis = await self.analyze_image(path_or_err, prompt=prompt)
        return f"Desktop Screenshot Captured ({path_or_err}):\n\n{analysis}"


# Singleton instance
_vision_service: Optional[VisionService] = None

def get_vision_service() -> VisionService:
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService()
    return _vision_service
