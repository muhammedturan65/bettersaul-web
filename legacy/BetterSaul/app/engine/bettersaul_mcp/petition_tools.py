"""Claude / Cursor için dilekçe iskeleti, biçim ve PDF. Vakıa uydurmaz."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

_PARTY = re.compile(
    r"^(DAVACI(?:\s+VEK[İI]L[İI]?)?|VEK[İI]L[İI]?|DAVALI|DAVA\s+KONUSU|HARCA\s+ESAS(?:\s+DE[ĞG]ER)?|KONU|"
    r"Ad Soyad|T\.C\.\s*Kimlik No|Adres)\s*[:：]\s*(.*)$",
    re.I,
)
_HEAD = re.compile(r"^(DAVACI(?:\s+VEK[İI]L[İI]?)?|DAVALI|KONU)\s*$", re.I)
_SEC = re.compile(
    r"^(A[ÇC]IKLAMALAR|HUKUK[İI]\s+(SEBEPLER|NEDENLER|DAYANAKLAR)|DEL[İI]LLER|"
    r"SONU[CÇ]\s+VE\s+[İI]STEM|EKLER|KONU|DAVA\s+[ŞS]ARTI)\s*:?\s*$",
    re.I,
)
_META = re.compile(r"^\s*(Delil|Hukuki dayanak|Hukuki sonuç)\s*[:：]", re.I)
_DATE = re.compile(r"^\d{1,2}(\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}|\.\d{1,2}\.\d{4})\s*$")

_AY = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)

_CSS = """
@page { size: A4; margin: 18mm 18mm 18mm 20mm; }
html, body { background: #fff; color: #000; margin: 0; }
body, .sheet {
  font-family: "Times New Roman", Times, serif;
  font-size: 12pt; line-height: 1.55; color: #000;
}
.p-tc { text-align: center; font-size: 16pt; font-weight: 700; letter-spacing: .35em; margin: 0 0 6pt; }
.p-court { text-align: center; font-size: 13.5pt; font-weight: 700; margin: 0 0 10pt; }
.p-banner { text-align: center; font-size: 11pt; font-weight: 700; margin: 2pt 0; }
.p-kind { text-align: center; font-size: 12pt; font-weight: 700; margin: 0 0 14pt; }
.row { display: table; width: 100%; margin: 0 0 8pt; text-align: left; }
.row .k { display: table-cell; width: 10.5em; font-weight: 700; vertical-align: top; padding-right: 10pt; white-space: nowrap; }
.row .v { display: table-cell; vertical-align: top; text-align: left; }
.sec { text-align: center; font-weight: 700; font-size: 13pt; letter-spacing: .06em; margin: 14pt 0 8pt; }
.vakia { margin: 0 0 10pt; text-align: left; }
.vakia-h { text-align: center; font-weight: 700; margin: 10pt 0 6pt; }
.vakia .vakia-h { text-align: left; }
.p { margin: 0 0 7pt; text-align: left; }
.sub { margin: 2pt 0 2pt 18pt; text-align: left; }
.lawyer, .sign { text-align: left; margin: 8pt 0 12pt; font-weight: 400; line-height: 1.45; }
.lawyer b, .sign b { font-weight: 700; }
"""

_SKELETONS = {
    "İdare": """T.C.

[İL] NÖBETÇİ İDARE MAHKEMESİ BAŞKANLIĞI'NA

— İVEDİ VE ÖNCELİKLİ İNCELEME TALEPLİDİR —
— YÜRÜTMEYİ DURDURMA TALEPLİDİR —

DAVA DİLEKÇESİ

İptal davası

DAVACI: [ad soyad]
T.C. Kimlik No : ........................
Tebligat adresi : ........................

VEKİLİ: Av. [ad soyad]
[baro]
Adres: ........................

DAVALI: [idare — tek satır; araştırma notu yok]
Adres: ........................

KONU: [işlem tarihi ve adı] iptali ve 2577 sayılı İYUK m. 27 uyarınca yürütmenin durdurulması talebidir.

HARCA ESAS DEĞER: Maktu (Harçlar Kanunu: iptal davasında maktu; nispi kalem yok)

AÇIKLAMALAR :

1- İşlemin tarihi, sayısı ve tebliği.
[Somut işlem, tarih, tebliğ. Uydurma. Gövde: müvekkil.]
Delil : İşlem evrakı ve tebliğ belgesi
Hukuki dayanak : İYUK m. 7
Hukuki sonuç : Tebliğ ve süre olgusu, iptal isteminin süresinde olduğunu gösterir.

2- İşlemin konusu ve müvekkilin hukuki durumu.
[Başvuru, kadro, somut durum.]
Delil : Başvuru / kadro evrakı
Hukuki dayanak : İYUK m. 2
Hukuki sonuç : Müvekkilin iptal davası açmakta hukuki yararı vardır.

3- Hukuka aykırılık (yetki / şekil / sebep / konu / maksat).
[Dayanak madde yalnızca gerçekse. Künye uydurma.]
Delil : [formda adı geçen belgeler]
Hukuki dayanak : [yalnızca çekilen madde]
Hukuki sonuç : Hukuka aykırılık olgusu, işlemin iptalini haklı kılar.

HUKUKİ SEBEPLER :

2577 sayılı İYUK m. 2, m. 27; [yalnızca çekilen kanun maddeleri].
Emsal içtihat (yalnızca resmî tarama): [çekilen künye — yoksa yazma]

DELİLLER :

1. İşlem evrakı ve tebliğ belgesi
2. [formda adı geçen belgeler]
3. Emsal içtihat (yalnızca taranan künye)

SONUÇ VE İSTEM :

Yukarıda açıklanan ve resen nazara alınacak nedenlerle;

1) Davanın ivedi ve öncelikli incelenmesine
2) 2577 sayılı İYUK m. 27 uyarınca yürütmenin durdurulmasına
3) İşlemin iptaline
4) yargılama giderleri ile vekâlet ücretinin davalı tarafa yükletilmesine

karar verilmesini vekâleten talep ederim.

[tarih]

Av. [ad soyad]
Davacı Vekili

EKLER :

1. Vekâletname
2. İşlem evrakı ve tebliğ belgesi
3. [formda adı geçen belgeler]
""",
    "Boşanma": """T.C.

[İL] AİLE MAHKEMESİ'NE

DAVA DİLEKÇESİ

Boşanma davası

DAVACI: [ad soyad]
T.C. Kimlik No : [TCKN]
Tebligat adresi : [adres]

VEKİLİ: Av. [ad soyad]
[baro]

DAVALI: [ad soyad]
T.C. Kimlik No : [TCKN]
Tebligat adresi : [adres]

