"""Validadores y utilidades para URLs de vídeo (YouTube)."""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
    "youtube-nocookie.com",
}


def extract_youtube_id(url: str) -> Optional[str]:
    """Extrae el ID de 11 caracteres de una URL válida de YouTube, o None si no es válida."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_YOUTUBE_HOSTS:
        return None

    video_id: Optional[str] = None
    path_parts = [p for p in parsed.path.split("/") if p]

    if host == "youtu.be":
        video_id = path_parts[0] if path_parts else None
    elif parsed.path == "/watch":
        video_id = (parse_qs(parsed.query).get("v") or [None])[0]
    elif len(path_parts) >= 2 and path_parts[0] in ("embed", "shorts", "live"):
        video_id = path_parts[1]

    if video_id and YOUTUBE_ID_RE.match(video_id):
        return video_id
    return None


def validate_youtube_url(value: str) -> None:
    """Valida que la URL pertenezca a YouTube y contenga un identificador de vídeo válido."""
    if not value:
        return
    if extract_youtube_id(value) is None:
        raise ValidationError(
            _("Introduce una URL válida de YouTube (youtube.com/watch?v=..., youtu.be/... o youtube.com/shorts/...).")
        )
