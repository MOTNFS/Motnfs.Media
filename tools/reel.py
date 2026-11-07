#!/usr/bin/env python3
"""ريل متنفس ٩:١٦ من صور حقيقية ونص على الشاشة.
python3 reel.py spec.json out.mp4
spec = {"assets": "<مجلد فيه fonts/ و brand/>", "audio": "ambient"|"<ملف صوت>",
        "slides": [{"photo": "<مسار>", "text": "<نص>", "small": "<سطر صغير اختياري>", "dur": 2.5}],
        "end": {"text": "<سطر الختام>", "sub": "<سطر صغير>", "dur": 2.5}}
المواصفات: ١٠٨٠×١٩٢٠، ٣٠ إطاراً، H.264 High CRF 20، AAC 48kHz، faststart.
النص داخل المنطقة الآمنة: x ٩٦–٩٤٠ و y ٢٧٠–١٢٥٠، بعيداً عن أزرار يمين الشاشة وأسفلها.
"""
import sys, json, pathlib, subprocess, shutil, tempfile

W, H, FPS = 1080, 1920, 30


def page(spec, assets):
    A = pathlib.Path(assets).resolve()
    fonts = "".join(
        f"@font-face{{font-family:P;font-weight:{w};src:url('file://{A}/fonts/plex-arabic-{w}-{s}.woff2')}}"
        for w in (400, 500, 600) for s in ("arabic", "latin"))
    t, layers = 0.0, []
    for i, s in enumerate(spec["slides"]):
        d = s.get("dur", 2.5)
        small = f'<div class="sm">{s["small"]}</div>' if s.get("small") else ""
        layers.append(f'''<section style="--a:{t}s;--b:{t+d}s;--d:{d+0.6}s">
<div class="ph" style="background-image:url('file://{pathlib.Path(s["photo"]).resolve()}')"></div><div class="vl"></div>
<div class="tx"><div class="t">{s["text"]}</div>{small}</div></section>''')
        t += d
    e = spec.get("end", {})
    ed = e.get("dur", 2.5)
    last_photo = pathlib.Path(spec["slides"][-1]["photo"]).resolve()
    layers.append(f'''<section class="end" style="--a:{t}s;--b:{t+ed+1}s;--d:{ed+0.6}s">
<div class="ph" style="background-image:url('file://{last_photo}');filter:blur(6px) brightness(.55)"></div><div class="vl"></div>
<div class="ec"><img src="file://{A}/brand/logo-sand.png"><div class="t">{e.get("text","")}</div><div class="sm">{e.get("sub","motnfs.com")}</div></div></section>''')
    total = t + ed
    html = f"""<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>{fonts}
*{{margin:0;padding:0;box-sizing:border-box}}html,body{{width:{W}px;height:{H}px;overflow:clip;background:#170838}}
body{{font-family:P,sans-serif;color:#fff}}
section{{position:absolute;inset:0;overflow:hidden;opacity:0;animation:show .45s ease var(--a) forwards,hide .45s ease var(--b) forwards}}
@keyframes show{{to{{opacity:1}}}}@keyframes hide{{to{{opacity:0}}}}
.ph{{position:absolute;inset:-80px;background-size:cover;background-position:center;animation:kb var(--d) linear var(--a) both}}
@keyframes kb{{from{{transform:scale(1.04)}}to{{transform:scale(1.16)}}}}
.vl{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(23,8,56,.25) 0%,rgba(23,8,56,.15) 35%,rgba(23,8,56,.78) 62%,rgba(23,8,56,.88) 100%)}}
.tx{{position:absolute;right:96px;left:140px;top:930px;animation:up .6s cubic-bezier(.2,.7,.2,1) var(--a) both}}
@keyframes up{{from{{opacity:0;transform:translateY(30px)}}to{{opacity:1;transform:none}}}}
.t{{font-weight:600;font-size:76px;line-height:1.32;text-wrap:balance;text-shadow:0 2px 18px rgba(0,0,0,.35)}}
.sm{{margin-top:26px;font-weight:500;font-size:40px;color:#F4E0AF;line-height:1.5}}
.end .ec{{position:absolute;right:96px;left:140px;top:640px;text-align:center;animation:up .7s ease var(--a) both}}
.end img{{height:120px}}.end .t{{margin-top:60px;font-size:68px}}
</style></head><body>{''.join(layers)}</body></html>"""
    return html, total


def ambient(seconds, path):
    # صوت هادئ مولّد: نغمتان ناعمتان + ضوضاء خفيفة، مع ظهور واختفاء تدريجي
    f = (f"sine=f=220:d={seconds}[a];sine=f=330:d={seconds}[b];anoisesrc=d={seconds}:c=pink:a=0.02[n];"
         f"[a][b][n]amix=inputs=3:weights=0.5 0.3 1,lowpass=f=1200,volume=0.35,"
         f"afade=t=in:d=1.2,afade=t=out:st={max(seconds-1.5,0)}:d=1.5[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", f, "-map", "[o]",
                    "-ar", "48000", "-ac", "2", path], check=True)


def render(spec_path, out):
    spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    html, total = page(spec, spec["assets"])
    from playwright.sync_api import sync_playwright
    tmp = pathlib.Path(tempfile.mkdtemp())
    hp = tmp / "r.html"; hp.write_text(html, encoding="utf-8")
    fd = tmp / "f"; fd.mkdir()
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(hp.as_uri()); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(400)
        ok = pg.evaluate("document.fonts.check('600 40px P','ع')")
        if not ok:
            raise SystemExit("الخط لم يُحمّل: توقّف")
        seek = "t=>document.getAnimations().forEach(a=>{a.pause();a.currentTime=t})"
        for i in range(int(total * FPS)):
            pg.evaluate(seek, i * 1000 / FPS)
            pg.screenshot(path=str(fd / f"{i:05d}.jpg"), type="jpeg", quality=95)
        b.close()
    aud = spec.get("audio", "ambient")
    ap = str(tmp / "a.m4a") if aud == "ambient" else aud
    if aud == "ambient":
        ambient(total, str(tmp / "a.wav")); ap = str(tmp / "a.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(fd / "%05d.jpg"), "-i", ap,
                    "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(tmp)
    return out, total


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2]))
