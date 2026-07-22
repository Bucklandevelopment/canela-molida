"""Generación de imagen 1:1 para el post (Stable Diffusion WebUI / ComfyUI)."""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class ImageRenderer:
    """
    Cliente HTTP para un backend de Stable Diffusion.

    Por defecto habla el dialecto AUTOMATIC1111 SD WebUI
    (POST /sdapi/v1/txt2img, devuelve `images: [base64,...]`).
    Apunta `IMAGE_BASE_URL` a otro backend si usas ComfyUI o similar
    (en ese caso ajusta el método `generate` para tu API).
    """

    def __init__(
        self,
        base_url: str,
        output_dir: Path,
        width: int = 1080,
        height: int = 1080,
        steps: int = 28,
        sampler: str = "DPM++ 2M Karras",
        cfg_scale: float = 6.5,
        timeout: float = 180.0,
        model_override: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.steps = steps
        self.sampler = sampler
        self.cfg_scale = cfg_scale
        self.timeout = timeout
        self.model_override = model_override

    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = -1,
    ) -> Path:
        """Genera y persiste un PNG. Devuelve la ruta absoluta."""
        if not prompt.strip():
            raise ValueError("Empty image prompt")

        body = {
            "prompt": prompt,
            "negative_prompt": negative_prompt
            or "text, watermark, logo, signature, blurry, lowres, deformed, "
            "bad anatomy, extra fingers, jpeg artifacts",
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "sampler_name": self.sampler,
            "cfg_scale": self.cfg_scale,
            "seed": seed,
            "n_iter": 1,
            "batch_size": 1,
        }
        if self.model_override:
            body["override_settings"] = {"sd_model_checkpoint": self.model_override}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/sdapi/v1/txt2img", json=body)
            resp.raise_for_status()
            data = resp.json()

        images = data.get("images") or []
        if not images:
            raise RuntimeError("Image backend returned no images")

        png_bytes = base64.b64decode(images[0].split(",", 1)[-1])
        out_path = self.output_dir / f"{uuid4().hex}.png"

        # Pillow opcional: validamos y reescribimos en formato canónico.
        try:
            from PIL import Image  # type: ignore

            img = Image.open(BytesIO(png_bytes)).convert("RGB")
            if img.size != (self.width, self.height):
                img = img.resize((self.width, self.height))
            img.save(out_path, format="PNG", optimize=True)
        except Exception:
            out_path.write_bytes(png_bytes)

        return out_path


@lru_cache
def get_image_renderer() -> ImageRenderer:
    settings = get_settings()
    base_url = os.getenv("IMAGE_BASE_URL", "http://localhost:7860")
    output_dir = Path(settings.data_dir) / "instagram" / "images"
    return ImageRenderer(
        base_url=base_url,
        output_dir=output_dir,
        width=int(os.getenv("IMAGE_WIDTH", "1080")),
        height=int(os.getenv("IMAGE_HEIGHT", "1080")),
        steps=int(os.getenv("IMAGE_STEPS", "28")),
        sampler=os.getenv("IMAGE_SAMPLER", "DPM++ 2M Karras"),
        cfg_scale=float(os.getenv("IMAGE_CFG_SCALE", "6.5")),
        timeout=float(os.getenv("IMAGE_TIMEOUT", "180")),
        model_override=os.getenv("IMAGE_MODEL") or None,
    )