KONU: Türk Medeni Kanunu m. 166 uyarınca evlilik birliğinin temelinden sarsılması nedeniyle boşanma [ve varsa fer’iler] talepli dava dilekçesidir.

AÇIKLAMALAR :

1- Evliliğin kuruluşu (tarih, evlenme yeri, evlilik cüzdanı).
[Evlilik tarihi ve yer. Uydurma. Gövde: müvekkil.]
Delil : Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi
Hukuki dayanak : TMK m. 166
Hukuki sonuç : Evliliğin kuruluşu olgusu, aşağıda yazılı istemlerin kabulünü haklı kılar.

2- Ortak çocuklar varsa kimlik ve yaşları.
[Yalnızca formdaysa. Uydurma.]
Delil : Nüfus kayıt örneği
Hukuki dayanak : TMK m. 182
Hukuki sonuç : Ortak çocuk olgusu, velayet ve nafaka istemlerini haklı kılar.

3- Birliğin sarsılmasına yol açan somut olaylar (tarih, yer, tanık).
[Tarih, yer, tanık. TMK m. 164 ile 166 karıştırılmasın.]
Delil : Tanık beyanları (isim ve tebliğ adresi yalnızca formdaysa)
Hukuki dayanak : TMK m. 166
Hukuki sonuç : Birliği sarsan olgular, boşanma isteminin kabulünü haklı kılar.

HUKUKİ SEBEPLER :

4721 sayılı TMK m. 166, m. 185; 6100 sayılı HMK m. 119.
Emsal içtihat (yalnızca resmî tarama): [çekilen künye — yoksa yazma]

DELİLLER :

1. Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi
2. [formda adı geçen belgeler]

SONUÇ VE İSTEM :

Yukarıda açıklanan ve resen nazara alınacak nedenlerle;

1) Boşanmaya
2) [yalnızca formdaki fer’iler]
3) yargılama giderleri ile vekâlet ücretinin davalı tarafa yükletilmesine

karar verilmesini vekâleten talep ederim.

[tarih]

Av. [ad soyad]
Davacı Vekili

EKLER :

1. Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi
2. [formda adı geçen belgeler]
""",
    "İş": """T.C.

[İL] İŞ MAHKEMESİ'NE

DAVA DİLEKÇESİ

İşçilik alacakları davası

DAVACI: [ad soyad]
Tebligat adresi : [adres]

VEKİLİ: Av. [ad soyad]
Adres: [büro]

DAVALI: [işveren]
Adres: [adres]

KONU: İşçilik alacaklarının tahsili.

DAVA ŞARTI: 7036 sayılı Kanun m. 3 — arabuluculuk son tutanağı [numara uydurma].

AÇIKLAMALAR :

1- İş ilişkisi ve ücret.
[Başlangıç, görev, ücret. Uydurma. Gövde: müvekkil.]
Delil : SGK hizmet dökümü, bordro
Hukuki dayanak : 4857 sayılı İş Kanunu m. 32
Hukuki sonuç : İş ilişkisi olgusu, alacak istemlerinin kabulünü haklı kılar.

2- Fesih ve ödenmeyen kalemler.
[Yalnızca formdaki kalem ve tutarlar.]
Delil : Arabuluculuk son tutanağı; [formda adı geçen belgeler]
Hukuki dayanak : 7036 sayılı Kanun m. 3
Hukuki sonuç : Ödenmeyen kalemler, tahsil istemini haklı kılar.

HUKUKİ SEBEPLER :

4857 sayılı İş Kanunu m. 32, m. 34; 7036 sayılı Kanun m. 3, m. 5.
Emsal içtihat (yalnızca resmî tarama): [çekilen künye — yoksa yazma]

DELİLLER :

1. SGK hizmet dökümü, bordro
2. Arabuluculuk son tutanağı
3. [formda adı geçen belgeler]

SONUÇ VE İSTEM :

Yukarıda açıklanan ve resen nazara alınacak nedenlerle alacakların davalıdan tahsiline, yargılama giderleri ile vekâlet ücretinin davalı tarafa yükletilmesine karar verilmesini vekâleten talep ederim.

[tarih]

Av. [ad soyad]
Davacı Vekili

EKLER :

