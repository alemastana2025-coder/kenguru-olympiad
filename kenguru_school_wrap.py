"""KENGURU long school name layout guard."""
from pathlib import Path
from io import BytesIO

VERSION = "school-wrap-20260930-v1"
MARKER = "KENGURU_SCHOOL_WRAP_V1"

def _wrap_words(draw, base, text, max_width, start_size, min_size, max_lines=2, bold=False):
    import document_image as di
    text = " ".join(str(text or "").split())
    if not text:
        return [], di._font(base, min_size, bold)
    words = text.split()
    for size in range(int(start_size), int(min_size)-1, -1):
        font = di._font(base, size, bold)
        lines, current = [], ""
        for word in words:
            trial = word if not current else current + " " + word
            if draw.textbbox((0,0), trial, font=font)[2] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                    current = word
                else:
                    lines.append(word)
                    current = ""
        if current:
            lines.append(current)
        if len(lines) <= max_lines and all(draw.textbbox((0,0), ln, font=font)[2] <= max_width for ln in lines):
            return lines, font
    font = di._font(base, min_size, bold)
    if len(words) <= 1:
        return [text], font
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa = draw.textbbox((0,0), a, font=font)[2]
        wb = draw.textbbox((0,0), b, font=font)[2]
        score = max(wa, wb)
        if best is None or score < best[0]:
            best = (score, [a,b])
    return best[1], font

def _draw_school(draw, base, text, center_x, center_y, max_width, start, minimum, fill=(11,37,81)):
    lines, font = _wrap_words(draw, base, text, max_width, start, minimum, 2, False)
    if not lines:
        return
    if len(lines) == 1:
        draw.text((center_x, center_y), lines[0], font=font, fill=fill, anchor="mm")
        return
    bbox = draw.textbbox((0,0), "Ag", font=font)
    line_h = max(1, bbox[3]-bbox[1])
    gap = max(2, int(line_h * .18))
    total = line_h*2 + gap
    y1 = center_y - total/2 + line_h/2
    y2 = y1 + line_h + gap
    draw.text((center_x, y1), lines[0], font=font, fill=fill, anchor="mm")
    draw.text((center_x, y2), lines[1], font=font, fill=fill, anchor="mm")

def _install_png_patch():
    import document_image as di
    if getattr(di, "_kenguru_school_wrap_installed", False):
        return
    def render(base, row, verify_url):
        from PIL import Image, ImageDraw
        import qrcode
        award = str(row["award"] or "")
        certificate = "сертификаты" in award.lower()
        template = Path(base) / ("certificate_template.png" if certificate else "diploma_template.png")
        with Image.open(template) as source:
            image = source.convert("RGBA")
        draw = ImageDraw.Draw(image)
        width, height = image.size
        sx = width / 1414
        date_box=(int(width*.765),int(height*.164),int(width*.975),int(height*.211))
        draw.rounded_rectangle(date_box,radius=max(5,int(8*sx)),fill=(238,248,255,252))
        di._draw_centered(draw,base,"15–30 ҚЫРКҮЙЕК",width*.87,height*.187,width*.20,29*sx,16,True,(7,26,58))
        if certificate:
            name_y, school_y, grade_y, supervisor_y=.447,.516,.586,.625
        else:
            name_y, school_y, grade_y, supervisor_y=.473,.543,.633,.654
        di._draw_centered(draw,base,row["full_name"],width*.50,height*name_y,width*.58,43*sx,22)
        _draw_school(draw,base,row["school"],width*.50,height*school_y,width*.58,27*sx,13,(11,37,81))
        grade_x=width*(.50 if certificate else .349)
        di._draw_centered(draw,base,row["grade"],grade_x,height*grade_y,width*(.43 if certificate else .10),31*sx,17)
        if not certificate:
            place=award.split()[0] if award.startswith(("I ","II ","III ")) else ""
            di._draw_centered(draw,base,place,width*.744,height*grade_y,width*.10,31*sx,17)
        supervisor=str(row["supervisor"] or "").strip()
        if supervisor:
            di._draw_centered(draw,base,f"Жетекшісі: {supervisor}",width*.50,height*supervisor_y,width*(.60 if certificate else .70),16*sx,10)
        number=str(row["diploma_no"] or "").strip()
        di._draw_centered(draw,base,f"№ {number}",width*.845,height*.967,width*.24,16*sx,10)
        qr=qrcode.make(verify_url).convert("RGBA")
        qr_size=int(width*(.122 if certificate else .124))
        qr=qr.resize((qr_size,qr_size),Image.Resampling.LANCZOS)
        qr_x=int(width*(1-(.046 if certificate else .042))-qr_size)
        qr_y=int(height*(1-(.066 if certificate else .062))-qr_size)
        pad=max(4,int(width*.0045))
        draw.rounded_rectangle((qr_x-pad,qr_y-pad,qr_x+qr_size+pad,qr_y+qr_size+pad),radius=pad,fill="white")
        image.alpha_composite(qr,(qr_x,qr_y))
        output=BytesIO()
        rgb=image.convert("RGB")
        palette=rgb.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        try:
            palette.save(output,"PNG",optimize=False,compress_level=3)
            payload=output.getvalue()
        finally:
            output.close(); palette.close(); rgb.close(); qr.close(); image.close()
        return payload, number
    di._render_document = render
    try:
        with di._DOCUMENT_LOCK:
            di._DOCUMENT_CACHE.clear()
    except Exception:
        pass
    di._kenguru_school_wrap_installed = True

