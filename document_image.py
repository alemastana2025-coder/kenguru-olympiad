"""Server-rendered KENGURU diploma/certificate PNG downloads."""

from collections import OrderedDict
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from urllib.parse import quote

import qrcode
from fastapi import HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont


# The Render instance has 512 MB RAM.  Pillow font loading and several parallel
# PNG encoders can exceed that limit, so document creation is serialized and a
# small bounded cache is shared by repeated open/download requests.
_DOCUMENT_CACHE = OrderedDict()
_DOCUMENT_CACHE_LIMIT = 16
_DOCUMENT_LOCK = Lock()


@lru_cache(maxsize=128)
def _font(base: Path, size: int, bold: bool = True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_size = max(8, int(size))
    candidates = (
        base / name,
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/dejavu") / name,
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), font_size)
    try:
        return ImageFont.truetype(name, font_size)
    except OSError:
        return ImageFont.load_default(size=font_size)


def _fit_font(draw, base, text, max_width, start, minimum, bold=True):
    size = int(start)
    while size > minimum:
        font = _font(base, size, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 1
    return _font(base, minimum, bold)


def _draw_centered(draw, base, text, center_x, center_y, max_width, start, minimum=13, bold=True, fill=(11, 37, 81)):
    text = str(text or "").strip()
    if not text:
        return
    font = _fit_font(draw, base, text, max_width, start, minimum, bold)
    draw.text((center_x, center_y), text, font=font, fill=fill, anchor="mm")


def _render_document(base: Path, row, verify_url: str):
    award = str(row["award"] or "")
    certificate = "сертификаты" in award.lower()
    template = base / ("certificate_template.png" if certificate else "diploma_template.png")
    with Image.open(template) as source:
        image = source.convert("RGBA")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    sx, sy = width / 1414, height / 1000

    # The official template contains 15–31; the event period ends on the 30th.
    date_box = (int(width * .765), int(height * .164), int(width * .975), int(height * .211))
    draw.rounded_rectangle(date_box, radius=max(5, int(8 * sx)), fill=(238, 248, 255, 252))
    _draw_centered(draw, base, "15–30 ҚЫРКҮЙЕК", width * .87, height * .187, width * .20, 29 * sx, 16, True, (7, 26, 58))

    if certificate:
        name_y, school_y, grade_y, supervisor_y = .447, .516, .586, .625
    else:
        name_y, school_y, grade_y, supervisor_y = .473, .543, .633, .654

    _draw_centered(draw, base, row["full_name"], width * .50, height * name_y, width * .58, 43 * sx, 22)
    _draw_centered(draw, base, row["school"], width * .50, height * school_y, width * .58, 27 * sx, 15)

    grade_x = width * (.50 if certificate else .349)
    _draw_centered(draw, base, row["grade"], grade_x, height * grade_y, width * (.43 if certificate else .10), 31 * sx, 17)

    if not certificate:
        place = award.split()[0] if award.startswith(("I ", "II ", "III ")) else ""
        _draw_centered(draw, base, place, width * .744, height * grade_y, width * .10, 31 * sx, 17)

    supervisor = str(row["supervisor"] or "").strip()
    if supervisor:
        _draw_centered(draw, base, f"Жетекшісі: {supervisor}", width * .50, height * supervisor_y, width * (.60 if certificate else .70), 16 * sx, 10)

    number = str(row["diploma_no"] or "").strip()
    _draw_centered(draw, base, f"№ {number}", width * .845, height * .967, width * .24, 16 * sx, 10)

    qr = qrcode.make(verify_url).convert("RGBA")
    qr_size = int(width * (.122 if certificate else .124))
    qr = qr.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_x = int(width * (1 - (.046 if certificate else .042)) - qr_size)
    qr_y = int(height * (1 - (.066 if certificate else .062)) - qr_size)
    pad = max(4, int(width * .0045))
    draw.rounded_rectangle((qr_x - pad, qr_y - pad, qr_x + qr_size + pad, qr_y + qr_size + pad), radius=pad, fill="white")
    image.alpha_composite(qr, (qr_x, qr_y))

    output = BytesIO()
    rgb = image.convert("RGB")
    palette = rgb.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    try:
        # optimize=True is extremely CPU-heavy on Render's 0.15 CPU instance.
        # A 256-colour palette keeps the PNG around 60% smaller while remaining
        # fast enough for the small instance and visually sharp for diplomas.
        palette.save(output, "PNG", optimize=False, compress_level=3)
        payload = output.getvalue()
    finally:
        output.close()
        palette.close()
        rgb.close()
        qr.close()
        image.close()
    return payload, number


def _document_cache_key(base: Path, row, verify_url: str):
    award = str(row["award"] or "")
    certificate = "сертификаты" in award.lower()
    template = base / ("certificate_template.png" if certificate else "diploma_template.png")
    try:
        template_revision = template.stat().st_mtime_ns
    except OSError:
        template_revision = 0
    return (
        str(base), template_revision, str(row["full_name"] or ""),
        str(row["school"] or ""), str(row["supervisor"] or ""),
        str(row["grade"] or ""), award, str(row["diploma_no"] or ""),
        verify_url,
    )


def _cached_document(base: Path, row, verify_url: str):
    key = _document_cache_key(base, row, verify_url)
    with _DOCUMENT_LOCK:
        cached = _DOCUMENT_CACHE.get(key)
        if cached is not None:
            _DOCUMENT_CACHE.move_to_end(key)
            return cached

        rendered = _render_document(base, row, verify_url)
        _DOCUMENT_CACHE[key] = rendered
        _DOCUMENT_CACHE.move_to_end(key)
        while len(_DOCUMENT_CACHE) > _DOCUMENT_CACHE_LIMIT:
            _DOCUMENT_CACHE.popitem(last=False)
        return rendered


def register_document_route(app, db, base_path):
    base = Path(base_path)

    @app.get("/api/document/{token}")
    def document_png(token: str, request: Request, download: int = 0):
        with db() as connection:
            row = connection.execute(
                """SELECT full_name, school, supervisor, grade, award, diploma_no, submitted_at
                   FROM participants WHERE token=? LIMIT 1""",
                (token,),
            ).fetchone()
        if not row or not row["submitted_at"] or not row["diploma_no"]:
            raise HTTPException(404, "Document not found")

        origin = str(request.base_url).rstrip("/")
        verify_url = f"{origin}/verify?no={quote(str(row['diploma_no']))}"
        payload, number = _cached_document(base, row, verify_url)
        disposition = "attachment" if download else "inline"
        filename = f"KENGURU-{number}.png"
        return Response(
            content=payload,
            media_type="image/png",
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Cache-Control": "private, max-age=300",
                "Content-Length": str(len(payload)),
            },
        )
