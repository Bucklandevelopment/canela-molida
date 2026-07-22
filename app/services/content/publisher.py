"""Publicación a Instagram via Graph API (cuenta Business/Creator)."""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


class InstagramPublisher:
    """
    Publica posts single-image vía Graph API.

    Requisitos (configuras tú una vez):
      - Cuenta Instagram Business o Creator
      - Conectada a una Facebook Page
      - App de Meta con permisos:
        instagram_basic, instagram_content_publish, pages_show_list
      - Long-lived access token

    Variables de entorno:
      IG_USER_ID         (Business account id)
      IG_ACCESS_TOKEN    (long-lived token)
      IG_PUBLIC_BASE_URL (URL pública desde donde Meta puede descargar la imagen)

    Pipeline (Graph API):
      1) POST /{ig-user-id}/media       → image_url + caption  → returns container id
      2) POST /{ig-user-id}/media_publish → creation_id        → returns media id
      3) (opcional) GET /{media-id}     → permalink
    """

    def __init__(
        self,
        ig_user_id: str,
        access_token: str,
        public_base_url: str,
        timeout: float = 60.0,
    ) -> None:
        self.ig_user_id = ig_user_id
        self.access_token = access_token
        self.public_base_url = public_base_url.rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.ig_user_id and self.access_token and self.public_base_url)

    def _public_url_for(self, image_path: Path) -> str:
        return f"{self.public_base_url}/instagram/images/{image_path.name}"

    async def publish(
        self,
        image_path: Path,
        caption: str,
    ) -> dict:
        if not self.configured:
            raise RuntimeError(
                "Instagram publisher not configured. Set IG_USER_ID, "
                "IG_ACCESS_TOKEN and IG_PUBLIC_BASE_URL in .env"
            )
        if not image_path.exists():
            raise FileNotFoundError(image_path)

        image_url = self._public_url_for(image_path)
        base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.ig_user_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            create = await client.post(
                f"{base}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": self.access_token,
                },
            )
            create.raise_for_status()
            container_id = create.json()["id"]

            # Esperamos a que Meta procese el contenedor.
            for _ in range(20):
                status_resp = await client.get(
                    f"https://graph.facebook.com/{GRAPH_API_VERSION}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": self.access_token,
                    },
                )
                status_resp.raise_for_status()
                status_code = status_resp.json().get("status_code")
                if status_code == "FINISHED":
                    break
                if status_code == "ERROR":
                    raise RuntimeError(
                        f"Container {container_id} ended in ERROR state"
                    )
                await asyncio.sleep(2)

            publish = await client.post(
                f"{base}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
            )
            publish.raise_for_status()
            media_id = publish.json()["id"]

            permalink = None
            try:
                pl = await client.get(
                    f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}",
                    params={
                        "fields": "permalink",
                        "access_token": self.access_token,
                    },
                )
                pl.raise_for_status()
                permalink = pl.json().get("permalink")
            except Exception:  # permalink es nice-to-have
                pass

        return {"media_id": media_id, "permalink": permalink}


@lru_cache
def get_publisher() -> InstagramPublisher:
    return InstagramPublisher(
        ig_user_id=os.getenv("IG_USER_ID", ""),
        access_token=os.getenv("IG_ACCESS_TOKEN", ""),
        public_base_url=os.getenv("IG_PUBLIC_BASE_URL", ""),
    )