1. Vekâletname
2. SGK hizmet dökümü, bordro
3. Arabuluculuk son tutanağı
""",
}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _data_dir() -> Path:
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "BetterSaul"
    else:
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        d = Path(root) / "BetterSaul"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _archive_db() -> Path:
    return _data_dir() / "archive.db"


def _out_dir() -> Path:
    d = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".") / "Downloads" / "BetterSaul-Dilekceler"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tool_text(*parts: str) -> str:
    for p in parts:
        t = (p or "").strip()
        if t and t != "Dilekçe metni boş.":
            return t
    return ""


def _line_after(text: str, label: str) -> str:
    m = re.search(rf"(?im)^{re.escape(label)}\s*[:：]\s*(.+)$", text or "")
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(
        rf"(?im)^{re.escape(label)}\s*$\s*(?:Ad Soyad|Unvan)\s*[:：]\s*(.+)$",
        text or "",
    )
    return (m.group(1) or "").strip() if m else ""


def _guess_court(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for ln in lines[:8]:
        if re.search(r"MAHKEME|BAŞKANLIĞI|DANIŞTAY|SAVCILIK", ln, re.I) and not ln.upper().startswith("T.C"):
            return ln
    return ""


def archive_petition(
    body: str,
    title: str = "dilekce",
    petition_type: str = "",
    pdf_path: str = "",
    research: str = "",
) -> int:
    """Masaüstü Geçmiş ile aynı archive.db. Mevcut satırları silmez."""
    text = (body or "").strip()
    if not text:
        return 0
    db = _archive_db()
    last: Exception | None = None
    for attempt in range(5):
        conn = sqlite3.connect(str(db), timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS petitions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL,
                  user_email TEXT,
                  user_name TEXT,
                  title TEXT,
                  petition_type TEXT,
                  template_name TEXT,
                  court TEXT,
                  parties TEXT,
                  case_summary TEXT,
                  requests TEXT,
                  extra_instructions TEXT,
                  lawyer_name TEXT,
                  lawyer_bar TEXT,
                  lawyer_bar_no TEXT,
                  lawyer_address TEXT,
                  lawyer_phone TEXT,
                  lawyer_email TEXT,
                  prompt TEXT,
                  research TEXT,
                  body TEXT,
                  model_id TEXT,
                  model_name TEXT,
                  pdf_path TEXT
                )
                """
            )
            davaci = _line_after(text, "DAVACI")
            davali = _line_after(text, "DAVALI")
            parties = "\n".join(x for x in (davaci and f"DAVACI: {davaci}", davali and f"DAVALI: {davali}") if x)
            konu = _line_after(text, "DAVA KONUSU") or _line_after(text, "KONU")
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            cur = conn.execute(
                """
                INSERT INTO petitions (
                  created_at, user_email, user_name, title, petition_type, template_name,
                  court, parties, case_summary, requests, extra_instructions,
                  lawyer_name, lawyer_bar, lawyer_bar_no, lawyer_address, lawyer_phone, lawyer_email,
                  prompt, research, body, model_id, model_name, pdf_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    now,
                    "",
                    "",
                    title or "Dilekçe",
                    petition_type or "Dilekçe",
                    "",
                    _guess_court(text),
                    parties,
                    konu,
                    "",
                    "BetterSaul MCP",
                    _line_after(text, "VEKİLİ") or _line_after(text, "VEKILI") or _line_after(text, "DAVACI VEKİLİ"),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "Masaüstünde yazıldı; BetterSaul Geçmiş’e işlendi.",
                    research or "",
                    text,
                    "bettersaul-mcp",
                    "BetterSaul MCP",
                    pdf_path or "",
                ),
            )
            conn.commit()
            return int(cur.lastrowid or 0)
        except sqlite3.OperationalError as exc:
            last = exc
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            time.sleep(0.35 * (attempt + 1))
        finally:
            conn.close()
    raise last or sqlite3.OperationalError("archive.db kilitli")


def _looks_like_petition(text: str) -> bool:
    t = text or ""
    if len(t.strip()) < 350:
        return False
    hits = 0
    if re.search(r"(?m)^T\.C\.\s*$", t):
        hits += 1
    if re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:2000]):
        hits += 1
    if re.search(r"(?m)^DAVACI\b", t):
        hits += 1
    if re.search(r"(?i)SONU[CÇ]\s+VE\s+[İI]STEM", t):
        hits += 1
    return hits >= 2


def auto_archive_petition(text: str, title: str = "", petition_type: str = "") -> int:
    """Biçimlenen dilekçeyi Geçmiş’e yazar; aynı metni tekrar etmez."""
    body = (text or "").strip()
    if not _looks_like_petition(body):
        return 0
    db = _archive_db()
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    try:
        conn = sqlite3.connect(str(db), timeout=15)
        try:
            rows = conn.execute(
                "SELECT id, body FROM petitions ORDER BY id DESC LIMIT 12"
            ).fetchall()
            for rid, old in rows:
                old_b = (old or "").strip()
                if old_b == body:
                    return int(rid or 0)
                if old_b and hashlib.sha256(old_b.encode("utf-8")).hexdigest() == digest:
                    return int(rid or 0)
        finally:
            conn.close()
    except Exception:
        pass
    konu = _line_after(body, "KONU") or _line_after(body, "DAVA KONUSU")
    return archive_petition(
        body,
        title=title or konu or "Dilekçe",
        petition_type=petition_type or "Dilekçe",
    )


def _safe_name(title: str) -> str:
    raw = (title or "dilekce").strip() or "dilekce"
    bad = '<>:"/\\|?*'
    name = "".join("-" if ch in bad else ch for ch in raw).strip(" .-")
    return (name[:60] or "dilekce")


def _tr_date() -> str:
    t = date.today()
    return f"{t.day} {_AY[t.month - 1]} {t.year}"


def _fold_tr(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i")
    t = t.lower().replace("\u0307", "")
    return (
        t.replace("ğ", "g").replace("ş", "s").replace("ö", "o").replace("ü", "u").replace("ç", "c")
    )


def _scan_dict(source: str) -> dict:
    """Kullanıcı / form metninden ad ve usul talebi. Uydurmaz."""
    raw = source or ""
    fold = _fold_tr(raw)
    name = ""
    pats = (
        r"(?i)ad\s*soyad\s*[:：]\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        r"(?i)(?:m[uü]vekkil(?:im)?|davac[ıi])\s*[:：]?\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ]{2,})\b",
    )
    for pat in pats:
        for m in re.finditer(pat, raw):
            cand = re.sub(r"\s+", " ", m.group(1)).strip(" ,.;:")
            if re.search(r"(?i)^(ad|soyad|ad\s*soyad)$", cand):
                continue
            if re.search(r"(?i)mahkeme|bakanl|müdür|kanun|karar|dilekçe", cand):
                continue
            if len(cand.split()) >= 2:
                name = cand
                break
        if name:
            break
    return {
        "muvekkil": name,
        "adli": "adli yardim" in fold
        or (
            bool(re.search(r"(?i)7315|atama uygunluk|infaz ve koruma|güvenlik soruştur", raw))
            and not re.search(r"(?i)adli yard[ıi]m (istenm|yok|talep edilm)", fold)
        ),
        "ivedi": "ivedi" in fold,
        "yd": "yurutme" in fold and "durdur" in fold,
        "idare": bool(re.search(r"(?i)idare|iyuk|7315|atama uygunluk", raw)),
        "aym_gerek": bool(re.search(r"(?i)idare|7315|güvenlik soruştur|kamu hizmetine", raw)),
    }


def scan_source(source: str) -> str:
    """Claude/Qwen yazmadan önce metni tara: müvekkil adı, adli yardım, AYM ihtiyacı."""
    d = _scan_dict(source)
    d["ok"] = True
    d["uyari"] = (
        "Gövdeye davacı değil müvekkil yaz. Başlık DAVACI: gerçek ad. "
        "Adli yardım varsa baner + vakıa + istem. İdarede AYM tarama zorunlu; "
        "çekilen 1 AYM künyesini göm, uydurma."
    )
    return json.dumps(d, ensure_ascii=False)


def strip_empty_placeholders(text: str) -> str:
    """Boş TCKN/adres/sicil nokta ve artık parantez satırlarını siler."""
    t = text or ""
    t = re.sub(r"\s*\(\s*[\.…]{3,}[^)]*\)", "", t)
    t = re.sub(r"\s*\([^)]*Sicil No:\s*[\.…]{3,}[^)]*\)", "", t, flags=re.I)
    t = re.sub(r"\s*\(\s*\)", "", t)
    t = re.sub(r"[ \t]+\(\s*$", "", t, flags=re.M)
    t = re.sub(r"(?im)^(T\.C\. Kimlik No|Adres|Sicil No|Tel|E-posta)\s*[:：]\s*[\.…]{3,}.*$", "", t)
    t = re.sub(r"(?im)^Ad Soyad\s*:\s*[\.…]{3,}\s*$", "", t)
    t = re.sub(r"(?im)^[\.…]{5,}\s*\)?\s*$", "", t)
    t = re.sub(r"\(\s*[\.…]{3,}\s*Barosu[^)]*\)", "", t, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def rewrite_body_muvekkil(text: str) -> str:
    """Başlık DAVACI kalır; gövdede Davacı Ad Soyad / davacı → müvekkil. Davacı Vekili dokunulmaz."""
    t = text or ""
    t = re.sub(r"(?i)Davacı Ad Soyad", "Müvekkil", t)
    parts = re.split(r"(?m)^(DAVACI(?:\s+VEK[İI]L[İI]?)?\s*:?.*)$", t)
    out: list[str] = []
    for p in parts:
        if re.match(r"(?m)^DAVACI\b", p or ""):
            out.append(p)
            continue
        p = re.sub(r"(?i)\bdavacının\b", "müvekkilin", p)
        p = re.sub(r"(?i)\bdavacıya\b", "müvekkile", p)
        p = re.sub(r"(?i)\bdavacıyı\b", "müvekkili", p)
        p = re.sub(r"(?i)\bDavacı(?!\s+Vekil)", "Müvekkil", p)
        out.append(p)
    return "".join(out)


def _insert_banner(t: str, banner: str) -> str:
    if banner in t:
        return t
    found = list(re.finditer(r"(?m)^—\s*.+TALEPL[İI]D[İI]R\s*—\s*$", t))
    if found:
        last = found[-1]
        return t[: last.end()] + "\n" + banner + t[last.end() :]
    if re.search(r"(?im)^DAVA D[İI]LEK", t):
        return re.sub(r"(?im)^(DAVA D[İI]LEK[ÇC]ES[İI])", banner + "\n\n\\1", t, count=1)
    return t


def _insert_sonuc_item(t: str, item: str) -> str:
    if re.search(re.escape(item), t, re.I):
        return t
    return re.sub(
        r"(?i)(karar verilmesini vek[aâ]leten)",
        item.rstrip(".") + "\n\n\\1",
        t,
        count=1,
    )


def apply_detected_facts(text: str, source: str = "") -> str:
    facts = _scan_dict(source or "")
    t = rewrite_body_muvekkil(text or "")
    name = facts.get("muvekkil") or ""
    if name:
        t = re.sub(
            r"(?m)^(DAVACI\s*:\s*)(\.{5,}.*|Ad Soyad.*|\[ad soyad\].*)\s*$",
            rf"\1{name}",
            t,
            count=1,
            flags=re.I,
        )
        t = re.sub(r"(?m)^(DAVACI\s*:\s*)$", f"DAVACI: {name}", t, count=1)
    if facts.get("adli"):
        t = _insert_banner(t, "— ADLİ YARDIM TALEPLİDİR —")
        t = _insert_sonuc_item(t, "Adli yardım talebinin kabulüne")
        body = t
        if "AÇIKLAMALAR" in t:
            end = t.find("SONUÇ") if "SONUÇ" in t else len(t)
            body = t[t.find("AÇIKLAMALAR") : end]
        if not re.search(r"(?i)adli yardım", body):
            t = re.sub(
                r"(?im)^(HUKUKİ (?:NEDENLER|DAYANAKLAR|SEBEPLER)\s*:?)",
                "Müvekkilin yargılama giderlerini karşılayacak maddi olanağı bulunmamaktadır; "
                "adli yardım talebinin kabulü ile yargılama giderlerinden geçici muafiyet talep olunur.\n\n\\1",
                t,
                count=1,
            )
    return t


def court_ready_text(text: str, court: str = "", source: str = "") -> str:
    """Claude ve Qwen çıktısından mahkeme sızıntısını siler; vakıa uydurmaz."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", t)
    t = re.sub(r"\*\*|__|`", "", t)
    t = re.sub(r"(?m)^>\s?", "", t)
    t = re.sub(r"(?m)^\s*---+\s*$", "", t)
    t = re.sub(r"(?is)\n+\s*\**\s*Vekile\s+Not:.*$", "", t)
    t = re.sub(r"(?im)^\s*\**\s*Vekile\s+Not:.*$", "", t)
    t = re.sub(r"(?is)\[DOĞRULANACAK[^\]]*\]", "", t)
    t = re.sub(r"(?is)\[Varsa[^\]]*\]", "", t)
    t = re.sub(r"(?is)\[[^\]]*(T\.C\.\s*KİMLİK|MÜVEKKİL AÇIK ADRES|TARİH|Uşak Barosu Sicil)[^\]]*\]", "", t)
    t = re.sub(r"(?i)\s*\(?teyit edilecek\)?", "", t)
    t = re.sub(r"(?i)kesinleştirilmeden dava açılmamalıdır\.?", "", t)
    t = re.sub(r"(?im)^.*(?:araştırma notu|bkz\.\s*Araştırma|Bölüm VII|Bölüm VIII).*\n?", "", t)
    t = re.sub(r"(?i)formda yoksa uydurulmaz[^.]*\.\s*", "", t)
    t = re.sub(r"(?i)Davacı Ad Soyad", "Müvekkil", t)
    t = re.sub(r"(?im)^\d+\.\s*BÖLÜM\s*—[^\n]*\n?", "", t)
    t = re.sub(r"(?is)Aşağıdaki metni aynı vakıalarla.*?(?:döndür\.\s*|\(truncated\))", "", t)
    t = re.sub(r"\(truncated\)", "", t)
    t = re.sub(r"(?im)^Sen Türk avukat.*$", "", t)
    t = re.sub(r"(?im)^WEB_FLUENCY:.*$", "", t)
    t = re.sub(r"(?im)^.*(?:wikipedia|üslup kalıp|internet dil kalıp|duckduckgo|Yargı MCP).*$", "", t)
    t = re.sub(
        r"(?im)^.*(?:search_bedesten|search_corpus_deep|get_bedesten_document|search_emsal|"
        r"search_mevzuat|get_mevzuat_article|list_mevzuat_catalog|search_anayasa|"
        r"get_anayasa_document|search_resmi_gazete|get_resmi_gazete_fihrist|"
        r"get_resmi_gazete_document|scan_source|petition_guide|petition_skeleton|"
        r"format_petition|check_petition|review_petition|save_petition_history|"
        r"save_petition_pdf).*$",
        "",
        t,
    )
    t = re.sub(r"işlemindır", "işlemdir", t, flags=re.I)
    t = re.sub(
        r"(?im)^(DAVALI)\s*:\s*.{0,40}(doğrulanacak|araştırma notu|husumet).*\n(?:.*\n){0,3}?(?=\s*(?:T\.C\.\s+)?(?:Adalet|Emniyet|İçişleri|Sağlık|Milli|Millî))",
        r"\1: ",
        t,
    )
    t = re.sub(r"(?m)^(DAVALI)\s*:\s*:\s*", r"\1: ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if not t:
        return "Dilekçe metni boş."
    gold = bool(re.search(r"(?m)^KONU\s*$", t) or re.search(r"(?m)^DAVACI VEKİLİ", t) or re.search(r"(?im)^Ad Soyad\s*:", t))
    if not gold and not re.search(r"(?m)^T\.C\.\s*$", t):
        head = "T.C.\n\n"
        if court.strip():
            head += court.strip() + "\n\n"
        t = head + t
    elif court.strip() and court.strip() not in t[:500]:
        if re.search(r"(?m)^T\.C\.\s*$", t):
            t = re.sub(r"(?m)^(T\.C\.\s*\n+)", r"\1" + court.strip() + "\n\n", t, count=1)
    if re.search(r"(?i)idare mahkemesi", t[:500]) and not re.search(r"(?i)nöbetçi", t[:500]):
        if re.search(r"(?i)ivedi|yürütme|adli yardım", t[:900]):
            t = re.sub(
                r"(?i)(ANKARA(?:\s+İDARE))",
                "ANKARA NÖBETÇİ İDARE",
                t,
                count=1,
            )
    if re.search(r"(?i)iptal", t) and re.search(r"(?i)idare", t[:900]) and not re.search(r"(?i)HARCA\s+ESAS", t):
        t = re.sub(
            r"(?im)^((?:DAVA\s+)?KONU(?:SU)?\s*:.*)",
            r"\1\n\nHARCA ESAS DEĞER: Maktu (Harçlar Kanunu: iptal davasında maktu; nispi kalem yok)",
            t,
            count=1,
        )
    for name in ("AÇIKLAMALAR", "DELİLLER", "HUKUKİ SEBEPLER", "HUKUKİ NEDENLER", "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM", "EKLER"):
        t = re.sub(rf"(?im)^({re.escape(name)})\s*$", r"\1 :", t)
    if not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:1200]):
        m = re.search(r"(?im)^DAVACI\b", t)
        if m:
            t = t[: m.start()] + "DAVA DİLEKÇESİ\n\n" + t[m.start() :]
    t = rewrite_body_muvekkil(t)
    t = strip_empty_placeholders(t)
    if source:
        t = apply_detected_facts(t, source)
        t = strip_empty_placeholders(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def check_court_ready(text: str, petition_type: str = "", source: str = "") -> str:
    """80 tabanı eksikleri. Metni yeniden yazmaz. source = kullanıcı/form metni."""
    t = text or ""
    p = petition_type or ""
    facts = _scan_dict(source or t)
    if not p:
        if facts.get("idare") or re.search(r"(?i)idare|iyuk|7315", t):
            p = "İdare"
        elif re.search(r"(?i)boşanma|tmk", t):
            p = "Boşanma"
        elif re.search(r"(?i)işçilik|4857", t):
            p = "İş"
    gaps: list[str] = []
    if not re.search(r"(?m)^T\.C\.\s*$", t):
        gaps.append("T.C. başlığı yok")
    if not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:1500]):
        gaps.append("DAVA DİLEKÇESİ başlığı yok")
    if not re.search(r"(?m)^KONU\b", t) and not re.search(r"(?m)^DAVA KONUSU", t):
        gaps.append("KONU bölümü yok")
    if not re.search(r"(?i)HUKUK[İI]\s+(SEBEPLER|DAYANAKLAR|NEDENLER)", t):
        gaps.append("HUKUKİ SEBEPLER yok")
    if "AÇIKLAMALAR" in t:
        if not re.search(r"(?im)^\s*Delil\s*[:：]", t):
            gaps.append("Vakıa altında Delil satırı yok")
        if not re.search(r"(?im)^\s*Hukuki dayanak\s*[:：]", t):
            gaps.append("Vakıa altında Hukuki dayanak satırı yok")
        if not re.search(r"(?im)^\s*Hukuki sonuç\s*[:：]", t):
            gaps.append("Vakıa altında Hukuki sonuç satırı yok")
    if re.search(r"(?i)Davacı Ad Soyad|işlemindır|formda yoksa uydurulmaz|BÖLÜM\s*—|Aşağıdaki metni aynı vakıalarla|\(truncated\)", t):
        gaps.append("Davacı Ad Soyad / işlemindır / motor notu — gövdede müvekkil yaz")
    if re.search(r"(?m)^Müvekkil\s*$", t) and not re.search(r"(?m)^DAVACI\b", t):
        gaps.append("Başlık Müvekkil olmuş; DAVACI yazılmalı")
    if "AÇIKLAMALAR" in t and re.search(r"(?i)\bDavacı (?!Vekil)", t[t.find("AÇIKLAMALAR") :]):
        gaps.append("Açıklamalarda davacı geçiyor; müvekkil yazılmalı")
    if facts.get("adli") and not re.search(r"(?i)adli yardım", t):
        gaps.append("Kaynakta adli yardım var; baner + vakıa + SONUÇ istemi yok")
    if "İdare" in p or re.search(r"(?i)idare mahkemesi", t[:500]):
        if re.search(r"(?i)ivedi", t) and not re.search(r"(?i)nöbetçi", t[:500]):
            gaps.append("İvedi varken Ankara Nöbetçi İdare yok")
        if not re.search(r"(?im)^KONU\b", t):
            gaps.append("KONU başlığı yok")
        if re.search(r"(?i)doğrulanacak|kesinleştirilmeden|araştırma notu|Vekile Not", t):
            gaps.append("Araştırma / vekile not dilekçede")
        if re.search(r"(?im)^Ad Soyad\s*:\s*(\.{5,}|\[|Ad Soyad)", t) or re.search(r"(?m)^DAVACI\s*:\s*(\.{5,}|\[)", t):
            gaps.append("DAVACI adı boş — metindeki müvekkil adını yaz")
        if re.search(r"(?m)^DAVALI\s*:\s*(\.{5,}|\[)", t):
            gaps.append("DAVALI boş")
        if not re.search(r"(?i)(?:Anayasa Mahkemesi|AYM).{0,80}(?:B\.\s*No|Başvuru\s+No|E\.\s*\d{4})", t):
            gaps.append("AYM atfı yok — AYM tara, çekilen 1 künyeyi göm, uydurma")
        if not re.search(r"(?i)Danıştay\s+\d", t) and not re.search(r"(?i)Danıştay’ın yerleşik", t):
            gaps.append("Gövgede doğrulanmış Danıştay künyesi yok (uydurma)")
        if re.search(r"\b\d{4}-\d{2}-\d{2}\b", t):
            gaps.append("ISO tarih — gg.aa.yyyy yaz")
        if re.search(r"(?i)Dayanak mevzuat\s*/\s*RG", t) and not re.search(r"(?i)RG[:\s]+\d", t):
            gaps.append("Boş Dayanak mevzuat / RG satırı")
        if re.search(r"(?i)7315|güvenlik soruştur", t) and not re.search(r"(?i)celb", t):
            gaps.append("Celp istemi yok")
        if re.search(r"(?i)Emniyet Genel Müdürlüğü\s*\(\s*7315", t):
            gaps.append("EGM uzun parantezi")
        ek = t[t.find("EKLER") :] if "EKLER" in t else ""
        if ek and len(re.findall(r"(?m)^\s*\d+[\.\)]\s+", ek)) < 2:
            gaps.append("EKLER tek kalem")
    if re.search(r"(?i)wikipedia|\*\*|## |Vekile Not|\[DOĞRULANACAK", t):
        gaps.append("Markdown veya sızıntı")
    if not re.search(r"(?m)^DAVACI\b", t) or not re.search(r"(?m)^DAVALI\b", t):
        gaps.append("DAVACI / DAVALI satırı eksik")
    if "AÇIKLAMALAR" not in t or "SONUÇ VE İSTEM" not in t:
        gaps.append("AÇIKLAMALAR veya SONUÇ VE İSTEM yok")
    huk = ""
    for lab in ("HUKUKİ SEBEPLER", "HUKUKİ DAYANAKLAR", "HUKUKİ NEDENLER"):
        if lab not in t:
            continue
        start = t.find(lab)
        end = -1
        for stop in ("DELİLLER", "SONUÇ VE İSTEM"):
            pos = t.find(stop, start + len(lab))
            if pos > start:
                end = pos
                break
        huk = t[start:end] if end > start else t[start:]
        break
    if huk:
        ay = huk[: huk.find("Kanunlar")] if "Kanunlar" in huk else huk[:180]
        if re.search(r"m\.\s*\d+", ay) and "(" not in ay:
            gaps.append("Anayasa maddesinde ilke / açıklama yok")
        if any(re.search(r"(?:E\.\s*\d{4}|B\.\s*No)", ln) and not re.search(r"—|–", ln) for ln in huk.splitlines()):
            gaps.append("İçtihat satırında isim soyisim / kısa açıklama yok")
        if "Boşanma" in p and re.search(r"m\.\s*164", huk) and re.search(r"m\.\s*166", huk):
            gaps.append("TMK 164 ile 166 aynı dayanakta karışmış")
    if "İdare" not in p and re.search(r"(?i)7315 sayılı|Atama Uygunluk Kararı", t):
        gaps.append("İdare/7315 metni bu dava türünde tutarsız")
    if "İdare" in p and re.search(r"(?i)\bziynet\b|TMK\s*m\.\s*16[46]", t):
        gaps.append("İdare dilekçesinde boşanma/ziynet tutarsızlığı")
    if re.search(r"(?i)(?:HAGB|hükmün açıklanmasının geri).{0,60}mahk[ûu]miyet", t):
        gaps.append("HAGB mahkûmiyet gibi yazılmış")
    if len(re.findall(r"(?i)İVEDİ YARGILAMA", t)) > 1:
        gaps.append("Çift ivedi baner")
    ok = not gaps
    lines = ["Mahkeme 80 tabanı: " + ("uygun" if ok else "eksik")]
    if gaps:
        lines.append("Eksik:")
        lines.extend(f"- {g}" for g in gaps)
        if facts.get("muvekkil"):
            lines.append(f"Metinden müvekkil: {facts['muvekkil']}")
        if facts.get("adli"):
            lines.append("Metinden usul: adli yardım")
    else:
        lines.append("Şekil ve sızıntı kontrolü geçti. TCKN/adres/tebliğ formda yoksa nokta bırak; uydurma.")
    return "\n".join(lines)


