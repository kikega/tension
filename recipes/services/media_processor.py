"""Validación y procesamiento de imágenes de recetas a WebP responsivo."""

from io import BytesIO
from pathlib import Path
from typing import Dict, Tuple
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

VARIANT_WIDTHS = {
    "large": 1600,
    "medium": 800,
    "thumb": 400,
}
STEP_VARIANT_WIDTHS = {
    "large": 1200,
    "thumb": 400,
}

WEBP_QUALITY = 82
WEBP_METHOD = 4


def validate_uploaded_image(uploaded_file) -> None:
    """Valida tamaño y formato real (vía Pillow) de un fichero de imagen subido."""
    if not uploaded_file:
        return
    size = getattr(uploaded_file, "size", None)
    if size is not None and size > MAX_IMAGE_FILE_SIZE_BYTES:
        raise ValidationError(_("La imagen supera el tamaño máximo permitido (10 MB)."))

    pos = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            fmt = (img.format or "").upper()
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(_("El fichero no es una imagen válida o está dañado.")) from exc
    finally:
        if pos is not None and hasattr(uploaded_file, "seek"):
            uploaded_file.seek(pos)

    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(_("Formato no permitido. Usa JPG, PNG o WebP."))


def _resize_to_max_width(img: Image.Image, max_width: int) -> Image.Image:
    """Redimensiona manteniendo proporción sin ampliar imágenes pequeñas."""
    if img.width <= max_width:
        return img.copy()
    ratio = max_width / float(img.width)
    new_height = max(1, int(round(img.height * ratio)))
    return img.resize((max_width, new_height), Image.Resampling.LANCZOS)


def _encode_webp(img: Image.Image) -> bytes:
    """Codifica a WebP eliminando metadatos EXIF."""
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=WEBP_METHOD)
    return buf.getvalue()


def process_image_variants(
    uploaded_file,
    widths: Dict[str, int] | None = None,
) -> Tuple[Dict[str, ContentFile], Tuple[int, int]]:
    """Convierte una imagen subida en variantes WebP normalizadas (EXIF transpuesto y eliminado).

    Returns:
        (variants_dict, (large_width, large_height))
    """
    validate_uploaded_image(uploaded_file)
    target_widths = widths or VARIANT_WIDTHS

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    with Image.open(uploaded_file) as raw_img:
        transposed = ImageOps.exif_transpose(raw_img)
        if transposed.mode in ("RGBA", "LA") or (transposed.mode == "P" and "transparency" in transposed.info):
            base_img = transposed.convert("RGBA")
        else:
            base_img = transposed.convert("RGB")

    stem = Path(getattr(uploaded_file, "name", "imagen")).stem
    token = uuid.uuid4().hex[:8]

    variants: Dict[str, ContentFile] = {}
    large_size = (base_img.width, base_img.height)

    for key, max_w in target_widths.items():
        resized = _resize_to_max_width(base_img, max_w)
        if key == "large":
            large_size = (resized.width, resized.height)
        data = _encode_webp(resized)
        filename = f"{stem}_{token}_{key}.webp"
        variants[key] = ContentFile(data, name=filename)

    return variants, large_size