def _patch_browser_assets(base):
    static = Path(base) / "static"
    css_path = static / "style.css"
    app_path = static / "app.js"
    css = css_path.read_text(encoding="utf-8")
    js = app_path.read_text(encoding="utf-8")
    if MARKER not in css:
        css += """
/* KENGURU_SCHOOL_WRAP_V1 */
.diplomaTemplate .templateSchool{
  white-space:normal!important;
  overflow:visible!important;
  text-overflow:clip!important;
  display:flex;
  align-items:center;
  justify-content:center;
  line-height:1.08!important;
  height:5.4%;
  transform:translateY(-1.4%);
  padding:0 .4%;
  box-sizing:border-box;
  overflow-wrap:normal;
  word-break:normal;
}
"""
        css_path.write_text(css, encoding="utf-8")
    if MARKER not in js:
        inject = """
// KENGURU_SCHOOL_WRAP_V1
function fitSchoolText(el,isCertificate){
  if(!el)return;
  const n=(el.textContent||'').trim().length;
  const size=n>125?0.82:n>105?0.92:n>85?1.02:n>65?1.15:1.45;
  el.style.fontSize=size+'cqw';
  el.style.whiteSpace='normal';
  el.style.overflow='visible';
  el.style.textOverflow='clip';
  el.style.lineHeight='1.08';
}
"""
        js = inject + "\n" + js
        old = "byId('dipSchool').textContent=s.school||'';"
        new = "byId('dipSchool').textContent=s.school||'';fitSchoolText(byId('dipSchool'),isCertificate);"
        if old not in js:
            raise RuntimeError("School wrap: dipSchool assignment anchor changed")
        js = js.replace(old,new,1)
        app_path.write_text(js, encoding="utf-8")

def register_school_wrap(app):
    if app.title != "Kenguru Olympiad" or getattr(app.state,"kenguru_school_wrap_registered",False):
        return
    app.state.kenguru_school_wrap_registered=True
    @app.on_event("startup")
    async def start_school_wrap():
        import main
        if main.app is not app:
            return
        _install_png_patch()
        _patch_browser_assets(main.BASE)
        app.state.kenguru_school_wrap_installed=True
        print("[KENGURU] SCHOOL WRAP ACTIVE: FULL SCHOOL NAME; UP TO 2 LINES",flush=True)