def petition_guide(petition_type: str = "") -> str:
    kind = (petition_type or "genel").strip()
    from .templates import guide as _gold
    return (
        "Dilekçe yazım kılavuzu (mahkeme 80 tabanı). Olay veya dava anlatılınca hemen yaz; sihirli cümle bekleme.\n"
        "==================================================================\n"
        f"{_gold(kind)}\n"
        "Sıra (atlanmaz):\n"
        "1) Kullanıcı metninden müvekkil adı, adli yardım, ivedi/YD çıkar.\n"
        "2) Usul iskeleti ve boş şablon.\n"
        "3) Madde çek. Çekilmeyen maddeyi yazma.\n"
        "4) İçtihat: idarede Danıştay tara; karar metnini çek. "
        "Ret / incelenemezlik / HSK meslekten çıkarma emsalini yazma.\n"
        "5) İdare: AYM tara (kamu hizmetine girme / güvenlik soruşturması). "
        "Çekilen 1 AYM künyesini gövdeye göm. "
        "B. No uydurma. Sonuç boşsa AYM yazma.\n"
        "6) Resmî Gazete: yoksa sayı uydurma; delile RG yazma.\n"
        "7) Dilekçeyi örnek sırada yaz (T.C. / mahkeme / DAVA DİLEKÇESİ / tür / taraflar / "
        "konu / açıklama / hukuki sebepler / delil / istem / imza / ekler).\n"
        "8) Biçimle, kontrol et, kaliteyi ölç, geçmişe veya PDF’ye kaydet.\n"
        "Araç adlarını sohbete ve dilekçeye yazma.\n\n"
        "80 şekil (HMK m. 119 / İYUK m. 3):\n"
        "T.C. / Mahkeme (ivedide NÖBETÇİ İDARE) / birleşik baner / DAVA DİLEKÇESİ / "
        "dava türü satırı (Boşanma davası, İptal davası …) / "
        "DAVACI (Ad Soyad / TCKN / Tebligat adresi) / VEKİLİ / DAVALI / KONU / "
        "AÇIKLAMALAR : her vakıa 1- 2- 3- başlık + müvekkil gövdesi + "
        "Delil : / Hukuki dayanak : / Hukuki sonuç : / "
        "HUKUKİ SEBEPLER : / DELİLLER : / SONUÇ VE İSTEM : / tarih / Davacı Vekili / EKLER :.\n"
        "T.C. ve DAVA DİLEKÇESİ yazılır. Her vakıanın altında üç satır zorunludur.\n"
        "TCKN, adres, sicil, tebliğ tarihi formda yoksa nokta; uydurma. "
        "Tebliğ yoksa «60 gün işlemez» cümlesi yazma; süre İYUK m. 7 ile anılır.\n\n"
        "Husumet: DAVALI kutusunda araştırma notu, «doğrulanacak», «kesinleştirilmeden» yok. "
        "Formdaki idare (ör. EGM veya Adalet Bakanlığı) tek satırda kilitlenir.\n"
        "İdare: iptal konusu idari işlemdir; ceza kararı yalnızca sebep olgusudur. "
        "HAGB mahkûmiyet / sabıka değildir. «Mahkûm edilmiş ancak HAGB» yazma. "
        "CMK 251 ancak olay özetinde varsa. TMK/ziynet/boşanma yazma. "
        "Ölçülülük, masumiyet, sonradan gerekçe yasağı, celp (İYUK m. 20) vakıada dursun.\n"
        "İçtihat: taranan 1–2 Danıştay künyesi ilgili paragrafa gömülür; uydurma yok. "
        "İdarede AYM atfı zorunlu deneme: AYM tara; çekildiyse 1 künye gömülür.\n"
        "Adli yardım kutuda veya metinde varsa: — ADLİ YARDIM TALEPLİDİR — + vakıa + "
        "«Adli yardım talebinin kabulüne». Görmezden gelme.\n"
        "Gövde zamiri: müvekkil. Başlık etiketi DAVACI kalır.\n"
        "Yasak dilekçe metni: Markdown, Vekile Not, Araştırma Notu, Wikipedia, "
        "sistem talimatı, araç adı, «formda yoksa uydurulmaz».\n"
        "Boşanma: TMK 164 ile 166 karışmaz. İş: formda olmayan kalem uydurulmaz.\n"
        f"İmza tarihi (olay tarihi değil): {_tr_date()}\n"
        f"PDF klasör: {_out_dir()}\n"
    )


def petition_skeleton(petition_type: str = "") -> str:
    from .templates import resolve_kind, skeleton as _sk
    kind = resolve_kind(petition_type or "")
    key = {"idare": "İdare", "bosanma": "Boşanma", "is": "İş"}.get(kind)
    if key and key in _SKELETONS:
        return _SKELETONS[key].replace("[tarih]", _tr_date())
    return _sk(petition_type or "").replace("[tarih]", _tr_date())


def format_petition(text: str, court: str = "", title: str = "", source: str = "") -> str:
    from bettersaul_mcp.license_gate import enforce
    enforce()
    t = court_ready_text(text, court=court, source=source)
    if t == "Dilekçe metni boş.":
        return t
    if not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:800]):
        t = re.sub(
            r"(?im)^(T\.C\.\s*\n+(?:[^\n]*MAHKEME[^\n]*\n+)?(?:—[^\n]*\n+)*)",
            r"\1DAVA DİLEKÇESİ\n\n",
            t,
            count=1,
        )
    cap = (title or "").strip()
    if cap and cap.upper() != "DAVA DİLEKÇESİ" and cap not in t[:800] and "DAVA KONUSU" not in t[:800]:
        t = re.sub(
            r"(?im)^(DAVA D[İI]LEK[ÇC]ES[İI]\s*\n+)",
            r"\1" + cap + "\n\n",
            t,
            count=1,
        )
    t = t.strip()
    try:
        auto_archive_petition(t, title=title)
    except Exception:
        pass
    return t


def petition_html(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    out: list[str] = []

    def skip() -> None:
        nonlocal i
        while i < len(lines) and not lines[i].strip():
            i += 1

    skip()
    if i < len(lines) and re.match(r"^T\.C\.\s*$", lines[i].strip(), re.I):
        out.append('<div class="p-tc"><b>T.C.</b></div>')
        i += 1
        skip()
    if i < len(lines) and re.search(r"MAHKEME|BAŞKANLIĞI|DANIŞTAY|SAVCILIK", lines[i], re.I):
        out.append(f'<div class="p-court"><b>{_esc(lines[i].strip())}</b></div>')
        i += 1
        skip()
        while i < len(lines) and re.search(r"TALEPL[İI]D[İI]R|^—.+—$", lines[i].strip()):
            out.append(f'<div class="p-banner"><b>{_esc(lines[i].strip())}</b></div>')
            i += 1
            skip()
    if i < len(lines) and re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", lines[i].strip()):
        out.append(f'<div class="p-kind"><b>{_esc(lines[i].strip())}</b></div>')
        i += 1
        skip()
        if i < len(lines):
            nxt = lines[i].strip()
            if (
                nxt
                and not _HEAD.match(nxt)
                and not _PARTY.match(nxt)
                and not _SEC.match(nxt)
                and not re.search(r"TALEPL", nxt, re.I)
            ):
                out.append(f'<div class="p-kind">{_esc(nxt)}</div>')
                i += 1
                skip()
    while i < len(lines):
        t = lines[i].strip()
        if not t:
            i += 1
            continue
        if re.search(r"TALEPL[İI]D[İI]R|^—.+—$", t):
            out.append(f'<div class="p-banner"><b>{_esc(t)}</b></div>')
            i += 1
            continue
        if re.search(r"(?i)^DAVA D[İI]LEK[ÇC]ES[İI]\s*$", t):
            out.append(f'<div class="p-kind"><b>{_esc(t)}</b></div>')
            i += 1
            continue
        if _META.match(t):
            out.append(f'<div class="sub">{_esc(t)}</div>')
            i += 1
            continue
        if _HEAD.match(t):
            out.append(f'<div class="sec"><b>{_esc(t)}</b></div>')
            i += 1
            if re.search(r"(?i)VEK", t):
                bits: list[str] = []
                while i < len(lines) and lines[i].strip():
                    nt = lines[i].strip()
                    if _HEAD.match(nt) or _SEC.match(nt) or _PARTY.match(nt):
                        break
                    bits.append(nt)
                    i += 1
                if bits:
                    out.append('<div class="lawyer">' + "<br>".join(_esc(b) for b in bits) + "</div>")
            continue
        if re.match(r"^[IVX]+\.\s+", t):
            out.append(f'<div class="vakia-h"><b>{_esc(t)}</b></div>')
            i += 1
            continue
        pm = _PARTY.match(t)
        if pm:
            vals = [pm.group(2).strip()] if pm.group(2).strip() else []
            i += 1
            while i < len(lines) and lines[i].strip():
                nt = lines[i].strip()
                if _PARTY.match(nt) or _SEC.match(nt) or _META.match(nt):
                    break
                vals.append(nt)
                i += 1
            label = re.sub(r"\s+", " ", pm.group(1)).upper()
            out.append(
                f'<div class="row"><span class="k"><b>{_esc(label)}</b></span>'
                f'<span class="v">{"<br>".join(_esc(v) for v in vals)}</span></div>'
            )
            continue
        if _SEC.match(t):
            out.append(f'<div class="sec"><b>{_esc(t.rstrip(":") + " :")}</b></div>')
            i += 1
            continue
        if _DATE.match(t) or t.startswith("Av.") or re.match(r"^Davac[ıi] Vekili", t, re.I):
            sign: list[str] = []
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if _SEC.match(s) or _PARTY.match(s):
                    break
                sign.append(s)
                i += 1
            if sign:
                out.append('<div class="lawyer">' + "<br>".join(_esc(s) for s in sign) + "</div>")
            continue
        if re.match(r"^\d{1,2}[\.\)\-]", t):
            head = t
            bits: list[str] = []
            meta: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip():
                nxt = lines[i].strip()
                if re.match(r"^\d{1,2}[\.\)\-]", nxt) or _SEC.match(nxt) or _PARTY.match(nxt):
                    break
                if _META.match(nxt):
                    meta.append(nxt)
                    i += 1
                    continue
                bits.append(nxt)
                i += 1
            chunk = [f'<div class="vakia"><div class="vakia-h"><b>{_esc(head)}</b></div>']
            if bits:
                chunk.append(f'<div class="p">{_esc(" ".join(bits))}</div>')
            chunk.extend(f'<div class="sub">{_esc(m)}</div>' for m in meta)
            chunk.append("</div>")
            out.append("".join(chunk))
            continue
        out.append(f'<div class="p">{_esc(t)}</div>')
        i += 1
    inner = "\n".join(out)
    return (
        "<!doctype html><html lang=\"tr\"><head><meta charset=\"utf-8\"/>"
        "<title>Dava Dilekçesi</title><style>" + _CSS + "</style></head>"
        f'<body><article class="sheet">{inner}</article></body></html>'
    )


def _browsers() -> list[Path]:
    found: list[Path] = []
    if sys.platform == "darwin":
        for p in [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]:
            if p.is_file():
                found.append(p)
        return found
    roots = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]
    names = [
        Path("Microsoft/Edge/Application/msedge.exe"),
        Path("Google/Chrome/Application/chrome.exe"),
    ]
    for root in roots:
        if not root:
            continue
        for rel in names:
            p = root / rel
            if p.is_file():
                found.append(p)
    return found


def _print_pdf(html_path: Path, pdf_path: Path) -> None:
    uri = html_path.resolve().as_uri()
    last = ""
    for exe in _browsers():
        cmd = [
            str(exe),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            uri,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
            if pdf_path.is_file() and pdf_path.stat().st_size > 400:
                return
            last = (proc.stderr or proc.stdout or "")[:240]
        except Exception as exc:
            last = str(exc)
    raise RuntimeError(last or "Edge/Chrome bulunamadı")


def write_court_petition(
    source: str = "",
    text: str = "",
    court: str = "",
    title: str = "",
    petition_type: str = "",
) -> str:
    """Olay veya tam metin gelince biçimler ve Geçmiş’e yazar."""
    raw = (text or "").strip() or (source or "").strip()
    if _looks_like_petition(raw):
        return format_petition(raw, court=court, title=title, source=source or text)
    scanned = scan_source(source or text or "")
    return (
        scanned
        + "\n\n"
        + petition_guide(petition_type)
        + "\n\n"
        + petition_skeleton(petition_type)
        + "\n\n"
        "Tam dilekçeyi şimdi yaz; ardından aynı isteği dilekçe metniyle gönder. "
        "Biçimlenen metin BetterSaul Geçmiş’e kendiliğinden yazılır."
    )


def save_petition_history(
    text: str = "",
    title: str = "dilekce",
    petition_type: str = "",
    body: str = "",
    petition: str = "",
    dilekce: str = "",
    content: str = "",
    source: str = "",
) -> str:
    """Yalnızca BetterSaul Geçmiş’e yazar; PDF üretmez."""
    raw = _tool_text(text, body, petition, dilekce, content, source)
    if not raw:
        return "Dilekçe metni boş. Tam dilekçe metnini gönderin; yalnızca başlık yetmez."
    formatted = format_petition(raw)
    keep = formatted if formatted != "Dilekçe metni boş." else raw
    if len(keep) < 80:
        keep = raw
    try:
        row_id = auto_archive_petition(keep, title=title or "Dilekçe", petition_type=petition_type) or archive_petition(keep, title=title or "Dilekçe", petition_type=petition_type)
    except Exception as exc:
        return f"Geçmişe yazılamadı ({exc}). BetterSaul açıksa tekrar deneyin; archive.db kilitli olabilir."
    if row_id <= 0:
        return "Geçmişe yazılamadı (boş kayıt)."
    return (
        f"BetterSaul Geçmiş’e yazıldı (id {row_id}, {len(keep)} karakter).\n"
        "Uygulamada Geçmiş → Dilekçeler sekmesini açın; Claude dilekçesi orada görünür."
    )


def save_petition_pdf(
    text: str = "",
    title: str = "dilekce",
    path: str = "",
    open_file: bool = False,
    petition_type: str = "",
    body: str = "",
    petition: str = "",
    dilekce: str = "",
    content: str = "",
    source: str = "",
    history_only: bool = False,
) -> str:
    raw = _tool_text(text, body, petition, dilekce, content, source)
    if not raw:
        return "Dilekçe metni boş. Tam dilekçe metnini gönderin; yalnızca başlık veya dosya adı yetmez."
    formatted = format_petition(raw)
    keep = formatted if formatted != "Dilekçe metni boş." else raw
    if len(keep) < 80:
        keep = raw
    try:
        row_id = auto_archive_petition(keep, title=title or "Dilekçe", petition_type=petition_type) or archive_petition(keep, title=title or "Dilekçe", petition_type=petition_type)
    except Exception as exc:
        return f"Geçmişe yazılamadı ({exc}). BetterSaul açıksa tekrar deneyin; archive.db kilitli olabilir."
    if row_id <= 0:
        return "Geçmişe yazılamadı (boş kayıt)."
    lines = [
        f"BetterSaul Geçmiş’e yazıldı (id {row_id}, {len(keep)} karakter).",
        "Uygulamada Geçmiş → Dilekçeler sekmesini açın; metin orada görünür.",
    ]
    if history_only:
        return "\n".join(lines)
    try:
        folder = Path(path).parent if path else _out_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stem = Path(path).stem if path else _safe_name(title)
        html_path = folder / f"{stem}.html"
        pdf_path = Path(path) if path else folder / f"{stem}.pdf"
        html_path.write_text(petition_html(keep), encoding="utf-8")
        lines.append(f"HTML: {html_path}")
        pdf_ok = ""
        try:
            _print_pdf(html_path, pdf_path)
            pdf_ok = str(pdf_path)
        except Exception as exc:
            lines.append(f"PDF üretilemedi ({exc}). Geçmiş kaydı duruyor.")
        if pdf_ok:
            try:
                db = _archive_db()
                conn = sqlite3.connect(str(db), timeout=8)
                try:
                    conn.execute("UPDATE petitions SET pdf_path=? WHERE id=?", (pdf_ok, row_id))
                    conn.commit()
                finally:
                    conn.close()
            except Exception:
                pass
            lines.append(f"PDF: {pdf_ok}")
            if open_file:
                try:
                    os.startfile(pdf_ok)  # type: ignore[attr-defined]
                except Exception:
                    pass
    except Exception as exc:
        lines.append(f"PDF/HTML atlandı ({exc}). Geçmiş kaydı duruyor.")
    return "\n".join(lines)
