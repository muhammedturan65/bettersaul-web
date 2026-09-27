#!/usr/bin/env python3
"""Yerel Qwen 2.5 7B / Qwen 3 14B TR + BetterSaul MCP. WinForms stdin/stdout JSON satırları."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from petition_packs import pack_for
try:
    from web_style import fetch_style_hints, internet_reachable
except Exception:
    def fetch_style_hints(kind: str = "") -> tuple[str, int]:
        return "", 0

    def internet_reachable() -> bool:
        return False

from legal_tracks import (
    PROMPT_RULES,
    align_form,
    court_override,
    drop_unrelated_evidence,
    is_labor,
    labor_evidence,
    labor_hukuk,
    labor_konu,
    labor_toxic,
    labor_wage_claim,
    mediation_header,
    mediation_vakia,
    needs_mediation,
    reconcile_date_span,
    strip_template_notes,
    wants_tazminat,
)

PROMPT = (HERE / "system_prompt.txt").read_text(encoding="utf-8")
PETITION_PROMPT = (HERE / "petition_prompt.txt").read_text(encoding="utf-8")
FILL_ANATOMY = (
    "Yazım disiplini (metne yapıştırma): HMK m.119 / İYUK m.3 iskeletini motor kurar; "
    "sen yalnızca numaralı vakıa yazarsın. Her vakıada içten bağ: somut olay, hangi belgeden "
    "anlaşılır, hangi madde, talebe etkisi. Alt başlık satırı (Delil/dayanak/sonuç) yok. "
    "Sıra: doğru hukuki sebep → kronoloji (tarih/yer/işlem/tebliğ) → hukuka aykırılık → "
    "dava şartı/süre/YD (formda varsa) → fer’iler (formda varsa). Müvekkil üzerinden yaz; "
    "birinci çoğul, soru, emir kipi yok. Tür karıştırma. İsim, TCKN, tanık, tutar, karar no uydurma. "
    "Emsal en fazla iki gerçek künye. “Arz ederim” yok."
)
try:
    TR_REASON = (HERE / "turkish_reason.txt").read_text(encoding="utf-8").strip()
except Exception:
    TR_REASON = ""
if TR_REASON:
    PROMPT = PROMPT.rstrip() + "\n\n" + TR_REASON
    PETITION_PROMPT = PETITION_PROMPT.rstrip() + "\n\n" + TR_REASON
MODEL = os.environ.get("BS_MODEL", "")
LLAMA = os.environ.get("BS_LLAMA", "llama-cli")


def _model_available() -> bool:
    if (os.environ.get("BS_NO_MODEL") or "").strip() == "1":
        return False
    path = (os.environ.get("BS_MODEL") or MODEL or "").strip()
    return bool(path) and os.path.isfile(path)
MCP_URL = os.environ.get("BS_MCP_URL", "https://127.0.0.1:8000/mcp")
MAX_TURNS = 8
RESEARCH_ROUNDS = 3


def _rounds(form: dict | None = None) -> int:
    return RESEARCH_ROUNDS


_emit_lock = threading.Lock()


def emit(event: str, text: str = "") -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps({"event": event, "text": text}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _fmt_prep_sure(sec: float) -> str:
    sec_i = max(0, int(sec))
    m, s = divmod(sec_i, 60)
    if m <= 0:
        return f"{s} saniye"
    if s == 0:
        return f"{m} dakika"
    return f"{m} dakika {s} saniye"


def _save_prep_timing(form: dict, sec: float, ok: bool = True) -> None:
    rec = {
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "title": str((form or {}).get("title") or ""),
        "petitionType": str((form or {}).get("petitionType") or ""),
        "seconds": int(max(0, sec)),
        "minutes": round(max(0.0, sec) / 60.0, 1),
        "ok": bool(ok),
    }
    root = Path(os.environ.get("LOCALAPPDATA") or "") / "BetterSaul"
    try:
        root.mkdir(parents=True, exist_ok=True)
        with (root / "petition_timings.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    label = _fmt_prep_sure(sec)
    emit("research", f"Hazırlanma süresi: {label}.")
    emit("status", f"{'Dilekçe hazır' if ok else 'Üretim kesildi'}. Süre: {label}.")


_LEAK_MARKERS = (
    "Bir Dilekçenin Anatomisi",
    "Araç Kullanımı",
    "Yargı MCP kullanma",
    "Yargı MCP",
    "search_bedesten",
    "petition_guide",
    "save_petition_pdf",
    "scan_source",
    "format_petition",
    "Av. M. Ufuk Tekin",
    "<|im_start|>",
    "<|im_end|>",
    "<think>",
    "</think>",
    "<tool_call>",
    "available commands",
    "Loading model",
    "Sen Türk hukukunda uzman",
    "Sen Türk avukat asistanısın",
    "Gizli yazım disiplini",
    "Aşağıdaki yazım disiplini gizlidir",
    "Anatomi (metne yazma)",
    "Yazım disiplini (metne yapıştırma)",
    "## Türkçe muhakeme",
    "Dilekçe henüz 5 A4 değil",
    "Yeni vakıa uydurma",
    "içerik mevcut değildir",
    "Exiting...",
    'Sen "BetterSaul"',
    'Sen "Be',
    "BetterSaul MCP",
    "MCP araçlarıyla",
    "Basit selamlaşmada",
    "uydurma. Basit",
    "Kullanılabilir araçlar:",
    "Yalnızca şu blokla yaz",
    "Halüsinasyon yasağı",
    "build      :",
    "b9999-",
    "Wikipedia",
    "tr.wikipedia",
    "DuckDuckGo",
    "İnternet dil kalıpları",
    "üslup kalıpları",
    "Üslup kalıpları",
)

_META_RE = re.compile(
    r"^(build|model|llama_|ggml_|print_|load_|system_info|sampler|slot |common_|clip_|srv |gguf|ftype|modalities)\b",
    re.I,
)
_PETITION_START = re.compile(
    r"(T\.C\.|MAHKEMES[İI]|DAVACI|DAVALI|VEK[İI]L[İI]?|KONU\s*:|AÇIKLAMALAR|SAYIN\s)",
    re.I,
)

_PETITION_HINTS = (
    "T.C.",
    "MAHKEME",
    "DAVACI",
    "DAVALI",
    "VEKİL",
    "KONU",
    "AÇIKLAMALAR",
    "İSTEM",
    "SONUÇ",
)


def _leak_lines() -> list[str]:
    lines = []
    for blob in (PROMPT, PETITION_PROMPT):
        for ln in blob.splitlines():
            s = ln.strip()
            if len(s) >= 28:
                lines.append(s)
    return lines


_LEAK_LINES = _leak_lines()


def _looks_like_petition(text: str) -> bool:
    head = (text or "")[:800].upper()
    return "T.C." in head or "MAHKEME" in head or "DAVACI" in head


def _is_banner(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    if "â–" in text or "available commands" in low or "/exit" in text or "/regen" in text:
        return True
    if "b9999-" in low or "build      :" in low:
        return True
    box = sum(1 for ch in text if 0x2500 <= ord(ch) <= 0x259F or ch in "█▄▀■░▒▓")
    return box >= 8


def _meta_line(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    if _META_RE.match(t) or re.match(r"^(build|model)\s*:", t, re.I):
        return True
    up = t.upper()
    return "BETTER~1" in up or "QWEN25" in up or ".GGUF" in up or t.upper().endswith(".GGU")


def _looks_like_answer(text: str) -> bool:
    if _is_banner(text) or _is_prompt_leak(text):
        return False
    letters = sum(1 for c in text if c.isalpha())
    return letters >= 36


def _is_prompt_leak(text: str) -> bool:
    if not text:
        return False
    hits = sum(1 for m in _LEAK_MARKERS if m in text)
    return hits >= 1 and not _looks_like_petition(text)


def _junk_line(s: str) -> bool:
    low = s.lower()
    if not s:
        return False
    if _meta_line(s):
        return True
    if low.startswith("loading model") or low.startswith("ftype") or low.startswith("modalities"):
        return True
    if "available commands" in low or s.startswith("/exit") or s.startswith("/regen") or s.startswith("/clear"):
        return True
    if s.startswith("/read") or s.startswith("/glob"):
        return True
    if "<|im_start|>" in s or "<|im_end|>" in s:
        return True
    if "â–" in s or "â–„" in s or "â–ˆ" in s:
        return True
    if any(
        m in s
        for m in (
            "Bir Dilekçenin Anatomisi",
            "Araç Kullanımı",
            "Yargı MCP",
            "Av. M. Ufuk Tekin",
            "Sen Türk hukukunda uzman",
            "Sen Türk avukat asistanısın",
            "Gizli yazım disiplini",
            "Aşağıdaki yazım disiplini gizlidir",
            "Anatomi (metne yazma)",
            "Yazım disiplini (metne yapıştırma)",
            "## Türkçe muhakeme",
            "Yazmadan önce Türkçe düşün",
            "Dilekçe henüz 5 A4 değil",
            "Yeni vakıa uydurma",
            "içerik mevcut değildir",
            "Exiting...",
            "Yalnızca numaralı AÇIKLAMALAR",
            "Yalnızca devam numaralı",
            'Sen "BetterSaul"',
            'Sen "Be',
            "BetterSaul MCP",
            "MCP araçlarıyla",
            "Basit selamlaşmada",
            "uydurma. Basit",
            "Kullanılabilir araçlar:",
            "Yalnızca şu blokla yaz",
            "Halüsinasyon yasağı",
            "b9999-",
        )
    ):
        return True
    box = sum(1 for ch in s if 0x2500 <= ord(ch) <= 0x259F or ch in "█▄▀■░▒▓")
    return bool(s) and box >= max(3, len(s) // 4)


def _drop_echo(text: str) -> str:
    if not text:
        return ""
    found = _PETITION_START.search(text)
    if found and found.start() > 0:
        head = text[: found.start()]
        if _is_prompt_leak(head) or _is_banner(head) or any(_meta_line(ln) for ln in head.splitlines()):
            return text[found.start() :]
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (not lines[i].strip() or _junk_line(lines[i]) or _meta_line(lines[i])):
        i += 1
    return "\n".join(lines[i:])


def _clean_llama_out(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S | re.I)
    if "<|im_start|>assistant" in text:
        text = text.split("<|im_start|>assistant")[-1]
        if text.startswith("\n"):
            text = text[1:]
        text = text.split("<|im_end|>")[0]
    skip_help = False
    kept: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if "available commands" in s.lower():
            skip_help = True
            continue
        if skip_help:
            if s.startswith("/") or s.startswith(">") or s == "":
                continue
            skip_help = False
        if s.startswith(">") and ("<|im_start|>" in s or s == ">"):
            continue
        if _junk_line(s) or _meta_line(s):
            continue
        kept.append(line)
    out = _strip_instr_leaks(_drop_echo("\n".join(kept)))
    for chunk in _LEAK_LINES:
        if chunk and chunk in out:
            out = out.replace(chunk, "")
    out = _strip_instr_leaks(re.sub(r"\n{3,}", "\n\n", out).strip())
    if _is_banner(out) or _has_instr_leak(out) or _is_prompt_leak(out):
        return ""
    return out


def _usable_text(text: str) -> str:
    cleaned = _clean_llama_out(text or "")
    if not cleaned:
        return ""
    if _looks_like_petition(cleaned) or _looks_like_answer(cleaned):
        return cleaned
    if len(cleaned) >= 80:
        return cleaned
    return ""


def _pretty_lawyer(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    low = name.lower()
    if low.startswith("av."):
        name = name[3:].strip()
    elif low.startswith("avukat "):
        name = name[7:].strip()
    return "Av. " + name if name else ""


def _lawyer_lines(form: dict) -> list[str]:
    name = _pretty_lawyer(_field(form, "lawyerName", "lawyer")) or "Av."
    bar = _field(form, "lawyerBar", "bar")
    bar_no = _field(form, "lawyerBarNo", "barNo")
    addr = _field(form, "lawyerAddress", "address")
    phone = _field(form, "lawyerPhone", "phone")
    email = _field(form, "lawyerEmail", "email")
    if bar and bar_no and not re.fullmatch(r"[\.…]{3,}", bar_no):
        head = f"{name} ({bar} - Sicil No: {bar_no})"
    elif bar:
        head = f"{name} ({bar})"
    else:
        head = name
    lines = [head]
    if addr and not re.fullmatch(r"[\.…]{3,}", addr.strip()):
        bar_il = _city_from_text(bar)
        addr_il = _city_from_text(addr)
        clash = bool(bar_il and addr_il and bar_il.casefold() != addr_il.casefold())
        if not clash:
            lines.append(f"Adres: {addr}")
    if phone:
        lines.append("Tel: " + phone)
    if email:
        lines.append("E-posta: " + email)
    return lines


def _tr_date() -> str:
    months = (
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    )
    today = date.today()
    return f"{today.day} {months[today.month - 1]} {today.year}"


def _kunye_tr(text: str) -> str:
    """ISO 2022-10-06 → 06.10.2022; künye uydurmaz."""

    def _iso(m: re.Match) -> str:
        return f"{int(m.group(3)):02d}.{int(m.group(2)):02d}.{m.group(1)}"

    return re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", _iso, text or "")


def _short_admin(name: str) -> str:
    t = re.sub(r"\s*\((?:7315|kapsamında|güvenlik soruştur).*$", "", name or "", flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" ,;:")


def _aym_weave(kunye: str, ilke: str = "") -> str:
    k = _kunye_tr(kunye).strip().rstrip(" .;")
    i = _kunye_tr(re.sub(r"\s+", " ", (ilke or "").strip()))
    if i and not re.search(r"[.!?]$", i):
        i = i.rstrip(" ,;") + "."
    if i:
        lead = i
        if i[:1].isupper() and not re.match(r"(?i)^(anayasa|aym|i+[\.\s])", i):
            lead = i[0].lower() + i[1:]
        return (
            f"{k} Anayasa Mahkemesi kararında {lead} "
            "Kararın ilkesi, kamu hizmetine girme hakkının gerekçesiz ve denetime elverişsiz "
            "idari işlemle kısıtlanamayacağıdır. Bu ilke somut uyuşmazlığa da uygulanmalıdır."
        )
    return (
        f"{k} Anayasa Mahkemesi kararında, kamu hizmetine girme hakkının gerekçesiz ve "
        "denetime elverişsiz idari işlemle kısıtlanamayacağı kabul edilmiştir. "
        "Bu ilke somut uyuşmazlığa da uygulanmalıdır."
    )


def _ensure_lawyer(text: str, form: dict | None) -> str:
    if not form:
        return text
    lines = _lawyer_lines(form)
    if not lines:
        return text
    name = lines[0]
    body = text or ""
    body = re.sub(
        r"\[(?:AVUKAT(?:\s+ADI)?|VEK[İI]L[İI]?|M[ÜU]VEKK[İI]L AVUKATI)[^\]]*\]",
        name,
        body,
        flags=re.I,
    )
    vekil = name + (("\n" + "\n".join(lines[1:])) if len(lines) > 1 else "")
    if name not in body:
        nxt, n = re.subn(
            r"(VEK[İI]L[İI]?\s*:?\s*)(\[.*?\]|.{0,40})",
            r"\1" + vekil + "\n",
            body,
            count=1,
            flags=re.I | re.S,
        )
        body = nxt if n else body
    tail = body[-900:]
    if name not in tail:
        block = ["", "Vekâleten talep ederim.", "", _tr_date(), *lines]
        body = body.rstrip() + "\n\n" + "\n".join(block)
    return body.strip()


def _strip_open_think(text: str) -> str:
    t = text or ""
    t = re.sub(r"<think>.*?</think>\s*", "", t, flags=re.S | re.I)
    t = re.sub(r"<think>.*$", "", t, flags=re.S | re.I)
    return t


def _think_snippet(raw: str) -> str:
    m = re.search(r"<think>(.*?)(?:</think>|$)", raw or "", flags=re.S | re.I)
    if not m:
        return ""
    bit = re.sub(r"\s+", " ", m.group(1)).strip()
    if len(bit) < 12:
        return ""
    return bit[-110:]


class LiveOut:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.raw = ""
        self.sent = 0
        self.pending = ""
        self.last = 0.0
        self.silent = False
        self.ready = False
        self.emitted = ""
        self._think_at = 0.0

    def feed(self, s: str) -> None:
        if not s:
            return
        self.raw += s
        snip = _think_snippet(self.raw)
        now = time.time()
        if snip and now - self._think_at >= 2.2:
            self._think_at = now
            emit("status", "Derin muhakeme: " + snip)
            emit("research", "Muhakeme: " + snip)
        if not self.enabled or self.silent:
            return
        clean = _clean_llama_out(_strip_open_think(self.raw))
        if not clean:
            return
        if "<tool_call" in clean[:240]:
            self.silent = True
            return
        if _is_prompt_leak(clean):
            return
        if not self.ready:
            if _looks_like_petition(clean) or _looks_like_answer(clean):
                self.ready = True
            else:
                return
        if len(clean) <= self.sent:
            return
        piece = clean[self.sent:]
        self.sent = len(clean)
        self._queue(piece)

    def _queue(self, s: str) -> None:
        if _is_prompt_leak(s):
            return
        self.pending += s
        now = time.time()
        if len(self.pending) >= 16 or now - self.last >= 0.05:
            emit("delta", self.pending)
            self.emitted += self.pending
            self.pending = ""
            self.last = now

    def flush(self) -> None:
        if self.pending and not self.silent and not _is_prompt_leak(self.pending):
            emit("delta", self.pending)
            self.emitted += self.pending
            self.pending = ""


def _mcp_err(exc: BaseException) -> str:
    msg = str(exc).split("\n")[0].strip()
    if "TaskGroup" in msg or "unhandled errors" in msg.lower():
        return "sunucu kapalı"
    return msg[:160] if msg else "bağlantı yok"


def _local_mcp():
    try:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        from bettersaul_mcp import sources
        return sources
    except Exception:
        return None


def _local_tool_list() -> list[dict]:
    return [
        {
            "name": "search_bedesten",
            "description": "Yargıtay / Danıştay / emsal karar ara (çok sayfa)",
            "input_schema": {"properties": {"phrase": {"type": "string"}, "court_types": {"type": "array"}}},
        },
        {
            "name": "search_corpus_deep",
            "description": "Birden fazla ifadeyle derin içtihat taraması",
            "input_schema": {
                "properties": {
                    "phrases": {"type": "array"},
                    "pages": {"type": "integer"},
                    "court_types": {"type": "array"},
                }
            },
        },
        {
            "name": "get_bedesten_document",
            "description": "Karar metnini getir. Holding ucu yok; özet yerelde çıkarılır.",
            "input_schema": {"properties": {"documentId": {"type": "string"}}},
        },
        {
            "name": "search_emsal",
            "description": "Emsal (UYAP) karar ara",
            "input_schema": {"properties": {"keyword": {"type": "string"}, "page_number": {"type": "integer"}}},
        },
        {
            "name": "search_mevzuat",
            "description": "mevzuat.gov.tr katalog eşlemesi",
            "input_schema": {"properties": {"query": {"type": "string"}}},
        },
        {
            "name": "get_mevzuat_article",
            "description": "Resmi madde özeti",
            "input_schema": {"properties": {"kanun": {"type": "string"}, "madde": {"type": "string"}}},
        },
        {
            "name": "list_mevzuat_catalog",
            "description": "Çekilebilir kanun kodları",
            "input_schema": {"properties": {}},
        },
        {
            "name": "search_anayasa",
            "description": "AYM kamu araması (idarede en fazla 1)",
            "input_schema": {
                "properties": {
                    "keywords": {"type": "string"},
                    "decision_type": {"type": "string"},
                }
            },
        },
        {
            "name": "get_anayasa_document",
            "description": "AYM karar metni / kısa ilke",
            "input_schema": {"properties": {"url_or_id": {"type": "string"}}},
        },
        {
            "name": "search_resmi_gazete",
            "description": "Resmî Gazete fihrist + başlık ara",
            "input_schema": {
                "properties": {
                    "query": {"type": "string"},
                    "date_start": {"type": "string"},
                    "date_end": {"type": "string"},
                }
            },
        },
        {
            "name": "get_resmi_gazete_fihrist",
            "description": "Günün Resmî Gazete fihristi",
            "input_schema": {"properties": {"date": {"type": "string"}}},
        },
        {
            "name": "get_resmi_gazete_document",
            "description": "Resmî Gazete belge düz metni",
            "input_schema": {"properties": {"url_or_date_and_item": {"type": "string"}}},
        },
        {
            "name": "petition_guide",
            "description": "Dilekçe usul kılavuzu",
            "input_schema": {"properties": {"petition_type": {"type": "string"}}},
        },
        {
            "name": "petition_skeleton",
            "description": "Boş dilekçe iskeleti",
            "input_schema": {"properties": {"petition_type": {"type": "string"}}},
        },
        {
            "name": "scan_source",
            "description": "Metinden müvekkil adı ve adli yardım / ivedi / YD",
            "input_schema": {"properties": {"source": {"type": "string"}}},
        },
        {
            "name": "format_petition",
            "description": "Mahkeme biçimi; sızıntı sil; gövde müvekkil",
            "input_schema": {
                "properties": {
                    "text": {"type": "string"},
                    "court": {"type": "string"},
                    "title": {"type": "string"},
                    "source": {"type": "string"},
                }
            },
        },
        {
            "name": "review_petition",
            "description": "Çelişki / madde / tutar / içtihat kalite raporu (yazmaz)",
            "input_schema": {
                "properties": {
                    "text": {"type": "string"},
                    "petition_type": {"type": "string"},
                    "source": {"type": "string"},
                }
            },
        },
        {
            "name": "check_petition",
            "description": "80 tabanı eksikleri (yazmaz)",
            "input_schema": {
                "properties": {
                    "text": {"type": "string"},
                    "petition_type": {"type": "string"},
                    "source": {"type": "string"},
                }
            },
        },
        {
            "name": "save_petition_history",
            "description": "Dilekçeyi BetterSaul Geçmiş’e yaz (PDF yok)",
            "input_schema": {
                "properties": {
                    "text": {"type": "string"},
                    "body": {"type": "string"},
                    "dilekce": {"type": "string"},
                    "title": {"type": "string"},
                    "petition_type": {"type": "string"},
                }
            },
        },
        {
            "name": "save_petition_pdf",
            "description": "Önce Geçmiş’e yaz, sonra PDF dene",
            "input_schema": {
                "properties": {
                    "text": {"type": "string"},
                    "body": {"type": "string"},
                    "dilekce": {"type": "string"},
                    "title": {"type": "string"},
                    "petition_type": {"type": "string"},
                    "history_only": {"type": "boolean"},
                }
            },
        },
    ]


def _local_mcp_call(name: str, args: dict) -> str:
    sources = _local_mcp()
    if sources is None:
        raise RuntimeError("BetterSaul MCP paketi yok")
    args = args or {}
    if name == "search_bedesten":
        return sources.search_bedesten(str(args.get("phrase") or args.get("query") or ""), args.get("court_types"))
    if name == "search_corpus_deep":
        phrases = args.get("phrases") or args.get("phrase") or args.get("query") or ""
        return sources.search_corpus_deep(phrases, int(args.get("pages") or 2), args.get("court_types"))
    if name == "get_bedesten_document":
        return sources.get_bedesten_document(str(args.get("documentId") or args.get("document_id") or args.get("id") or ""))
    if name == "get_bedesten_holding":
        doc_id = str(args.get("documentId") or args.get("document_id") or args.get("id") or "")
        raw = sources.get_bedesten_document(doc_id)
        fn = getattr(sources, "extract_holding", None)
        return fn(raw) if fn and raw else raw
    if name == "search_emsal":
        return sources.search_emsal(str(args.get("keyword") or args.get("phrase") or args.get("query") or ""), int(args.get("page_number") or 1))
    if name == "search_resmi_gazete":
        return sources.search_resmi_gazete(
            str(args.get("query") or args.get("phrase") or args.get("keyword") or ""),
            str(args.get("date_start") or args.get("dateStart") or ""),
            str(args.get("date_end") or args.get("dateEnd") or ""),
        )
    if name == "get_resmi_gazete_fihrist":
        return sources.get_resmi_gazete_fihrist(str(args.get("date") or args.get("tarih") or ""))
    if name == "get_resmi_gazete_document":
        return sources.get_resmi_gazete_document(
            str(args.get("url_or_date_and_item") or args.get("url") or args.get("item") or "")
        )
    from bettersaul_mcp import anayasa as _aym
    from bettersaul_mcp import mevzuat as _mz
    if name == "search_mevzuat":
        return _mz.search_mevzuat(str(args.get("query") or args.get("phrase") or args.get("keyword") or ""))
    if name == "get_mevzuat_article":
        return _mz.get_mevzuat_article(str(args.get("kanun") or args.get("law") or ""), str(args.get("madde") or args.get("article") or ""))
    if name == "list_mevzuat_catalog":
        return _mz.list_mevzuat_catalog()
    if name == "search_anayasa":
        return _aym.search_anayasa(
            str(args.get("keywords") or args.get("query") or args.get("phrase") or ""),
            str(args.get("decision_type") or args.get("decisionType") or "bireysel_basvuru"),
        )
    if name == "get_anayasa_document":
        return _aym.get_anayasa_document(str(args.get("url_or_id") or args.get("url") or args.get("id") or ""))
    from bettersaul_mcp import petition_tools as _pt
    if name == "petition_guide":
        return _pt.petition_guide(str(args.get("petition_type") or args.get("petitionType") or ""))
    if name == "petition_skeleton":
        return _pt.petition_skeleton(str(args.get("petition_type") or args.get("petitionType") or ""))
    if name == "scan_source":
        return _pt.scan_source(str(args.get("source") or args.get("text") or args.get("prompt") or ""))
    if name == "format_petition":
        raw = _pt._tool_text(
            str(args.get("text") or ""),
            str(args.get("body") or ""),
            str(args.get("petition") or ""),
            str(args.get("dilekce") or ""),
            str(args.get("source") or ""),
        )
        return _pt.format_petition(
            raw,
            str(args.get("court") or ""),
            str(args.get("title") or ""),
            str(args.get("source") or ""),
        )
    if name == "review_petition":
        from bettersaul_mcp import quality as _q
        raw = _pt._tool_text(
            str(args.get("text") or ""),
            str(args.get("body") or ""),
            str(args.get("petition") or ""),
            str(args.get("dilekce") or ""),
        )
        return _q.review_text(
            raw,
            petition_type=str(args.get("petition_type") or args.get("petitionType") or ""),
            source=str(args.get("source") or ""),
            memory=_CASE_MEMORY or _load_case_memory(),
        )
    if name == "check_petition":
        raw = _pt._tool_text(
            str(args.get("text") or ""),
            str(args.get("body") or ""),
            str(args.get("petition") or ""),
            str(args.get("dilekce") or ""),
            str(args.get("source") or ""),
        )
        return _pt.check_court_ready(
            raw,
            str(args.get("petition_type") or args.get("petitionType") or ""),
            str(args.get("source") or ""),
        )
    if name == "save_petition_history":
        return _pt.save_petition_history(
            text=str(args.get("text") or ""),
            title=str(args.get("title") or "dilekce"),
            petition_type=str(args.get("petition_type") or args.get("petitionType") or ""),
            body=str(args.get("body") or ""),
            petition=str(args.get("petition") or ""),
            dilekce=str(args.get("dilekce") or ""),
            content=str(args.get("content") or ""),
            source=str(args.get("source") or ""),
        )
    if name == "save_petition_pdf":
        return _pt.save_petition_pdf(
            str(args.get("text") or ""),
            title=str(args.get("title") or "dilekce"),
            path=str(args.get("path") or ""),
            open_file=bool(args.get("open_file")),
            petition_type=str(args.get("petition_type") or args.get("petitionType") or ""),
            body=str(args.get("body") or ""),
            petition=str(args.get("petition") or ""),
            dilekce=str(args.get("dilekce") or ""),
            content=str(args.get("content") or ""),
            source=str(args.get("source") or ""),
            history_only=bool(args.get("history_only") or args.get("historyOnly")),
        )
    raise RuntimeError(f"Bilinmeyen araç: {name}")


def mcp_tools(quiet: bool = False) -> list[dict]:
    local = _local_tool_list()
    if _local_mcp() is not None:
        return local
    try:
        from mcp import ClientSession
        import anyio
        from bettersaul_mcp.tls import open_mcp

        async def _list() -> list[dict]:
            with anyio.fail_after(8):
                async with open_mcp(MCP_URL) as streams:
                    r, w = streams[0], streams[1]
                    async with ClientSession(r, w) as s:
                        await s.initialize()
                        res = await s.list_tools()
                        out = []
                        for t in res.tools:
                            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)
                            out.append(
                                {
                                    "name": t.name,
                                    "description": t.description or "",
                                    "input_schema": schema,
                                }
                            )
                        return out

        remote = anyio.run(_list)
        names = {t["name"] for t in remote}
        for t in local:
            if t["name"] not in names:
                remote.append(t)
        return remote or local
    except Exception as exc:
        if not quiet:
            emit("status", f"BetterSaul MCP HTTP yok ({_mcp_err(exc)}); yerel araçlar kullanılacak.")
        return local


def wait_mcp_tools(seconds: int = 8) -> list[dict]:
    last = mcp_tools(quiet=True)
    if last:
        emit("status", f"BetterSaul MCP hazır ({len(last)} araç).")
        return last
    emit("status", "BetterSaul MCP bekleniyor…")
    deadline = time.time() + max(2, seconds)
    while time.time() < deadline:
        last = mcp_tools(quiet=True)
        if last:
            emit("status", f"BetterSaul MCP hazır ({len(last)} araç).")
            return last
        time.sleep(1)
    emit("status", "BetterSaul MCP bu oturumda açılamadı. Kurulum → Bağlantı’dan başlatın.")
    return last


def warmup_model() -> None:
    emit("status", "Model yükleniyor…")
    try:
        generate(
            [{"role": "user", "content": "Hazır."}],
            n_predict=6,
            n_ctx=512,
            live=False,
            busy="Model yükleniyor…",
        )
        emit("status", "Model hazır.")
    except Exception as exc:
        emit("status", f"Model ısınma uyarısı: {exc}")


def mcp_call(name: str, args: dict) -> str:
    if _local_mcp() is not None:
        try:
            return _local_mcp_call(name, args)
        except Exception as exc:
            return f"Araç yanıt vermedi: {exc}"
    try:
        from mcp import ClientSession
        import anyio
        from bettersaul_mcp.tls import open_mcp

        async def _call() -> str:
            with anyio.fail_after(28):
                async with open_mcp(MCP_URL) as streams:
                    r, w = streams[0], streams[1]
                    async with ClientSession(r, w) as s:
                        await s.initialize()
                        res = await s.call_tool(name, args)
                        parts = []
                        for item in res.content or []:
                            if getattr(item, "type", "") == "text":
                                parts.append(item.text)
                            else:
                                parts.append(str(item))
                        text = "\n".join(parts)
                        return text[:20000] if len(text) > 20000 else text

        return anyio.run(_call)
    except Exception as exc:
        return f"Araç yanıt vermedi: {exc}"


def _schema_args(schema: dict | None, query: str) -> dict:
    props = (schema or {}).get("properties") if isinstance(schema, dict) else None
    props = props or {}
    for key in ("phrase", "query", "q", "search", "keyword", "keywords", "text"):
        if key in props:
            return {key: query}
    for key, spec in props.items():
        if isinstance(spec, dict) and spec.get("type") == "string":
            return {key: query}
    return {"phrase": query, "query": query}


def _research_note(line: str) -> None:
    emit("research", line)


def _brief_hits(text: str, limit: int = 4) -> str:
    cites = _extract_cites(text)
    if cites:
        return " · ".join(cites[:limit])
    titles = re.findall(
        r'"(?:baslik|title|kararBasligi|daire|esasNo|kararNo)"\s*:\s*"([^"]{6,140})"',
        text or "",
        re.I,
    )
    if titles:
        return " · ".join(titles[:limit])
    lines = [ln.strip() for ln in (text or "").splitlines() if len(ln.strip()) > 24]
    return " · ".join(lines[:limit])[:320] if lines else "sonuç özeti yok"


def _json_strs(text: str, key: str) -> list[str]:
    return re.findall(rf'"{key}"\s*:\s*"([^"]+)"', text or "", re.I)


def _json_field(blob: str, *keys: str) -> str:
    for k in keys:
        m = re.search(rf'"{re.escape(k)}"\s*:\s*"([^"]*)"', blob or "", re.I)
        if m and m.group(1).strip() and m.group(1) not in ("null", "None"):
            return m.group(1).strip()
        m = re.search(rf'"{re.escape(k)}"\s*:\s*(\d{{4}}/\d+|\d{{5,}})', blob or "", re.I)
        if m:
            return m.group(1).strip()
    return ""


def _normalize_court_name(raw: str) -> str:
    d = re.sub(r"\s+", " ", (raw or "").strip())
    if not d:
        return ""
    if re.search(r"(?i)anayasa|AYM", d) and "Mahkemesi" not in d:
        return "Anayasa Mahkemesi"
    if re.search(r"(?i)^\d+\.\s*Hukuk Dairesi", d) and "Yargıtay" not in d and "Danıştay" not in d:
        return "Yargıtay " + d
    if re.search(r"(?i)^\d+\.\s*Daire", d) and "Danıştay" not in d and "Yargıtay" not in d:
        return "Danıştay " + d
    if re.search(r"(?i)Hukuk Genel Kurulu", d) and "Yargıtay" not in d:
        return "Yargıtay Hukuk Genel Kurulu"
    return d


def _row_kunye(row: dict) -> str:
    d = _normalize_court_name(str(row.get("kaynak") or row.get("birimAdi") or "").strip())
    e = str(row.get("esas") or "").strip()
    k = str(row.get("karar") or "").strip()
    t = str(row.get("tarih") or row.get("kararTarihiStr") or "").strip()
    t = re.sub(r"T\d{2}:\d{2}:\d{2}.*$", "", t)
    t = _kunye_tr(t)
    t = re.sub(r"^(\d{1,2}\.\d{1,2}\.\d{4})$", r"T. \1", t)
    blob = f"{d}"
    if re.search(r"danistay|Danıştay", blob, re.I):
        bit = d or "Danıştay"
    elif re.search(r"yargitay|Yargıtay", blob, re.I):
        bit = d or "Yargıtay"
    elif re.search(r"(?i)AYM|Anayasa", blob):
        bit = d or "Anayasa Mahkemesi"
    else:
        bit = d or "karar"
    if e:
        bit += f", E. {e}"
    if k:
        bit += f", K. {k}"
    if t:
        bit += f", {t}" if not t.startswith("T.") else f", {t}"
    return _kunye_tr(re.sub(r"\s+", " ", bit).strip(" ,"))


def _yk_pair(item: dict, yil_key: str, sira_key: str, ready: str) -> str:
    if ready:
        return str(ready).strip()
    yil, sira = item.get(yil_key), item.get(sira_key)
    if yil not in (None, "") and sira not in (None, ""):
        return f"{yil}/{sira}"
    return ""


def _cite_from_mapping(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    esas = _yk_pair(item, "esasNoYil", "esasNoSira", item.get("esasNo") or item.get("esas"))
    karar = _yk_pair(item, "kararNoYil", "kararNoSira", item.get("kararNo") or item.get("karar"))
    bno = str(item.get("basvuruNo") or item.get("BNo") or "").strip()
    if not (esas or karar or bno):
        return None
    tarih = (
        item.get("kararTarihiStr")
        or item.get("kararTarihi")
        or item.get("tarih")
        or ""
    )
    return {
        "kaynak": _normalize_court_name(
            str(
                item.get("birimAdi")
                or item.get("daire")
                or item.get("kaynak_adi")
                or item.get("kaynak")
                or item.get("mahkeme")
                or ""
            )
        ),
        "esas": esas or bno,
        "karar": str(karar or ""),
        "tarih": str(tarih or ""),
        "ozet": str(
            item.get("ozet")
            or item.get("holding")
            or item.get("aciklama")
            or item.get("kararOzeti")
            or item.get("ilke")
            or ""
        )[:420],
        "baslik": str(item.get("baslik") or item.get("title") or item.get("kunye") or ""),
        "documentId": str(item.get("documentId") or item.get("id") or ""),
    }


def _extract_cite_rows(research: str) -> list[dict]:
    """İç içe JSON dahil künye çıkarır. Uydurmaz."""
    text = research or ""
    out: list[dict] = []
    seen: set[str] = set()

    def add(row: dict | None) -> None:
        if not row:
            return
        key = f"{row.get('esas')}|{row.get('karar')}|{row.get('kaynak')}".lower()
        if key in seen:
            if row.get("ozet"):
                for x in out:
                    if x.get("esas") == row.get("esas") and x.get("karar") == row.get("karar") and not x.get("ozet"):
                        x["ozet"] = row["ozet"]
            return
        seen.add(key)
        out.append(row)

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            add(_cite_from_mapping(obj))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    dec = json.JSONDecoder()
    i = 0
    while i < len(text):
        if text[i] in "{[":
            try:
                obj, end = dec.raw_decode(text, i)
                walk(obj)
                i = end
                continue
            except Exception:
                pass
        i += 1
    if out:
        return out[:24]
    for m in re.finditer(r"\{[^{}]{20,2000}\}", text):
        blob = m.group(0)
        if not re.search(r"esasNo|kararNo|\"esas\"|B\.\s*No|kunye", blob, re.I):
            continue
        add(
            {
                "kaynak": _normalize_court_name(
                    _json_field(blob, "birimAdi", "daire", "kaynak_adi", "kaynak", "mahkeme")
                ),
                "esas": _json_field(blob, "esasNo", "esas") or _json_field(blob, "basvuruNo", "BNo"),
                "karar": _json_field(blob, "kararNo", "karar"),
                "tarih": _json_field(blob, "kararTarihiStr", "kararTarihi", "tarih"),
                "ozet": _json_field(blob, "ozet", "holding", "aciklama", "kararOzeti", "ilke"),
                "baslik": _json_field(blob, "baslik", "title", "kunye"),
                "documentId": _json_field(blob, "documentId", "id"),
            }
        )
    return out[:24]


def _extract_cites(research: str) -> list[str]:
    rows = _extract_cite_rows(research)
    if rows:
        return [_row_kunye(r) for r in rows if r.get("esas") or r.get("karar")]
    text = research or ""
    esas = _json_strs(text, "esasNo") or _json_strs(text, "esas")
    karar = _json_strs(text, "kararNo") or _json_strs(text, "karar")
    daire = _json_strs(text, "birimAdi") or _json_strs(text, "daire")
    tarih = _json_strs(text, "kararTarihi") or _json_strs(text, "tarih")
    kaynak = _json_strs(text, "kaynak")
    n = max(len(esas), len(karar), len(daire), 0)
    out: list[str] = []
    for i in range(min(n, 24)):
        e = esas[i] if i < len(esas) else ""
        k = karar[i] if i < len(karar) else ""
        d = daire[i] if i < len(daire) else ""
        t = tarih[i] if i < len(tarih) else ""
        src = kaynak[i] if i < len(kaynak) else ""
        if not (e or k):
            continue
        bit = _row_kunye({"kaynak": d or src, "esas": e, "karar": k, "tarih": t})
        if bit not in out:
            out.append(bit)
    return out


def _is_portal_junk(text: str) -> bool:
    t = text or ""
    return bool(
        re.search(
            r"image/svg|svg\+xml|böyle bir içerik mevcut değildir|"
            r"Bilgi İşlem Genel Müdürlüğü|Uygulama içerisinde böyle bir içerik|"
            r"adalet\s+Bakanl[ıi]ğ[ıi]\s+Bilgi İşlem|"
            r"(?:HTTP\s+)?404(?:\s+Uygulama|\s+Not Found|\s+Sayfa)|"
            r"image/svg\+xml\s*404",
            t,
            re.I,
        )
    )


def _strip_portal_junk(text: str) -> str:
    t = text or ""
    t = re.sub(
        r"(?is)(?:adalet\s+Bakanl[ıi]ğ[ıi]\s+)?Bilgi İşlem Genel Müdürlüğü.{0,280}?"
        r"(?:mevcut değildir\.?|404|image/svg\+xml)",
        " ",
        t,
    )
    t = re.sub(r"(?is)image/svg\+xml.{0,240}", " ", t)
    t = re.sub(r"(?is)<svg\b.*?</svg>", " ", t)
    t = re.sub(r"(?is)Uygulama içerisinde böyle bir içerik mevcut değildir\.?", " ", t)
    t = re.sub(r"(?<![/\dE.])\b404\b(?![/\d])", " ", t)
    lines = []
    for ln in t.splitlines():
        if _is_portal_junk(ln) and len(re.sub(r"\s+", "", ln)) < 80:
            continue
        lines.append(ln)
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"\n{3,}", "\n\n", "\n".join(lines))).strip()


def _extract_ozetler(research: str) -> list[str]:
    ozets = _json_strs(research, "ozet")
    holds = _json_strs(research, "holding")
    out: list[str] = []
    for s in holds + ozets:
        t = re.sub(r"\s+", " ", s or "").strip()
        if len(t) < 24 or _is_portal_junk(t):
            continue
        if t not in out:
            out.append(t)
    return out[:12]


def _doc_ids(text: str) -> list[str]:
    found = re.findall(r'"documentId"\s*:\s*"([^"]+)"', text or "")
    found += re.findall(r'"documentId"\s*:\s*(\d{5,})', text or "")
    if not found:
        found = re.findall(r"documentId[\"'\s:=]+([A-Za-z0-9_\-]{5,})", text or "")
    out: list[str] = []
    for x in found:
        if x and x not in out:
            out.append(x)
    return out[:8]


_MEMORY_PATH = Path(os.environ.get("LOCALAPPDATA") or "") / "BetterSaul" / "case_memory.json"
_CASE_MEMORY: dict = {}
_FETCHED_DOCS: set[str] = set()


def _save_case_memory(mem: dict) -> None:
    global _CASE_MEMORY
    _CASE_MEMORY = dict(mem or {})
    try:
        _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _MEMORY_PATH.write_text(json.dumps(_CASE_MEMORY, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_case_memory() -> dict:
    if _CASE_MEMORY:
        return _CASE_MEMORY
    try:
        if _MEMORY_PATH.is_file():
            data = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _memory_brief(mem: dict | None = None, limit: int = 1800) -> str:
    mem = mem if mem is not None else _load_case_memory()
    if not mem:
        return ""
    lines: list[str] = []
    if mem.get("petitionType"):
        lines.append(f"Dava türü: {mem['petitionType']}")
    if mem.get("issues"):
        lines.append("Hukuki meseleler: " + ", ".join(mem["issues"][:8]))
    cites = mem.get("cites") or []
    if cites:
        lines.append("Taranan içtihat:")
        lines.extend(f"- {c}" for c in cites[:10])
    holds = mem.get("holdings") or []
    if holds:
        lines.append("Karar özetleri (yalnızca bunlar kullanılabilir):")
        lines.extend(f"- {h}" for h in holds[:6])
    facts = (mem.get("facts") or "").strip()
    if facts:
        lines.append("Olay özeti: " + facts[:500])
    notes = mem.get("think_notes") or []
    if notes:
        lines.append("Muhakeme notları:")
        lines.extend(f"- {n}" for n in notes[-3:])
    stats = mem.get("statutes") or []
    if stats:
        lines.append("Resmi maddeler (yalnızca bunlar; çekilemeyen şişirilmez):")
        for s in stats[:10]:
            if isinstance(s, dict) and s.get("label"):
                bit = s["label"]
                if s.get("ozet"):
                    bit += " — " + str(s["ozet"])[:160]
                lines.append(f"- {bit}")
            elif isinstance(s, str):
                lines.append(f"- {s}")
    aym = mem.get("aym") or []
    if aym:
        lines.append("AYM (en fazla 1; yoksa uydurma):")
        for a in aym[:1]:
            if isinstance(a, dict):
                lines.append(f"- {a.get('kunye') or a.get('baslik') or ''} {a.get('ilke') or a.get('ozet') or ''}".strip())
    rg = mem.get("rg") or []
    if rg:
        real = [r for r in rg if isinstance(r, dict) and (r.get("baslik") or r.get("url")) and r.get("sonuc") != "taranamadı"]
        if real:
            lines.append("Resmî Gazete (yalnızca gerçek kayıt):")
            lines.extend(f"- {r.get('baslik') or r.get('url')}" for r in real[:3])
        else:
            lines.append("Resmî Gazete: taranamadı — sayı/tarih uydurma.")
    return "\n".join(lines)[:limit]


def _looks_legal_query(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 24:
        return False
    if re.search(
        r"(içtihat|yargıtay|danıştay|dava|dilekçe|tmk|tbk|hmk|iik|tck|cmk|"
        r"boşanma|nafaka|velayet|kıdem|alacak|tahliye|tazminat|icra|iptal|"
        r"ayıplı|kira|işe iade|emsal|mevzuat|anayasa|7315|iyuk)",
        t,
        re.I,
    ):
        return True
    return len(t) >= 90


def _guess_ptype(text: str) -> str:
    t = (text or "").lower()
    pairs = (
        ("boşan", "Boşanma Davası"),
        ("velayet", "Boşanma Davası"),
        ("nafaka", "Boşanma Davası"),
        ("kıdem", "İş Davası"),
        ("işe iade", "İş Davası"),
        ("işçilik", "İş Davası"),
        ("icra", "İcra Hukuku"),
        ("itirazın iptali", "İcra Hukuku"),
        ("tahliye", "Kira / Tahliye"),
        ("kira", "Kira / Tahliye"),
        ("ayıplı", "Tüketici Hukuku"),
        ("tüketici", "Tüketici Hukuku"),
        ("idare", "İdare Hukuku"),
        ("iptal dav", "İdare Hukuku"),
        ("tazminat", "Tazminat Davası"),
        ("ceza", "Ceza Hukuku"),
        ("alacak", "Alacak Davası"),
    )
    for key, name in pairs:
        if key in t:
            return name
    return "Diğer"


def _form_blob(form: dict) -> str:
    return " ".join(
        str(form.get(k) or "")
        for k in ("petitionType", "title", "caseSummary", "extraInstructions", "requests", "userPrompt")
    ).lower()


def _divorce_ground(form: dict) -> str:
    """164 yalnızca açıkça terke dayalı dava istenirse; aksi hâlde 166. Terk vakıası 166’yı 164 yapmaz."""
    blob = _form_blob(form)
    wants_164 = bool(
        re.search(
            r"tmk\s*m\.?\s*164|164\s*uyarınca|terke\s+dayal[ıi]|terk\s+davas[ıi]|müstakil\s+terk",
            blob,
        )
    )
    wants_166 = bool(
        re.search(
            r"tmk\s*m\.?\s*166|166\s*uyarınca|temelinden\s+sars|şiddetli\s+geçimsiz",
            blob,
        )
    )
    if wants_164 and not wants_166:
        return "164"
    return "166"


def _research_queries(form: dict) -> list[str]:
    ptype = str(form.get("petitionType") or "").strip()
    summary = str(form.get("caseSummary") or "")
    extra = str(form.get("extraInstructions") or "")
    reqs = str(form.get("requests") or "")
    up = str(form.get("userPrompt") or "")
    blob = f"{summary} {extra} {reqs} {up}".lower()
    mapped = {
        "Boşanma Davası": "boşanma evlilik birliği temelinden sarsılması TMK 166",
        "İş Davası": "işçilik alacağı ücret 4857",
        "Alacak Davası": "alacak davası temerrüt haksız fiil TBK",
        "İcra Hukuku": "icra itirazın iptali inkâr tazminatı İİK 67",
        "İdare Hukuku": "iptal davası idari işlem tam yargı İYUK",
        "Tazminat Davası": "maddi manevi tazminat haksız fiil TBK 49",
        "Ceza Hukuku": "kasten yaralama ceza davası TCK",
        "Kira / Tahliye": "kira tahliye temerrüt ihtiyaç TBK 315",
        "Tüketici Hukuku": "ayıplı mal tüketici TKHK",
    }
    by_type: dict[str, list[str]] = {
        "Boşanma Davası": (
            [
                "Yargıtay 2 HD terk TMK 164 boşanma",
                "Yargıtay 2 HD terk süresi ihtar ortak konut",
            ]
            if _divorce_ground(form) == "164"
            else [
                "Yargıtay 2 Hukuk Dairesi evlilik birliği temelinden sarsılması TMK 166",
                "Yargıtay 2 HD sadakat yükümlülüğü TMK 185 boşanma",
                "Yargıtay 2 HD ortak hayat çekilmez TMK 166 kusur",
            ]
        ),
        "İş Davası": [
            "Yargıtay 9 Hukuk Dairesi ücret alacağı 4857 m 32",
            "Yargıtay 9 HD ödenmeyen ücret en yüksek mevduat faizi",
            "Yargıtay 9 HD 7036 m 3 arabuluculuk dava şartı son tutanak",
            "Yargıtay 9 HD 4857 m 34 en yüksek mevduat faizi ücret",
            "Yargıtay 9 HD ücretin zamanında ödenmemesi",
            "Yargıtay HGK işçilik alacağı belirsiz alacak HMK 107",
        ],
        "Alacak Davası": [
            "Yargıtay 3 HD alacak temerrüt TBK 117",
            "Yargıtay 11 HD sözleşme alacağı ifa etmeme",
            "Yargıtay 6 HD eser sözleşmesi alacak",
        ],
        "İcra Hukuku": [
            "Yargıtay 12 HD itirazın iptali İİK 67",
            "Yargıtay 12 HD inkâr tazminatı icra",
        ],
        "İdare Hukuku": [
            "Danıştay güvenlik soruşturması 7315 soyut gerekçe iptal",
            "Danıştay değerlendirme komisyonu atama uygunluk",
            "Danıştay sebep unsuru güvenlik soruşturması hukuka aykırı",
            "Danıştay HAGB memuriyete engel güvenlik soruşturması",
        ],
        "Tazminat Davası": [
            "Yargıtay 4 HD maddi manevi tazminat TBK 49",
            "Yargıtay 4 HD kusur illiyet zarar",
            "Yargıtay 4 HD trafik kazası tazminat",
        ],
        "Ceza Hukuku": [
            "Yargıtay Ceza Genel Kurulu kasten yaralama",
            "Yargıtay 1 CD kamu davasına katılma CMK 237",
        ],
        "Kira / Tahliye": [
            "Yargıtay 3 HD kira tahliye temerrüt TBK 315",
            "Yargıtay 3 HD ihtiyaç tahliyesi TBK 350",
            "Yargıtay 3 HD kira alacağı ihtar",
        ],
        "Tüketici Hukuku": [
            "Yargıtay 3 HD ayıplı mal TKHK 8 11",
            "Yargıtay 3 HD tüketici seçimlik hak bedel iadesi",
        ],
    }
    qs = list(by_type.get(ptype) or [mapped.get(ptype, ptype or "hukuk")])
    extra_map = (
        (("velayet", "müşterek çocuk", "ortak çocuk"), "Yargıtay 2 HD velayet çocuğun üstün yararı TMK 182"),
        (("nafaka", "yoksul"), "Yargıtay 2 HD yoksulluk nafakası TMK 175"),
        (("ziynet", "altın"), "Yargıtay 2 HD ziynet eşyası iadesi"),
        (("6284", "uzaklaştır", "aile içi şiddet"), "Yargıtay 2 HD aile içi şiddet boşanma TMK 166"),
        (("kıdem",), "Yargıtay 9 HD kıdem tazminatı 1475 m 14"),
        (("ihbar",), "Yargıtay 9 HD ihbar tazminatı 4857 m 17"),
        (("işe iade",), "Yargıtay 9 HD işe iade 4857 m 18 21"),
        (("fazla mesai", "ubgt"), "Yargıtay 9 HD fazla çalışma ücreti"),
        (("itirazın iptali",), "Yargıtay 12 HD itirazın iptali"),
        (("tahliye",), "Yargıtay 3 HD kira tahliye"),
        (("ayıplı",), "Yargıtay 3 HD ayıplı mal tüketici"),
        (("manevi tazminat",), "Yargıtay 4 HD manevi tazminat TBK 58"),
        (("ücret alacağı", "ödenmeyen ücret", "maaş"), "Yargıtay 9 HD ücret alacağı 4857 m 32 faiz"),
        (("güvenlik soruştur", "7315"), "Danıştay 7315 güvenlik soruşturması olumsuz soyut gerekçe"),
        (("atama uygunluk", "değerlendirme komisyon"), "Danıştay atama uygunluk değerlendirme komisyonu"),
        (("HAGB", "hükmün açıklanmasının geri"), "Danıştay HAGB güvenlik soruşturması atama"),
        (("infaz ve koruma",), "Danıştay infaz koruma memuru güvenlik soruşturması"),
        (("657", "devlet memur", "memuriyet"), "657 sayılı Kanun memuriyet iptal"),
    )
    hint = _prompt_search_hint(up)
    if len(hint) > 24 and not _is_prompt_block(up) and not _is_prompt_block(hint):
        qs.insert(0, hint)
    labor = is_labor(form)
    if labor:
        claims = _form_claims(form)
        claim_qs: list[str] = []
        if "ise_iade" in claims:
            claim_qs.append("Yargıtay 9 HD işe iade 4857 m 18 21 2024 2025 2026")
        if "kidem" in claims:
            claim_qs.append("Yargıtay 9 HD kıdem tazminatı 1475 m 14 2024 2025 2026")
        if "ihbar" in claims:
            claim_qs.append("Yargıtay 9 HD ihbar tazminatı 4857 m 17 2024 2025 2026")
        if "fazla" in claims:
            claim_qs.append("Yargıtay 9 HD fazla çalışma ücreti 4857 m 41 2024 2025 2026")
        if "ucret" in claims or not claim_qs:
            claim_qs.append("Yargıtay 9 HD ücret alacağı 4857 m 32 34 2024 2025 2026")
        qs = claim_qs + [q for q in qs if q not in claim_qs]
    for keys, q in extra_map:
        if labor and re.search(r"2 HD|ziynet|nafaka|velayet|TMK 16|4 HD", q):
            continue
        if "İdare" in ptype and "Yargıtay" in q:
            continue
        if any(k in blob for k in keys):
            qs.append(q)
    seen: list[str] = []
    for q in qs:
        if not q or _is_prompt_block(q) or q in seen:
            continue
        if re.search(r"Yargıtay|Danıştay", q) and not re.search(r"20\d{2}", q):
            q = q + " 2024 2025 2026"
        seen.append(q)
    return seen[:12] if labor else seen[:8]


def _find_tool(by_name: dict, *needles: str) -> str:
    for n in by_name:
        low = n.lower()
        if all(x.lower() in low for x in needles):
            return n
    return ""


def _issue_labels(form: dict) -> list[str]:
    blob = _intent_blob(form).lower() + " " + str(form.get("petitionType") or "").lower()
    labels = [str(form.get("petitionType") or "").strip() or "hukuk"]
    for key, lab in (
        ("aldat", "sadakat / aldatma"),
        ("zina", "sadakat / aldatma"),
        ("velayet", "velayet"),
        ("nafaka", "nafaka"),
        ("ücret", "ücret alacağı"),
        ("tazminat", "tazminat"),
        ("ziynet", "ziynet"),
        ("şiddet", "aile içi şiddet"),
        ("kıdem", "kıdem / ihbar"),
        ("işe iade", "işe iade"),
        ("fazla mesai", "fazla mesai"),
        ("tahliye", "tahliye"),
        ("ayıplı", "ayıplı mal"),
        ("itirazın iptali", "itirazın iptali"),
        ("idari işlem", "idari işlem"),
        ("7315", "7315 / güvenlik soruşturması"),
        ("güvenlik soruştur", "7315 / güvenlik soruşturması"),
        ("HAGB", "HAGB"),
        ("atama uygunluk", "atama uygunluk"),
        ("alacak", "alacak"),
    ):
        if key in blob and lab not in labels:
            if is_labor(form) and lab in {
                "tazminat",
                "ziynet",
                "nafaka",
                "velayet",
                "sadakat / aldatma",
                "aile içi şiddet",
            }:
                continue
            labels.append(lab)
    return labels[:8]


def _uniq_keep(items: list[str], limit: int = 12) -> list[str]:
    out: list[str] = []
    for x in items:
        t = (x or "").strip()
        if t and t not in out:
            out.append(t)
    return out[:limit]


def _think_next_queries(form: dict, raw: str, used: list[str], tur: int = 2) -> list[str]:
    """Önceki turu muhakeme edip sonraki sorguyu kurar (10 tura kadar)."""
    ptype = str(form.get("petitionType") or "")
    next_qs: list[str] = []
    if "İdare" in ptype:
        dairler = _uniq_keep(
            re.findall(
                r"Danıştay\s+(?:\d+\.\s*Daire|İdare Dava Daireleri Kurulu|Vergi Dava Daireleri Kurulu|İDDK|VDDK|İBK|DBGK)",
                raw or "",
                re.I,
            ),
            4,
        )
    else:
        dairler = _uniq_keep(re.findall(r"\d+\.\s*Hukuk Dairesi", raw or "", re.I), 4)
    ozets = [o for o in _extract_ozetler(raw) if not _is_portal_junk(o)]
    cites = _extract_cites(raw)
    _research_note(
        f"Muhakeme {tur}/{_rounds(form)}: "
        + (f"{len(cites)} karar, " if cites else "karar zayıf, ")
        + (f"daire {', '.join(dairler[:2])}." if dairler else "daire netleşmedi.")
    )
    core = {
        "Boşanma Davası": "boşanma TMK 166",
        "İş Davası": "işçilik alacağı 4857",
        "Alacak Davası": "alacak temerrüt",
        "İcra Hukuku": "itirazın iptali",
        "İdare Hukuku": "iptal davası",
        "Tazminat Davası": "tazminat TBK 49",
        "Ceza Hukuku": "kamu davası",
        "Kira / Tahliye": "tahliye kira",
        "Tüketici Hukuku": "ayıplı mal",
    }.get(ptype, ptype or "hukuk")
    pack = pack_for(ptype)
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{6,}", " ".join(ozets)[:900])
    stop = {"kararında", "uyarınca", "nedeniyle", "bakımından", "açıklanan", "gereğince", "yargıtay"}
    rare = [w for w in words if w.lower() not in stop]
    deep9 = {
        "Boşanma Davası": "Yargıtay 2 HD ziynet aynen iade faiz TMK 174 175 182 2024 2025 2026",
        "İş Davası": "Yargıtay 9 HD ücret alacağı 4857 m 32 7036 m 3 arabuluculuk 2024 2025 2026",
        "Alacak Davası": "Yargıtay 3 HD temerrüt faiz TBK 117 alacak 2024 2025 2026",
        "İcra Hukuku": "Yargıtay 12 HD itirazın iptali inkâr tazminatı İİK 67 2024 2025 2026",
        "İdare Hukuku": "Danıştay 7315 güvenlik soruşturması sebep unsuru soyut gerekçe 2024 2025 2026",
        "Tazminat Davası": "Yargıtay 4 HD maddi manevi tazminat illiyet TBK 49 2024 2025 2026",
        "Ceza Hukuku": "Yargıtay CD katılma CMK 237 tazminat 2024 2025 2026",
        "Kira / Tahliye": "Yargıtay 3 HD tahliye temerrüt TBK 315 350 2024 2025 2026",
        "Tüketici Hukuku": "Yargıtay 3 HD ayıplı mal seçimlik hak TKHK 11 2024 2025 2026",
    }.get(ptype, core + " hukuki sonuç")
    if tur <= 2:
        for d in dairler:
            next_qs.append(f"{d} {core}")
        if not dairler:
            next_qs.append(core + " ilgili daire emsal")
    elif tur == 3:
        for st in (pack.get("statutes") or [])[:4]:
            next_qs.append(f"{st} {core}")
    elif tur == 4:
        if rare[:4]:
            next_qs.append(" ".join(rare[:6])[:90])
        next_qs.append(core + " emsal karar gerekçe")
    elif tur == 5:
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD 4857 m 32 ücret alacağı ödenmemesi")
            next_qs.append("Yargıtay 9 HD belirsiz alacak işçilik HMK 107")
        else:
            next_qs.append(f"{core} kusur illiyet")
            next_qs.append(f"{core} istinaf emsal")
    elif tur == 6:
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD 4857 m 34 en yüksek mevduat faizi")
            next_qs.append("Yargıtay 9 HD işçilik alacağı belirsiz alacak")
        else:
            next_qs.append(f"{core} yerel mahkeme emsal")
            next_qs.append(f"{core} bölge adliye")
    elif tur == 7:
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD 7036 m 3 arabuluculuk usulden red son tutanak")
            next_qs.append("Yargıtay 9 HD iş mahkemesi görev 7036 m 5")
        else:
            next_qs.append(core + " yerleşik içtihat")
            if dairler:
                next_qs.append(f"{dairler[0]} {core} son içtihat")
    elif tur == 8:
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD HMK 107 belirsiz alacak ıslah işçilik")
            next_qs.append("Yargıtay 9 HD bordro banka dekont ücret ispat")
        else:
            next_qs.append(f"{core} hukuki sonuç hüküm")
            next_qs.append(f"{core} bozma onama")
    elif tur == 9:
        next_qs.append(deep9)
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD 2024 2025 2026 ücret alacağı")
        else:
            next_qs.append(f"{core} güncel içtihat")
    else:
        if "İş" in ptype:
            next_qs.append("Yargıtay 9 HD ücret alacağı 2024 2025 2026")
            next_qs.append("Yargıtay HGK işçilik alacağı belirsiz alacak")
            next_qs.append("Yargıtay 9 HD 4857 m 32 ödenmeyen ücret")
        else:
            next_qs.append(core + " 2024 2025 2026 içtihat")
            next_qs.append(f"{core} KG içtihat birleştirme")
        if dairler:
            next_qs.append(f"{dairler[0]} {core} son dönem")
    if "Danıştay" in (raw or "") or "İdare" in ptype:
        next_qs.append("Danıştay " + core)
    if not cites:
        next_qs.append(core + " emsal karar")
    used_l = {u.lower() for u in used}
    out = []
    for q in next_qs:
        if q.lower() not in used_l and q not in out:
            out.append(q)
    return out[:5]


def _parse_think_queries(text: str) -> list[str]:
    if not text:
        return []
    block = text
    m = re.search(r"(?is)SORULAR\s*:\s*(.*?)(?:\n[A-ZÇĞİÖŞÜ]{3,}\s*:|$)", text)
    if m:
        block = m.group(1)
    qs: list[str] = []
    for ln in (block or "").splitlines():
        ln = re.sub(r"^[\s\-–•*\d\.\)\(]+", "", ln).strip()
        if len(ln) < 10 or len(ln) > 160:
            continue
        if _looks_like_petition(ln) or _is_prompt_block(ln):
            continue
        low = ln.lower()
        if any(w in low for w in ("açıklamalar", "sonuç ve istem", "dilekçe yaz", "t.c.")):
            continue
        if ln not in qs:
            qs.append(ln)
    return qs[:4]


def _think_note_brief(text: str) -> str:
    m = re.search(r"(?is)TEZ\s*:\s*(.*?)(?:\n[A-ZÇĞİÖŞÜ]{3,}\s*:|$)", text or "")
    bit = m.group(1) if m else (text or "")
    return re.sub(r"\s+", " ", bit).strip()[:700]


def _llm_think_tour(form: dict, tur: int, digest: str, used: list[str]) -> list[str]:
    """Her turda model düşünür; dilekçe yazmaz. CUDA sunucusu hazır olmalı."""
    total = _rounds(form)
    emit("status", f"Tur {tur}/{total} — model CUDA ile muhakeme ediyor; dilekçe henüz yazılmıyor…")
    emit("research", f"Tur {tur}/{total} muhakeme (GPU). Dilekçe yok.")
    mem = _CASE_MEMORY or _load_case_memory()
    cites = "\n".join(f"- {c}" for c in (mem.get("cites") or _extract_cites(digest))[:6])
    holds = "\n".join(f"- {h[:420]}" for h in (mem.get("holdings") or [])[:4])
    used_txt = "\n".join(f"- {q}" for q in (used or [])[-6:])
    last = tur >= total
    user = (
        f"Tur {tur}/{total}. DİLEKÇE YAZMA. AÇIKLAMALAR, SONUÇ VE İSTEM, T.C. satırı yazma.\n"
        "Yalnızca hukuki muhakeme et. İçtihat numarası, tutar, isim, TCKN uydurma.\n\n"
        f"Dava: {form.get('petitionType') or ''}\n"
        f"Başlık: {form.get('title') or ''}\n"
        f"Olay:\n{str(form.get('caseSummary') or '')[:900]}\n"
        f"Talepler:\n{str(form.get('requests') or '')[:400]}\n"
        f"Yazım yönü:\n{str(form.get('userPrompt') or '')[:400]}\n"
        f"Kullanılmış sorgular:\n{used_txt or '- yok'}\n"
        f"Bulunan künye:\n{cites or '- yok'}\n"
        f"Gerekçe özeti:\n{holds or '- yok'}\n\n"
        "Çıktı biçimi:\n"
        "TEZ:\n(hangi madde, hangi vakıa, davanın hukuki çerçevesi)\n"
        "BOSLUK:\n(hangi emsal veya madde eksik)\n"
        "SORULAR:\n- ...\n- ...\n- ...\n"
    )
    if "İdare" in str(form.get("petitionType") or ""):
        user += (
            "İdari dava: SORULAR yalnızca Danıştay / İYUK / idari işlem içersin. "
            "Yargıtay, ticaret mahkemesi veya hukuk dairesi yazma.\n"
        )
    if last:
        user += (
            "PLAN:\n(5 A4 açıklama için 8–12 vakıa başlığı; henüz paragraf yazma)\n"
        )
    try:
        raw = generate(
            [
                {
                    "role": "system",
                    "content": (
                        "Sen Türk avukat asistanısın. Bu turda yalnızca muhakeme ve tarama sorusu üretirsin. "
                        "Dilekçe metni yazmazsın. Uydurma künye ve tutar yazmazsın. "
                        "İdari davada yalnızca Danıştay emsali sor."
                    ),
                },
                {"role": "user", "content": user},
            ],
            n_predict=256,
            n_ctx=_27b_ctx(PETITION_CTX) if _is_27b() else min(PETITION_CTX, 8192),
            live=True,
            busy=f"Tur {tur}/{total} muhakeme (GPU)…",
            think=True,
            allow_cli=False,
        )
    except Exception as exc:
        emit("research", f"Tur {tur} muhakeme atlandı ({exc}). Kural sorgusu kullanılacak.")
        return _think_next_queries(form, digest, used, tur=tur)
    text = _usable_text(raw) or _clean_llama_out(raw) or ""
    if _looks_like_petition(text):
        emit("research", f"Tur {tur}: dilekçe taslağı atıldı; yalnızca sorgu alınacak.")
        text = ""
    note = _think_note_brief(text)
    if note:
        emit("research", f"Tur {tur} tez: {note[:420]}")
        mem = dict(_CASE_MEMORY or mem or {})
        notes = list(mem.get("think_notes") or [])
        notes.append(f"Tur {tur}: {note[:800]}")
        mem["think_notes"] = notes[-6:]
        _save_case_memory(mem)
    qs = _parse_think_queries(text)
    if not qs:
        qs = _think_next_queries(form, digest, used, tur=tur)
    return qs


def _cite_holdings(research: str) -> list[str]:
    cites = _extract_cites(research)
    ozets = _extract_ozetler(research)
    out: list[str] = []
    for i, cite in enumerate(cites[:8]):
        ozet = ozets[i] if i < len(ozets) else ""
        bit = f"{cite}: {ozet}" if ozet else cite
        if bit not in out:
            out.append(bit)
    return out


def _usable_holding(text: str) -> bool:
    t = re.sub(r"\s+", " ", text or "").strip()
    if len(t) < 40:
        return False
    if t.startswith("Araç yanıt") or t.startswith("HTTP ") or t.startswith("Belge alınamadı"):
        return False
    return not _is_portal_junk(t)


def _pull_holdings(research: str, by_name: dict) -> list[str]:
    ids = _doc_ids(research)
    ozets = _extract_ozetler(research)
    holds: list[str] = list(ozets)
    getter = _find_tool(by_name, "get_bedesten_document") or "get_bedesten_document"
    src = _local_mcp()
    ids = [x for x in ids if x not in _FETCHED_DOCS]
    take = ids[:2]
    for i, doc_id in enumerate(take, 1):
        _FETCHED_DOCS.add(doc_id)
        _research_note(f"Karar metni okunuyor ({i}/{len(take)})…")
        raw = mcp_call(getter, {"documentId": doc_id})
        if not _usable_holding(raw or "") and src is not None:
            try:
                raw = src.get_bedesten_document(doc_id)
            except Exception:
                pass
        text = re.sub(r"&lt;br\s*/?&gt;|<br\s*/?>", " ", raw or "", flags=re.I)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not _usable_holding(text):
            why = "erişim sınırı" if re.search(r"eri[sş]im s[iı]n[iı]r|429", text or "", re.I) else "boş yanıt"
            _research_note(f"   → {why} atlandı")
            continue
        fn = getattr(src, "extract_holding", None) if src else None
        piece = fn(text) if fn else text[:520]
        piece = _strip_portal_junk(piece or "")
        if piece and not _is_portal_junk(piece) and piece not in holds:
            holds.append(piece)
            _research_note("   → gerekçe özeti alındı")
    if len(holds) < 2:
        for bit in _cite_holdings(research):
            if bit not in holds:
                holds.append(bit)
        if holds:
            _research_note("Karar metni eksik kaldı; esas-karar künyesi dilekçeye işlendi.")
    return [h for h in holds if not _is_portal_junk(h)][:10]


def _rg_query_for(form: dict) -> str:
    ptype = str(form.get("petitionType") or "")
    blob = _source_blob(form) if "_source_blob" in globals() else " ".join(
        str(form.get(k) or "") for k in ("caseSummary", "userPrompt", "title", "requests")
    )
    if "İdare" in ptype:
        if re.search(r"(?i)3500|infaz ve koruma|sözleşmeli personel", blob):
            return "sözleşmeli infaz ve koruma memuru"
        if re.search(r"(?i)7315|güvenlik soruştur|arşiv araştırm", blob):
            return "güvenlik soruşturması arşiv araştırması yönetmelik"
        return "güvenlik soruşturması"
    if "İş" in ptype:
        return "asgari ücret"
    if "Boşanma" in ptype:
        return "Türk Medeni Kanunu"
    if "Tüketici" in ptype:
        return "tüketici"
    if "İcra" in ptype:
        return "icra"
    return (ptype.split()[0] if ptype else "kanun").strip()


def _aym_query_for(form: dict) -> str:
    return _aym_queries_for(form)[0]


def _aym_queries_for(form: dict) -> list[str]:
    return [q for q, _ in _aym_search_plan(form)]


def _aym_search_plan(form: dict) -> list[tuple[str, str]]:
    """Olaydan AYM MCP sorgu + tür. Künye yazılmaz; yalnızca arama."""
    blob = " ".join(
        str(form.get(k) or "")
        for k in ("caseSummary", "userPrompt", "extraInstructions", "title", "requests", "petitionType")
    )
    plan: list[tuple[str, str]] = []
    if re.search(r"(?i)HAGB|hükmün açıklanmasının geri|kasten yaralama", blob):
        plan.append(("HAGB kasten yaralama kamu hizmetine girme masumiyet", "bireysel_basvuru"))
    if re.search(r"(?i)7315|güvenlik soruştur|arşiv araştırm|atama uygunluk", blob):
        plan.append(("güvenlik soruşturması kamu hizmetine girme gerekçesiz işlem", "bireysel_basvuru"))
        plan.append(("7315 güvenlik soruşturması arşiv araştırması", "norm_denetimi"))
    if re.search(r"(?i)soyut|gerekçesiz|belgeye erişim|atanmama", blob) or "İdare" in str(
        form.get("petitionType") or ""
    ):
        plan.append(("kamu görevine atanmama soyut gerekçe belgeye erişim", "bireysel_basvuru"))
    if re.search(r"(?i)kişisel veri|kvkk|arşiv araştırm", blob):
        plan.append(("güvenlik soruşturması kişisel veri masumiyet karinesi", "bireysel_basvuru"))
    if not plan:
        plan.append(("kamu hizmetine girme hak arama hürriyeti", "bireysel_basvuru"))
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for q, kind in plan:
        key = q + "|" + kind
        if key not in seen:
            seen.add(key)
            out.append((q, kind))
    return out[:5]


def _seed_official_sources(form: dict, by_name: dict) -> tuple[list, list, list]:
    """İçtihattan sonra resmi madde / 1 AYM / 1 RG turu. Olay metni gitmez."""
    statutes: list[dict] = []
    aym_hits: list[dict] = []
    rg_hits: list[dict] = []
    ptype = str(form.get("petitionType") or "")
    blob = " ".join(
        str(form.get(k) or "") for k in ("caseSummary", "userPrompt", "extraInstructions", "title", "petitionType")
    )

    if True:
        try:
            from bettersaul_mcp import mevzuat as _mz
            pulls = _mz.default_pulls(form)
        except Exception:
            pulls = []
        _research_note(f"Mevzuat: {len(pulls)} madde çekilecek.")
        for i, (kanun, madde) in enumerate(pulls, 1):
            raw = mcp_call("get_mevzuat_article", {"kanun": kanun, "madde": madde})
            try:
                data = json.loads(raw or "")
            except Exception:
                data = {}
            if isinstance(data, dict) and data.get("ok") and data.get("label"):
                statutes.append(
                    {
                        "ok": True,
                        "kanun": data.get("kanun") or kanun,
                        "madde": data.get("madde") or madde,
                        "label": data.get("label"),
                        "ozet": (data.get("ozet") or "")[:800],
                    }
                )
                _research_note(f"   → {data.get('label')} alındı")
            else:
                _research_note(f"   → {kanun} m. {madde} yok, uydurulmadı")

    want_aym = "İdare" in ptype
    if want_aym:
        seen_aym: set[str] = set()
        try:
            from bettersaul_mcp import anayasa as _aym
        except Exception:
            _aym = None
        for q, dtype in _aym_search_plan(form):
            if len(aym_hits) >= 4:
                break
            _research_note(f"AYM: MCP {dtype} ({q})")
            raw = mcp_call("search_anayasa", {"keywords": q, "decision_type": dtype})
            rows: list = []
            if _aym:
                try:
                    rows = _aym.helpful_list(raw, limit=2)
                except Exception:
                    rows = []
            if not rows:
                try:
                    payload = json.loads(raw or "")
                    rows = [r for r in (payload.get("kayitlar") or []) if isinstance(r, dict)][:2]
                except Exception:
                    rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("kunye") or row.get("url") or row.get("baslik") or "")[:120]
                if not key or key in seen_aym:
                    continue
                if row.get("url"):
                    doc = mcp_call("get_anayasa_document", {"url_or_id": row.get("url")})
                    try:
                        extra = json.loads(doc or "")
                    except Exception:
                        extra = {}
                    if isinstance(extra, dict) and extra.get("ok"):
                        if extra.get("ilke"):
                            row["ilke"] = extra["ilke"]
                        if extra.get("kunye"):
                            row["kunye"] = extra["kunye"]
                aym_hits.append(row)
                seen_aym.add(key)
                _research_note("   → AYM künye alındı: " + (row.get("kunye") or key)[:80])
        if not aym_hits:
            _research_note("   → AYM uygun künye yok; yazılmayacak")

    if True:
        q = _rg_query_for(form)
        _research_note(f"Resmî Gazete: {q}")
        raw = mcp_call("search_resmi_gazete", {"query": q})
        try:
            data = json.loads(raw or "")
        except Exception:
            data = {}
        recs = data.get("kayitlar") if isinstance(data, dict) else []
        if recs:
            first = recs[0] if isinstance(recs[0], dict) else {"baslik": str(recs[0])}
            rg_hits.append(first)
            _research_note("   → RG kayıt alındı")
        else:
            rg_hits.append({"sonuc": "taranamadı", "query": q})
            _research_note("   → RG taranamadı; dilekçede RG uydurulmayacak")
    return statutes, aym_hits, rg_hits


def seed_research(form: dict, tools: list[dict]) -> str:
    global _FETCHED_DOCS
    _FETCHED_DOCS = set()
    tools = list(tools or []) or _local_tool_list()
    by_name = {t["name"]: t for t in tools}
    for t in _local_tool_list():
        by_name.setdefault(t["name"], t)
    if by_name:
        _research_note(
            "BetterSaul MCP " + str(len(by_name)) + " araç: " + ", ".join(sorted(by_name))
        )
    used_q = _research_queries(form)
    digest: list[str] = []
    step = 0
    raw_all = ""

    def run(name: str, args: dict, label: str) -> str:
        nonlocal step
        step += 1
        _research_note(f"{step}. {label}")
        raw = mcp_call(name, args)
        brief = _brief_hits(raw)
        _research_note(f"   → {brief or 'kayıt yok'}")
        return raw

    deep = _find_tool(by_name, "search_corpus_deep") or _find_tool(by_name, "corpus", "deep")
    bedesten = _find_tool(by_name, "bedesten", "search") or _find_tool(by_name, "search_bedesten")
    emsal = _find_tool(by_name, "emsal", "search")
    ptype = str(form.get("petitionType") or "")
    courts = ["DANISTAYKARAR"] if "İdare" in ptype else ["YARGITAYKARARI"]

    def pass_search(phrases: list[str], pages: int, tur: int) -> str:
        nonlocal raw_all
        if not phrases:
            return ""
        _research_note(f"Tur {tur}/{_rounds(form)} — {len(phrases)} sorgu ile taranıyor…")
        chunk = ""
        if "İdare" in ptype and bedesten:
            take = phrases[:1] if tur > 1 else phrases[:2]
            for i, q in enumerate(take):
                piece = run(
                    bedesten,
                    {"phrase": q, "court_types": ["DANISTAYKARAR"]},
                    f"Tur {tur} Danıştay ({i + 1}/{len(take)}): {q}",
                )
                chunk += "\n" + piece
        elif deep:
            take = phrases[:2] if "İdare" in ptype else phrases[:3]
            chunk = run(
                deep,
                {"phrases": take, "pages": 1, "court_types": courts},
                f"Tur {tur} derin tarama: " + " | ".join(take),
            )
        elif bedesten:
            for i, q in enumerate(phrases):
                piece = run(bedesten, {"phrase": q, "court_types": courts}, f"Tur {tur} havuz ({i + 1}/{len(phrases)}): {q}")
                chunk += "\n" + piece
        elif emsal:
            chunk = run(emsal, {"keyword": phrases[0], "page_number": tur}, f"Tur {tur} emsal: {phrases[0]}")
        chunk = _strip_portal_junk(chunk)
        if chunk:
            digest.append(f"### İçtihat tur {tur}\n{chunk[:20000]}")
            raw_all += "\n" + chunk
        if re.search(r"eri[sş]im s[iı]n[iı]r", chunk or "", re.I):
            _research_note("Portal erişim sınırı; ek istek kesildi.")
        return chunk

    def remember() -> None:
        raw_digest = "\n".join(digest)
        rows_now = _bind_holdings_to_rows(
            _prefer_chamber_rows(ptype, _extract_cite_rows(raw_digest)),
            holdings,
        )
        cites_now = _prefer_chamber_cites(ptype, [_row_kunye(r) for r in rows_now] or _extract_cites(raw_digest))
        mem = dict(_CASE_MEMORY or {})
        mem.update(
            {
                "petitionType": ptype,
                "title": str(form.get("title") or ""),
                "facts": str(form.get("caseSummary") or "")[:2000],
                "requests": str(form.get("requests") or "")[:800],
                "issues": _issue_labels(form),
                "queries": _uniq_keep(used_q, 24),
                "cites": cites_now,
                "cite_rows": rows_now,
                "holdings": holdings,
                "statutes": statutes,
                "aym": aym_hits,
                "rg": rg_hits,
                "updated": time.strftime("%Y-%m-%d %H:%M"),
            }
        )
        _save_case_memory(mem)

    pass_search(used_q[:2], 1, 1)
    totals = re.findall(r'"havuz"\s*:\s*(\d+)', raw_all or "")
    grand = re.search(r'"taranan_havuz"\s*:\s*(\d+)', raw_all or "")
    if grand:
        _research_note(f"İlk tur havuz: {int(grand.group(1)):,}".replace(",", "."))
    elif totals:
        _research_note("Havuz: " + " + ".join(f"{int(x):,}".replace(",", ".") for x in totals[:4]))

    holdings: list[str] = []
    statutes: list = []
    aym_hits: list = []
    rg_hits: list = []
    remember()
    total = _rounds(form)
    for tur in range(1, total):
        nxt = _think_next_queries(form, "\n".join(digest), used_q, tur=tur + 1)
        if re.search(r"eri[sş]im s[iı]n[iı]r", raw_all or "", re.I):
            _research_note("Erişim sınırı: ek portal turu yok.")
            break
        if not nxt:
            pack = pack_for(ptype)
            nxt = [f"{st} emsal tur {tur + 1}" for st in (pack.get("statutes") or [])[:2]]
        if "İdare" in ptype:
            filtered = [
                q if "danıştay" in q.lower() else "Danıştay " + q
                for q in nxt
                if "iyuk" in q.lower() or "danıştay" in q.lower() or "idari" in q.lower()
            ]
            nxt = filtered or [q if "danıştay" in q.lower() else "Danıştay " + q for q in nxt[:2]]
        used_q.extend(nxt)
        pass_search(nxt[:2], 1, tur + 1)
        remember()
    holdings = _pull_holdings("\n".join(digest), by_name) if digest else []
    remember()
    statutes, aym_hits, rg_hits = _seed_official_sources(form, by_name)
    if statutes:
        digest.append("### Mevzuat\n" + json.dumps(statutes, ensure_ascii=False, indent=2))
    if aym_hits:
        digest.append("### AYM\n" + json.dumps(aym_hits[:4], ensure_ascii=False, indent=2))
    if rg_hits:
        digest.append("### Resmî Gazete\n" + json.dumps(rg_hits[:3], ensure_ascii=False, indent=2))
    remember()
    _llm_think_tour(form, total, "\n".join(digest), used_q)
    _research_note("Tarama bitti. Dilekçe şimdi CUDA ile yazılacak.")
    if holdings:
        digest.append("### Karar özetleri\n" + json.dumps([{"holding": h} for h in holdings], ensure_ascii=False, indent=2))
    raw_digest = "\n".join(digest)
    cite_rows = _bind_holdings_to_rows(
        _prefer_chamber_rows(str(form.get("petitionType") or ""), _extract_cite_rows(raw_digest)),
        holdings,
    )
    cites = _prefer_chamber_cites(
        str(form.get("petitionType") or ""),
        [_row_kunye(r) for r in cite_rows] or _extract_cites(raw_digest),
    )
    prev = dict(_CASE_MEMORY or {})
    mem = {
        "petitionType": str(form.get("petitionType") or ""),
        "title": str(form.get("title") or ""),
        "facts": str(form.get("caseSummary") or "")[:2000],
        "requests": str(form.get("requests") or "")[:800],
        "issues": _issue_labels(form),
        "queries": _uniq_keep(used_q, 24),
        "cites": cites,
        "cite_rows": cite_rows,
        "holdings": holdings,
        "statutes": statutes,
        "aym": aym_hits[:4],
        "rg": rg_hits,
        "think_notes": list(prev.get("think_notes") or []),
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }
    _save_case_memory(mem)
    if not digest:
        _research_note("MCP araçları bu oturumda listelenemedi.")
    else:
        _research_note("Çok turlu tarama bitti. İçtihat, madde ve resmi kayıt hafızaya alındı.")
        if cites:
            _research_note("Hafıza: " + " · ".join(cites[:5]))
        if statutes:
            _research_note("Maddeler: " + " · ".join(s.get("label") or "" for s in statutes if isinstance(s, dict))[:240])
        if aym_hits:
            _research_note("AYM: " + str((aym_hits[0] or {}).get("kunye") or "1 kayıt"))
        elif "İdare" in ptype:
            _research_note("AYM: künye yok — dilekçede uydurulmayacak.")
    return "\n\n".join(digest)


def _model_research_brief(research: str) -> str:
    parts: list[str] = []
    mem = _memory_brief(_CASE_MEMORY or None, 1400)
    if mem:
        parts.append(mem)
    for block in (research or "").split("### "):
        block = block.strip()
        if not block:
            continue
        title, _, body = block.partition("\n")
        if title.strip().lower().startswith("karar"):
            parts.append(f"- {title.strip()}: {body.strip()[:700]}")
        else:
            parts.append(f"- {title.strip()}: {_brief_hits(body, 5)}")
    return "\n".join(parts)[:3200] or "Kayıt özeti yok."


TOOL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def complete_llamacpp(messages: list[dict]) -> str:
    from llama_cpp import Llama  # type: ignore

    want_ctx = 8192 if _is_27b() else 16384
    have = int(getattr(complete_llamacpp, "_ctx", 0) or 0)
    if not hasattr(complete_llamacpp, "_llm") or have < want_ctx:
        emit("status", "Model yükleniyor…")
        complete_llamacpp._llm = Llama(  # type: ignore[attr-defined]
            model_path=MODEL,
            n_ctx=8192 if _is_27b() else 16384,
            n_gpu_layers=int(_gpu_layers()),
            verbose=False,
        )
        complete_llamacpp._ctx = 8192 if _is_27b() else 16384  # type: ignore[attr-defined]
    llm = complete_llamacpp._llm  # type: ignore[attr-defined]
    out = llm.create_chat_completion(messages=messages, temperature=0.3, max_tokens=4096)
    return out["choices"][0]["message"]["content"] or ""


def _win_short(path: str) -> str:
    if os.name != "nt" or not path:
        return path
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(520)
        n = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 520)
        if n:
            return buf.value or path
    except Exception:
        pass
    return path


def _decode_tr(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    n = len(data)
    while n > 0:
        try:
            return data[:n].decode("utf-8")
        except UnicodeDecodeError as exc:
            if exc.start < n - 4:
                break
            n = exc.start
    utf = data.decode("utf-8", errors="replace").rstrip("\ufffd")
    if utf.count("\ufffd") <= 1:
        return utf
    return data.decode("cp1254", errors="replace")


CHAT_PREDICT = 2048
CHAT_CTX = 16384
_SERVER_PORT = 8742
_server_proc: subprocess.Popen[bytes] | None = None
_server_log = None
_server_key = ""
PETITION_PREDICT = 4800
PETITION_CTX = 16384
MIN_PETITION_CHARS = 18000


def _has_gpu_backend() -> bool:
    llama_dir = Path(LLAMA).resolve().parent if LLAMA else Path()
    kind = ""
    marker = llama_dir / "backend.txt"
    if marker.is_file():
        kind = marker.read_text(encoding="utf-8", errors="ignore").strip().lower()
    names = {p.name.lower() for p in llama_dir.glob("*.dll")} if llama_dir.is_dir() else set()
    return kind in ("cuda", "vulkan", "hip", "gpu") or any(
        n.startswith("ggml-cuda") or n.startswith("ggml-vulkan") or n.startswith("cublas")
        for n in names
    )


def _nvidia_smi() -> str:
    candidates = [
        "nvidia-smi",
        str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"),
        r"C:\Windows\System32\nvidia-smi.exe",
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    ]
    for exe in candidates:
        if exe != "nvidia-smi" and not Path(exe).is_file():
            continue
        try:
            p = subprocess.run(
                [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if p.returncode == 0 and (p.stdout or "").strip():
                return p.stdout
        except Exception:
            continue
    return ""


def _vram_mb() -> int:
    text = _nvidia_smi()
    vals = []
    for line in text.splitlines():
        parts = [x.strip() for x in line.split(",")]
        token = (parts[-1] if parts else "").split()[0] if parts else ""
        if token:
            try:
                vals.append(int(float(token)))
            except ValueError:
                pass
    return max(vals) if vals else 0


def _model_tag() -> str:
    return ((os.environ.get("BS_MODEL_ID") or "") + " " + (MODEL or "")).lower()


def _is_qwen3() -> bool:
    t = _model_tag()
    return "qwen3" in t or "qwen35" in t or "qwen38" in t or "sungur" in t or "14b-tr" in t or "9b-tr" in t or "27b" in t


def _is_14b() -> bool:
    return "14b" in _model_tag() and "27b" not in _model_tag()


def _is_27b() -> bool:
    t = _model_tag()
    return "27b" in t or "qwen38" in t or "3.8" in t


def _is_9b() -> bool:
    t = _model_tag()
    return "9b" in t or "qwen35" in t or "3.5" in t


def _cpu_threads() -> int:
    n = os.cpu_count() or 4
    if _is_27b():
        return max(2, min(4, n - 4 if n >= 8 else n - 1))
    forced = os.environ.get("BS_CPU_THREADS")
    if forced and forced.strip().isdigit():
        return max(2, min(16, int(forced.strip())))
    reserve = 2 if n >= 8 else 1
    return max(2, min(8, n - reserve))


def _hw_local_ok() -> bool:
    return True


def _27b_ctx(n_ctx: int) -> int:
    return min(max(n_ctx, 4096), 4096)


def _27b_predict(n_predict: int) -> int:
    return min(max(n_predict, 256), 4096)


_THINK_MODE = True


def _think_flags() -> list[str]:
    if _is_27b():
        return ["--reasoning", "on", "--reasoning-budget", "128"]
    return ["--reasoning", "off", "--reasoning-budget", "0"]


def _speed_flags() -> list[str]:
    t = str(_cpu_threads())
    if _is_27b():
        # Küçük batch + flash-attn kapalı: 6 GB VRAM’de takılma/OOM azalır.
        # q8 V önbelleği flash-attn ister; kapalı olursa sunucu açılmaz.
        return [
            "-t",
            t,
            "-tb",
            t,
            "-b",
            "256",
            "-ub",
            "128",
            "-fa",
            "on",
            "-ctk",
            "q4_0",
            "-ctv",
            "q4_0",
        ]
    return ["-t", t, "-tb", t, "-b", "256", "-ub", "128", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0"]


def _gpu_layers() -> str:
    # C# bazen nvidia-smi zaman aşımında BS_NGL=0 basıyor. 0 = ölçüm yok, GPU kapatma değil.
    forced = (os.environ.get("BS_NGL") or "").strip()
    if not _has_gpu_backend():
        return "0"
    mb = _vram_mb()
    # 27B ~16.5 GB. RTX 4050 6 GB + q4 KV: 22 katman. nvidia-smi kaçarsa 6 GB varsay.
    if mb <= 0:
        mb = 6144
    if _is_27b():
        if mb <= 4096:
            want = 12
        elif mb <= 6144:
            want = 20
        elif mb <= 8192:
            want = 28
        else:
            want = 32
        return str(want)
    if forced not in ("", "0"):
        return forced
    large = _is_14b()
    mid = _is_9b()
    if mb <= 4096:
        return "4" if large else ("8" if mid else "12")
    if mb <= 6144:
        return "12" if large else ("20" if mid else "28")
    if mb <= 8192:
        return "12" if large else ("24" if mid else "32")
    return "20" if large else ("32" if mid else "40")


def _server_exe() -> str:
    p = Path(LLAMA).with_name("llama-server.exe")
    return str(p) if p.is_file() else ""


def _stop_server() -> None:
    global _server_proc, _server_key, _server_log
    proc = _server_proc
    logf = _server_log
    _server_proc = None
    _server_log = None
    _server_key = ""
    if proc is not None:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=4)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    if logf is not None:
        try:
            logf.close()
        except Exception:
            pass


def _server_health() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{_SERVER_PORT}/health", timeout=2) as r:
            return int(getattr(r, "status", 200)) < 500
    except Exception:
        return False


def _kill_port(port: int) -> None:
    if os.name != "nt":
        return
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, timeout=8)
    except Exception:
        return
    pids: set[int] = set()
    for line in out.splitlines():
        if f":{port} " not in line or "LISTENING" not in line.upper():
            continue
        pid = line.strip().split()[-1]
        if pid.isdigit() and int(pid) not in (0, os.getpid()):
            pids.add(int(pid))
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, timeout=8)
        except Exception:
            pass


def _gpu_used_line() -> str:
    text = ""
    for exe in (
        "nvidia-smi",
        str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"),
    ):
        try:
            p = subprocess.run(
                [exe, "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if p.returncode == 0 and (p.stdout or "").strip():
                text = p.stdout.strip().splitlines()[0]
                break
        except Exception:
            continue
    if not text:
        return ""
    parts = [x.strip() for x in text.split(",")]
    if len(parts) < 2:
        return ""
    return f"VRAM {parts[0]} MB · GPU %{parts[1]}"


def _ensure_server(n_ctx: int) -> bool:
    global _server_proc, _server_key, _server_log
    exe = _server_exe()
    if not exe or not MODEL:
        return False
    primary = _gpu_layers()
    want_key = f"{MODEL}|{primary}|{n_ctx}"
    if _server_proc is not None and _server_proc.poll() is None and _server_key == want_key and _server_health():
        return True
    if _server_health() and _server_key != want_key:
        emit("status", "Eski CPU/düşük-GPU sunucu kapatılıyor; CUDA ile yeniden açılacak…")
        _stop_server()
        _kill_port(_SERVER_PORT)
    ngl_opts = [primary]
    if primary not in ("16", "12", "8") and primary != "0":
        ngl_opts.extend(x for x in ("16", "12") if x not in ngl_opts and x != primary)
    cwd = str(Path(LLAMA).resolve().parent)
    env = os.environ.copy()
    env["PATH"] = cwd + os.pathsep + env.get("PATH", "")
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    env.setdefault("GGML_CUDA_NO_PINNED", "1")
    flags = 0x08000000 if os.name == "nt" else 0
    log_path = Path(os.environ.get("TEMP", cwd)) / "bs-llama-server.log"
    for ngl in ngl_opts:
        key = f"{MODEL}|{ngl}|{n_ctx}"
        if _server_proc is not None and _server_proc.poll() is None and _server_key == key and _server_health():
            return True
        _stop_server()
        cmd = [
            _win_short(exe),
            "-m",
            _win_short(MODEL),
            "--host",
            "127.0.0.1",
            "--port",
            str(_SERVER_PORT),
            "-c",
            str(n_ctx),
            "-ngl",
            ngl,
            "-np",
            "1",
            *_think_flags(),
            *_speed_flags(),
        ]
        emit("status", f"27B sunucu açılıyor (GPU {ngl} katman, RAM’e düşülmez)…")
        try:
            _server_log = open(log_path, "ab")
        except Exception:
            _server_log = subprocess.DEVNULL
        _server_proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=_server_log,
            stderr=_server_log,
            creationflags=flags,
        )
        _server_key = key
        started = time.time()
        while time.time() - started < 240:
            if _server_proc.poll() is not None:
                _server_key = ""
                emit("status", f"GPU {ngl} katman açılamadı, daha az katman deneniyor.")
                break
            if _server_health():
                used = _gpu_used_line()
                emit("status", f"27B hazır. GPU {ngl} katman" + (f" · {used}" if used else " kullanılıyor."))
                return True
            emit("status", f"27B GPU’ya yükleniyor… {int(time.time() - started)} sn")
            time.sleep(2)
        else:
            _stop_server()
    return False


def _build_prompt(messages: list[dict]) -> str:
    has_system = any((m.get("role") or "") == "system" for m in messages)
    prompt = "" if has_system else (PROMPT + "\n\n")
    last_i = max((i for i, m in enumerate(messages) if (m.get("role") or "") == "user"), default=-1)
    for i, m in enumerate(messages):
        role = m.get("role", "user")
        content = m.get("content", "")
        if _is_27b() and i == last_i and "/no_think" not in content and "/think" not in content:
            content = content.rstrip() + ("\n/think" if _THINK_MODE else "\n/no_think")
        prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    if _is_qwen3() and not (_is_27b() and _THINK_MODE):
        prompt += "<|im_start|>assistant\n<think>\n\n</think>\n"
    else:
        prompt += "<|im_start|>assistant\n"
    return prompt


def _chat_messages(messages: list[dict]) -> list[dict]:
    out: list[dict] = []
    last_i = max((i for i, m in enumerate(messages) if (m.get("role") or "") == "user"), default=-1)
    for i, m in enumerate(messages):
        role = m.get("role") or "user"
        content = str(m.get("content") or "")
        if _is_27b() and i == last_i and "/no_think" not in content and "/think" not in content:
            content = content.rstrip() + ("\n/think" if _THINK_MODE else "\n/no_think")
        out.append({"role": role, "content": content})
    return out


def complete_server(
    messages: list[dict],
    n_predict: int,
    live: bool,
    busy: str,
) -> str:
    import urllib.request

    chat = _chat_messages(messages)
    payload = json.dumps(
        {
            "messages": chat,
            "max_tokens": n_predict,
            "temperature": 0.3,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": bool(_is_27b() and _THINK_MODE)},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{_SERVER_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    streamer = LiveOut(live)
    chunks: list[str] = []
    last_beat = time.time()
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line in ("[DONE]", "data: [DONE]"):
                break
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = obj.get("content") or obj.get("token") or ""
            if not piece:
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content") or ""
                    if not piece:
                        piece = (choices[0].get("message") or {}).get("content") or ""
            if not piece:
                delta = obj.get("delta")
                if isinstance(delta, dict):
                    piece = delta.get("content") or ""
            if piece:
                chunks.append(piece)
                streamer.feed(piece)
            now = time.time()
            if now - last_beat >= 7:
                last_beat = now
                emit("status", (busy or "İşleniyor") + " — sürüyor, kilitlenmedi.")
            if obj.get("stop") or obj.get("stopped_eos"):
                break
            choices = obj.get("choices") or []
            if choices and choices[0].get("finish_reason"):
                break
    streamer.flush()
    text = _usable_text("".join(chunks)) or _clean_llama_out("".join(chunks))
    if not text:
        raise RuntimeError(busy + " boş döndü.")
    return text.strip()


def _run_llama(
    cmd: list[str],
    cwd: str,
    env: dict,
    live: LiveOut | None = None,
    busy: str = "Yanıt üretiliyor…",
) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        bufsize=0,
    )
    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []
    decoded_n = 0
    raw = bytearray()

    def _pump_err() -> None:
        try:
            while True:
                block = proc.stderr.read(4096) if proc.stderr else b""
                if not block:
                    break
                err_chunks.append(block)
        except Exception:
            pass

    def _pump_out() -> None:
        nonlocal decoded_n
        try:
            while True:
                block = proc.stdout.read(64) if proc.stdout else b""
                if not block:
                    break
                out_chunks.append(block)
                raw.extend(block)
                text = _decode_tr(bytes(raw))
                if live and len(text) > decoded_n:
                    live.feed(text[decoded_n:])
                    decoded_n = len(text)
        except Exception:
            pass

    threading.Thread(target=_pump_out, daemon=True).start()
    threading.Thread(target=_pump_err, daemon=True).start()
    started = time.time()
    last_out = started
    last_beat = started
    last_bytes = 0
    while proc.poll() is None:
        now = time.time()
        got = sum(len(x) for x in out_chunks)
        if got > last_bytes:
            last_out = now
            last_bytes = got
        if now - last_beat >= 12:
            last_beat = now
            elapsed = int(now - started)
            if got:
                emit("status", f"{busy} ({elapsed} sn)")
            else:
                emit("status", f"{busy} — bekleniyor ({elapsed} sn)")
        streamed = bool(live and (live.emitted or "").strip())
        idle = now - last_out
        load_limit = 180 if _is_27b() else 75
        if got == 0 and now - started > load_limit:
            proc.kill()
            try:
                proc.wait(timeout=8)
            except Exception:
                pass
            raise RuntimeError("GPU yanıt vermedi (takılma). Daha az katman deneniyor.")
        if streamed and idle > (40 if _is_27b() else 12):
            proc.kill()
            try:
                proc.wait(timeout=8)
            except Exception:
                pass
            break
        if idle > 120 and got > 0:
            proc.kill()
            try:
                proc.wait(timeout=8)
            except Exception:
                pass
            break
        if now - started > 900:
            proc.kill()
            try:
                proc.wait(timeout=8)
            except Exception:
                pass
            break
        time.sleep(0.05)
    try:
        proc.wait(timeout=2)
    except Exception:
        pass
    if live:
        live.flush()
    stdout = b"".join(out_chunks)
    stderr = b"".join(err_chunks)
    code = proc.returncode if proc.returncode is not None else 1
    return subprocess.CompletedProcess(cmd, code, stdout, stderr)


def complete_cli(
    messages: list[dict],
    n_predict: int = CHAT_PREDICT,
    n_ctx: int = CHAT_CTX,
    live: bool = False,
    busy: str = "Yanıt üretiliyor…",
) -> str:
    if not LLAMA or not Path(LLAMA).is_file():
        raise RuntimeError("llama-cli bulunamadı. Kurulumu tekrar çalıştırın.")
    if not MODEL or not Path(MODEL).is_file():
        raise RuntimeError("Model dosyası yok. Kurulumu çalıştırın.")
    prompt = _build_prompt(messages)
    cwd = str(Path(LLAMA).resolve().parent)
    env = os.environ.copy()
    env["PATH"] = cwd + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    tmp = Path(os.environ.get("TEMP", cwd)) / f"bs-prompt-{os.getpid()}.txt"
    tmp.write_bytes(prompt.encode("utf-8"))
    if _is_27b():
        n_ctx = _27b_ctx(n_ctx)
        n_predict = _27b_predict(n_predict)
    layers = _gpu_layers()
    attempts = [layers]
    if _is_27b():
        for n in ("12", "8"):
            if n != layers:
                attempts.append(n)
    elif layers != "0":
        if layers != "12":
            attempts.append("12")

    def _run(ngl: str) -> tuple[subprocess.CompletedProcess[bytes], LiveOut]:
        streamer = LiveOut(live)
        cmd = [
            _win_short(LLAMA),
            "-m",
            _win_short(MODEL),
            "-f",
            _win_short(str(tmp)),
            "-n",
            str(n_predict),
            "--temp",
            "0.3",
            "-ngl",
            ngl,
            "-c",
            str(n_ctx),
            "--simple-io",
            "--single-turn",
            "--no-jinja",
            "--no-display-prompt",
            "--log-disable",
            "--no-warmup",
            *_think_flags(),
            *_speed_flags(),
        ]
        return _run_llama(cmd, cwd, env, live=streamer, busy=busy), streamer

    proc: subprocess.CompletedProcess[bytes] | None = None
    last_err = ""
    accepted = ""
    try:
        for ngl in attempts:
            if ngl != "0":
                emit("status", f"GPU kullanılıyor ({ngl} katman)…")
            else:
                emit("status", "İşlemciye düşülüyor…")
            try:
                proc, streamer = _run(ngl)
            except Exception as exc:
                last_err = str(exc)
                emit("status", last_err)
                continue
            cleaned = _usable_text(_decode_tr(proc.stdout or b""))
            if not cleaned:
                cleaned = _usable_text(_decode_tr(proc.stderr or b""))
            if not cleaned:
                cleaned = _usable_text(streamer.emitted)
            if cleaned:
                accepted = cleaned
                if proc.returncode != 0:
                    emit("status", "Model yanıt verdi; kapanış uyarısı yok sayılıyor.")
                proc = subprocess.CompletedProcess(proc.args, 0, accepted.encode("utf-8"), proc.stderr)
                break
            last_err = _decode_tr(proc.stderr or proc.stdout or b"").strip() or f"llama-cli {proc.returncode}"
            emit("status", "Logo/banner atlandı; yedek deneniyor…")
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    if not accepted:
        raise RuntimeError((last_err or "llama-cli hata")[-800:])
    return accepted.strip()


def generate(
    messages: list[dict],
    n_predict: int = CHAT_PREDICT,
    n_ctx: int = CHAT_CTX,
    live: bool = False,
    busy: str = "Yanıt üretiliyor…",
    think: bool | None = None,
    allow_cli: bool = True,
) -> str:
    if not _model_available():
        raise RuntimeError("Dilekçe ve sohbet Claude / ChatGPT / Gemini Desktop + BetterSaul MCP ile yapılır.")
    global _THINK_MODE
    prev = _THINK_MODE
    if think is not None:
        _THINK_MODE = bool(think)
    try:
        if _is_27b():
            n_ctx = _27b_ctx(n_ctx)
            n_predict = _27b_predict(n_predict)
            try:
                if _ensure_server(n_ctx):
                    return complete_server(messages, n_predict=n_predict, live=live, busy=busy)
            except Exception as exc:
                emit("status", f"27B sunucu atlandı ({exc}).")
                if not allow_cli:
                    raise
                emit("status", "Tek seferlik motor deneniyor.")
            if not allow_cli:
                raise RuntimeError("27B sunucusu kapalı; model yeniden yüklenmeyecek.")
            return complete_cli(messages, n_predict=n_predict, n_ctx=n_ctx, live=live, busy=busy)
        try:
            import llama_cpp  # noqa: F401
        except Exception:
            return complete_cli(messages, n_predict=n_predict, n_ctx=n_ctx, live=live, busy=busy)
        try:
            return complete_llamacpp(messages)
        except Exception as exc:
            emit("status", f"llama-cpp-python atlandı ({exc}). llama-cli kullanılıyor.")
            return complete_cli(messages, n_predict=n_predict, n_ctx=n_ctx, live=live, busy=busy)
    finally:
        _THINK_MODE = prev


def _hw_refuse() -> str:
    if _hw_local_ok():
        return ""
    return (
        "Bu bilgisayar yerel dil modeli için uygun değil. "
        "BetterSaul MCP’yi Claude Desktop veya Cursor’a bağlayın; "
        "sohbet ve dilekçeyi orada yürütün."
    )


def run_agent(
    user_messages: list[dict],
    system_prompt: str | None = None,
    n_predict: int = CHAT_PREDICT,
    n_ctx: int = CHAT_CTX,
    min_chars: int = 0,
    form: dict | None = None,
    research: str | None = None,
) -> str:
    blocked = _hw_refuse()
    if blocked:
        emit("status", blocked)
        return blocked
    if form is None and not _model_available():
        msg = (
            "Sohbet kaldırıldı. Dilekçe BetterSaul’da; araştırma Claude Desktop + BetterSaul MCP ile yürür. "
            "Claude açık kalsın; iki uygulama eşzamanlı çalışır."
        )
        emit("status", msg)
        return msg
    sys_msg = system_prompt or PROMPT
    if form is not None:
        if research is None:
            tools = wait_mcp_tools(20)
            if tools:
                emit("status", "Resmî kaynaklar taranıyor (BetterSaul MCP)…")
                research = seed_research(form, tools)
            else:
                research = ""
        if (research or "").strip():
            sys_msg += "\n\n## MCP özet (uydurma yasak)\n" + _model_research_brief(research)
            sys_msg += (
                "\n\nAraştırma özeti yukarıda. Şimdi makam, taraflar, konu, açıklamalar, "
                "deliller, hukuki nedenler ve sonuç-istem sırasıyla eksiksiz dilekçe yaz. "
                "Bölümler arasında boş satır bırak. İçtihat ve RG yalnızca gerçek kayıtlardan. "
                "Uydurma yasak. Türkçe muhakeme et; günlük dili resmî dile çevir."
            )
        else:
            emit("status", "MCP bağlı değil; içtihat ve RG uydurulmayacak.")
            sys_msg += (
                "\n\nMCP yok. Karar numarası, RG sayısı, mahkeme içtihadı UYDURMA. "
                "[KAYNAK YOK] yaz. tool_call yazma."
            )
    else:
        emit("status", "1/4 Anlam çözülüyor…")
        emit("research", "1/4 Kullanıcı metni okundu; günlük dil hukuki anlama çevrilecek.")
        last_user = ""
        for m in reversed(user_messages or []):
            if (m.get("role") or "") == "user":
                last_user = str(m.get("content") or "")
                break
        tools = mcp_tools() or _local_tool_list()
        if tools:
            names = ", ".join(t["name"] for t in tools)
            sys_msg += (
                "\n\nBetterSaul MCP bu oturumda açık (" + str(len(tools)) + " araç): " + names
                + "\nMotor bunları kendisi çağırır. «Araç setinde görünmüyor» / "
                "«önceki oturumda kullanabiliyordum» yazma."
            )
        if tools and _looks_legal_query(last_user):
            emit("status", "2/4 İçtihat taranıyor (BetterSaul MCP)…")
            emit("research", "2/4 Hukuki niteleme ve ilgili daire taraması.")
            fake = {
                "petitionType": _guess_ptype(last_user),
                "caseSummary": last_user[:2000],
                "requests": "",
                "title": "",
            }
            research = seed_research(fake, tools)
            if (research or "").strip():
                sys_msg += "\n\n## MCP özet (uydurma yasak)\n" + _model_research_brief(research)
        mem = _memory_brief(limit=1600)
        if mem:
            sys_msg += (
                "\n\n## Dava hafızası (BetterSaul MCP taraması)\n"
                "İçtihat uydurma. Yalnızca aşağıdaki gerçek kayıtları kullan.\n"
                + mem
            )
    history = [{"role": "system", "content": sys_msg}] + user_messages
    busy = "Dilekçe üretiliyor…" if form is not None else "3/4 Derin muhakeme ile yanıt yazılıyor…"
    final = ""
    if form is None:
        emit("status", "3/4 Derin muhakeme ile yanıt yazılıyor…")
        emit("research", "3/4 27B düşünme açık; tokenler aktıkça durum satırı güncellenir.")
    for turn in range(2 if _is_27b() else MAX_TURNS):
        emit("status", busy if form is None else f"Model düşünüyor ({turn + 1}/{MAX_TURNS})…")
        text = generate(history, n_predict=n_predict, n_ctx=n_ctx, live=True, busy=busy, think=True if form is None else None)
        text = _usable_text(text) or _clean_llama_out(text)
        m = TOOL_RE.search(text or "")
        if not text.strip() and turn < MAX_TURNS - 1:
            emit("status", "Gereksiz model çıktısı atıldı; yeniden yazılıyor…")
            continue
        if not m:
            final = TOOL_RE.sub("", text or "").strip()
            break
        try:
            spec = json.loads(m.group(1))
        except json.JSONDecodeError:
            final = text
            break
        name = str(spec.get("name", ""))
        args = spec.get("arguments") or {}
        emit("status", f"BetterSaul MCP: {name}")
        result = mcp_call(name, args if isinstance(args, dict) else {})
        history.append({"role": "assistant", "content": text})
        history.append({"role": "user", "content": f"Araç sonucu ({name}):\n{result}"})
    extra_round = 0
    section_hints = (
        "Açıklamalarda olayı kronolojik ve akıcı yaz; her paragrafın altına Delil/dayanak satırı koyma.",
        "Hangi maddeye dayanıldığını ve davanın neden açıldığını metnin içinde anlat; bir emsali akışa göm.",
        "Sonuç ve istemi maddeli yaz; EK listesini tamamla. İçtihat listesi yapıştırma.",
    )
    while min_chars and len(final) < min_chars and extra_round < 6:
        hint = section_hints[min(extra_round, len(section_hints) - 1)]
        extra_round += 1
        emit("status", f"Dilekçe kitap uzunluğuna dolduruluyor ({len(final)}/{min_chars} karakter)…")
        history.append({"role": "assistant", "content": final[-2500:]})
        history.append(
            {
                "role": "user",
                "content": (
                    f"Dilekçe henüz 5 A4 değil ({len(final)} karakter). "
                    f"{hint} Aynı dilekçeyi silmeden devam ettir. "
                    "Yalnızca devam metnini yaz; bölümler ve vakıalar arasında boş satır bırak. "
                    "İçtihat uydurma."
                ),
            }
        )
        extra = TOOL_RE.sub("", generate(history, n_predict=2400, n_ctx=n_ctx, live=True, busy=busy)).strip()
        extra = _usable_text(extra) or _clean_llama_out(extra)
        if not extra or _is_banner(extra):
            break
        final = (final.rstrip() + "\n\n" + extra).strip()
    if form is not None:
        final = _ensure_lawyer(final, form)
        return final
    final = _polish_tr(_fix_word_spacing(final or ""))
    if final and not _looks_like_petition(final):
        try:
            final = _reason_tr_pass(final)
        except Exception:
            pass
    return final


_USER_PROMPT_RE = re.compile(r"(?s)^\s*KULLANICI_PROMPT:\s*\n(.*?)\n---\s*\n?")


def _take_user_prompt(form: dict) -> str:
    f = form if isinstance(form, dict) else {}
    up = str(f.get("userPrompt") or f.get("petitionPrompt") or "").strip()
    extra = str(f.get("extraInstructions") or "")
    m = _USER_PROMPT_RE.match(extra)
    if m:
        if not up:
            up = (m.group(1) or "").strip()
        f["extraInstructions"] = extra[m.end() :].strip()
    extra2 = str(f.get("extraInstructions") or "")
    flag = re.search(r"WEB_FLUENCY\s*:\s*([01])", extra2, re.I)
    if flag:
        f["webFluency"] = flag.group(1) == "1"
        f["extraInstructions"] = re.sub(r"\n?WEB_FLUENCY\s*:\s*[01]\s*", "\n", extra2).strip()
    elif "webFluency" not in f:
        f["webFluency"] = True
    f["userPrompt"] = up
    return up


def _source_blob(form: dict) -> str:
    return "\n".join(
        str(form.get(k) or "")
        for k in ("userPrompt", "caseSummary", "extraInstructions", "parties", "title", "requests")
    )


def _intent_blob(form: dict) -> str:
    try:
        from bettersaul_mcp.quality import intent_text

        return intent_text(form or {})
    except Exception:
        return "\n".join(
            str((form or {}).get(k) or "")
            for k in ("requests", "extraInstructions", "caseSummary", "userPrompt")
        )


def _form_claims(form: dict) -> set[str]:
    try:
        from bettersaul_mcp.quality import form_claims

        return form_claims(form or {})
    except Exception:
        return {"ucret"} if is_labor(form) else set()


def _party_blank(s: str) -> bool:
    t = (s or "").strip()
    if not t or _is_placeholder(t):
        return True
    compact = re.sub(r"[\[\]\.…\s:,/\-]", "", t)
    if len(compact) < 4:
        return True
    fold = _fold_tr(t)
    if re.search(r"ad soyad|teblig adresi|\[ad|daval[iy] idare:\s*\[", fold):
        return True
    if t.count(".") >= 10 or "........................" in t:
        return True
    return False


def _clean_person_name(name: str) -> str:
    t = re.sub(r"\s+", " ", (name or "")).strip(" ,.;:")
    if not t or len(t.split()) < 2:
        return ""
    if re.search(r"(?i)^(ad|soyad|ad\s*soyad|kimlik|adres|tckn)\b", t):
        return ""
    bad = re.compile(
        r"(?i)\b(mahkemesi|dairesi|bakanl[ıi][gğ][ıi]|m[uü]d[uü]rl[uü][gğ][uü]|"
        r"kanunu|karar[ıi]|dilek[cç]e|asliye|ceza|idare|dan[ıi][sş]tay|"
        r"yarg[ıi]tay|hakaret|kasten|g[uü]venlik|atama|uygunluk|m[uü]vekkil|"
        r"davac[ıi]|daval[ıi]|avukat|baro|adalet|genel|limited|ltd|şti|anonim|"
        r"soyad|kimlik|adres)\b"
    )
    if bad.search(t):
        parts = [w for w in t.split() if not bad.search(w) and _fold_tr(w) not in {"ad", "soyad"}]
        t = " ".join(parts)
        if len(t.split()) < 2:
            return ""
    if re.match(r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){1,2}$", t):
        return t
    if re.match(
        r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ]{2,}){1,2}$",
        t,
    ):
        return t
    if re.match(r"^[A-ZÇĞİÖŞÜ]{2,}(?:\s+[A-ZÇĞİÖŞÜ]{2,}){1,2}$", t):
        return t.title()
    return ""


def _extract_person_names(blob: str) -> list[str]:
    out: list[str] = []
    pats = (
        r"(?i)ad\s*soyad\s*[:：]\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        r"(?i)(?:m[uü]vekkil(?:im)?|davac[ıi])\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        r"\b([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})\s+hakk[ıi]nda",
        r"(?i)davac[ıi]\s*[:：]\s*([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
        r"(?i)daval[ıi]\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü]+){1,2})",
    )
    for pat in pats:
        for m in re.finditer(pat, blob or ""):
            name = _clean_person_name(m.group(1))
            if name and not re.search(r"(?i)^ad\s*soyad$", name) and name not in out:
                out.append(name)
    return out


def _extract_admin_name(blob: str) -> str:
    t = blob or ""
    pairs = (
        (
            r"Adalet Bakanlığı.{0,40}Ceza ve Tevkifevleri Genel Müdürlüğü|"
            r"Ceza ve Tevkifevleri Genel Müdürlüğü",
            "Adalet Bakanlığı (Ceza ve Tevkifevleri Genel Müdürlüğü)",
        ),
        (r"Emniyet Genel Müdürlüğü", "Emniyet Genel Müdürlüğü"),
        (r"Adalet Bakanlığı", "Adalet Bakanlığı"),
        (r"\bCTE\b", "Adalet Bakanlığı (Ceza ve Tevkifevleri Genel Müdürlüğü)"),
        (r"Aile ve Sosyal Hizmetler Bakanlığı", "Aile ve Sosyal Hizmetler Bakanlığı"),
        (r"İçişleri Bakanlığı", "İçişleri Bakanlığı"),
        (r"Mill[îi] Eğitim Bakanlığı", "Millî Eğitim Bakanlığı"),
        (r"Sağlık Bakanlığı", "Sağlık Bakanlığı"),
        (r"Çalışma ve Sosyal G[uü]venlik Bakanlığı", "Çalışma ve Sosyal Güvenlik Bakanlığı"),
        (r"Hazine ve Maliye Bakanlığı", "Hazine ve Maliye Bakanlığı"),
        (r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?\s+Büyükşehir Belediyesi)", ""),
        (r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+Belediyesi)", ""),
        (r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+Valili[gğ]i)", ""),
        (r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[ÜU]niversitesi)", ""),
    )
    for pat, fixed in pairs:
        m = re.search(pat, t, re.I)
        if not m:
            continue
        return fixed or re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(
        r"([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9.& ]{1,48}?(?:Ltd\.?\s*Şti\.?|Limited Şirketi|A\.Ş\.))",
        t,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def _labeled_party_value(blob: str, kind: str) -> str:
    if kind == "davaci":
        pat = r"(?im)^DAVAC[Iİ](?!\s+VEK)(?:\s*[:：]\s*|\s+)(.+)$"
        inline = r"(?i)\bdavac[ıi]\s*[:：]\s*(.+)"
    else:
        pat = r"(?im)^DAVAL[Iİ](?:\s+İDARE)?(?:\s*[:：]\s*|\s+)(.+)$"
        inline = r"(?i)\bdaval[ıi](?:\s+idare)?\s*[:：]\s*(.+)"
    m = re.search(pat, blob or "") or re.search(inline, blob or "")
    if not m:
        return ""
    val = m.group(1).strip()
    val = re.split(r"(?im)\n(?=DAVAC[Iİ]|DAVAL[Iİ]|VEK[İI]L|KONU|AÇIKLAM)", val)[0].strip()
    val = re.split(r"(?i)\b(?:DAVAC[Iİ](?!\s+VEK)|DAVAL[Iİ]|VEK[İI]L[İI]?)\s*[:：]", val)[0].strip()
    if _party_blank(val):
        return ""
    return val


def _find_tckn(blob: str, near: str = "") -> str:
    if near:
        i = (blob or "").lower().find(near.lower())
        if i >= 0:
            window = blob[max(0, i - 80) : i + len(near) + 180]
            m = re.search(r"\b([1-9]\d{10})\b", window)
            if m:
                return m.group(1)
    m = re.search(r"(?i)(?:T\.C\.\s*Kimlik No|TCKN)\s*[:：]?\s*([1-9]\d{10})\b", blob or "")
    return m.group(1) if m else ""


def _find_addr(blob: str, near: str = "") -> str:
    m = re.search(r"(?im)^Adres\s*[:：]\s*(.+)$", blob or "")
    if m:
        line = m.group(1).strip()
        if line and not _party_blank(line) and not re.search(r"(?i)^teblig adresi", line):
            return line
    if near:
        i = (blob or "").lower().find(near.lower())
        if i >= 0:
            window = blob[i : i + 240]
            m = re.search(
                r"((?:[A-ZÇĞİÖŞÜa-zçğıöşü0-9./\s]+(?:Mah\.|Cad\.|Sok\.|Sk\.)[^,\n]{0,48})(?:,\s*[^,\n]+){0,3})",
                window,
            )
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip(" ,;")
    return ""


def _davali_from_prompt(blob: str) -> str:
    labeled = _labeled_party_value(blob, "davali")
    if labeled:
        name = _short_admin(_strip_party_label(labeled))
        name = re.sub(r"\b\d{10,13}\b", "", name or "").strip(" ,;")
        name = re.split(r"(?i)\b(?:TCKN|T\.C\. Kimlik|Adres)\b", name)[0].strip(" ,;")
        if name and not _party_blank(name):
            return name
    return _extract_admin_name(blob)


def _extract_idare_act(form: dict) -> str:
    blob = _source_blob(form)
    m = re.search(
        r"(\d{1,2}[./]\d{1,2}[./]\d{4})\s*tarihli\s+[\"“”']?([^\"“”'\n,]{6,70}?)[\"“”']?"
        r"(?:\s+başlıklı)?\s+(?:karar[ıi]?|i[sş]lem)",
        blob,
        re.I,
    )
    if m:
        title = re.sub(r"\s+", " ", m.group(2)).strip(" .;:")
        if re.search(r"(?i)atama uygunluk", title) and not re.search(r"(?i)karar", title):
            title = "Atama Uygunluk Kararı"
        return f"{m.group(1)} tarihli {title} başlıklı işlemin"
    if re.search(r"atama uygunluk", blob, re.I):
        d = re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{4}).{0,48}atama uygunluk|atama uygunluk.{0,24}(\d{1,2}[./]\d{1,2}[./]\d{4})", blob, re.I)
        day = (d.group(1) or d.group(2)) if d else ""
        return f"{(day + ' tarihli ') if day else ''}Atama Uygunluk Kararı başlıklı işlemin"
    return ""


def _hydrate_parties(form: dict) -> None:
    blob = _source_blob(form)
    ptype = str(form.get("petitionType") or "")
    davaci, davali = _split_party_blocks(_field(form, "parties"))
    people = _extract_person_names(blob)
    prompt_davaci = _labeled_party_value(blob, "davaci")
    prompt_davali = _davali_from_prompt(blob)
    admin = prompt_davali or _extract_admin_name(blob)
    if _party_blank(davaci):
        if prompt_davaci:
            bit = _strip_party_label(prompt_davaci).split(",")[0].strip()
            davaci = _clean_person_name(bit) or bit
        if _party_blank(davaci) and people:
            davaci = people[0]
    if _party_blank(davali):
        if prompt_davali:
            davali = prompt_davali
        elif "İdare" in ptype or admin:
            davali = admin or davali
        elif len(people) > 1:
            davali = people[1]
    bits = []
    if davaci and not _party_blank(davaci):
        bits.append(f"DAVACI: {davaci}")
    if davali and not _party_blank(davali):
        bits.append(f"DAVALI: {davali}")
    if bits:
        form["parties"] = "\n".join(bits)
    act = _extract_idare_act(form)
    if act:
        form["_idare_act"] = act


def _hydrate_form_facts(form: dict) -> None:
    """Prompt’taki isim/olay boş taraf ve özet kutularına işlenir; prompt silinmez."""
    _hydrate_parties(form)
    summary = str(form.get("caseSummary") or "").strip()
    if summary and not _is_placeholder(summary) and len(summary) >= 40:
        return
    up = str(form.get("userPrompt") or "")
    extra = str(form.get("extraInstructions") or "")
    sents = _all_fact_sentences(up, extra)
    if sents:
        form["caseSummary"] = " ".join(sents)[:2200]
        return
    blob = f"{up} {extra}"
    keys: list[str] = []
    for pat, label in (
        (r"güvenlik soruştur", "güvenlik soruşturması olumsuz"),
        (r"7315", "7315 sayılı Kanun"),
        (r"\bHAGB\b|hükmün açıklanmasının geri", "HAGB"),
        (r"infaz ve koruma", "infaz ve koruma memuru"),
        (r"atama uygunluk", "atama uygunluk kararı"),
        (r"değerlendirme komisyon", "değerlendirme komisyonu"),
        (r"kasten yaralama", "basit kasten yaralama"),
    ):
        if re.search(pat, blob, re.I) and label not in keys:
            keys.append(label)
    if keys:
        form["caseSummary"] = " ".join(keys)


def _prompt_search_hint(up: str) -> str:
    if _is_prompt_block(up):
        return ""
    if re.search(r"(?i)^rolün|görev:\s*aşağıda|kıdemli bir hukuk", up or ""):
        return ""
    t = re.sub(r"(?i)\b(incele|araştır|araştırın|bul|cevapla|yaz|listele)\b", " ", up or "")
    t = re.sub(r"\s+", " ", t).strip(" .;,-")
    if len(t) > 160 or _is_prompt_block(t):
        return ""
    return t[:140]


def petition_messages(form: dict) -> list[dict]:
    _take_user_prompt(form)
    parts = [
        f"Dilekçe türü: {form.get('petitionType','')}",
        f"Dilekçe başlığı: {form.get('title','')}",
    ]
    if form.get("court"):
        parts.append(f"Mahkeme: {form.get('court')}")
    if form.get("parties"):
        parts.append(f"Taraf bilgileri:\n{form.get('parties')}")
    parts.append(f"Olay özeti ve dava bilgileri:\n{form.get('caseSummary','')}")
    if form.get("requests"):
        parts.append(f"Talepler:\n{form.get('requests')}")
    if form.get("_case"):
        try:
            from bettersaul_mcp.motor.stages import case_brief

            parts.append("Yapılandırılmış dosya:\n" + case_brief(form["_case"]))
        except Exception:
            pass
    elif form.get("userPrompt") and not _is_prompt_block(str(form.get("userPrompt") or "")):
        parts.append("Olay notu:\n" + str(form.get("userPrompt"))[:1200])
    if form.get("extraInstructions"):
        parts.append(f"Ek talimatlar:\n{form.get('extraInstructions')}")
    if form.get("templateName"):
        hint = (form.get("templateHint") or "").strip()
    parts.append(
            "Seçilen şablon:\n"
            + str(form["templateName"])
            + (("\n" + hint) if hint else "")
        )
    lawyer = _lawyer_lines(form)
    if lawyer:
        parts.append(
            "VEKİL / AVUKAT (VEKİLİ satırına ve imza bloğuna aynen yaz):\n" + "\n".join(lawyer)
        )
    pack = pack_for(str(form.get("petitionType") or ""))
    vakia = "\n".join(f"{i}. {v}" for i, v in enumerate(pack.get("vakia") or [], 1))
    delil = "\n".join(f"{i}. {e}" for i, e in enumerate(pack.get("evidence") or [], 1))
    dayanak = labor_hukuk(form) if is_labor(form) else ", ".join(pack.get("statutes") or [])
    parts.append(
        "AÇIKLAMALAR numaralı vakıa (1- 2- 3-) olsun. Her vakıanın altında ZORUNLU üç satır:\n"
        "Delil : …\nHukuki dayanak : …\nHukuki sonuç : …\n"
        f"Olası vakıa başlıkları:\n{vakia}\n\n"
        f"Deliller (HUKUKİ SEBEPLER’den sonra bir kez):\n{delil}\n\n"
        f"Dayanak maddeleri (HUKUKİ SEBEPLER ve vakıa satırlarında): {dayanak}\n\n"
        "ZORUNLU BİÇİM: T.C. / mahkeme / birleşik baner / DAVA DİLEKÇESİ / tür satırı / "
        "DAVACI / VEKİLİ / DAVALI / KONU / AÇIKLAMALAR / HUKUKİ SEBEPLER / "
        "DELİLLER / SONUÇ VE İSTEM / imza / EKLER.\n"
        "Gövde: müvekkil. T.C. ve DAVA DİLEKÇESİ yaz.\n"
        "KONU ve ilk açıklamada hangi maddeye dayanıldığı ve davanın neden açıldığı yazılsın. "
        "Taranan tek bir emsal kararı, açıklamaların ahengini bozmadan metne gömülsün; "
        "alt alta esas/karar listesi yazılmasın. İçtihat uydurma.\n"
        "Kelimeler arasında boşluk bırak. Bitişik yazma. tool_call yazma. "
        "Yanıtın yalnızca dilekçe metni olsun."
    )
    return [{"role": "user", "content": "\n\n".join(parts)}]


_ILLER = (
    "Adana Adıyaman Afyonkarahisar Ağrı Amasya Ankara Antalya Artvin Aydın "
    "Balıkesir Bilecik Bingöl Bitlis Bolu Burdur Bursa Çanakkale Çankırı "
    "Çorum Denizli Diyarbakır Edirne Elazığ Erzincan Erzurum Eskişehir "
    "Gaziantep Giresun Gümüşhane Hakkari Hatay Isparta Mersin İstanbul "
    "İzmir Kars Kastamonu Kayseri Kırklareli Kırşehir Kocaeli Konya Kütahya "
    "Malatya Manisa Kahramanmaraş Mardin Muğla Muş Nevşehir Niğde Ordu "
    "Rize Sakarya Samsun Siirt Sinop Sivas Tekirdağ Tokat Trabzon Tunceli "
    "Şanlıurfa Uşak Van Yozgat Zonguldak Aksaray Bayburt Karaman Kırıkkale "
    "Batman Şırnak Bartın Ardahan Iğdır Yalova Karabük Kilis Osmaniye Düzce"
).split()


def _party_heading(kind: str) -> re.Pattern[str]:
    if kind == "davaci":
        return re.compile(r"(?im)^DAVAC[Iİ](?!\s+VEK)\s*[:：]?\s*", re.M)
    return re.compile(r"(?im)^DAVAL[Iİ]\s*[:：]?\s*", re.M)


def _value_from_party_block(block: str) -> str:
    t = (block or "").strip()
    if not t:
        return ""
    m = re.search(r"(?im)^\s*Ad\s*Soyad\s*[:：]\s*(.+)$", t)
    if m and not _party_blank(m.group(1)):
        return m.group(1).strip()
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    skip = re.compile(r"(?i)^(ad\s*soyad|t\.?c\.?\s*kimlik|adres|telefon|davac[ıi]\s+vekil)")
    kept: list[str] = []
    for ln in lines:
        if skip.match(ln) and ":" not in ln:
            continue
        if re.match(r"(?i)^(ad\s*soyad)\s*[:：]", ln):
            kept.append(re.sub(r"(?i)^ad\s*soyad\s*[:：]\s*", "", ln).strip())
            continue
        if re.match(r"(?i)^(t\.?c\.?|adres|telefon)", ln) and kept:
            break
        kept.append(re.sub(r"(?i)^(davac[ıi]|daval[ıi])\s*[:：]\s*", "", ln).strip())
        if kept and (_looks_public(kept[0]) or _clean_person_name(kept[0])):
            break
    return " ".join(x for x in kept if x).strip()


def _split_party_blocks(raw: str) -> tuple[str, str]:
    text = (raw or "").strip()
    if not text:
        return "[DAVACI ADI, TCKN, TEBLİĞ ADRESİ]", "[DAVALI ADI, TCKN, TEBLİĞ ADRESİ]"
    m_davali = _party_heading("davali").search(text)
    m_davaci = _party_heading("davaci").search(text)
    davaci = davali = ""
    if m_davaci and m_davali:
        if m_davaci.start() < m_davali.start():
            davaci = text[m_davaci.end() : m_davali.start()].strip()
            davali = text[m_davali.end() :].strip()
        else:
            davali = text[m_davali.end() : m_davaci.start()].strip()
            davaci = text[m_davaci.end() :].strip()
    elif m_davaci:
        davaci = text[m_davaci.end() :].strip()
    elif m_davali:
        davali = text[m_davali.end() :].strip()
    else:
        davaci = text
    davaci = _value_from_party_block(davaci) or davaci
    davali = _value_from_party_block(davali) or davali
    return davaci or "[DAVACI ADI, TCKN, TEBLİĞ ADRESİ]", davali or "[DAVALI ADI, TCKN, TEBLİĞ ADRESİ]"


def _fold_tr(s: str) -> str:
    t = (s or "").replace("İ", "i").replace("I", "i").replace("ı", "i")
    t = t.lower().replace("\u0307", "")
    return (
        t.replace("ğ", "g")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ç", "c")
    )


def _is_placeholder(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return True
    if re.fullmatch(r"\[.*\]", t):
        return True
    low = _fold_tr(t)
    if any(
        x in low
        for x in (
            "varsa yazin",
            "iskelet dolar",
            "ture gore",
            "somut yazin",
            "evlilik ve ayrilik tarihi",
            "kusur olaylari",
            "yalnizca promt",
            "yalnizca prompt",
            "yalnızca prompt",
        )
    ):
        return True
    return "[" in t and any(
        x in low for x in ("ad soyad", "ad, dogum", "tckn", "…", "...", "teblig adresi")
    )


def _child_line(parties: str) -> str:
    m = re.search(
        r"(?im)^\s*(ortak\s+çocu[kç]|müşterek\s+çocu[kç])[^:\n]*:\s*(.+)$",
        parties or "",
    )
    if not m or _is_placeholder(m.group(2)):
        return ""
    return f"{m.group(1).title()}: {m.group(2).strip()}"


def _looks_public(name: str) -> bool:
    return bool(
        re.search(
            r"(?i)bakanl[ıi][gğ]|m[uü]d[uü]rl[uü][gğ]|belediye|valili|[uü]niversite|"
            r"rekt[oö]rl[uü][gğ]|genel m[uü]d[uü]r|\bcte\b|ba[sş]kanl[ıi][gğ]|"
            r"ltd\.?\s*şti|a\.ş|limited|şirketi",
            name or "",
        )
    )


def _strip_party_label(raw: str) -> str:
    return re.sub(r"(?i)^(davac[ıi]|daval[ıi]|idare)\s*[:：]?\s*", "", (raw or "").strip())


def _resolved_parties(form: dict) -> tuple[str, str]:
    _hydrate_parties(form)
    blob = _source_blob(form)
    people = _extract_person_names(blob)
    admin = _extract_admin_name(blob)
    raw_d, raw_v = _split_party_blocks(_field(form, "parties"))
    davaci = _strip_party_label(raw_d)
    davali = _strip_party_label(raw_v)
    prompt_davali = _davali_from_prompt(blob)
    if _party_blank(davali) and prompt_davali:
        davali = prompt_davali
    if _looks_public(davaci) and (_party_blank(davali) or not _looks_public(davali)):
        if people:
            davali, davaci = davaci, people[0]
        elif admin:
            davali = admin if _party_blank(davali) else davali
            davaci = people[0] if people else ""
    if _party_blank(davaci) and people:
        davaci = people[0]
    if _party_blank(davali) and admin:
        davali = admin
    if _party_blank(davali) and len(people) > 1:
        davali = people[1]
    if _looks_public(davaci) and people and davaci != people[0]:
        davaci = people[0]
    return davaci, davali


def _format_party_card(raw: str, public: bool = False) -> str:
    text = re.sub(r"\s+", " ", _strip_party_label(raw or ""))
    text = re.split(r"(?i)\b(?:ortak|m[uü][sş]terek)\s+çocu[kç]\b", text)[0].strip(" ,;")
    public = public or _looks_public(text)
    if not text or _party_blank(text):
        return ""
    if public:
        name = re.sub(r"(?i)\b(TCKN|T\.C\. Kimlik No)[^,\n]*", "", text).strip(" ,;")
        name = re.sub(r"(?i)^daval[ıi]\s*[:：]\s*", "", name).strip()
        name = re.sub(r"\s*\((?:7315|kapsamında|güvenlik soruştur).*$", "", name, flags=re.I).strip()
        return name
    tckn = ""
    m = re.search(r"\b(\d{10,13})\b", text)
    if m:
        tckn = m.group(1)
        text = (text[: m.start()] + " " + text[m.end() :]).strip(" ,;")
    bits = [p.strip(" :") for p in re.split(r"[,;\n]|TCKN|T\.C\.|adres(?:i)?", text, flags=re.I) if p.strip(" :")]
    name = bits[0] if bits else text
    addr = ", ".join(bits[1:]) if len(bits) > 1 else ""
    city = _city_from_text(addr) or _city_from_text(text)
    if city and re.search(rf"\b{re.escape(city)}\s*$", name, re.I):
        name = re.sub(rf"\s+{re.escape(city)}\s*$", "", name, flags=re.I).strip()
        if not addr:
            addr = city
    bits_out = [name]
    if tckn:
        bits_out.append(f"T.C. Kimlik No: {tckn}")
    if addr and not re.fullmatch(r"[\.…]{3,}", addr.strip()):
        bits_out.append(f"Adres: {addr}")
    return "\n".join(bits_out)


def _lab(key: str, val: str, width: int = 16) -> str:
    lines = (val or "").splitlines() or [""]
    out = [f"{key.ljust(width)}: {lines[0]}"]
    pad = " " * (width + 2)
    out.extend(pad + ln for ln in lines[1:])
    return "\n".join(out)


def _city_from_text(text: str) -> str:
    for il in sorted(_ILLER, key=len, reverse=True):
        if re.search(rf"\b{re.escape(il)}\b", text or "", re.I):
            return il
    return ""


def _infer_city(form: dict) -> str:
    for src in (_field(form, "court"), _field(form, "parties"), _field(form, "title")):
        city = _city_from_text(src)
        if city:
            return city
    return ""


def _tr_upper(s: str) -> str:
    out: list[str] = []
    for ch in s:
        if ch == "i":
            out.append("İ")
        elif ch == "ı":
            out.append("I")
        else:
            out.append(ch.upper())
    return "".join(out)


def _urgent_flags(form: dict) -> dict[str, bool]:
    extra = _field(form, "extraInstructions", "extra")
    tags = "\n".join(
        m.group(1)
        for m in re.finditer(
            r"(?im)^\s*(İVEDİ VE ÖNCELİKLİ İNCELEME|YÜRÜTMEYİ DURDURMA|"
            r"ADLİ YARDIM|İHTİYATİ TEDBİR|İHTİYATİ HACİZ)\s*$",
            extra or "",
        )
    )
    full = _fold_tr(
        " ".join(
            [
                extra,
                tags,
                _field(form, "userPrompt"),
                _field(form, "caseSummary"),
                _field(form, "requests"),
                _field(form, "title"),
                str(form.get("petitionType") or ""),
            ]
        )
    )

    def _flag(*keys: str) -> bool:
        for k in keys:
            v = form.get(k)
            if v in (True, 1, "1", "true", "True", "evet"):
                return True
        return False

    return {
        "ivedi": "ivedi" in full or _flag("ivedi", "urgent", "priorityReview"),
        "yd": ("yurutme" in full and "durdur" in full)
        or "yurutmeyi durdurma" in full
        or _flag("yd", "stay", "yurutme"),
        "adli": "adli yardim" in full
        or _flag("adli", "legalAid", "adliYardim")
        or (
            ("idare" in full or bool(re.search(r"7315|atama uygunluk|infaz ve koruma|guvenlik sorustur", full)))
            and bool(re.search(r"7315|atama uygunluk|infaz ve koruma|guvenlik sorustur", full))
            and not re.search(r"adli yardim (istenm|yok|talep edilm)", full)
        ),
        "tedbir": "ihtiyati tedbir" in full or _flag("tedbir", "injunction"),
        "haciz": "ihtiyati haciz" in full or _flag("haciz"),
    }


def _banner_lines(form: dict) -> list[str]:
    f = _urgent_flags(form)
    out: list[str] = []
    if f["ivedi"]:
        out.append("— İVEDİ VE ÖNCELİKLİ İNCELEME TALEPLİDİR —")
    if f["yd"]:
        out.append("— YÜRÜTMEYİ DURDURMA TALEPLİDİR —")
    if f["adli"]:
        out.append("— ADLİ YARDIM TALEPLİDİR —")
    if f["tedbir"]:
        out.append("— İHTİYATİ TEDBİR TALEPLİDİR —")
    if f["haciz"]:
        out.append("— İHTİYATİ HACİZ TALEPLİDİR —")
    return out


def _court_honorific(ptype: str, raw: str) -> str:
    blob = _fold_tr(f"{ptype} {raw}")
    if any(w in blob for w in ("idare", "vergi", "danistay")):
        return "baskanlik"
    if "savci" in blob or "savcilik" in blob:
        return "savcilik"
    if "mudur" in blob:
        return "mudurluk"
    return "mahkeme"


def _court_line(form: dict, pack: dict) -> str:
    ptype = str(form.get("petitionType") or "")
    raw = court_override(form) or (_field(form, "court") or pack.get("court") or "Mahkemesi'ne")
    raw = raw.replace("…", " ").replace("...", " ")
    raw = re.sub(r"\s+", " ", raw).strip(" '")
    raw = re.sub(r"(?i)\s*(başkanlığı|hakimliği|müdürlüğü|savcılığı)?\s*'?[Nn][EAae]\s*$", "", raw).strip()
    raw = re.sub(r"(?i)\s*başkanlığı\s*$", "", raw).strip()
    already = _city_from_text(raw)
    city = already or _infer_city(form)
    up = _tr_upper(raw)
    if already:
        if "nobetci" not in _fold_tr(raw):
            raw = re.sub(rf"(?i)^{re.escape(already)}\s+", f"{already} Nöbetçi ", raw, count=1)
    elif city and _tr_upper(city) not in up:
        raw = f"{city} Nöbetçi {raw}"
    body = re.sub(r"\s+", " ", _tr_upper(raw)).strip(" '")
    honor = _court_honorific(ptype, raw)
    if honor == "baskanlik":
        if "BAŞKANLIĞI" not in body:
            body = body + " BAŞKANLIĞI"
        return body + "'NA"
    if honor == "savcilik":
        if "SAVCILIĞI" not in body:
            body = body + " SAVCILIĞI"
        return body + "'NA"
    if honor == "mudurluk":
        if "MÜDÜRLÜĞÜ" not in body:
            body = body + " MÜDÜRLÜĞÜ"
        return body + "'NE"
    if not body.endswith("NE"):
        body = body + "'NE"
    return body


def _header_bits(form: dict, pack: dict | None = None) -> tuple[str, str]:
    from bettersaul_mcp.templates import combined_banner

    pack = pack or pack_for(str(form.get("petitionType") or ""))
    court = _court_line(form, pack)
    banner = combined_banner(_urgent_flags(form), str(form.get("petitionType") or ""))
    return court, banner


def _ensure_header(form: dict, pack: dict | None, text: str) -> str:
    """T.C. / mahkeme / baner / DAVA DİLEKÇESİ üstte kalır."""
    t = text or ""
    t = re.sub(r"(?im)^\s*T\.C\.\s*\n+", "", t)
    court, banner = _header_bits(form, pack)
    lines = t.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and re.search(
        r"(?i)MAHKEME|SAVCILIK|BAŞKANLI|MÜDÜRLÜK",
        lines[i],
    ):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    while i < len(lines) and re.search(r"(?i)^\s*—.*TALEPL[İI]", lines[i]):
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
    rest = "\n".join(lines[i:]).lstrip()
    parts = ["T.C."]
    if court:
        parts.append(court)
    if banner:
        parts.append(banner)
    if not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", rest[:500]):
        parts.append("DAVA DİLEKÇESİ")
    if rest:
        parts.append(rest)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(parts)).strip()


def _extract_body(text: str, header: str) -> str:
    t = _usable_text(text) or _clean_llama_out(text) or (text or "")
    t = TOOL_RE.sub("", t).strip()
    m = re.search(rf"{header}\s*[:：]?\s*\n", t, re.I)
    if m:
        rest = t[m.end() :]
        nxt = re.search(r"\n(?:DELİLLER|HUKUK[İI]|SONU[CÇ]|EKLER|VEKÂLETEN)\b", rest, re.I)
        return (rest[: nxt.start()] if nxt else rest).strip()
    return t.strip()


def _has_numbered_vakia(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*1[\.\)\-]\s+\S.{12,}", text or ""))


def _has_book_subs(text: str) -> bool:
    t = text or ""
    return bool(
        re.search(
            r"(?im)(\*\*(Olay|Hukuki Sonuç|Gerçek Em[sş]al|Kronoloji|Dava Şartı))",
            t,
        )
    )


def _has_instr_leak(text: str) -> bool:
    t = text or ""
    return bool(
        re.search(
            r"(?i)Sen Türk avukat asistanısın|##\s*Türkçe muhakeme|"
            r"Dilekçe henüz 5 A4|Yeni vakıa uydurma|Yalnızca numaralı AÇIKLAMALAR|"
            r"içerik mevcut değildir|Exiting\.\.\.|Yazmadan önce Türkçe düşün|"
            r"paragraftan itibaren en az dört|Formda olmayan tutar|"
            r"Yanıtın tamamı Türkçe olsun|aldatma → sadakat|boşanalım →|"
            r"Yalnızca devam numaralı|Aşağıdaki metni aynı hukuki|"
            r"Üslup kalıpları|Tekrarlayan cümleyi birleştir|"
            r"Soru ve emir kipi yazma|Gizli yazım disiplini|"
            r"Aşağıdaki yazım disiplini gizlidir|Anatomi \(metne yazma\)|"
            r"Olay, hukuki sonuç ve gerçek emsal|"
            r"Resmî üslubu uygula|Türk hukuk yazım editörü|"
            r"Yalnızca verilen AÇIKLAMALAR|Üslup:|"
            r"Cümleler özne|Kronoloji \(Tarih|Fer’iler \(Formda|"
            r"wikipedia|duckduckgo|İnternet dil kalıpları|üslup kalıpları|"
            r"BÖLÜM\s*—|Aşağıdaki metni aynı vakıalarla|\(truncated\)|"
            r"Madde ekleme veya çıkarma|"
            r"araç setinde görünmüyor|önceki oturumda kullanabildiğim",
            t,
        )
    )


def _strip_instr_leaks(text: str) -> str:
    t = text or ""
    if TR_REASON and TR_REASON in t:
        t = t.replace(TR_REASON, "\n")
    t = re.sub(r"(?i)Sen Türk avukat asistanısın[^\n]*", "", t)
    t = re.sub(
        r"(?is)##\s*Türkçe muhakeme.*?(?=\n\s*\d{1,2}\.\s+|\nAÇIKLAMALAR|\nDELİLLER|\nT\.C\.|\Z)",
        "\n",
        t,
    )
    t = re.sub(r"(?im)^Yazmadan önce Türkçe düşün.*$", "", t)
    t = re.sub(r"(?im)^Kullanıcının günlük dilini.*$", "", t)
    t = re.sub(r"(?im)^Sıra:\s*$", "", t)
    t = re.sub(r"(?im)^\d+\)\s+(Özne, yüklem|Sözcüğü hukuki|TDK:|Özne-yüklem|İmla:|Yasak:).*$", "", t)
    t = re.sub(r"(?im)^Yalnızca numaralı AÇIKLAMALAR.*$", "", t)
    t = re.sub(r"(?im)^Yalnızca devam numaralı.*$", "", t)
    t = re.sub(r"(?im)^.*İçtihat uydurmazsın\.?\s*$", "", t)
    t = re.sub(r"(?im)^.*Kelimeler arasında boşluk bırakırsın.*$", "", t)
    t = re.sub(r"(?im)^Talimatı dilekçeye yapıştırmazsın\.?\s*$", "", t)
    t = re.sub(
        r"(?is)Dilekçe henüz 5 A4 değil.*?(?=\n\s*\d{1,2}\.\s+|\nDELİLLER|\nHUKUKİ|\Z)",
        "\n",
        t,
    )
    t = re.sub(r"(?im)^Exiting\.\.\.\s*$", "", t)
    t = re.sub(r"(?i)\s*/\s*svg\s*/\s*içerik mevcut değildir", "", t)
    t = re.sub(r"(?i)\s*içerik mevcut değildir\.?", "", t)
    t = re.sub(r"(?i)Delil\s*/\s*Hukuki\s+dayanak\s*/\s*Hukuki\s+sonuç\s*:[^\n]*", "", t)
    t = re.sub(r"(?im)^\s*(Delil|Hukuki\s+dayanak|Hukuki\s+sonuç)\s*:.*$", "", t)
    t = re.sub(r"(?i)\*\*(Olay|Hukuki Sonuç|Gerçek Em[sş]al İlke):\*\*\s*", "", t)
    t = re.sub(
        r"(?is)Aşağıdaki metni aynı hukuki içeriği koruyarak.*?(?=\n[A-ZÇĞİÖŞÜİ]|\n\d{1,2}[\.\)]|\nDELİLLER|\nHUKUKİ|\Z)",
        "\n",
        t,
    )
    t = re.sub(
        r"(?is)önceki oturumda kullanabildiğim.{0,400}araç setinde görünmüyor[^\n]*",
        "",
        t,
    )
    t = re.sub(r"(?im)^\d+\.\s*BÖLÜM\s*—[^\n]*\n?", "", t)
    t = re.sub(r"(?is)Aşağıdaki metni aynı vakıalarla.*?(?:döndür\.\s*|\(truncated\))", "", t)
    t = re.sub(r"\(truncated\)", "", t)
    t = re.sub(r"(?im)^Üslup kalıpları:.*$", "", t)
    t = re.sub(r"(?im)^-\s*Cümleler özne.*$", "", t)
    t = re.sub(r"(?im)^Tekrarlayan cümleyi birleştir.*$", "", t)
    t = re.sub(r"(?im)^Soru ve emir kipi yazma.*$", "", t)
    t = re.sub(r"(?im)^Gizli yazım disiplini.*$", "", t)
    t = re.sub(r"(?im)^Aşağıdaki yazım disiplini gizlidir.*$", "", t)
    t = re.sub(r"(?im)^Anatomi \(metne yazma\).*$", "", t)
    t = re.sub(r"(?im)^Yazım disiplini \(metne yapıştırma\).*$", "", t)
    t = re.sub(r"(?im)^Olay, hukuki sonuç ve gerçek emsal\s*:?\s*", "", t)
    t = re.sub(r"(?im)^.*Resmî üslubu uygula.*$", "", t)
    t = re.sub(r"(?is)Türk hukuk yazım editörüsün.*?(?=\n\s*\d{1,2}[\.\-]|Davanın hukuki|\nDELİLLER|\Z)", "\n", t)
    t = re.sub(r"(?im)^\*\*(Kronoloji|Dava Şartı|Fer.iler).*$", "", t)
    t = re.sub(r"(?i)davan[ıi]n reddine dayanmaktadır[^.]*\.?", "", t)
    t = re.sub(r"(?i)dava açılış tarihi\s+\d{1,2}[./]\d{1,2}[./]\d{4}[^.]*\.?", "", t)
    t = re.sub(r"(?i)\binceledik\b", "incelenmiştir", t)
    t = re.sub(r"(?i)\bgördük\b", "görülmüştür", t)
    t = re.sub(r"(?i)\btespit ettik\b", "tespit edilmiştir", t)
    t = re.sub(r"(?i)\bdeğerlendirdik\b", "değerlendirilmiştir", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _draft_wrong_track(form: dict, text: str) -> bool:
    ptype = str(form.get("petitionType") or "")
    t = text or ""
    if _has_instr_leak(t):
        return True
    if "Boşanma" not in ptype and re.search(
        r"(?i)evlilik birliğinin temelinden sarsıl|boşanma koşulları oluş|"
        r"ortak hayat[^\n.]{0,40}çekilmez|TMK\s*m\.\s*16[46]",
        t,
    ):
        return True
    if "İdare" in ptype and re.search(
        r"(?i)sarsımın temelinde|7315[^.\n]{0,50}m\.\s*16[46]|"
        r"TMK\s*m\.\s*185|evlilik birliğini|"
        r"(Asliye|Ağır)\s+Ceza[^\n.]{0,80}idari (işlem|tasarruf)|"
        r"ceza mahkemesi[^\n.]{0,60}idari (işlem|tasarruf)",
        t,
    ):
        return True
    if "İş" in ptype and re.search(r"(?i)boşanma koşulları|TMK\s*m\.\s*16[46]|7315 sayılı", t):
        return True
    if "İcra" in ptype and re.search(r"(?i)boşanma koşulları|idari işlemin iptali|7315 sayılı", t):
        return True
    return False


def _vakia_too_repetitive(text: str) -> bool:
    paras = re.findall(
        r"(?ms)^\s*\d{1,2}\.\s+(?:\*\*[^*]+\*\*\s*)?(.+?)(?=^\s*\d{1,2}\.\s+|\Z)",
        text or "",
    )
    bodies = [re.sub(r"\s+", " ", p).strip()[:90] for p in paras if len((p or "").strip()) > 40]
    if len(bodies) < 5:
        return False
    return len(set(bodies)) <= max(2, len(bodies) // 4)


def _strip_book_subs(text: str) -> str:
    return _strip_instr_leaks(text)


def _offtrack_sentence(form: dict, s: str) -> bool:
    ptype = str(form.get("petitionType") or "")
    fold = _fold_tr(s or "")
    if _is_prompt_block(s) or _has_instr_leak(s):
        return True
    if "Boşanma" not in ptype and re.search(
        r"evlilik birliginin temelinden|bosanma kosullari|ortak hayat.{0,40}cekilmez|"
        r"velayetin davaciya|tmk m\.\s*16[46]",
        fold,
    ):
        return True
    if "İdare" in ptype and re.search(
        r"(asliye|agir) ceza.{0,80}idari (islem|tasarruf)|"
        r"ceza mahkemesi.{0,60}idari (islem|tasarruf)|"
        r"hmk m\.\s*119|tmk m\.\s*185|evlilik birligini|"
        r"olay, hukuki sonuc ve gercek emsal|"
        r"hangi bilgi veya belgenin dikkate|"
        r"15/1-b|14/3 ve 15|"
        r"davanin redine|davanin reddine karar|davanin reddine dayan|"
        r"kesin ve yurutulebilir yani kesinlesmis|"
        r"sozlesme / akit belgesi",
        fold,
    ):
        return True
    if "İş" in ptype and re.search(r"bosanma kosullari|tmk m\.\s*16[46]|atama uygunluk", fold):
        return True
    if is_labor(form):
        claims = _form_claims(form)
        ghosts = (
            ("ise_iade", r"ise iade|feshin gecersiz"),
            ("baslatmama", r"ise baslatmama"),
            ("bos_sure", r"bosta gecen"),
            ("kidem", r"kidem tazmin"),
            ("ihbar", r"ihbar tazmin"),
            ("fazla", r"fazla (calis|mesai)"),
        )
        for code, pat in ghosts:
            if code not in claims and re.search(pat, fold):
                return True
    return False


def _sanitize_petition(form: dict, text: str) -> str:
    t = _strip_instr_leaks(text or "")
    ptype = str(form.get("petitionType") or "")
    blob = _source_blob(form)
    if "İdare" in ptype or re.search(r"(?i)HAGB|hükmün açıklanmasının geri", blob):
        t = re.sub(
            r"(?i)basit kasten yaralama yönünden ise mahk[ûu]miyet kararı vermiştir",
            "basit kasten yaralama yönünden hükmün açıklanmasının geri bırakılmasına karar verilmiştir",
            t,
        )
        t = re.sub(r"(?i)ceza soruşturması/mahk[ûu]miyet/HAGB", "ceza yargılaması / HAGB", t)
        t = re.sub(r"(?i)mahk[ûu]miyet/HAGB", "HAGB", t)
        t = re.sub(r"(?i)HMK m\.\s*119 usulüne uygundur\.?\s*", "", t)
    t = re.sub(r"(?i)\s*Tebliğ tarihi formda yoksa uydurulmaz;\s*", " ", t)
    t = re.sub(r"(?i)\s*Mahk[ûu]miyet sonucu formda açıkça yazılmamışsa uydurulmaz\.\s*", " ", t)
    t = re.sub(r"(?i)formda yoksa uydurulmaz[^.]*\.\s*", "", t)
    t = re.sub(r"(?i)Davacı Ad Soyad", "Müvekkil", t)
    t = re.sub(r"\s*\(veya formda 164 ise yalnızca 164\)", "", t)
    t = re.sub(r"(?i)\s*veya formda 164 ise[^.]*\.?", "", t)
    try:
        from bettersaul_mcp.petition_tools import apply_detected_facts as _adf
        from bettersaul_mcp.petition_tools import court_ready_text as _crt
        from bettersaul_mcp.petition_tools import strip_empty_placeholders as _sep
        t = _crt(t, source=_source_blob(form))
        t = _adf(t, _source_blob(form))
        t = _sep(t)
    except Exception:
        pass
    blob = _source_blob(form)
    if not re.search(r"(?i)CMK\s*m?\.?\s*251|basit yargılama", blob):
        t = re.sub(r"(?i)\s*(?:ve\s+)?CMK\s*m?\.?\s*251(?:\s+indirim(?:leri)?)?", "", t)
    t = re.sub(
        r"(?i)mahk[ûu]m edilmiş(?:tir)?,?\s+ancak\s+(?:CMK m\.\s*231 uyarınca\s+)?hükmün açıklanmasının geri bırakılmasına",
        "hükmün açıklanmasının geri bırakılmasına",
        t,
    )
    kept: list[str] = []
    seen: list[str] = []
    for para in re.split(r"\n{2,}", t):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        clean = [s for s in sents if not _offtrack_sentence(form, s)]
        if not clean:
            continue
        body = " ".join(clean)
        norm = re.sub(r"\s+", " ", body.lower())[:140]
        if any(norm == s or (len(norm) > 50 and norm in s) for s in seen):
            continue
        seen.append(norm)
        kept.append(body)
    t = "\n\n".join(kept) if kept else t
    t = re.sub(r"(?is)\nVekâleten talep ederim\.\s*\n+\d{1,2}\s+\S+\s+\d{4}\s*\nAv\.[^\n]+(?:\n[^\n]+){0,4}\s*$", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _looks_spaced(text: str) -> bool:
    t = text or ""
    letters = sum(1 for ch in t if ch.isalpha())
    spaces = t.count(" ")
    if letters < 40:
        return True
    if spaces / letters < 0.10:
        return False
    return not re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]{22,}", t)


def _fix_word_spacing(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"([a-zçğıöşü])([A-ZÇĞİÖŞÜ])", r"\1 \2", text)
    text = re.sub(r"([.!?:,;])([A-ZÇĞİÖŞÜa-zçğıöşüIıİ])", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-zÇĞİÖŞÜçğıöşü])", r"\1 \2", text)
    text = re.sub(r"T\.\s+C\.", "T.C.", text)
    text = re.sub(r"\bm\.\s+(\d)", r"m. \1", text)
    glue = (
        r"(davacı|davalı|müvekkil|mahkeme|nedeniyle|tarihinde|uyarınca|"
        r"hakkında|olarak|olduğu|olduğunu|olduğuna|edilmesi|edilmesini|"
        r"talebi|talebinin|dilekçesi|açıklanan)"
    )
    text = re.sub(rf"(?<=[a-zçğıöşü])({glue})", r" \1", text, flags=re.I)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def _split_facts(text: str, n: int) -> list[str]:
    raw = (text or "").strip()
    if n <= 1:
        return [raw]
    parts = [p.strip() for p in re.split(r"\n{2,}", raw) if p.strip()]
    if len(parts) < n:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
        if len(sents) >= 2:
            parts = sents
    if not parts:
        return [""] * n
    if len(parts) >= n:
        return parts[: n - 1] + [" ".join(parts[n - 1 :])]
    return parts + [""] * (n - len(parts))


def _extract_vakia_map(draft: str) -> dict[int, str]:
    found: dict[int, str] = {}
    chunks = re.split(r"(?m)(?=^\s*\d{1,2}[\.\)\-]\s+)", draft or "")
    for chunk in chunks:
        m = re.match(r"^\s*(\d{1,2})[\.\)\-]\s+", chunk)
        if not m:
            continue
        body = chunk.strip()
        if _looks_spaced(body) and len(body) > 40:
            found[int(m.group(1))] = body
    return found


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def _is_prompt_block(s: str) -> bool:
    fold = _fold_tr(s or "")
    return bool(
        re.search(
            r"prompt|amacin dogrudan dilekce|hukuki arastirma ve dava|"
            r"dava stratejisi|su soruyu cevapla|tek tek cevap|"
            r"emsal (karar.*)?uydurma|arastirmanin sonunda|"
            r"sonucta bana|cok onemli:|asla uydurma|"
            r"her karar icin|asagidaki sirayla|"
            r"dilekce henuz 5 a4|yeni vakia uydurma|"
            r"yalnizca numarali aciklamalar|yalnizca devam numarali|"
            r"paragraftan itibaren en az dort|formda olmayan tutar|"
            r"sen turk avukat asistanisin|yazmadan once turkce dusun|"
            r"yanitin tamami turkce olsun|"
            r"asagidaki metni ayni hukuki|uslup kaliplari|"
            r"tekrarlayan cumleyi birlestir|soru ve emir kipi yazma|"
            r"\brolun\b|kidemli bir hukuk|dilekce taslagi uret|"
            r"asagida tum detaylari|hukuk yapay zeka|"
            r"turkiye cumhuriyeti yargi sistemine",
            fold,
        )
    )


def _is_petition_question(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return True
    if t.endswith("?"):
        return True
    fold = _fold_tr(t)
    if re.search(
        r"\b(m[iı]d[iı]r|midir|mudur|mudur|miyim|miyiz)\b|"
        r"\b(incele|arastir|bul|cevapla|analiz et|sirala)\s*[.:]?\s*$|"
        r"hangi (mahkeme|belge|veri|kanun|olay|tarih)|"
        r"nasil (talep|degerlendir|aciklan|celb)|"
        r"zorunda m[iı]d[iı]r|mumkun mudur|yeterli midir|"
        r"ozellikle su konularda emsal|"
        r"bu soruyu|asagida aciklanan uyusmazligi",
        fold,
    ):
        return True
    return False


def _is_request_noise(s: str) -> bool:
    low = (s or "").lower().strip()
    if not low:
        return True
    if _is_prompt_block(low) or _is_petition_question(low):
        return True
    if "ortak çocuk" in low and not low.endswith("?"):
        return False
    fold = _fold_tr(low)
    if re.search(
        r"ivedi ve oncelikli|yurutmeyi durdurma|adli yardim|ihtiyati tedbir|ihtiyati haciz",
        fold,
    ) and len(low) < 80:
        return True
    return bool(
        re.search(
            r"(talep(te bulun| ediyorum| etmektedir| olun| olunmaktadır)|"
            r"almak istiyorum|boşanmak istiyorum|"
            r"istiyorum(\s+(ivedi|acil))?\.?\s*$|"
            r"nihayet\s+boşan|"
            r"^\s*(ivedi|acil)\b|"
            r"ivedi\s*$)",
            low,
        )
    )


def _title_keys(title: str) -> list[str]:
    stop = {"varsa", "veya", "için", "ile", "yol", "açan", "ayrı", "hususu"}
    words = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{4,}", (title or "").lower()) if w not in stop]
    extra = {
        "kuruluş": ["evlen", "cüzdan", "nikah", "evlilik"],
        "çocuk": ["çocuk", "doğum", "velayet", "oğul", "kız"],
        "sarsıl": ["geçimsiz", "şiddet", "hakaret", "aldat", "tartış", "tanık"],
        "kusur": ["kusur", "tutum", "sadakat", "hakaret", "aldat"],
        "ayrılık": ["ayrılık", "terk", "şiddet", "tedbir", "6284"],
        "gelir": ["gelir", "nafaka", "ücret", "bordro"],
        "velayet": ["velayet", "çocuk", "üstün", "kişisel"],
        "ziynet": ["ziynet", "altın", "eşya", "tapu", "mal"],
    }
    keys = list(words)
    blob = (title or "").lower()
    for stem, syns in extra.items():
        if stem in blob or any(stem in w for w in words):
            keys.extend(syns)
    return keys


def _vakia_kind(title: str) -> str:
    low = (title or "").lower()
    if any(x in low for x in ("kuruluş", "cüzdan", "evlenme yeri")):
        return "kurulus"
    if "ortak çocuk" in low or re.search(r"çocuklar varsa", low):
        return "cocuk"
    if any(x in low for x in ("sarsıl", "somut olay")):
        return "sarsilma"
    if "kusur" in low:
        return "kusur"
    if any(x in low for x in ("şiddet", "terk", "ayrılık", "tedbir")):
        return "siddet"
    if any(x in low for x in ("gelir", "nafaka")):
        return "nafaka"
    if "velayet" in low or "üstün yarar" in low:
        return "velayet"
    if any(x in low for x in ("ziynet", "mal rejim", "eşya")):
        return "ziynet"
    if any(x in low for x in ("iş ilişki", "ücreti", "işyeri")):
        return "is_iliski"
    if any(x in low for x in ("fazla mesai", "hafta tatili", "çalışma süre")):
        return "mesai"
    if any(x in low for x in ("fesih", "ibraname")):
        return "fesih"
    if any(x in low for x in ("arabuluculuk",)):
        return "arabulucu"
    if any(x in low for x in ("alacak", "hesabı", "dava değeri")):
        return "alacak"
    if any(x in low for x in ("sözleşme", "borç ilişki", "fatura", "icap")):
        return "sozlesme"
    if any(x in low for x in ("temerrüt", "ihtar", "muacceliyet")):
        return "temerrut"
    if any(x in low for x in ("takip", "ödeme emri", "icra")):
        return "icra"
    if any(x in low for x in ("idari işlem", "iptal", "tebliğ")):
        return "idare"
    if any(x in low for x in ("kira", "tahliye", "taşınmaz")):
        return "kira"
    if any(x in low for x in ("ayıp", "tüketici", "seçimlik")):
        return "tuketici"
    if "içtihat" in low:
        return "ictihat"
    return "diger"


def _facts_for_vakia(title: str, facts: str, extra: str, child: str) -> list[str]:
    pool = [
        s
        for s in _sentences(_fact_source(facts)) + _sentences(_fact_source(extra))
        if s and not _is_placeholder(s) and not _is_request_noise(s)
    ]
    kind = _vakia_kind(title)
    keys = _title_keys(title)
    hit = [s for s in pool if any(k in s.lower() for k in keys)]
    if kind in ("sarsilma", "kusur"):
        for s in pool:
            if s in hit:
                continue
            if any(w in s.lower() for w in ("aldat", "zina", "sadakat", "hakaret", "geçimsiz", "çekilmez")):
                hit.append(s)
    if kind in ("cocuk", "velayet"):
        hit = [
            s
            for s in hit
            if any(w in s.lower() for w in ("çocuk", "velayet", "oğul", "kız"))
            and not any(w in s.lower() for w in ("aldat", "zina", "sadakat"))
        ]
        if child:
            hit.append(child)
    if kind == "kurulus":
        hit = [
            s
            for s in hit
            if any(w in s.lower() for w in ("evlen", "nikah", "cüzdan", "kuruluş", "evlilik tarihi"))
            and not any(w in s.lower() for w in ("aldat", "zina", "velayet"))
        ]
    if kind == "siddet":
        hit = [s for s in pool if any(w in s.lower() for w in ("şiddet", "terk", "6284", "uzaklaştır", "tedbir", "yaralama"))]
    if kind == "nafaka":
        hit = [s for s in pool if any(w in s.lower() for w in ("nafaka", "gelir", "ücret", "yoksul", "ihtiyaç"))]
    if kind == "ziynet":
        hit = [s for s in pool if any(w in s.lower() for w in ("ziynet", "altın", "eşya", "tapu", "mal rejim"))]
    seen: set[str] = set()
    out: list[str] = []
    for s in hit:
        k = s.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _fact_source(text: str) -> str:
    parts: list[str] = []
    for para in re.split(r"\n{2,}", text or ""):
        if _is_prompt_block(para):
            continue
        sents = _sentences(para)
        if not sents:
            continue
        nq = sum(1 for s in sents if _is_petition_question(s))
        if nq >= 3 and nq * 2 >= len(sents):
            continue
        parts.append(para)
    return "\n".join(parts)


def _all_fact_sentences(facts: str, extra: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in _sentences(_fact_source(facts)) + _sentences(_fact_source(extra)):
        if not s or _is_placeholder(s) or _is_request_noise(s):
            continue
        if re.search(r"(?i)hmk m\.\s*119 nispi|ziynet alacağı dökümü:", s):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _hukuki_dil(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if _is_request_noise(t):
        return ""
    t = re.sub(r"(?i)\s*nihayet\s+.*(istiyorum|ivedi).*$", "", t).strip()
    if not t:
        return ""
    reps = (
        (r"(?i)otel odasındaki aldatma görüntüleri (çıkmıştır|çıkmış|elde edilmiştir|vardır)",
         "davalının sadakat yükümlülüğünü ağır şekilde ihlal ettiğine ilişkin otel konaklama kayıtları ve görsel materyaller elde edilmiştir"),
        (r"(?i)aldatma görüntüleri (çıkmıştır|çıkmış|bulunmuştur|vardır)",
         "sadakat yükümlülüğünün ihlaline ilişkin görsel materyaller temin edilmiştir"),
        (r"(?i)görüntüler(i)? çıkmıştır", "görsel materyaller temin edilmiştir"),
        (r"(?i)\beşini aldat(mış|mıştır|tı)\b", "sadakat yükümlülüğünü ihlal etmiştir"),
        (r"(?i)\baldatmıştır\b", "sadakat yükümlülüğünü ihlal etmiştir"),
        (r"(?i)\baldatarak\b", "sadakat yükümlülüğünü ihlal etmek suretiyle"),
        (r"(?i)sadakat yükümlülüğünü ihlal ederek aldatmıştır", "sadakat yükümlülüğünü ihlal etmiştir"),
        (r"(?i)evi terk et(ti|miştir|miş)", "ortak konutu terk ederek fiilî ayrılığı başlatmıştır"),
        (r"(?i)evde hakaret ve geçimsizlik (yaşanmıştır|olmuştur)",
         "ortak konutta hakaretamiz sözler sarf edilmiş ve geçimsizlik meydana gelmiştir"),
        (r"(?i)çıkmıştır", "tespit edilmiştir"),
        (r"(?i)yaşanmıştır", "meydana gelmiştir"),
        (r"(?i)olmuştur\b", "gerçekleşmiştir"),
        (r"(?i)kötü konuş(muş|muştur|tu)", "hakaretamiz sözler sarf etmiştir"),
        (r"(?i)\b(kovdu|kapıya koydu|işten attı)\b", "iş sözleşmesini feshetti"),
        (r"(?i)maaş(ı)? yatmadı", "ücret ödenmedi"),
        (r"(?i)para vermedi", "ücreti ödemedi"),
        (r"(?i)boşanalım|boşanmak istiyorum", "evlilik birliğinin sona erdirilmesi talep olunur"),
        (r"(?i)çocuk bende kalsın", "velayetin davacıya verilmesi talep olunur"),
        (r"(?i)\bkavga ettik\b", "geçimsizlik meydana gelmiştir"),
        (r"(?i)\bçok bağır(ıyor|dı|mıştır)\b", "hakaretamiz ve yüksek sesle sözler sarf etmiştir"),
        (r"(?i)tarihinde Uşak’ta evlenmiştir", "tarihinde Uşak ilinde evlilik birliği tesis etmişlerdir"),
        (r"(?i)tarihinde (.+?) evlenmiştir", r"tarihinde \1 evlilik birliği tesis etmişlerdir"),
        (r"(?i)^taraflar (.+) evlenmiştir", r"Taraflar \1 evlilik birliği tesis etmişlerdir"),
    )
    for pat, repl in reps:
        t = re.sub(pat, repl, t)
    t = re.sub(
        r"(?i)sadakat yükümlülüğünü ihlal ederek sadakat yükümlülüğünü ihlal etmiştir",
        "sadakat yükümlülüğünü ihlal etmiştir",
        t,
    )
    t = t[0].upper() + t[1:] if t else t
    t = reconcile_date_span(t)
    return t.rstrip(" .;") + "."


def _weave_facts(hits: list[str]) -> str:
    parts: list[str] = []
    for s in hits:
        t = _hukuki_dil(s)
        if t and t not in parts:
            parts.append(t)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    out = parts[0].rstrip(".")
    for i, p in enumerate(parts[1:], 1):
        bit = p.rstrip(".")
        if bit[:1].isupper() and not re.match(r"^(Müvekkil|Davacı|Davalı|Taraflar)\b", bit):
            bit = bit[0].lower() + bit[1:]
        out += ". " + bit
    return out.rstrip(".") + "."


def _delil_for(pack: dict, title: str, i: int) -> str:
    kind = _vakia_kind(title)
    by_kind = {
        "kurulus": "Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi (nüfus müdürlüğü)",
        "cocuk": "Nüfus kayıt örneği (nüfus müdürlüğü — çocuk kimliği)",
        "sarsilma": "Davacı beyanı; yazışma, görüntü ve yargılamada sunulacak belgeler",
        "kusur": "Davacı beyanı; yazışma, görüntü ve yargılamada sunulacak belgeler",
        "velayet": "Nüfus kaydı; okul/sağlık belgesi (ilgili kurumdan celp)",
        "siddet": "Sağlık raporu, adli evrak, tedbir kararı (ilgili makamdan celp)",
        "nafaka": "Gelir belgesi, bordro, SGK hizmet dökümü (işveren / SGK)",
        "ziynet": "Ziynet, banka ve tapu kayıtları (banka / tapu müdürlüğü)",
    }
    if kind in by_kind:
        return by_kind[kind]
    ev = list(pack.get("evidence") or ["Dayanak belgeler"])
    return ev[i % len(ev)]


def _strip_disclaimers(text: str) -> str:
    t = text or ""
    t = re.sub(r"(?i)\s*bu (bilgiler )?dilekçede uydurulmamıştır\.?", "", t)
    t = re.sub(r"(?i)\s*esas ve karar numarası uydurulmamıştır\.?", "", t)
    t = re.sub(r"(?i)\s*yargıtay uygulaması da bu yöndedir \([^)]+\)[:.][^.]*\.", "", t)
    t = re.sub(r"(?i)\s*aynı doğrultuda [^.]*emsaldir\.?", "", t)
    t = re.sub(r"(?i)\s*at[ıi]f, yalnızca birliğin temelinden sarsılması[^.]*\.", "", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def _legal_wrap(kind: str, olay: str, facts: str) -> str:
    blob = (facts or "").lower()
    if kind == "kurulus":
        return (
            f"{olay} Evlilik birliği bu kayıtlarla sabittir. "
            "Nüfus kaydı ve evlilik cüzdanı, birliğin kuruluşunu ve tarafların evlilik sıfatını "
            "çekişmesiz biçimde ortaya koyacaktır."
        )
    if kind == "cocuk":
        return (
            f"{olay} Müşterek çocuğun kimliği nüfus kaydı ile sabittir. "
            "Bu olgu, velayet, kişisel ilişki ve iştirak nafakası taleplerinin dayanağını oluşturur."
        )
    if kind == "sarsilma":
        extra = ""
        if any(w in blob for w in ("aldat", "zina", "sadakat")):
            extra = (
                " Davalının sadakat yükümlülüğüne aykırı tutumu, birliğin temelinden sarsılmasında "
                "ağırlıklı kusur unsurudur."
            )
        return (
            f"{olay}{extra} Eşlerin evlilik birliğini karşılıklı sevgi, saygı ve sadakat içinde "
            "sürdürme yükümlülüğü (TMK m. 185) somut olayda ihlal edilmiştir. Ortak hayat, "
            "müvekkil bakımından çekilmez hâle gelmiştir. TMK m. 166 uyarınca evlilik birliği "
            "temelinden sarsılmış olup boşanma koşulları oluşmuştur."
        )
    if kind == "kusur":
        return (
            f"{olay} Açıklanan vakıalar birlikte değerlendirildiğinde kusur davalı taraftadır. "
            "Davacıdan birliği sürdürmesi beklenemez. Kusur dağılımı, boşanma ile birlikte "
            "tazminat ve nafaka taleplerinin de hukuki temelini oluşturur."
        )
    if kind == "velayet":
        return (
            f"{olay} Velayet, çocuğun üstün yararı esas alınarak belirlenir (TMK m. 182, m. 339). "
            "Davalının birliği sarsan tutumu, çocuğun bedensel ve ruhsal gelişimi ile günlük "
            "düzeni bakımından da nazara alınmalıdır. Velayetin davacıya bırakılması, çocuğun "
            "üstün yararına uygundur."
        )
    if kind == "siddet":
        return (
            f"{olay} Aile içi şiddet ve birliği fiilen sona erdiren ayrılık olguları, hem boşanma "
            "hem de koruyucu tedbir bakımından ayrı önem taşır. Bu vakıa, evlilik birliğinin "
            "çekilmezliğini pekiştirir."
        )
    if kind == "nafaka":
        return (
            f"{olay} Nafaka, yoksulluğa düşme tehlikesi ve tarafların ekonomik durumu gözetilerek "
            "hükmedilir (TMK m. 175, m. 182). Müvekkilin geçimini sağlayacak düzenli ve yeterli "
            "geliri bulunmadığı ölçüde tedbir ve yoksulluk nafakası talep olunur."
        )
    if kind == "ziynet":
        return (
            f"{olay} Ziynet ve kişisel eşya, kural olarak kadına özgülenmiş mal niteliğindedir. "
            "İade edilmeyen kalemler belgeler ve tanıkla kanıtlanacak; mal rejimi tasfiyesi "
            "saklı kalmak üzere iade talep olunur."
        )
    if kind == "is_iliski":
        return (
            f"{olay} İş sözleşmesi ve fiilî çalışma olgusu SGK kayıtları ile bordro/banka "
            "hareketleriyle kanıtlanacaktır. Ücret ve işyeri, alacak kalemlerinin hesabına esastır."
        )
    if kind == "mesai":
        return (
            f"{olay} Fazla çalışma ve tatil emeği, işverenin kayıtları ile tanık ve puantaj "
            "delilleriyle ortaya konulacaktır. Karşılığı ödenmeyen çalışma, 4857 sayılı Kanun "
            "uyarınca ayrıca talep olunur."
        )
    if kind == "fesih":
        return (
            f"{olay} Feshin tarihi ve şekli, ücret ve işçilik alacaklarının muacceliyeti "
            "bakımından belirleyicidir. Ödenmeyen kalemler bu vakıaya dayanır."
        )
    if kind == "arabulucu":
        return (
            f"{olay} Dava şartı olan arabuluculuk süreci tamamlanmıştır. Son tutanak, yargılama "
            "önkoşulunun yerine getirildiğini gösterir."
        )
    if kind == "sozlesme":
        return (
            f"{olay} Borç ilişkisi sözleşme, fatura veya icap-kabul ile kurulmuştur. Bu vakıa, "
            "alacağın kaynağını ve tarafların edimlerini ortaya koyar."
        )
    if kind == "temerrut":
        return (
            f"{olay} Muacceliyet ve ihtar ile davalı temerrüde düşmüştür. Temerrüt, asıl alacakla "
            "birlikte faiz talebinin dayanağıdır (TBK m. 117)."
        )
    if kind == "alacak":
        return (
            f"{olay} Talep edilen tutar, dayanak belgeler ve hesap cetveline göre muayyendir. "
            "Dava değeri bu kalemler üzerinden gösterilmiştir."
        )
    if kind == "icra":
        return (
            f"{olay} İcra takibi ve ödeme emri tebliği dosya örneği ile sabittir. İtiraz, mevcut "
            "belgeler karşısında haksızdır; takibin devamı gerekir."
        )
    if kind == "idare":
        return (
            f"{olay} İptal davasının konusu, idarenin tek yanlı ve yürütülmesi zorunlu işlemidir "
            "(İYUK m. 2). Ceza mahkemesi kararı bu işlemin kendisi değildir; varsa yalnızca "
            "işlemin sebep unsurunda değerlendirilen olgudur. İşlem yetki, şekil, sebep, konu ve "
            "amaç yönünden hukuka aykırıdır. Dava açma süresi İYUK m. 7 (ve varsa m. 11) "
            "çerçevesinde hesaplanır. Soyut gerekçeyle tesis edilen işlem, sebep unsuru yönünden "
            "denetlenebilir olmalı; somut fiil ve ölçüt açıklanmalıdır."
        )
    if kind == "kira":
        return (
            f"{olay} Kira ilişkisi ve temerrüt/ihtiyaç olgusu sözleşmeyle sabittir. Tahliye ve "
            "birikmiş alacak talepleri bu vakıaya dayanır."
        )
    if kind == "tuketici":
        return (
            f"{olay} Ayıp, tüketici işleminin kurulmasından sonra ortaya çıkmış ve satıcıya "
            "bildirilmiştir. 6502 sayılı Kanun’daki seçimlik haklar kullanılmaktadır."
        )
    return (
        f"{olay} Bu vakıa, aşağıda yazılı hukuki nedenler ve istemlerle doğrudan bağlantılıdır."
    )


def _case_paragraph(
    title: str,
    hits: list[str],
    facts: str,
    cites: list[str],
    i: int,
) -> str | None:
    kind = _vakia_kind(title)
    if hits:
        olay = _weave_facts(hits)
        return _strip_disclaimers(_legal_wrap(kind, olay, facts))
    if kind == "kurulus":
        return _legal_wrap(
            kind,
            "Taraflar evlilik birliği içindedir.",
            facts,
        )
    if kind == "cocuk":
        blob = (facts or "").lower()
        if "çocuk" in blob or "velayet" in blob:
            return _legal_wrap(kind, "Evlilik birliğinden müşterek çocuk bulunmaktadır.", facts)
        return None
    if kind == "velayet":
        blob = (facts or "").lower() + " " + (title or "").lower()
        if "velayet" in blob or "çocuk" in blob:
            return _legal_wrap(kind, "Müşterek çocuğun velayetinin davacıya bırakılması talep olunur.", facts)
        return None
    if kind in ("siddet", "nafaka", "ziynet"):
        return None
    return None


def _hukuki_sonuc(kind: str, title: str) -> str:
    short = re.sub(r"\s*\(.*\)\s*$", "", title or "").rstrip(" .")
    by_kind = {
        "kurulus": "Evliliğin sabit oluşu, boşanma ve fer’i taleplerin görülmesini mümkün kılar.",
        "cocuk": "Müşterek çocuk olgusu velayet, kişisel ilişki ve iştirak nafakasını zorunlu kılar.",
        "sarsilma": "Birliğin temelinden sarsılması, TMK m. 166 uyarınca boşanma hükmünü haklı kılar.",
        "kusur": "Kusurun davalıda toplanması, boşanma ile tazminat ve nafaka istemlerini güçlendirir.",
        "velayet": "Çocuğun üstün yararı, velayetin davacıya bırakılmasını gerektirir.",
        "siddet": "Şiddet ve ayrılık olgusu, boşanma ile tedbir taleplerini ayrıca haklı kılar.",
        "nafaka": "Ekonomik denge ve yoksulluk tehlikesi nafaka hükmünü gerektirir.",
        "ziynet": "İade edilmeyen ziynet ve eşya, iade ve tasfiye istemlerinin kabulünü gerektirir.",
        "is_iliski": "İş ilişkisinin sabitliği, işçilik alacaklarının dinlenmesini sağlar.",
        "mesai": "Ödenmeyen fazla çalışma ve tatil ücretleri ayrıca hükme bağlanmalıdır.",
        "fesih": "Fesih olgusu, muaccel işçilik alacaklarının temelidir.",
        "arabulucu": "Dava şartı yerine gelmiş olup işin esasına girilmelidir.",
        "sozlesme": "Borç ilişkisinin kuruluşu, alacak isteminin kabulünü haklı kılar.",
        "temerrut": "Temerrüt, asıl alacakla birlikte faiz istemini doğurur.",
        "alacak": "Muayyen alacak kalemleri hüküm altına alınmalıdır.",
        "icra": "İtirazın iptali ve takibin devamı gerekir.",
        "idare": "Hukuka aykırı işlemin iptali (ve varsa tazminat) gerekir.",
        "kira": "Tahliye ve kira alacağı istemleri bu vakıaya dayanır.",
        "tuketici": "Seçimlik hak ve bedel iadesi kabul olunmalıdır.",
    }
    return by_kind.get(kind, f"{short} olgusu, aşağıda yazılı istemlerin kabulünü haklı kılar.")


def _clean_req(line: str) -> str:
    return re.sub(r"^[\s\-•]*\d+[\.\)\-]\s*", "", (line or "").strip()).rstrip(".")


def _find_amounts(text: str) -> list[str]:
    found = re.findall(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)\s*(?:TL|₺)",
        text or "",
        re.I,
    )
    out: list[str] = []
    for a in found:
        t = f"{a} TL"
        if t not in out:
            out.append(t)
    return out


def _blank_tl() -> str:
    return "........................ TL"


def _fmt_user_tl(raw: str) -> str:
    t = re.sub(r"\s+", " ", (raw or "").replace("₺", "").strip())
    if not t or not re.search(r"\d", t):
        return ""
    if not re.search(r"TL", t, re.I):
        t = t + " TL"
    return t


def _tl_number(raw: str) -> float | None:
    t = re.sub(r"[^\d,\.]", "", raw or "")
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _fmt_sum_tl(n: float) -> str:
    s = f"{n:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " TL"


def _claim_vals(form: dict) -> dict:
    raw = form.get("claimValues")
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    out: dict = {}
    for k, v in raw.items():
        if k == "ziynet":
            rows = []
            for row in v or []:
                if not isinstance(row, dict):
                    continue
                item = {kk: str(row.get(kk) or "").strip() for kk in ("cins", "adet", "ayar", "gram", "tl")}
                if any(item.values()):
                    rows.append(item)
            if rows:
                out["ziynet"] = rows
            continue
        t = _fmt_user_tl(str(v or ""))
        if t:
            out[str(k)] = t
    return out


def _ziynet_rows(form: dict) -> list[dict]:
    rows = list(_claim_vals(form).get("ziynet") or [])
    if rows:
        return rows
    blob = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests")]
    )
    for m in re.finditer(
        r"(\d+)\s*adet\s+(\d+\s*ayar)?\s*(\d+(?:[.,]\d+)?\s*(?:gr|gram))?\s*([^,;\n]+?)"
        r"(?:\s*=\s*|\s+)(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)\s*(?:TL|₺)",
        blob,
        re.I,
    ):
        rows.append(
            {
                "adet": m.group(1),
                "ayar": (m.group(2) or "").strip(),
                "gram": (m.group(3) or "").strip(),
                "cins": (m.group(4) or "").strip(" -"),
                "tl": _fmt_user_tl(m.group(5)),
            }
        )
    return rows


def _ziynet_table(form: dict) -> str:
    rows = _ziynet_rows(form)
    if not rows:
        return ""
    lines = [
        "Ziynet alacağı dökümü (cins, adet, ayar, gram ve TL değeri; aynen iade, "
        "mümkün olmazsa rayiç bedel):"
    ]
    total = 0.0
    have_sum = False
    for i, r in enumerate(rows, 1):
        bits = [
            x
            for x in (
                (r.get("adet") + " adet") if r.get("adet") else "",
                r.get("ayar"),
                r.get("gram"),
                r.get("cins"),
                r.get("tl"),
            )
            if x
        ]
        lines.append(f"{i}) " + ", ".join(bits))
        n = _tl_number(r.get("tl") or "")
        if n is not None:
            total += n
            have_sum = True
    cv = _claim_vals(form)
    tot = cv.get("ziynetToplam") or ( _fmt_sum_tl(total) if have_sum else "")
    if tot:
        lines.append(f"Toplam rayiç bedel: {tot}")
    return "\n".join(lines)


def _amount_near(blob: str, keys: tuple[str, ...]) -> str:
    for kw in keys:
        m = re.search(
            rf"(\d{{1,3}}(?:\.\d{{3}})*(?:,\d{{2}})?|\d+)\s*(?:TL|₺)\s+{kw}|"
            rf"{kw}[^\d]{{0,32}}(\d{{1,3}}(?:\.\d{{3}})*(?:,\d{{2}})?|\d+)\s*(?:TL|₺)",
            blob or "",
            re.I,
        )
        if m:
            return _fmt_user_tl(m.group(1) or m.group(2))
    return ""


def _claim_amount(form: dict, key: str, *near: str) -> str:
    cv = _claim_vals(form)
    if cv.get(key):
        return str(cv[key])
    blob = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests")]
    )
    return _amount_near(blob, near) if near else ""


def _with_amount(line: str, amount: str) -> str:
    if not amount:
        return line
    if re.search(r"\.{5,}\s*TL", line):
        return re.sub(r"\.{5,}\s*TL", amount, line, count=1)
    if re.search(r"\d.+\s*TL", line, re.I):
        return line
    return f"{amount} {line[0].lower() + line[1:]}" if line[:1].isupper() else f"{amount} {line}"


def _apply_claim_amounts(lines: list[str], form: dict) -> list[str]:
    rules = (
        (r"iştirak", "istirak", ("iştirak",)),
        (r"yoksulluk", "yoksulluk", ("yoksulluk",)),
        (r"(çocuk|müşterek).{0,40}tedbir nafaka|tedbir nafaka.{0,40}(çocuk|müşterek)", "tedbirCocuk", ("çocuk.*tedbir", "müşterek.*tedbir")),
        (r"tedbir nafaka", "tedbirDavaci", ("tedbir nafaka",)),
        (r"maddi tazminat", "maddi", ("maddi tazminat",)),
        (r"manevi tazminat", "manevi", ("manevi tazminat",)),
        (r"kıdem", "kidem", ("kıdem",)),
        (r"ihbar", "ihbar", ("ihbar",)),
        (r"fazla mesai", "fazlaMesai", ("fazla mesai",)),
        (r"ubgt", "ubgt", ("ubgt", "ulusal bayram")),
        (r"yıllık izin", "yillikIzin", ("yıllık izin",)),
        (r"asıl alacak|alacağın tahsil|ödenmeyen ücret|ücret alaca", "alacak", ("asıl alacak", "alacak", "ücret")),
        (r"ziynet", "ziynetToplam", ("ziynet",)),
    )
    out: list[str] = []
    for line in lines:
        t = line
        for pat, key, near in rules:
            if re.search(pat, t, re.I):
                amt = _claim_amount(form, key, *near)
                if amt:
                    t = _with_amount(t, amt)
                break
        out.append(t)
    return out


def _is_blank_money(line: str) -> bool:
    if re.search(r"nafaka|ödenmeyen ücret|işçilik alacak", line, re.I):
        return False
    if not re.search(r"tazminat|alacak|ücret|bedel|ziynet", line, re.I):
        return False
    return bool(re.search(r"\.{5,}\s*TL", line))


def _nispi_sum(form: dict, reqs: list[str]) -> str:
    cv = _claim_vals(form)
    if cv.get("harcaEsas"):
        return str(cv["harcaEsas"])
    keys = ("kidem", "ihbar", "fazlaMesai", "ubgt", "yillikIzin", "alacak")
    if not is_labor(form):
        keys = ("maddi", "manevi", "ziynetToplam") + keys
    total = 0.0
    n = 0
    for k in keys:
        v = _tl_number(str(cv.get(k) or ""))
        if v is not None:
            total += v
            n += 1
    if not is_labor(form):
        for r in _ziynet_rows(form):
            v = _tl_number(r.get("tl") or "")
            if v is not None and "ziynetToplam" not in cv:
                total += v
                n += 1
    if n:
        return _fmt_sum_tl(total)
    return ""


def _ensure_claim_amount(line: str) -> str:
    t = (line or "").strip()
    if not t:
        return t
    if re.search(
        r"yargılama gider|vek[aâ]let ücret|boşanmalarına|velayet|iptaline|katılmaya|"
        r"cezalandırmaya|takiğin devam|aynen iade|dökümü verilen ziynet|nafaka|"
        r"ödenmeyen ücret|işçilik alacak",
        t,
        re.I,
    ):
        return t
    if not re.search(r"tazminat|alacak|ücret|bedel|faiz", t, re.I):
        return t
    if re.search(r"\d|…|\.{5,}|TL|₺", t):
        return t
    if t[:1].isupper():
        return f"{_blank_tl()} {t[0].lower() + t[1:]}"
    return f"{_blank_tl()} {t}"


def _expand_requests(form: dict, reqs: list[str], pack: dict) -> list[str]:
    blob = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests"), " ".join(reqs)]
    )
    low = blob.lower()
    factish = re.sub(
        r"(?i)ortak\s+çocuk:\s*ad.*$|\[ad[^\]]*\]",
        "",
        " ".join([_field(form, "caseSummary"), _field(form, "parties"), _field(form, "extraInstructions")]),
    )
    cv0 = _claim_vals(form)
    child = bool(re.search(r"çocuk", factish, re.I)) or bool(cv0.get("istirak") or cv0.get("tedbirCocuk"))
    ptype = str(form.get("petitionType") or "")
    out: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        t = _ensure_claim_amount(_clean_req(line))
        if not t:
            return
        if re.search(r"yargılama gider|vek[aâ]let ücret", t, re.I):
            return
        k = re.sub(r"\s+", " ", t.lower())
        if k not in seen:
            seen.add(k)
            out.append(t)

    flags = _urgent_flags(form)
    if flags["ivedi"]:
        add("Davanın ivedi ve öncelikli incelenmesine")
    if flags["yd"]:
        add("2577 sayılı İYUK m. 27 uyarınca yürütmenin durdurulmasına")
    if flags["adli"]:
        add("Adli yardım talebinin kabulüne")
    if "İdare" in ptype and re.search(r"(?i)7315|güvenlik soruştur|atama uygunluk|değerlendirme komisyon", blob):
        add(
            "Güvenlik soruşturması ve değerlendirme komisyonu evrakının mahkeme aracılığıyla "
            "davalı idareden celbine"
        )
    if flags["tedbir"]:
        add("HMK m. 389 vd. uyarınca ihtiyati tedbire")
    if flags["haciz"]:
        add("İhtiyati hacze")
    labor = is_labor(form)
    user_low = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests")]
    ).lower()
    for r in reqs:
        if not child and re.search(r"çocuk|müşterek|velayet|iştirak", r, re.I):
            continue
        if labor and re.search(r"maddi tazminat|manevi tazminat|haksız fiil", r, re.I) and not wants_tazminat(form):
            continue
        if "İdare" in ptype and re.search(r"tazminat|\.{5,}\s*TL", r, re.I) and not wants_tazminat(form):
            continue
        if "İdare" in ptype and re.search(r"(?i)\biptal\b", r) and not re.search(r"(?i)iptaline", r):
            add("İşlemin iptaline")
            continue
        if "İdare" in ptype and re.search(r"ziynet|boşanma|nafaka|velayet", r, re.I):
            continue
        if "Boşanma" not in ptype and re.search(r"boşanmalarına|yoksulluk nafaka|iştirak nafaka|ziynet eşya", r, re.I):
            continue
        if labor and re.search(r"kıdem|ihbar|fazla mesai|ubgt|yıllık izin", r, re.I):
            if not re.search(r"kıdem|ihbar|fazla mesai|ubgt|yıllık izin", user_low):
                continue
        if labor and re.search(r"işe iade|boşta geçen|işe başlatmama", r, re.I):
            if not re.search(r"işe iade|boşta geçen|işe başlatmama", user_low):
                continue
        for piece in _split_combo_claim(r):
            if labor and re.search(r"maddi tazminat|manevi tazminat", piece, re.I) and not wants_tazminat(form):
                continue
            add(piece)
    if labor:
        claims = _form_claims(form)
        if "ise_iade" in claims and not any(re.search(r"işe iade", r, re.I) for r in out):
            add("Feshin geçersizliğinin tespitine ve müvekkilin işe iadesine")
        if "bos_sure" in claims and not any(re.search(r"boşta geçen", r, re.I) for r in out):
            add("Boşta geçen süre ücretine (miktar formda yoksa yazılmaz)")
        if "baslatmama" in claims and not any(re.search(r"işe başlatmama", r, re.I) for r in out):
            add("İşe başlatmama tazminatına (miktar formda yoksa yazılmaz)")
        if "kidem" in claims and not any(re.search(r"kıdem", r, re.I) for r in out):
            add("Kıdem tazminatına")
        if "ihbar" in claims and not any(re.search(r"ihbar", r, re.I) for r in out):
            add("İhbar tazminatına")
        if "fazla" in claims and not any(re.search(r"fazla", r, re.I) for r in out):
            add("Fazla çalışma ücretine")
        if not any(re.search(r"ücret|kıdem|ihbar|mesai|izin|alaca|işe iade", r, re.I) for r in out):
            add(labor_wage_claim(form))
    if "Boşanma" in ptype:
        if not any("boşan" in r.lower() for r in out):
            add("Tarafların TMK m. 166 uyarınca boşanmalarına")
        if child and not any("velayet" in r.lower() for r in out):
            add("Müşterek çocuğun velayetinin davacıya bırakılmasına")
        if child and not any("iştirak" in r.lower() for r in out):
            ist = _claim_amount(form, "istirak", "iştirak")
            add(
                f"Müşterek çocuk yararına aylık {ist} iştirak nafakasına"
                if ist
                else "Müşterek çocuk yararına iştirak nafakasına (miktarın takdiri mahkemeye aittir)"
            )
        if any(w in low for w in ("nafaka", "tedbir", "yoksul")) or child:
            yok = _claim_amount(form, "yoksulluk", "yoksulluk")
            if not any("yoksulluk" in r.lower() for r in out) and ("yoksul" in low or "nafaka" in low or yok or child):
                add(
                    f"Davacı yararına aylık {yok} yoksulluk nafakasına"
                    if yok
                    else "Davacı yararına yoksulluk nafakasına (miktarın takdiri mahkemeye aittir)"
                )
    elif not out:
        for r in pack.get("requests") or []:
            for piece in _split_combo_claim(r):
                add(piece)

    _separate_money_claims(out, seen, add, form, low, child)
    filled = _apply_claim_amounts(out, form)
    done = [_soften_nafaka(r) for r in filled if not _is_blank_money(r)]
    if is_labor(form):
        fixed: list[str] = []
        for r in done:
            if re.search(r"ücret|işçilik alacak", r, re.I) and not re.search(r"faiz", r, re.I):
                r = r.rstrip(" .") + (
                    "; 4857 sayılı Kanun m. 34 uyarınca mevduata uygulanan en yüksek faiziyle tahsiline"
                )
            fixed.append(r)
        done = fixed
    return done


def _soften_nafaka(line: str) -> str:
    t = (line or "").strip()
    if not re.search(r"nafaka", t, re.I):
        return t
    if re.search(r"\d.+\s*TL", t, re.I) and not re.search(r"\.{5,}\s*TL", t):
        return t
    if re.search(r"\.{5,}\s*TL", t):
        t = re.sub(r"(?i)aylık\s*", "", t, count=1)
        t = re.sub(r"\.{5,}\s*TL\s*", "", t)
        if "takdir" not in t.lower():
            t = t.rstrip(" .") + " (miktarın takdiri mahkemeye aittir)"
        return re.sub(r"\s+", " ", t).strip()
    return t


def _split_combo_claim(line: str) -> list[str]:
    t = _clean_req(line)
    low = t.lower()
    if re.search(r"maddi[\s/\-]*(ve[\s/\-]*)?manevi", low):
        madde = " (TMK m. 174)" if "174" in t or "tmk" in low else ""
        return [f"{_blank_tl()} maddi tazminata{madde}", f"{_blank_tl()} manevi tazminata{madde}"]
    if re.search(r"kıdem\s+ve\s+ihbar", low):
        return [f"{_blank_tl()} kıdem tazminatının tahsiline", f"{_blank_tl()} ihbar tazminatının tahsiline"]
    if re.search(r"tedbir\s+ve\s+yoksulluk", low):
        return []
    if re.search(r"fazla mesai.*yıllık izin|ubgt.*yıllık izin", low):
        return [
            f"{_blank_tl()} fazla mesai ücretinin tahsiline",
            f"{_blank_tl()} UBGT ücretinin tahsiline",
            f"{_blank_tl()} yıllık izin ücretinin tahsiline",
        ]
    return [t] if t else []


def _separate_money_claims(
    out: list[str],
    seen: set[str],
    add,
    form: dict,
    low: str,
    child: bool,
) -> None:
    ptype = str(form.get("petitionType") or "")
    combined = [r for r in list(out) if re.search(r"maddi[\s/\-]*(ve[\s/\-]*)?manevi", r, re.I)]
    for r in combined:
        out.remove(r)
        seen.discard(re.sub(r"\s+", " ", r.lower()))
    if wants_tazminat(form):
        madde = " (TMK m. 174)" if "Boşanma" in ptype else ""
        maddi = _claim_amount(form, "maddi", "maddi tazminat")
        manevi = _claim_amount(form, "manevi", "manevi tazminat")
        if maddi and not any(re.search(r"maddi tazminat", r, re.I) for r in out):
            add(f"{maddi} maddi tazminata{madde}")
        if manevi and not any(re.search(r"manevi tazminat", r, re.I) for r in out):
            add(f"{manevi} manevi tazminata{madde}")

    vague_tedbir = [
        r
        for r in list(out)
        if re.search(r"tedbir nafaka", r, re.I)
        and not re.search(r"davacı|müvekkil|çocuk|müşterek", r, re.I)
    ]
    for r in vague_tedbir:
        out.remove(r)
        seen.discard(re.sub(r"\s+", " ", r.lower()))
    need_tedbir = "Boşanma" in ptype and (
        any(w in low for w in ("nafaka", "tedbir", "yoksul")) or child or vague_tedbir
    )
    if need_tedbir:
        td = _claim_amount(form, "tedbirDavaci", "tedbir nafaka")
        tc = _claim_amount(form, "tedbirCocuk", "çocuk.*tedbir", "müşterek.*tedbir")
        if td and not any(re.search(r"tedbir nafaka.*davacı|davacı.*tedbir nafaka|müvekkil.*tedbir nafaka", r, re.I) for r in out):
            add(f"Yargılama süresince davacı yararına aylık {td} tedbir nafakasına")
        if child and tc and not any(re.search(r"(çocuk|müşterek).*tedbir nafaka|tedbir nafaka.*(çocuk|müşterek)", r, re.I) for r in out):
            add(f"Yargılama süresince müşterek çocuk yararına aylık {tc} tedbir nafakasına")

    zrows = _ziynet_rows(form)
    ztot = _claim_amount(form, "ziynetToplam", "ziynet")
    if zrows or ztot or any(w in low for w in ("ziynet", "altın", "bilezik")):
        out[:] = [r for r in out if not re.search(r"ziynet|altın|bilezik", r, re.I)]
        seen.clear()
        for r in list(out):
            seen.add(re.sub(r"\s+", " ", r.lower()))
        tot_bit = f" (toplam rayiç {ztot})" if ztot else ""
        add(
            f"Aşağıda dökümü verilen ziynet eşyalarının{tot_bit} aynen iadesine, "
            "mümkün olmaması halinde rayiç bedelinin yasal faiziyle tahsiline"
        )

    cv = _claim_vals(form)
    extras = (
        ("kidem", r"kıdem", "{0} kıdem tazminatının tahsiline"),
        ("ihbar", r"ihbar", "{0} ihbar tazminatının tahsiline"),
        ("fazlaMesai", r"fazla mesai", "{0} fazla mesai ücretinin tahsiline"),
        ("ubgt", r"ubgt", "{0} UBGT ücretinin tahsiline"),
        ("yillikIzin", r"yıllık izin", "{0} yıllık izin ücretinin tahsiline"),
        ("alacak", r"asıl alacak|alacağın tahsil", "{0} asıl alacağın tahsiline"),
        ("yoksulluk", r"yoksulluk", "Davacı yararına aylık {0} yoksulluk nafakasına"),
        ("istirak", r"iştirak", "Müşterek çocuk yararına aylık {0} iştirak nafakasına"),
    )
    for key, needle, tmpl in extras:
        if cv.get(key) and not any(re.search(needle, r, re.I) for r in out):
            add(tmpl.format(cv[key]))


def _needs_harc(form: dict, reqs: list[str]) -> bool:
    blob = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests"), " ".join(reqs)]
    ).lower()
    if "İdare" in str(form.get("petitionType") or "") and not wants_tazminat(form):
        return False
    if "Ceza" in str(form.get("petitionType") or "") and not wants_tazminat(form):
        return False
    return bool(
        re.search(
            r"tazminat|ziynet|alacak|kıdem|ihbar|bedel|ink[aâ]r|fazla mesai|yıllık izin",
            blob,
        )
    )


def _harc_line(form: dict, reqs: list[str]) -> str:
    summed = _nispi_sum(form, reqs)
    if summed:
        return summed
    blob = " ".join([_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests"), " ".join(reqs)])
    m = re.search(r"harca\s+esas[^\d]{0,20}(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)\s*(?:TL|₺)?", blob, re.I)
    if m:
        return _fmt_user_tl(m.group(1))
    if _needs_harc(form, reqs):
        return _blank_tl()
    return ""


def _claim_labels(form: dict, reqs: list[str]) -> list[str]:
    blob = " ".join(
        [_field(form, "caseSummary"), _field(form, "extraInstructions"), _field(form, "requests"), " ".join(reqs)]
    ).lower()
    pairs = (
        ("boşan", "boşanma"),
        ("velayet", "velayet"),
        ("iştirak", "iştirak nafakası"),
        ("tedbir nafaka", "tedbir nafakası"),
        ("yoksulluk", "yoksulluk nafakası"),
        ("maddi tazminat", "maddi tazminat"),
        ("manevi tazminat", "manevi tazminat"),
        ("ziynet", "ziynet alacağı"),
        ("işe iade", "işe iade"),
        ("kıdem", "kıdem tazminatı"),
        ("ihbar", "ihbar tazminatı"),
        ("fazla mesai", "fazla mesai alacağı"),
        ("itirazın iptali", "itirazın iptali"),
        ("tahliye", "tahliye"),
        ("ayıplı", "ayıplı mal"),
    )
    out: list[str] = []
    for key, lab in pairs:
        if key in blob and lab not in out:
            out.append(lab)
    if (
        wants_tazminat(form)
        and re.search(r"maddi\s+tazminat|manevi\s+tazminat", blob)
        and "maddi tazminat" not in out
        and "manevi tazminat" not in out
    ):
        out.append("maddi-manevi tazminat")
    if is_labor(form) and not wants_tazminat(form):
        out[:] = [x for x in out if "tazminat" not in x or "kıdem" in x or "ihbar" in x]
    return out


def _konu_line(form: dict, pack: dict, reqs: list[str]) -> str:
    ptype = str(form.get("petitionType") or "")
    bits = _claim_labels(form, reqs)
    if "Boşanma" in ptype:
        if _divorce_ground(form) == "164":
            konu = "Türk Medeni Kanunu’nun 164. maddesi uyarınca terke dayalı boşanma"
        else:
            konu = (
                "Türk Medeni Kanunu’nun 166/1. maddesi uyarınca evlilik birliğinin "
                "temelinden sarsılması nedeniyle boşanma"
            )
        extra = [b for b in bits if b != "boşanma"]
        if extra:
            konu += ", " + ", ".join(extra)
        return konu + " davasıdır."
    if is_labor(form):
        return labor_konu(form)
    if "İdare" in ptype:
        act = str(form.get("_idare_act") or _extract_idare_act(form) or "").strip()
        act = re.sub(r"(?i)\s+işlemin$", " işlem", act).strip() or "iptali istenen idari işlem"
        if re.search(r"(?i)işlem$", act):
            act_bit = act + "inin"
        elif re.search(r"(?i)kararı$", act):
            act_bit = act + "nın"
        else:
            act_bit = act + " işleminin"
        flags = _urgent_flags(form)
        src = _source_blob(form)
        who = ""
        if re.search(r"(?i)infaz ve koruma|3\.?500|sözleşmeli personel", src):
            who = (
                "Müvekkilin sözleşmeli infaz ve koruma memuru olarak görevlendirilmesinin "
                "uygun olmadığına dair "
            )
        bits = [f"{who}{act_bit} iptali"]
        if flags.get("yd"):
            bits.append("yürütmenin durdurulması")
        if flags.get("adli"):
            bits.append("adli yardım")
        if wants_tazminat(form):
            bits.append("tam yargı")
        if len(bits) == 1:
            return bits[0] + " talebidir."
        return bits[0] + " ile " + " ve ".join(bits[1:]) + " talebidir."
    konu = str(pack.get("konu") or "Aşağıda açıklanan vakıalara dayalı talep dilekçesidir.")
    extra = [b for b in bits if b not in konu.lower()]
    if extra:
        konu = konu.rstrip(".") + "; talepler: " + ", ".join(extra) + "."
    return konu


def _polish_tr(text: str) -> str:
    t = text or ""
    t = t.replace("alışkanlıklıklarla", "alışkanlıklarla")
    t = t.replace("Alışkanlıklıklarla", "Alışkanlıklarla")
    reps = (
        ("herşey", "her şey"),
        ("Herşey", "Her şey"),
        ("birşey", "bir şey"),
        ("Birşey", "Bir şey"),
        ("hiç bir", "hiçbir"),
        ("Hiç bir", "Hiçbir"),
        ("bir çok", "birçok"),
        ("Bir çok", "Birçok"),
        ("her hangi", "herhangi"),
        ("Her hangi", "Herhangi"),
        ("vekaleten", "vekâleten"),
        ("Vekaleten", "Vekâleten"),
        ("vekaletname", "vekâletname"),
        ("Vekaletname", "Vekâletname"),
        ("vekalet ", "vekâlet "),
        ("resmi evrak", "resmî evrak"),
        ("Resmi Gazete", "Resmî Gazete"),
        ("resmi gazete", "Resmî Gazete"),
        ("hakim ", "hâkim "),
        ("Hakim ", "Hâkim "),
        ("taleb ederim", "talep ederim"),
        ("içtihad ", "içtihat "),
    )
    for a, b in reps:
        t = t.replace(a, b)

    def _iyelik(m: re.Match[str]) -> str:
        w = m.group(1)
        name = w[:1].upper() + w[1:] if w[:1].islower() else w
        return name + "'ın"

    t = re.sub(r"\b([A-Za-zÇĞİÖŞÜçğıöşü]{3,})\s+[ıi]n\b", _iyelik, t)
    t = re.sub(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+[ıi]nın\b", r"\1'ının", t)
    t = re.sub(r"(?i)(?:^|(?<=[.!?]\s))[^.]*boşanmak istiyorum[^.]*\.?\s*", "", t)
    t = re.sub(r"(?i)\s*Nihayet\s+[^.]*istiyorum[^.]*\.?", "", t)
    t = re.sub(r"(?im)^\s*DAVA D[İI]LEK[ÇC]ES[İI]\s*$\n?", "", t)
    t = strip_template_notes(t)
    t = reconcile_date_span(t)
    kept: list[str] = []
    for para in re.split(r"\n{2,}", t):
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        clean = [s for s in sents if not _is_petition_question(s) and not _is_prompt_block(s)]
        if clean:
            kept.append(" ".join(clean))
    t = "\n\n".join(kept) if kept else t
    t = re.sub(r"(?i)\s*Bu süreçte\s+", " ", t)
    t = re.sub(r"(?i)\s*;\s*müteakiben\s+", ". ", t)
    return _strip_instr_leaks(_strip_portal_junk(t))


def _reason_tr_pass(text: str) -> str:
    raw = (text or "").strip()
    if len(raw) < 48:
        return _polish_tr(raw)
    if _is_27b() and not _server_health():
        emit("status", "4/4 Türkçe editör: sunucu kapalı, yalnızca yazım düzeltmesi.")
        emit("research", "Türkçe editör atlandı (27B sunucusu yok; kilitlenmesin).")
        return _polish_tr(raw)
    emit("status", "4/4 Türkçe editör turu: anlatım ve yazım denetleniyor…")
    emit("research", "Türkçe editör: özne-yüklem, bağlaç, hukuki karşılık, TDK.")
    guide = TR_REASON or "Türkçe muhakeme et; TDK yazımına uy; anlamı değiştirme."
    out = generate(
        [
            {
                "role": "system",
                "content": (
                    "Sen kıdemli bir Türk hukuk yazım editörüsün. Vakıayı, ismi, tutarı ve "
                    "karar numarasını değiştirmezsin. Yalnızca Türkçe muhakeme ederek cümleyi "
                    "düzeltirsin. Talimat sızdırmazsın. Yanıtın yalnızca düzeltilmiş metin olsun."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{guide}\n\nAşağıdaki metni aynı hukuki içeriği koruyarak yeniden yaz. "
                    "Yeni vakıa ekleme. Yalnızca düzeltilmiş metni yaz.\n\n"
                    + raw[:12000]
                ),
            },
        ],
        n_predict=min(2048, max(400, len(raw) // 2 + 240)),
        n_ctx=CHAT_CTX,
        live=False,
        busy="Türkçe editör turu…",
        think=False,
    )
    out = _polish_tr(_fix_word_spacing(_usable_text(out) or _clean_llama_out(out) or ""))
    if len(out) < max(80, int(len(raw) * 0.45)):
        emit("status", "Türkçe editör kısa kaldı; ilk metin yazımla düzeltildi.")
        return _polish_tr(raw)
    emit("status", "Türkçe editör turu bitti.")
    return out


def _chrono_sents(sents: list[str]) -> list[str]:
    aylar = {
        "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
        "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
    }

    def key(s: str) -> tuple[int, int, int]:
        m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s or "")
        if m:
            return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.search(r"(\d{1,2})\s+(ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\s+(\d{4})", s or "", re.I)
        if m:
            return (int(m.group(3)), aylar.get(m.group(2).lower(), 12), int(m.group(1)))
        m = re.search(r"\b((?:19|20)\d{2})\b", s or "")
        if m:
            return (int(m.group(1)), 6, 15)
        return (9999, 12, 31)

    dated = [s for s in sents if key(s)[0] < 9999]
    rest = [s for s in sents if key(s)[0] == 9999]
    return sorted(dated, key=key) + rest


def _plot_why(facts: str, extra: str, reqs: str, ptype: str = "") -> str:
    blob = f"{facts} {extra} {reqs}".lower()
    by_type = {
        "İş": "işçilik alacaklarının ödenmemesi ve fesih olgusu",
        "Alacak": "muaccel alacağın ifa edilmemesi",
        "İcra": "icra takibine vaki itiraz",
        "İdare": "idari işlemin hukuka aykırılığı",
        "Tazminat": "haksız fiil / sözleşmeye aykırılık nedeniyle doğan zarar",
        "Ceza": "suçtan zarar görme ve katılma talebi",
        "Kira": "kira ilişkisinden kaynaklanan tahliye ve alacak",
        "Tüketici": "ayıplı mal veya hizmet",
    }
    for key, why in by_type.items():
        if key in (ptype or ""):
            return why
    bits: list[str] = []
    if any(w in blob for w in ("aldat", "zina", "sadakat")):
        bits.append("davalının sadakat yükümlülüğüne aykırı tutumu")
    if any(w in blob for w in ("hakaret", "yaralama", "6284", "aile içi şiddet", "fiziksel şiddet")):
        bits.append("hakaret ve şiddet olguları")
    if any(w in blob for w in ("geçimsiz", "çekilmez", "sarsıl")):
        bits.append("ortak hayatın çekilmez hâle gelmesi")
    if not bits:
        bits.append("somut vakıalara dayalı hukuki uyuşmazlık")
    if len(bits) == 1:
        return bits[0]
    return ", ".join(bits[:-1]) + " ve " + bits[-1]


def _prefer_chamber_rows(ptype: str, rows: list[dict]) -> list[dict]:
    ranked = _rank_cite_rows(rows)
    cites = _prefer_chamber_cites(ptype, [_row_kunye(r) for r in ranked])
    by_key = {_row_kunye(r): r for r in ranked}
    out = [by_key[c] for c in cites if c in by_key]
    if out:
        return out
    return ranked[:8]


def _bind_holdings_to_rows(rows: list[dict], holdings: list[str]) -> list[dict]:
    """Gerekçeyi aynı davanın künyesine bağlar; başka karardan cümle yapıştırmaz."""
    used: set[int] = set()
    for r in rows:
        ozet = str(r.get("ozet") or "").strip()
        if _dayanak_expl(ozet):
            r["ozet"] = _dayanak_expl(ozet)
            continue
        esas = str(r.get("esas") or "")
        karar = str(r.get("karar") or "")
        doc = str(r.get("documentId") or "")
        for i, h in enumerate(holdings or []):
            if i in used or not h:
                continue
            if esas and esas in h:
                clean = _dayanak_expl(h)
                if clean:
                    r["ozet"] = clean
                    used.add(i)
                    break
            if karar and karar in h:
                clean = _dayanak_expl(h)
                if clean:
                    r["ozet"] = clean
                    used.add(i)
                    break
            if doc and doc in h:
                clean = _dayanak_expl(h)
                if clean:
                    r["ozet"] = clean
                    used.add(i)
                    break
    return rows


def _prefer_chamber_cites(ptype: str, cites: list[str]) -> list[str]:
    # Yargıtay BGK 2026/1 (RG 30.06.2026 / 33296): daire ihtisasları.
    want = {
        "Boşanma": r"2\.\s*(Hukuk|HD)|Hukuk Genel Kurulu",
        "İş": r"(9|10|22)\.\s*(Hukuk|HD)",
        "Alacak": r"(3|6|11)\.\s*(Hukuk|HD)",
        "İcra": r"12\.\s*(Hukuk|HD)",
        "İdare": r"Danıştay",
        "Tazminat": r"4\.\s*(Hukuk|HD)",
        "Ceza": r"Ceza",
        "Kira": r"3\.\s*(Hukuk|HD)",
        "Tüketici": r"(3|13)\.\s*(Hukuk|HD)",
    }
    if "İdare" in (ptype or ""):
        ranked = _prefer_recent_cites(cites)
        hit = [
            c
            for c in ranked
            if re.search(r"Danıştay|Anayasa Mahkemesi|\bAYM\b", c, re.I)
            and not re.search(r"VDDK|Vergi Dava", c, re.I)
        ]
        return hit[:8]
    pat = next((p for k, p in want.items() if k in (ptype or "")), "")
    ranked = _prefer_recent_cites(cites)
    if pat:
        hit = [c for c in ranked if re.search(pat, c, re.I)]
        if hit:
            return hit[:8]
    return ranked[:8]


def _cite_year(row_or_text: dict | str) -> int:
    if isinstance(row_or_text, dict):
        blob = " ".join(
            str(row_or_text.get(k) or "")
            for k in ("tarih", "esas", "karar", "kaynak", "kunye")
        )
    else:
        blob = str(row_or_text or "")
    years = [int(x) for x in re.findall(r"\b(20\d{2}|19\d{2})\b", blob)]
    return max(years) if years else 0


def _prefer_recent_cites(cites: list[str]) -> list[str]:
    recent = [c for c in cites if _cite_year(c) >= 2020]
    pool = recent or list(cites)
    return sorted(pool, key=_cite_year, reverse=True)


def _rank_cite_rows(rows: list[dict]) -> list[dict]:
    recent = [r for r in rows if _cite_year(r) >= 2020]
    pool = recent or list(rows)
    return sorted(pool, key=lambda r: (_cite_year(r), 1 if r.get("ozet") else 0), reverse=True)


def _prefer_family_cites(cites: list[str]) -> list[str]:
    return _prefer_chamber_cites("Boşanma", cites)


def _clean_holding(text: str) -> str:
    if _is_portal_junk(text or ""):
        return ""
    t = re.sub(r"\s+", " ", _strip_portal_junk(text or "")).strip()
    t = re.sub(r"^(SONUÇ|HÜKÜM|GEREKÇE)\s*[:.]?\s*", "", t, flags=re.I)
    t = re.sub(r"(?i)işbu (karar|dava)[^.]*\.", "", t)
    t = t.strip(" .;")
    if len(t) < 40:
        return ""
    cut = t[:240]
    if "." in cut:
        cut = cut.rsplit(".", 1)[0]
    return cut.strip() + "."


_ADVERSE_HOLD = re.compile(
    r"(?i)davan[ıi]n reddi|davan[ıi]n redine|incelenmesine (imkan|imkân) bulunmad|"
    r"kesin ve y[uü]r[uü]t[uü]lebilir.{0,50}olmad[ıi][gğ]|"
    r"14/3|15/1-b|esas[ıi]n[ıi]n incelenmesine"
)


def _holding_helps(text: str, ptype: str, blob: str = "") -> bool:
    t = text or ""
    if not t or _ADVERSE_HOLD.search(t):
        return False
    if "İdare" in (ptype or ""):
        if re.search(r"(?i)7315|g[uü]venlik soru[sş]tur|sebep unsur|soyut gerek[cç]e|"
                     r"atama uygunluk|[oö]l[cç][uü]l[uü]l[uü]k|iptal", t):
            return True
        return "hukuka aykırı" in t.lower()
    return True


def _filter_cites(form: dict, cites: list[str], holdings: list[str]) -> tuple[list[str], list[str]]:
    ptype = str(form.get("petitionType") or "")
    blob = _source_blob(form)
    cites = _prefer_chamber_cites(ptype, cites)
    good_h = [h for h in (holdings or []) if _holding_helps(h, ptype, blob)]
    good_c: list[str] = []
    for c in cites:
        if _ADVERSE_HOLD.search(c):
            continue
        good_c.append(c)
    if not good_h:
        good_h = [h for h in (holdings or []) if not _ADVERSE_HOLD.search(h or "")]
    if "İdare" in ptype and not good_h:
        return [], []
    return good_c[:4], good_h[:4]


def _emsal_in_flow(cites: list[str], holdings: list[str], ptype: str, form: dict | None = None) -> str:
    if form:
        cites, holdings = _filter_cites(form, cites, holdings)
    else:
        cites = _prefer_chamber_cites(ptype, cites)
        holdings = [h for h in (holdings or []) if not _ADVERSE_HOLD.search(h or "")]
    if not cites:
        if "İdare" in (ptype or ""):
            return (
                "Danıştay’ın yerleşik uygulamasına göre güvenlik soruşturmasına dayanan olumsuz "
                "işlemin sebep unsuru somut, denetime elverişli ve ölçülü gerekçeye dayanmalıdır. "
                "Soyut “görevlendirmeye engel veri” ifadesi bu ölçütü karşılamaz. "
                "Esas ve karar numarası çekilmemişse yazılmaz."
            )
        return ""
    pieces: list[str] = []
    for i, cite in enumerate(cites[:2]):
        hold = _clean_holding(holdings[i]) if i < len(holdings) else ""
        if hold and not _holding_helps(hold, ptype):
            hold = ""
        if "Boşanma" in ptype:
            sent = (
                f"{cite} sayılı kararda, evlilik birliğinin temelinden sarsılması ve ortak hayatın "
                "eşlerden biri bakımından çekilmez hâle gelmesi hâlinde boşanmaya hükmedileceği kabul edilmiştir."
            )
        elif "İş" in ptype:
            sent = (
                f"{cite} sayılı kararda, 4857 sayılı Kanun m. 32 uyarınca ücretin zamanında ödenmesi "
                "gerektiği ve işçilik alacağının haksız fiil tazminatı değil iş sözleşmesinden doğan "
                "alacak olduğu kabul edilmiştir."
            )
        elif "İdare" in ptype:
            sent = (
                f"{_kunye_tr(cite)} sayılı kararda, idari işlemin sebep unsurunun somut, denetime "
                "elverişli ve ölçülü gerekçeye dayanması gerektiği kabul edilmiştir."
            )
        else:
            sent = f"{cite} sayılı karardaki ilke somut olaya da uygundur."
        if hold and not re.search(r"HTTP |alınamadı|error", hold, re.I):
            h = hold[0].lower() + hold[1:] if hold[:1].isupper() else hold
            sent += f" Anılan kararın gerekçesinde {h}"
            if not sent.endswith("."):
                sent += "."
        pieces.append(sent)
    lead = (
        "Danıştay’ın yerleşik uygulaması da aynı yöndedir. "
        if "İdare" in (ptype or "")
        else "Yargıtay’ın yerleşik uygulaması da aynı yöndedir. "
    )
    if len(pieces) > 1:
        lead += pieces[0] + " Aynı doğrultuda " + pieces[1][0].lower() + pieces[1][1:]
    else:
        lead += pieces[0]
    return lead + " Bu ilkeler, somut olaya da uygulanmalıdır."


def _pick_sents(sents: list[str], keys: tuple[str, ...]) -> list[str]:
    return [s for s in sents if any(k in s.lower() for k in keys)]


def _labor_narrative(form: dict, pack: dict, research: str) -> str:
    facts = _field(form, "caseSummary", "case_summary")
    extra = _field(form, "extraInstructions", "extra")
    reqs = _field(form, "requests")
    sents = _chrono_sents(_all_fact_sentences(facts, extra))
    cites = _prefer_chamber_cites("İş Davası", _extract_cites(research))
    mem = _CASE_MEMORY or _load_case_memory()
    holds = list(mem.get("holdings") or _extract_ozetler(research) or [])
    blocks: list[str] = []
    n = 1

    def add(title: str, body: str) -> None:
        nonlocal n
        body = reconcile_date_span(_strip_disclaimers(_strip_book_subs(body)))
        if not body or len(body) < 24:
            return
        blocks.append(f"{n}- {title.rstrip(' :')}:\n\n{body}")
        n += 1

    dayanak = _hukuki_nedenler_line(form, pack)
    add(
        "Davanın hukuki dayanağı",
        "İşbu dava, iş sözleşmesinden / iş ilişkisinden doğan işçilik alacağıdır; "
        "haksız fiile dayalı maddi veya manevi tazminat davası değildir. "
        f"Dayanak: {dayanak} "
        "Görevli mahkeme İş Mahkemesi’dir. "
        "Ücret kural olarak ayda bir ödenir; gününde ödenmeyen ücrete 4857 m. 34 uyarınca "
        "bankalarca mevduata uygulanan en yüksek faiz yürütülür. "
        "Alacak kalemi henüz tam belirlenememişse talep HMK m. 107 anlamında belirsiz "
        "alacak olarak ileri sürülür; tutar formda yoksa uydurulmaz.",
    )
    work = _pick_sents(
        sents,
        ("iş", "ücret", "maaş", "çalış", "tarih", "işveren", "iş yeri", "pozisyon", "görev", "sgk"),
    )
    if work:
        add(
            "İş ilişkisi ve süre",
            _weave_facts(work)
            + " Çalışma süresi ile ödenmeyen ücret dönemi aynı şey değildir. "
            "Hangi ayların ödenmediği ve fesih şekli formda yazılmamışsa uydurulmaz.",
        )
    unpaid = _pick_sents(sents, ("öden", "alamad", "ücret", "maaş", "alacak", "aylık"))
    leftover = [s for s in sents if s not in work]
    plot = unpaid or leftover or sents
    if plot:
        add(
            "Ödenmeyen ücret alacağı",
            _weave_facts(plot)
            + " Talep, maddi/manevi tazminat değil ücret alacağıdır. "
            "Net/brüt ücret ve ödenmeyen ay sayısı formda yoksa hesap uydurulmaz.",
        )
    emsal = _emsal_in_flow(cites, holds, "İş Davası", form)
    add(
        "Hukuki nitelendirme",
        "Açıklanan vakıalar, 4857 sayılı Kanun m. 32 uyarınca muaccel ücret alacağını "
        "ve 7036 sayılı Kanun m. 5 uyarınca İş Mahkemesi’nin görevini göstermektedir. "
        + (emsal or "Yargıtay 9. ve 22. Hukuk Dairelerinin yerleşik uygulaması da bu yöndedir."),
    )
    _add_usul_vakia(add, form)
    return "\n\n".join(blocks)


def _idare_fact_bits(blob: str) -> dict[str, str]:
    t = blob or ""
    out = {"para": "", "yil": "", "aile": False, "denetim": "", "ozet_madde": ""}
    m = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*TL\s+adli para", t, re.I)
    if not m:
        m = re.search(r"adli para[^\d]{0,28}(\d{1,3}(?:\.\d{3})*)\s*TL", t, re.I)
    if m:
        out["para"] = m.group(1) + " TL"
    if re.search(r"(?i)aile\s+i[cç]i|aile çevresi|münferit", t):
        out["aile"] = True
    m = re.search(r"(?:üzerinden\s+)?(?:yaklaşık\s+)?(\d)\s+yıl(?!\s*denetim)", t, re.I)
    if m:
        out["yil"] = m.group(1)
    m = re.search(r"(\d)\s+yıl(?:lık)?\s+denetim", t, re.I)
    if m:
        out["denetim"] = m.group(1)
    mem = _CASE_MEMORY or _load_case_memory()
    ozets = []
    for s in (mem.get("statutes") or [])[:4]:
        if isinstance(s, dict) and s.get("ok") and s.get("label") and s.get("ozet"):
            ozets.append(f"{s['label']}: {str(s['ozet'])[:220].rstrip(' .')}." )
    out["ozet_madde"] = " ".join(ozets[:3])
    return out


def _acm_facts(blob: str) -> dict[str, str]:
    out = {"court": "", "esas": "", "karar": "", "date": ""}
    m = re.search(r"((?:Erzurum|Ankara|İstanbul|İzmir|[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+\d+\.\s*Asliye Ceza Mahkemesi)", blob or "", re.I)
    if m:
        out["court"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(
        r"(\d{4})\s*/\s*(\d+)\s*(?:E(?:sas)?\.?|Esas)[^\d]{0,28}(\d{4})\s*/\s*(\d+)\s*(?:K(?:arar)?\.?|Karar)",
        blob or "",
        re.I,
    )
    if m:
        out["esas"] = f"{m.group(1)}/{m.group(2)}"
        out["karar"] = f"{m.group(3)}/{m.group(4)}"
    else:
        m = re.search(r"(\d{4})\s*/\s*(\d+)\s*E[^\d]{0,16}(\d{4})\s*/\s*(\d+)\s*K", blob or "", re.I)
        if m:
            out["esas"] = f"{m.group(1)}/{m.group(2)}"
            out["karar"] = f"{m.group(3)}/{m.group(4)}"
    m = re.search(r"(?:karar tarihi|karar tarihi:)\s*(\d{1,2}[./]\d{1,2}[./]\d{4})", blob or "", re.I)
    if m:
        out["date"] = m.group(1)
    return out


def _idare_narrative(form: dict, pack: dict, research: str) -> str:
    blob = _source_blob(form)
    davaci, davali = _resolved_parties(form)
    davaci = _strip_party_label(davaci) or "müvekkil"
    if re.search(r"(?i)^ad\s*soyad$", davaci.strip()):
        people = _extract_person_names(blob)
        davaci = next((p for p in people if not re.search(r"(?i)^ad\s*soyad$", p)), "müvekkil")
    davali = _short_admin(_strip_party_label(davali) or "davalı idare") or "davalı idare"
    act = str(form.get("_idare_act") or _extract_idare_act(form) or "iptali istenen idari işlem")
    acm = _acm_facts(blob)
    hagb = bool(re.search(r"(?i)HAGB|hükmün açıklanmasının geri", blob))
    beraat = bool(re.search(r"(?i)hakaret.{0,60}beraat|beraat.{0,40}hakaret", blob))
    yaralama = bool(re.search(r"(?i)kasten yaralama", blob))
    kadro = bool(re.search(r"(?i)infaz ve koruma|3\.?500|sözleşmeli personel", blob))
    cites, holds = _filter_cites(
        form,
        (_CASE_MEMORY or _load_case_memory()).get("cites") or _extract_cites(research),
        (_CASE_MEMORY or _load_case_memory()).get("holdings") or _extract_ozetler(research),
    )
    emsal = _emsal_in_flow(cites, holds, "İdare Hukuku", form)
    blocks: list[tuple[str, list[str]]] = []

    def add(title: str, body: str) -> None:
        body = re.sub(r"\s+", " ", (body or "")).strip()
        if len(body) < 40:
            return
        title = title.rstrip(" :")
        if blocks and blocks[-1][0] == title:
            blocks[-1][1].append(body)
        else:
            blocks.append((title, [body]))

    bits = _idare_fact_bits(blob)
    labs = _statute_labels()
    dayanak = ", ".join(labs) if labs else "2577 sayılı İYUK m. 2, m. 3, m. 7 ve Anayasa m. 36, m. 40, m. 70"
    dayanak_body = (
        f"İşbu dava, {dayanak} uyarınca {act} iptali istemiyle açılmıştır. "
        "Dilekçe İYUK m. 3 şekil kurallarına uygundur. HMK m. 119 idari yargıda uygulanmaz. "
        "Anayasa’nın 36. maddesindeki hak arama hürriyeti, 40. maddesindeki etkili başvuru "
        "ve 70. maddesindeki kamu hizmetine girme hakkı somut uyuşmazlığın anayasal zeminidir."
    )
    if bits.get("ozet_madde"):
        dayanak_body += " Çekilen resmi madde özetleri: " + bits["ozet_madde"]
    hire = _extract_admin_name(blob)
    if hire and _looks_public(davali) and _short_admin(hire).split("(")[0].strip() not in davali:
        kadro_idare = _short_admin(hire)
    else:
        kadro_idare = davali
    act_noun = re.sub(r"(?i)\s+işlemin$", " işlem", act).strip()
    if kadro:
        add(
            "DAVANIN KONUSU: DAVA KONUSU İŞLEMİN TESPİTİ",
            f"Müvekkil, {kadro_idare} bünyesinde ilan edilen sözleşmeli infaz ve koruma "
            "memuru alımı kapsamında görevlendirilmek üzere başvurmuştur. Güvenlik soruşturması "
            "ve arşiv araştırması 7315 sayılı Kanun uyarınca yapılmıştır. Müvekkilin bu alıma "
            "ilişkin hukuki yararı, işlemin görevlendirmeyi engellemesiyle somutlaşmıştır.",
        )
    add(
        "DAVANIN KONUSU: DAVA KONUSU İŞLEMİN TESPİTİ",
        f"İptal davasının konusu, {davali} tarafından tesis edilen {act_noun}dir. "
        "İşlem, 7315 sayılı Kanun kapsamında oluşan değerlendirme üzerine, elde edilen verinin "
        "görevlendirmeye engel nitelikte olduğu gerekçesine dayandırılmıştır. "
        "Dava açma süresi İYUK m. 7 (ve varsa m. 11) çerçevesinde tebliğden itibaren hesaplanır. "
        "İşlem, idarenin tek yanlı, kesin ve yürütülmesi gereken tasarrufudur.",
    )
    ceza = (
        f"{(acm['court'] + ' ').lstrip()}"
        + (f"{acm['esas']} E. " if acm["esas"] else "")
        + (f"{acm['karar']} K. " if acm["karar"] else "")
        + (f"({acm['date']}) " if acm["date"] else "")
    ).strip()
    if ceza or hagb or yaralama or beraat:
        ceza_bits = [
            "Ceza mahkemesi kararı idari işlem değildir; varsa yalnızca sebep unsurunda "
            "değerlendirilen bir olgudur."
        ]
        if ceza:
            ceza_bits.append(f"Dosyada {ceza} sayılı yargılama bulunmaktadır.")
        if yaralama:
            ceza_bits.append("Yargılamada basit kasten yaralama vakıası yer almaktadır.")
        if beraat:
            ceza_bits.append("Hakaret isnadı yönünden beraat kararı verilmiştir.")
        if hagb:
            ceza_bits.append(
                "Basit kasten yaralama yönünden hükmün açıklanmasının geri bırakılmasına "
                "karar verilmiştir. HAGB, CMK m. 231 uyarınca mahkûmiyet hükmü gibi "
                "sonuç doğurmaz; tek başına kamu görevine alınmamayı zorunlu kılmaz."
            )
        add("MÜVEKKİL HAKKINDAKİ CEZA DOSYASININ HUKUKİ NİTELİĞİ", " ".join(ceza_bits))
    add(
        "SEBEP UNSURU YÖNÜNDEN HUKUKA AYKIRILIK",
        "İşlem gerekçesi, elde edilen verinin görevlendirmeye engel olduğu yönündedir; "
        "hangi somut olgunun, belgenin ve ölçütün esas alındığı açıklanmamıştır. "
        "Takdir yetkisi, idareye gerekçesiz ve denetime kapalı atamama yetkisi vermez. "
        "Soyut güvenlik soruşturması işlemi, sebep unsuru yönünden hukuka aykırıdır. "
        "7315 sayılı Kanun, verinin ilgiliye ve yargıya denetime elverişli biçimde "
        "somutlaştırılmasını gerektirir.",
    )
    add(
        "ŞEKİL UNSURU YÖNÜNDEN HUKUKA AYKIRILIK: GEREKÇESİZLİK",
        "İdari işlemlerde gerekçe, hukuk devleti ilkesinin (Anayasa m. 2) ve etkili yargısal "
        "denetimin (Anayasa m. 125) gereğidir. Mahkeme, işlemin sebebini ancak gerekçeyi "
        "görerek denetleyebilir; müvekkil de savunmasını ancak dayanağı bilerek kurabilir. "
        "Dava konusu belgede yalnızca “elde edilen verinin görevlendirmeye engel olduğu” "
        "ifadesi vardır. Hangi olgu, kaynak, madde ve ölçütün kullanıldığı yazılmamıştır. "
        "Bu soyutluk, Anayasa m. 36’daki hak arama hürriyetini ve Anayasa m. 40’taki etkili "
        "başvuru hakkını işlemez kılar. Gerekçesiz işlem şekil unsuru yönünden sakattır.",
    )
    olcu = (
        "HAGB uygulanmış bir kararın, görevlendirmeye kesin engel sayılması ölçülülük ilkesine aykırıdır. "
        "Elverişlilik, gereklilik ve orantılılık birlikte aranır; soyut “engel teşkil eder” ifadesi bunları karşılamaz."
    )
    if bits.get("yil") or bits.get("para") or bits.get("aile"):
        pieces = []
        if bits.get("aile"):
            pieces.append("olayın aile çevresinde münferit bir tartışmadan kaynaklanması")
        if bits.get("yil"):
            pieces.append(f"üzerinden yaklaşık {bits['yil']} yıl geçmiş bulunması")
        if bits.get("para"):
            pieces.append(f"yaptırımın {bits['para']} adli para cezası ile sınırlı kalması")
        if bits.get("denetim"):
            pieces.append(f"{bits['denetim']} yıl denetim süresi öngörülmesi")
        olcu = (
            "Ölçülülük bakımından " + ", ".join(pieces) + " birlikte değerlendirilmelidir. "
            + olcu
        )
    add("ÖLÇÜLÜLÜK İLKESİ", olcu +
        " Basit kasten yaralama olgusunun infaz ve koruma memurluğu görevinin güncel ve somut riski ile "
        "bağlantısı işlemde gösterilmemiştir. İdare bu bağlantıyı nesnel biçimde kurmak zorundadır.")
    add(
        "MASUMİYET KARİNESİ VE KAMU HİZMETİNE GİRME HAKKI",
        "HAGB’nin arşiv araştırmasında elde edilmesi ile bu kaydın otomatik olarak kamu görevine "
        "engel sayılması aynı şey değildir. Anayasa m. 38 anlamında masumiyet karinesi, HAGB’nin "
        "hiç değerlendirilemeyeceği anlamına gelmez; ancak idare bireyselleştirilmiş, güncel ve "
        "görevle bağlantılı bir değerlendirme yapmak zorundadır. Hakaret isnadından beraat, "
        "olumsuz değerlendirmenin otomatik gerekçesi olamaz.",
    )
    add(
        "SEBEP UNSURU YÖNÜNDEN HUKUKA AYKIRILIK",
        "İşlem tesis tarihinde gösterilmeyen somut sebep, dava dilekçesine cevapta "
        "“aslında şu ceza dosyasıdır” denilerek sonradan ikame edilemez. Sebep unsuru, "
        "işlemin kurulduğu andaki gerekçe ile denetlenir. İdarenin yargılama aşamasında "
        "yeni gerekçe üretmesi, gerekçesizlik sakatlığını gidermez.",
    )
    add(
        "YÜRÜTMENİN DURDURULMASI TALEBİ",
        "Değerlendirme komisyonuna sunulan bilgi ve belgeler, güvenlik soruşturması raporu, "
        "tutanaklar ve dayanak verilerin mahkeme aracılığıyla celbi talep olunur. Kişisel veri "
        "veya gizlilik, yargısal denetimi ortadan kaldırmaz; mahkeme gizli evrakı inceleyerek "
        "hukuka uygunluk denetimi yapabilir. Somut sebep açıklanmadan etkili başvuru (Anayasa m. 40) "
        "ve idari yargı denetimi (Anayasa m. 125) işlemez.",
    )
    if emsal:
        add("KANUN ÇERÇEVESİNDE TAKDİR YETKİSİNİN SINIRI", emsal)
    for row in _aym_memory_rows()[:3]:
        ilke = str(row.get("ilke") or row.get("ozet") or "").strip()
        kunye = str(row.get("kunye") or row.get("baslik") or "").strip()
        if kunye:
            add("MASUMİYET KARİNESİ VE KAMU HİZMETİNE GİRME HAKKI", _aym_weave(kunye, ilke))
    flags = _urgent_flags(form)
    if flags.get("ivedi"):
        add(
            "YÜRÜTMENİN DURDURULMASI TALEBİ",
            "Kadro ve atama döneminin geçmesi tehlikesi nedeniyle davanın ivedi ve "
            "öncelikli incelenmesi talep olunur.",
        )
    if flags.get("yd"):
        add(
            "YÜRÜTMENİN DURDURULMASI TALEBİ",
            "İşlemin uygulanması hâlinde müvekkilin bu alım dönemindeki görevlendirmesi "
            "fiilen imkânsızlaşacak, telafisi güç zarar doğacaktır. Soyut gerekçeyle "
            "tesis edilen işlem açıkça hukuka aykırı görünmektedir. İYUK m. 27’deki "
            "iki koşul birlikte oluştuğundan yürütmenin durdurulması gerekir.",
        )
    if flags.get("adli"):
        add(
            "ÖNCELİKLİ TALEP: ADLİ YARDIM",
            "Müvekkilin yargılama giderlerini karşılayacak maddi olanağı bulunmamaktadır. "
            "6100 sayılı HMK m. 334 ve 2577 sayılı İYUK m. 31 uyarınca adli yardım talebinin "
            "kabulü ile yargılama giderlerinden geçici muafiyet talep olunur.",
        )
    add(
        "KONU VE MAKSAT UNSURLARI YÖNÜNDEN HUKUKA AYKIRILIK",
        "7315 sayılı Kanun, değerlendirme komisyonuna sunulan verinin görevle ilgili, olgusal, "
        "nesnel ve gerekçeli olmasını gerektirir. Görevle somut bağ kurulmadan verilen olumsuz "
        "sonuç, kanuni yetkinin konusunu aşar. Güvenlik soruşturmasının meşru amacı, kamu "
        "hizmetini gerçek ve güncel güvenlik riskinden korumaktır. Bireyselleştirilmemiş, "
        "ölçüsüz ve gerekçesiz ret bu amacı taşımaz; Anayasa m. 70’deki kamu hizmetine girme "
        "hakkını orantısız kısıtlar. İşlem konu ve maksat unsurları yönünden de sakattır.",
    )
    from bettersaul_mcp.templates import render_roman, sort_sections
    return render_roman(sort_sections(blocks, str(form.get("petitionType") or "İdare"), flags, blob))


def _draft_quality_ok(form: dict, text: str) -> bool:
    t = text or ""
    ptype = str(form.get("petitionType") or "")
    if not t or len(t) < 360:
        return False
    if _has_instr_leak(t) or _has_book_subs(t) or _vakia_too_repetitive(t) or _draft_wrong_track(form, t):
        return False
    if re.search(
        r"(?i)davan[ıi]n reddine dayan|Türk hukuk yazım editörü|Üslup:|"
        r"Kronoloji \(Tarih|Fer’iler \(Formda|dava açılış tarihi\s+\d|"
        r"hangi argüman|stratejiye dayan",
        t,
    ):
        return False
    if "Boşanma" not in ptype and re.search(r"(?i)ziynet|TMK\s*m\.\s*185|evlilik birliğinin temelinden", t):
        return False
    if "İdare" not in ptype and re.search(r"(?i)7315 sayılı|atama uygunluk|İYUK m\.\s*27", t):
        return False
    if not is_labor(form) and re.search(r"(?i)7036 sayılı.*arabuluculuk|4857 sayılı Kanun m\.\s*32", t) and "İş" not in ptype:
        return False
    return True


def _idare_draft_ok(form: dict, text: str) -> bool:
    return _draft_quality_ok(form, text)


def _narrative_aciklamalar(form: dict, pack: dict, research: str) -> str:
    if "İdare" in str(form.get("petitionType") or ""):
        return _idare_narrative(form, pack, research)
    if is_labor(form):
        return _labor_narrative(form, pack, research)
    facts = _field(form, "caseSummary", "case_summary")
    extra = "\n".join(x for x in (_field(form, "extraInstructions", "extra"), _field(form, "userPrompt")) if x)
    reqs = _field(form, "requests")
    child = _child_line(_field(form, "parties"))
    ptype = str(form.get("petitionType") or "")
    sents = _all_fact_sentences(facts, extra)
    if child:
        sents.append(child)
    sents = _chrono_sents(sents)
    cites = _extract_cites(research)
    mem = _CASE_MEMORY or _load_case_memory()
    holds = list(mem.get("holdings") or _extract_ozetler(research) or [])
    blocks: list[str] = []
    n = 1

    def add(title: str, body: str) -> None:
        nonlocal n
        body = _strip_disclaimers(_strip_book_subs(body))
        if not body or len(body) < 24:
            return
        title = title.rstrip(" :") + ":"
        blocks.append(f"{n}- {title}\n\n{body}")
        n += 1

    if "Boşanma" in ptype:
        ground = _divorce_ground(form)
        has_terk = bool(re.search(r"terk", f"{facts} {extra}", re.I))
        if ground == "164":
            add(
                "Davanın hukuki dayanağı",
                "İşbu dava, 4721 sayılı Türk Medeni Kanunu’nun 164. maddesinde düzenlenen terk "
                "sebebine dayanılarak açılmıştır. Terk, evlilik birliğinin temelinden sarsılmasından "
                "(TMK m. 166) ayrı, müstakil bir boşanma sebebidir. Kanunda öngörülen süre, ihtar "
                "ve ortak konuta dönmeme koşulları somut olaya uygulanacaktır.",
            )
        else:
            dayanak = (
                "İşbu dava, 4721 sayılı Türk Medeni Kanunu’nun 166. maddesi uyarınca, evlilik "
                "birliğinin temelinden sarsılması sebebine dayanılarak açılmıştır. Anılan maddeye göre "
                "birlik, ortak hayatı temelinden sarsacak derecede bozulmuş ve eşlerden birinin birliği "
                "sürdürmesi beklenemez hâle gelmişse boşanmaya karar verilir. Eşlerin sadakat, yardım "
                "ve güçbirliği yükümlülüğü TMK m. 185’te düzenlenmiştir; bu yükümlülüğün ihlali, "
                "166. maddedeki boşanma sebebini somutlaştırır."
            )
            if has_terk:
                dayanak += (
                    " Davalının ortak konutu terk etmesi, TMK m. 164 anlamında müstakil terk davasının "
                    "sebebi olarak ileri sürülmemekte; birliğin sarsıldığını gösteren vakıalardan biri "
                    "olarak nazara alınmaktadır."
                )
            add("Davanın hukuki dayanağı", dayanak)
        evlilik = _pick_sents(sents, ("evlen", "nikah", "cüzdan", "evlilik tarihi", "birliği"))
        cocuk = _pick_sents(sents, ("çocuk", "oğul", "kız", "velayet", "doğum"))
        if child and child not in cocuk:
            cocuk.append(child)
        fam = evlilik + [s for s in cocuk if s not in evlilik]
        if fam:
            add(
                "Evlilik birliği ve aile",
                _weave_facts(fam)
                + " Evlilik ve nüfus kayıtları bu olguları belgelemektedir.",
            )
        elif any(w in (facts or "").lower() for w in ("çocuk", "evl")):
            add(
                "Evlilik birliği ve aile",
                "Taraflar evlilik birliği içindedir. Müşterek çocuk bulunması hâlinde kimlik "
                "nüfus kaydı ile sabittir.",
            )
        plot_keys = (
            "aldat", "zina", "sadakat", "hakaret", "şiddet", "geçimsiz", "terk",
            "çekilmez", "yazış", "tanık", "olay", "tarihinde",
        )
        plot = [s for s in sents if s not in fam]
        if not plot:
            plot = _pick_sents(sents, plot_keys) or sents
        if plot:
            add(
                "Birliğin sarsılmasına yol açan vakıalar",
                _weave_facts(plot)
                + " Davalının bu tutumu evlilik birliğini temelinden sarsmış; ortak hayat "
                "müvekkil bakımından çekilmez hâle gelmiştir. Davacıdan birliği sürdürmesi "
                "beklenemez.",
            )
        cites = _prefer_chamber_cites(ptype, cites)
        emsal = _emsal_in_flow(cites, holds, ptype, form)
        nit = (
            "Açıklanan vakıalar birlikte değerlendirildiğinde kusur davalı taraftadır. "
            "TMK m. 185’teki sadakat yükümlülüğü ihlal edilmiş; TMK m. 166’daki boşanma "
            "koşulları oluşmuştur."
        )
        if ground == "164":
            nit = (
                "Açıklanan vakıalar, TMK m. 164’teki terkin koşullarının oluştuğunu göstermektedir. "
                "İşbu dava dördüncü fıkradaki evlilik birliğinin temelinden sarsılması sebebine "
                "karıştırılmamaktadır."
            )
        add("Hukuki nitelendirme", nit + " " + (emsal or "Bu nedenle boşanmaya karar verilmesi gerekir."))
        vel = _pick_sents(sents, ("velayet", "çocuk", "üstün", "okul"))
        if vel or "velayet" in (reqs or "").lower() or "çocuk" in (facts or "").lower():
            body = _weave_facts(vel) if vel else "Müşterek çocuğun velayetinin davacıya bırakılması talep olunur."
            add(
                "Velayet",
                body
                + " Velayet, çocuğun üstün yararı esas alınarak belirlenir (TMK m. 182, m. 339). "
                "Davalının birliği sarsan tutumu, çocuğun düzeni bakımından da nazara alınmalıdır.",
            )
        feri_s = _pick_sents(sents, ("nafaka", "gelir", "ücret", "tazminat", "ziynet", "altın", "eşya"))
        feri_req = any(x in (reqs or "").lower() for x in ("nafaka", "tazminat", "ziynet"))
        if feri_s or feri_req:
            body = _weave_facts(feri_s) if feri_s else "Fer’i talepler, boşanmanın sonuçları olarak ayrıca istenmektedir."
            bits = []
            if "nafaka" in (reqs + " " + facts).lower() or child:
                bits.append(
                    "davacı yararına tedbir ve yoksulluk nafakası ile müşterek çocuk yararına "
                    "ayrı tedbir ve iştirak nafakası (TMK m. 175, 182; tutarlar sonuç kısmında ayrı kalem)"
                )
            if "tazminat" in (reqs + " " + facts).lower():
                bits.append(
                    "maddi tazminat ile manevi tazminat ayrı ayrı (TMK m. 174; tutarlar sonuç kısmında ayrı kalem)"
                )
            ztab = _ziynet_table(form)
            if "ziynet" in (reqs + " " + facts).lower() or "altın" in (facts or "").lower() or ztab:
                if ztab:
                    bits.append("aşağıdaki döküme göre ziynetlerin aynen iadesi, mümkün olmaması halinde rayiç bedelinin faiziyle tahsili")
                else:
                    bits.append(
                        "ziynet alacağı (cins, adet, ayar, gram ve TL değeri formdaki tabloda "
                        "gösterilmelidir); aynen iade, mümkün değilse rayiç bedelin faiziyle tahsili"
                    )
            tail = (" " + "; ".join(bits) + " talep olunur.") if bits else ""
            add("Fer’i talepler ve ziynet alacağı", body + tail + (("\n\n" + ztab) if ztab else ""))
        _add_usul_vakia(add, form)
        return "\n\n".join(blocks)

    return _generic_floor_narrative(form, pack, research)


def _generic_floor_narrative(form: dict, pack: dict, research: str) -> str:
    ptype = str(form.get("petitionType") or "")
    facts = _field(form, "caseSummary", "case_summary")
    extra = "\n".join(x for x in (_field(form, "extraInstructions", "extra"), _field(form, "userPrompt")) if x)
    davaci, davali = _resolved_parties(form)
    davaci = _strip_party_label(davaci) or "davacı"
    davali = _strip_party_label(davali) or "davalı"
    sents = _chrono_sents(_all_fact_sentences(facts, extra))
    plot = _weave_facts(sents[:16]) if sents else ""
    mem = _CASE_MEMORY or _load_case_memory()
    cites, holds = _filter_cites(form, mem.get("cites") or _extract_cites(research), mem.get("holdings") or [])
    emsal = _emsal_in_flow(cites, holds, ptype, form)
    n = 1
    blocks: list[str] = []

    def add(title: str, body: str) -> None:
        nonlocal n
        body = _strip_disclaimers(_strip_book_subs(body or ""))
        if not body or len(body) < 36:
            return
        blocks.append(f"{n}- {title.rstrip(' :')}:\n\n{body}")
        n += 1

    fetched = _statute_labels()
    if fetched:
        dayanak = (
            "İşbu dava, " + ", ".join(fetched)
            + " hükümlerine dayanılarak açılmıştır. Çekilemeyen madde metni yazılmaz. "
            "Formda olmayan tutar, tanık ve karar numarası yazılmaz."
        )
    elif "Alacak" in ptype:
        dayanak = (
            "İşbu dava, 6098 sayılı TBK m. 83 ve m. 117 uyarınca muaccel alacağın tahsili "
            "istemiyle açılmıştır. Dilekçe HMK m. 119’a uygundur. Alacak kalemi ve tutar "
            "formda yoksa uydurulmaz; belirsizse HMK m. 107 anlamında şimdilik talep edilir."
        )
    elif "İcra" in ptype:
        dayanak = (
            "İşbu başvuru, 2004 sayılı İİK hükümleri (özellikle m. 67) uyarınca icra "
            "takiğine ilişkin uyuşmazlığın çözümü içindir. Takip dosyası ve ödeme emri "
            "formda yoksa numarası uydurulmaz."
        )
    elif "Tazminat" in ptype:
        dayanak = (
            "İşbu dava, 6098 sayılı TBK m. 49 vd. uyarınca haksız fiile / sözleşmeye "
            "aykırılığa dayalı maddi ve manevi tazminat istemiyle açılmıştır. Kusur, "
            "zarar ve illiyet formda yazılan olgularla sınırlıdır; tutar yoksa uydurulmaz."
        )
    elif "Kira" in ptype:
        dayanak = (
            "İşbu dava, 6098 sayılı TBK’nin kira hükümleri (m. 299 vd., temerrütte m. 315) "
            "uyarınca tahliye / kira alacağı istemiyle açılmıştır. Sözleşme tarihi ve "
            "ihtar formda yoksa uydurulmaz."
        )
    elif "Tüketici" in ptype:
        dayanak = (
            "İşbu dava, 6502 sayılı TKHK uyarınca ayıplı mal / hizmetten kaynaklanan "
            "seçimlik hakların kullanılması istemiyle açılmıştır. Ayıp bildirimi ve fatura "
            "formda yoksa uydurulmaz."
        )
    elif "Ceza" in ptype:
        dayanak = (
            "İşbu dilekçe, 5271 sayılı CMK hükümleri uyarınca yargılamaya katılma / "
            "talep bildirmek içindir. Suç vasfı ve ceza miktarı uydurulmaz."
        )
    elif is_labor(form):
        dayanak = (
            "İşbu dava, " + labor_hukuk(form)
            + " Formda olmayan işçilik kalemi (işe iade, kıdem, ihbar, fazla çalışma) yazılmaz."
        )
    else:
        dayanak = (
            "İşbu dava, " + ", ".join((pack.get("statutes") or ["HMK m. 119"])[:5])
            + " hükümlerine dayanılarak açılmıştır. Dilekçe HMK m. 119’a uygundur. "
            "Formda olmayan tutar, tanık ve karar numarası yazılmaz."
        )
    add("Davanın hukuki dayanağı", dayanak)
    add(
        "Taraflar ve uyuşmazlık",
        f"Müvekkil, davalı {davali} aleyhine işbu davayı açmıştır. "
        + (plot or "Somut olay form ve prompt’taki vakıalarla sınırlıdır; yeni olgu eklenmez."),
    )
    if sents[8:]:
        add("Kronoloji ve somut vakıalar", _weave_facts(sents[8:18]) or plot)
    add(
        "Hukuki nitelendirme",
        "Açıklanan vakıalar, yukarıdaki dayanak maddeleri çerçevesinde müvekkilin taleplerini "
        "haklı kılar. " + (emsal or "İçtihat künyesi yoksa numara uydurulmaz."),
    )
    _add_usul_vakia(add, form)
    return "\n\n".join(blocks)


def _add_usul_vakia(add, form: dict) -> None:
    flags = _urgent_flags(form)
    if flags["ivedi"]:
        add(
            "İvedi ve öncelikli inceleme",
            "Uyuşmazlığın niteliği ve telafisi güç zarar tehlikesi nedeniyle davanın ivedi ve "
            "öncelikli incelenmesi talep olunur. Bu talep, dilekçe başlığında ayrıca gösterilmiştir.",
        )
    if flags["yd"]:
        add(
            "Yürütmenin durdurulması",
            "İdari işlemin uygulanması hâlinde telafisi güç veya imkânsız zararlar doğacaktır. "
            "İşlemin açıkça hukuka aykırı olması ve zarar koşulu birlikte gerçekleştiğinden "
            "2577 sayılı İYUK m. 27 uyarınca yürütmenin durdurulması gerekir.",
        )
    if flags["adli"]:
        add(
            "Adli yardım",
            "Müvekkilin yargılama giderlerini karşılayacak maddi olanağı bulunmamaktadır. "
            "Adli yardım talebinin kabulü ile yargılama giderlerinden geçici muafiyet talep olunur.",
        )
    if flags["tedbir"]:
        add(
            "İhtiyati tedbir",
            "Hakkın elde edilmesinin önemli ölçüde zorlaşması veya imkânsızlaşması tehlikesi "
            "nedeniyle HMK m. 389 vd. uyarınca ihtiyati tedbir talep olunur.",
        )
    if flags["haciz"]:
        add(
            "İhtiyati haciz",
            "Alacağın tahsilini güvence altına almak üzere ihtiyati haciz talep olunur.",
        )
    if needs_mediation(form):
        title, body = mediation_vakia(form)
        add(title, body)


def _split_vakia_blocks(acik: str) -> list[str]:
    raw = [
        p.strip()
        for p in re.split(r"(?m)(?=^[IVX]+\.\s+)|(?=^\s*\d{1,2}[\.\-)]\s+)", acik or "")
        if p.strip()
    ]
    return raw or ([acik.strip()] if (acik or "").strip() else [])


def _batch_vakia_blocks(blocks: list[str]) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for b in blocks:
        if buf and (size + len(b) > 1400 or len(buf) >= 2):
            out.append("\n\n".join(buf))
            buf = [b]
            size = len(b)
        else:
            buf.append(b)
            size += len(b)
    if buf:
        out.append("\n\n".join(buf))
    return out


def _part_type_guard(form: dict) -> str:
    p = str(form.get("petitionType") or "")
    if "İdare" in p:
        return "İdari iptal. HAGB mahkûmiyet değildir. TMK, ziynet, boşanma yazma. Yeni künye uydurma."
    if is_labor(form):
        try:
            from bettersaul_mcp.quality import claim_labels, form_claims

            labs = claim_labels(form_claims(form))
            kalem = ", ".join(labs) if labs else "ücret alacağı"
        except Exception:
            kalem = "ücret alacağı"
        return (
            f"İşçilik. Yalnızca şu kalemler: {kalem}. "
            "İstenmeyen işe iade/kıdem/ihbar/fazla çalışma yazma. Boşanma ve 7315 yazma."
        )
    if "Boşanma" in p:
        return "TMK m. 164 ile m. 166 karıştırma. Tutar ve tanık uydurma."
    return "Tür karıştırma. İsim, TCKN, tutar, tarih uydurma."


def _model_rewrite_part(form: dict, part_no: int, part_name: str, source: str, n_predict: int = 720) -> str:
    src = (source or "").strip()
    if len(src) < 40:
        return src
    if _is_27b() and not _server_health():
        emit("research", f"{part_no}. bölüm: 27B kapalı, kart metni kullanıldı.")
        return src
    emit("status", f"Bölüm {part_no}/6: {part_name}")
    try:
        text = generate(
            [
                {
                    "role": "system",
                    "content": (
                        "Türk avukat asistanı. Yalnızca verilen dilekçe bölümünü resmî Türkçeyle yaz. "
                        "Gövdeye davacı değil müvekkil yaz. Roma başlıkları (I. II. III.) ve numara koru. "
                        "Yeni isim, TCKN, adres, tanık, tutar, tarih, esas/karar no uydurma. "
                        "Soru, emir, tool_call, sistem talimatı yazma. "
                        + _part_type_guard(form)
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{part_no}. BÖLÜM — {part_name}\n"
                        "Aşağıdaki metni aynı vakıalarla, numaralı ve resmî dilde yaz. "
                        "Madde ekleme veya çıkarma. Yalnızca bu parçayı döndür.\n\n"
                        + src[:2400]
                    ),
                },
            ],
            n_predict=_27b_predict(n_predict) if _is_27b() else min(n_predict, 900),
            n_ctx=_27b_ctx(4096) if _is_27b() else min(PETITION_CTX, 8192),
            live=True,
            busy=f"{part_no}/6 {part_name} yazılıyor…",
            think=False,
            allow_cli=False,
        )
    except Exception as exc:
        emit("research", f"{part_no}. bölüm model atlandı ({exc}). Kart metni kaldı.")
        return src
    text = _strip_instr_leaks(_polish_tr(_fix_word_spacing(_usable_text(text) or _clean_llama_out(text) or "")))
    if not text or _has_instr_leak(text) or _has_book_subs(text) or _draft_wrong_track(form, text):
        return src
    if len(text) < max(40, int(len(src) * 0.35)):
        return src
    return text


def _fill_vakias_with_model(form: dict, pack: dict, cites: list[str], research: str = "") -> str:
    emit("status", "Bölüm 3/6: Açıklamalar — olay kronolojisi parçalara bölünüyor…")
    emit("research", "3. bölüm: model tek seferde 5 A4 yazmaz; vakıalar 2’şer yazılır.")
    card = _narrative_aciklamalar(form, pack, research)
    batches = _batch_vakia_blocks(_split_vakia_blocks(card))
    if not batches:
        return ""
    out: list[str] = []
    for i, batch in enumerate(batches, 1):
        emit("research", f"3. bölüm parça {i}/{len(batches)} modele verildi.")
        piece = _model_rewrite_part(form, 3, f"Açıklamalar ({i}/{len(batches)})", batch, 800)
        out.append(piece)
    text = "\n\n".join(out).strip()
    if _has_instr_leak(text) or _has_book_subs(text) or _draft_wrong_track(form, text) or _vakia_too_repetitive(text):
        emit("research", "3. bölüm sızıntı/tekrar: vakıa kartı kullanılacak.")
        return ""
    if _has_numbered_vakia(text) and len(text) > 280:
        return text
    return ""


def _book_vakia_block(form: dict, pack: dict, draft: str, research: str) -> str:
    draft = _strip_book_subs(_fix_word_spacing(_extract_body(draft, "AÇIKLAMALAR") or (draft or "")))
    if "İdare" in str(form.get("petitionType") or ""):
        if _draft_quality_ok(form, draft):
            return draft
        return _idare_narrative(form, pack, research)
    if is_labor(form):
        if _draft_quality_ok(form, draft) and not labor_toxic(draft) and len(draft) > 800:
            return draft
        return _labor_narrative(form, pack, research)
    if _draft_quality_ok(form, draft) and _has_numbered_vakia(draft) and _looks_spaced(draft):
        if "Boşanma" in str(form.get("petitionType") or "") and not re.search(
            r"m\.\s*16[46]|16[46]\.\s*madde|uyarınca açıl", draft, re.I
        ):
            return _narrative_aciklamalar(form, pack, research)
        return draft
    return _narrative_aciklamalar(form, pack, research)


def _evidence_from_text(blob: str) -> list[str]:
    low = (blob or "").lower()
    cues = (
        (r"otel|konaklama kay[ıi]t", "Otel konaklama kayıtları"),
        (r"görsel materyal|görüntü|fotoğraf|video kay[ıi]t|kamer", "Görsel materyaller (fotoğraf / video kayıtları)"),
        (r"yazışma|whatsapp|mesaj|sms|e-posta|elektronik ileti", "Elektronik yazışma ve mesaj kayıtları"),
        (r"sağlık rapor|adli rapor|hastane rapor|adli tıp", "Sağlık / adli rapor"),
        (r"6284|uzaklaştır|gizlilik kararı", "6284 sayılı Kanun uyarınca verilen tedbir / uzaklaştırma kararı"),
        (r"nüfus kay[ıi]t|evlilik cüzdan", "Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi"),
        (r"banka|dekont|hesap hareket|eft", "Banka dekontu ve hesap hareketleri"),
        (r"sgk|hizmet döküm|bordro|puantaj", "SGK hizmet dökümü, bordro ve puantaj kayıtları"),
        (r"tapu|taşınmaz kay[ıi]t", "Tapu kayıtları"),
        (r"ziynet|altın|bilezik|gerdanlık|küpe", "Ziynet eşyalarına ilişkin fotoğraf, fatura ve bilirkişi incelemesi"),
        (r"(?<![a-zçğıöşü])sözleşme(?!li)|ak[iı]t belgesi|iş sözleşmesi|kira sözleşmesi", "Sözleşme / akit belgesi"),
        (r"fatura|irsaliye", "Fatura ve irsaliye"),
        (r"ihtar|ihtarname|tebliğ evrak", "İhtarname ve tebliğ evrakı"),
        (r"arabuluculuk|son tutanak", "Arabuluculuk son tutanağı"),
        (r"fesih bildir|ibraname", "Fesih bildirimi / ibraname"),
        (r"icra dosya|ödeme emri", "İcra dosyası örneği, ödeme emri ve tebliğ"),
        (r"idari işlem|işlem evrak|tebliğ mazbata", "İdari işlem evrakı ve tebliğ belgesi"),
        (r"atama uygunluk", "Atama Uygunluk Kararı ve tebliğ belgesi"),
        (r"7315|g[uü]venlik soru[sş]tur|ar[sş]iv ara[sş]t[ıi]r", "7315 sayılı Kanun kapsamında güvenlik soruşturması / arşiv araştırması evrakı"),
        (r"de[gğ]erlendirme komisyon", "Değerlendirme komisyonu evrakı, tutanak ve dayanak belgelerinin celbi"),
        (r"asliye ceza|a[gğ][ıi]r ceza|\d{4}/\d+\s*[EeKk]", "İlgili ceza mahkemesi kararı (yalnızca sebep olgusu)"),
        (r"kaza tutana[kğ]|trafik kaza", "Kaza / olay tutanağı"),
        (r"kira sözleşme|tahliye taahhüt", "Kira sözleşmesi ve varsa tahliye taahhüdü"),
        (r"tanık", "Tanık beyanları (isim ve tebliğ adresi dilekçede / listede)"),
    )
    out: list[str] = []
    for pat, label in cues:
        if re.search(pat, low) and label not in out:
            out.append(label)
    return out


def _relevant_evidence(form: dict, pack: dict, acik: str) -> list[str]:
    blob = " ".join(
        [
            acik or "",
            _field(form, "caseSummary"),
            _field(form, "extraInstructions"),
            _field(form, "userPrompt"),
            _field(form, "requests"),
            _ziynet_table(form),
        ]
    )
    low = blob.lower()
    out: list[str] = []
    for e in pack.get("evidence") or []:
        if drop_unrelated_evidence(e, form):
            continue
        if re.search(r"(?i)dayanak mevzuat\s*/\s*rg|resm[iî]\s*gazete", e or "") and not _rg_memory_real():
            continue
        if re.search(r"(?i)^zarar belge", e or "") and not wants_tazminat(form):
            continue
        el = (e or "").lower()
        if any(w in el for w in ("ziynet", "altın", "tapu")) and not any(
            w in low for w in ("ziynet", "altın", "eşya", "tapu")
        ):
            continue
        if "nafaka" in el or "bordro" in el or "sgk" in el:
            if not any(w in low for w in ("nafaka", "gelir", "ücret", "yoksul", "kıdem", "işçi")):
                if "Boşanma" not in str(form.get("petitionType") or "") and "İş" not in str(form.get("petitionType") or ""):
                    continue
        if any(w in el for w in ("6284", "uzaklaştır", "sağlık")) and not any(
            w in low for w in ("aile içi şiddet", "6284", "uzaklaştır", "yaralama", "adli rapor", "sağlık")
        ):
            continue
        if e not in out:
            out.append(e)
    for e in _evidence_from_text(blob):
        if drop_unrelated_evidence(e, form):
            continue
        if e not in out:
            out.append(e)
    if is_labor(form):
        for e in labor_evidence():
            if e not in out:
                out.append(e)
    if not out:
        out = list(pack.get("evidence") or ["Dayanak belgeler"])[:3]
    ptype = str(form.get("petitionType") or "")
    if out and "nüfus" not in " ".join(out).lower() and "Boşanma" in ptype:
        out.insert(0, "Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi")
    out = [
        re.sub(r"(?i)^tanık.*", "Tanık beyanları (isim ve adresleri sunulacaktır)", e)
        for e in out
    ]
    joined = " ".join(out).lower()
    if any(w in low for w in ("nafaka", "tazminat", "gelir")) and "sosyal ve ekonomik" not in joined:
        if "Boşanma" in ptype or "Tazminat" in ptype:
            out.append("Tarafların sosyal ve ekonomik durum araştırması (SED), gelir belgesi, SGK dökümü")
    if "Boşanma" in ptype and (_ziynet_rows(form) or any(w in low for w in ("ziynet", "altın"))):
        if "ziynet alacağı döküm" not in joined:
            out.append("Ziynet alacağı döküm tablosu (cins, adet, ayar, gram, TL)")
        if "ziynet eşyalarına ilişkin" not in joined:
            out.append("Ziynet eşyalarına ilişkin fotoğraf/video kayıtları ve bilirkişi incelemesi")
    if "yasal delil" not in joined and "İdare" not in ptype:
        out.append("Emsal içtihat ve her türlü yasal delil")
    if "İdare" in ptype:
        extra_ev = [
            "İptali istenen işlem ve tebliğ evrakı",
            "Güvenlik soruşturması / değerlendirme komisyonu evrakı (celp)",
        ]
        if re.search(r"(?i)asliye ceza|HAGB|kasten yaralama", low):
            extra_ev.append("Ceza mahkemesi kararı (varsa esas/karar ile)")
        for e in extra_ev:
            if e not in out:
                out.append(e)
    seen: list[str] = []
    for e in out:
        if e and e not in seen:
            seen.append(e)
    return seen


def _statute_labels(limit: int = 10) -> list[str]:
    mem = _CASE_MEMORY or _load_case_memory()
    out: list[str] = []
    for s in mem.get("statutes") or []:
        if isinstance(s, dict):
            lab = str(s.get("label") or "").strip()
            if lab and s.get("ok") is not False:
                out.append(lab)
        elif isinstance(s, str) and s.strip():
            out.append(s.strip())
    return out[:limit]


_ANAYASA_ILKE = {
    "2": "hukuk devleti",
    "10": "kanun önünde eşitlik",
    "13": "ölçülülük",
    "20": "özel hayatın korunması",
    "35": "mülkiyet hakkı",
    "36": "hak arama hürriyeti",
    "38": "suç ve cezalara ilişkin esaslar",
    "38/4": "masumiyet karinesi",
    "40": "etkili başvuru",
    "41": "ailenin korunması",
    "49": "çalışma hakkı ve ödevi",
    "70": "kamu hizmetine girme hakkı",
    "125": "idarenin yargısal denetimi",
    "172": "tüketicilerin korunması",
}

_BAD_DAYANAK_HOLD = re.compile(
    r"(?i)temyiz edilmekle|evrak (?:okunup|üzerinde)|landırılabilecek|"
    r"formda 164|çekilmemişse yazılmaz|4\.\s*BÖLÜM|wikipedia"
)

_CITE_PERSON_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?\s+[A-ZÇĞİÖŞÜ]{2,})\b"
)
_CITE_APP_RE = re.compile(
    r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,2})\s+başvurusu",
    re.I,
)


def _label_anayasa_line(text: str) -> str:
    def _one(m: re.Match) -> str:
        art = re.sub(r"\s+", "", m.group(1) or "")
        tail = m.group(2) or ""
        if tail.strip().startswith("("):
            return m.group(0)
        ilke = _ANAYASA_ILKE.get(art) or _ANAYASA_ILKE.get(art.split("/")[0])
        if not ilke:
            return m.group(0)
        return f"m. {m.group(1).strip()} ({ilke}){tail}"

    return re.sub(r"m\.\s*(\d+(?:\s*/\s*\d+)?)(\s*(?:\([^)]*\))?)?", _one, text or "")


def _label_kanun_line(text: str) -> str:
    t = text or ""
    swaps = (
        (r"TMK\s*m\.\s*166(?:/1)?(?!/)(?!\s*\()", "TMK m. 166/1 (evlilik birliğinin temelinden sarsılması)"),
        (r"TMK\s*m\.\s*164(?!\d)(?!\s*\()", "TMK m. 164 (terk nedeniyle boşanma)"),
        (r"TMK\s*m\.\s*174(?!\d)(?!\s*\()", "TMK m. 174 (maddi ve manevi tazminat)"),
        (r"TMK\s*m\.\s*175(?!\d)(?!\s*\()", "TMK m. 175 (yoksulluk nafakası)"),
        (r"İYUK\s*m\.\s*2/1-a(?!\s*\()", "İYUK m. 2/1-a (iptal davası)"),
        (r"İYUK\s*m\.\s*3(?!\d)(?!\s*\()", "İYUK m. 3 (dilekçede bulunacak hususlar)"),
        (r"İYUK\s*m\.\s*7(?!\d)(?!\s*\()", "İYUK m. 7 (dava açma süresi)"),
        (r"İYUK\s*m\.\s*27(?!\d)(?!\s*\()", "İYUK m. 27 (yürütmenin durdurulması)"),
        (r"İYUK\s*m\.\s*31(?!\d)(?!\s*\()", "İYUK m. 31 (HMK yolları)"),
        (r"CMK\s*m\.\s*231(?!\d)(?!\s*\()", "CMK m. 231 (hükmün açıklanmasının geri bırakılması)"),
        (r"HMK\s*m\.\s*334(?!\d)(?!\s*\()", "HMK m. 334 (adli yardım)"),
        (r"İş Kanunu\s*m\.\s*32(?!\d)(?!\s*\()", "İş Kanunu m. 32 (ücret)"),
        (r"İş Kanunu\s*m\.\s*34(?!\d)(?!\s*\()", "İş Kanunu m. 34 (ücretin gününde ödenmemesi)"),
    )
    for pat, repl in swaps:
        t = re.sub(pat, repl, t)
    return t


def _cite_person_name(*texts: str) -> str:
    blob = " ".join(x or "" for x in texts)
    m = _CITE_PERSON_RE.search(blob) or _CITE_APP_RE.search(blob)
    if not m:
        return ""
    name = re.sub(r"\s+", " ", m.group(1)).strip()
    if re.search(r"(?i)daire|mahkeme|anayasa|yargıtay|danıştay|başvuru|karar|genel kurul", name):
        return ""
    if len(name) < 5:
        return ""
    return name


def _insert_cite_person(cite: str, person: str) -> str:
    if not person or person.lower() in (cite or "").lower():
        return cite
    out = re.sub(
        r"((?:Anayasa Mahkemesi|AYM)(?:\s*\(GK\))?)\s*,\s*(?=E\.|K\.|B\.\s*No|Başvuru)",
        rf"\1, {person}, ",
        cite or "",
        count=1,
        flags=re.I,
    )
    if person in out:
        return out
    out = re.sub(
        r"((?:Yargıtay\s+\d+\.\s*(?:Hukuk\s+)?Dairesi|Danıştay\s+\d+\.\s*Daire))\s*,\s*",
        rf"\1, {person}, ",
        out,
        count=1,
        flags=re.I,
    )
    return out


def _dayanak_expl(text: str) -> str:
    t = _clean_holding(text or "")
    if not t or _BAD_DAYANAK_HOLD.search(t):
        return ""
    t = _kunye_tr(re.sub(r"\s+", " ", t)).strip(" .;")
    return t[:220]


def _default_cite_expl(form: dict, cite: str) -> str:
    p = str(form.get("petitionType") or "")
    if re.search(r"(?i)AYM|Anayasa Mahkemesi", cite):
        if "İdare" in p:
            return "kamu görevine girişte masumiyet karinesi ve gerekçeli işlem güvencesi"
        if "Boşanma" in p:
            return "aile hayatının ve hak arama hürriyetinin korunması"
        return "hak arama hürriyeti ve adil yargılanma güvencesi"
    if re.search(r"(?i)Danıştay", cite):
        return "idari işlemin sebep unsurunun somut ve denetime elverişli olması"
    if re.search(r"(?i)Yargıtay|Hukuk Dairesi", cite) and "Boşanma" in p:
        return "evlilik birliğinin ortak hayatı sürdüremeyecek derecede temelinden sarsılması"
    if re.search(r"(?i)Yargıtay", cite) and "İş" in p:
        return "işçilik alacağının ve fesih sonucunun somut delille kanıtlanması"
    return ""


def _format_ictihat_line(
    form: dict,
    cite: str,
    *,
    holding: str = "",
    name: str = "",
    ilke: str = "",
) -> str:
    line = _kunye_tr(re.sub(r"\s+", " ", (cite or "").strip()))
    if not line:
        return ""
    person = name or _cite_person_name(line, holding, ilke)
    line = _insert_cite_person(line, person)
    expl = _dayanak_expl(ilke) or _dayanak_expl(holding)
    if expl and expl[:36].lower() not in line.lower() and " — " not in line:
        line = f"{line} — {expl.rstrip(' .')}"
    return line


def _format_dayanak_from_case(row: dict) -> str:
    """Yalnızca çekilen davanın kaynağı + o davanın özeti. Genel cümle yazılmaz."""
    kaynak = str(row.get("kaynak") or "").strip()
    name = _cite_person_name(str(row.get("baslik") or ""), str(row.get("ozet") or ""), str(row.get("kunye") or ""))
    line = str(row.get("kunye") or "").strip() or _row_kunye(row)
    if name and name.lower() not in line.lower():
        line = _insert_cite_person(line, name)
    if kaynak and kaynak.lower() not in line.lower():
        line = f"{kaynak}, {line}" if not line.lower().startswith(kaynak.lower()[:8]) else line
    expl = _dayanak_expl(str(row.get("ilke") or "")) or _dayanak_expl(str(row.get("ozet") or ""))
    if not expl:
        raw = re.sub(r"\s+", " ", str(row.get("ozet") or row.get("ilke") or "")).strip()
        if len(raw) >= 28 and not _is_portal_junk(raw) and not _BAD_DAYANAK_HOLD.search(raw):
            expl = raw[:180].rstrip(" .")
    if expl and expl[:36].lower() not in line.lower():
        line = f"{line} — {expl.rstrip(' .')}"
    return _kunye_tr(re.sub(r"\s+", " ", line).strip(" ,"))


def _rich_ictihat_lines(form: dict) -> list[str]:
    mem = _CASE_MEMORY or _load_case_memory()
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str, ghost_ok: bool = False) -> None:
        t = (raw or "").strip()
        if not t:
            return
        if is_labor(form) and not ghost_ok:
            try:
                from bettersaul_mcp.quality import cite_fits_claims

                if not cite_fits_claims(t, _form_claims(form)):
                    return
            except Exception:
                pass
        key = re.sub(r"\s+", " ", t.lower())[:160]
        if key in seen:
            return
        seen.add(key)
        out.append(t)

    ptype = str(form.get("petitionType") or "")
    holds = [str(h) for h in (mem.get("holdings") or []) if str(h).strip()]
    rows = list(mem.get("cite_rows") or [])
    if not rows:
        rows = _extract_cite_rows(json.dumps(mem, ensure_ascii=False))
    rows = _rank_cite_rows(_bind_holdings_to_rows(_prefer_chamber_rows(ptype, rows), holds))
    if "İdare" in ptype:
        for row in _aym_memory_rows()[:2]:
            add(
                _format_ictihat_line(
                    form,
                    str(row.get("kunye") or row.get("baslik") or ""),
                    holding=str(row.get("ozet") or ""),
                    name=_cite_person_name(str(row.get("baslik") or ""), str(row.get("kunye") or "")),
                    ilke=str(row.get("ilke") or row.get("ozet") or ""),
                )
            )
    for row in rows[:8]:
        line = _format_dayanak_from_case(row) or _row_kunye(row)
        add(line)
    if len(out) < 2:
        for row in rows[:8]:
            add(_row_kunye(row), ghost_ok=True)
        for c in _prefer_recent_cites([str(x) for x in (mem.get("cites") or [])])[:8]:
            add(_normalize_court_name(c) if c and not c.lower().startswith("yargıtay") else c, ghost_ok=True)
    return out[:6]


def _hukuki_nedenler_line(form: dict, pack: dict) -> str:
    from bettersaul_mcp.templates import KINDS, dayanak_block, resolve_kind
    ptype = str(form.get("petitionType") or "")
    kind = resolve_kind(ptype)
    spec = KINDS[kind]
    blob = _source_blob(form)
    gs = bool(re.search(r"(?i)7315|güvenlik soruştur|atama uygunluk|HAGB|kamu hizmetine", blob))
    kanun = spec.get("kanun_7315") if (kind == "idare" and gs) else spec["kanun"]
    if is_labor(form) and kind == "is":
        kanun = labor_hukuk(form)
    if kind == "bosanma":
        if _divorce_ground(form) == "164":
            kanun = "4721 sayılı TMK m. 164 (terk nedeniyle boşanma); 6100 sayılı HMK"
        else:
            kanun = "4721 sayılı TMK m. 166/1 (evlilik birliğinin temelinden sarsılması); 6100 sayılı HMK"
    flags = _urgent_flags(form)
    if flags.get("adli") and "334" not in (kanun or ""):
        kanun = (kanun.rstrip(".") + "; 6100 sayılı HMK m. 334 (adli yardım)").strip("; ")
    anayasa = _label_anayasa_line(spec["anayasa"])
    kanun = _label_kanun_line(kanun)
    return dayanak_block(anayasa, kanun, _rich_ictihat_lines(form))


def _aym_memory_rows() -> list[dict]:
    mem = _CASE_MEMORY or _load_case_memory()
    out: list[dict] = []
    seen: set[str] = set()
    for row in mem.get("aym") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("kunye") or row.get("baslik") or row.get("url") or "")[:120]
        if not key or key in seen:
            continue
        if row.get("kunye") or row.get("baslik"):
            seen.add(key)
            out.append(row)
    return out


def _aym_memory_row() -> dict:
    rows = _aym_memory_rows()
    return rows[0] if rows else {}


def _rg_memory_real() -> list[dict]:
    mem = _CASE_MEMORY or _load_case_memory()
    out = []
    for r in mem.get("rg") or []:
        if isinstance(r, dict) and (r.get("baslik") or r.get("url")) and r.get("sonuc") != "taranamadı":
            out.append(r)
    return out


def _card_bits(card: str) -> tuple[str, str, str]:
    t = card or ""
    tckn = ""
    m = re.search(r"(?:T\.C\. Kimlik No|TCKN)\s*[:：]?\s*(\S+)", t, re.I)
    if m and not re.search(r"^\.+$", m.group(1)):
        tckn = m.group(1)
    addr = ""
    am = re.search(r"(?im)^Adres\s*[:：]\s*(.+)$", t)
    if am and not re.search(r"^\.+$", am.group(1).replace(" ", "")):
        addr = am.group(1).strip()
    name = re.split(r"(?i)T\.C\.|TCKN|Adres", t)[0]
    name = re.sub(r"\s+", " ", name).strip(" ,;:")
    return name, tckn, addr


def _compose_petition(form: dict, pack: dict, acik: str, research: str) -> str:
    from bettersaul_mcp import templates as _tpl
    court = _court_line(form, pack)
    flags = _urgent_flags(form)
    banner = _tpl.combined_banner(flags, str(form.get("petitionType") or ""))
    ptype = str(form.get("petitionType") or "")
    davaci_raw, davali_raw = _resolved_parties(form)
    blob = _source_blob(form)
    d_pub = _looks_public(davaci_raw)
    d_name, d_tckn, d_addr = _card_bits(_format_party_card(davaci_raw, public=d_pub))
    if _party_blank(d_name):
        d_name = _strip_party_label(davaci_raw) if not _party_blank(davaci_raw) else ""
    if not d_tckn:
        d_tckn = _find_tckn(blob, d_name)
    if not d_addr:
        d_addr = _find_addr(blob, d_name)
    v_pub = "İdare" in ptype or _looks_public(davali_raw) or _looks_public(_davali_from_prompt(blob))
    v_src = davali_raw if not _party_blank(davali_raw) else _davali_from_prompt(blob)
    v_name, v_tckn, v_addr = _card_bits(_format_party_card(v_src, public=v_pub))
    if _party_blank(v_name):
        v_name = _short_admin(_strip_party_label(v_src) or _davali_from_prompt(blob))
    if not v_addr:
        v_addr = _find_addr(blob, v_name)
    if not v_tckn and not v_pub:
        v_tckn = _find_tckn(blob, v_name)
    lawyer = _lawyer_lines(form)
    davaci = _tpl.client_block(d_name, d_tckn, d_addr)
    vekil = _tpl.lawyer_block(lawyer or ["Av. ........................"])
    davali = _tpl.defendant_block(v_name, v_addr, public=v_pub, tckn="" if v_pub else v_tckn)
    reqs = [_clean_req(ln) for ln in _field(form, "requests").splitlines() if ln.strip()]
    reqs = [r for r in reqs if r]
    if not reqs:
        reqs = [labor_wage_claim(form)] if is_labor(form) else [_clean_req(r) for r in pack["requests"]]
    reqs = _expand_requests(form, reqs, pack)
    konu = _konu_line(form, pack, reqs)
    req_block = "\n".join(f"{i + 1}) {r}" for i, r in enumerate(reqs))
    hukuki = _hukuki_nedenler_line(form, pack)
    form["_hukuki_part"] = hukuki
    acik = _book_vakia_block(form, pack, acik, research)
    if not re.search(r"(?m)^I\.\s+", acik or ""):
        from bettersaul_mcp.templates import outline, render_roman
        chunks = _split_vakia_blocks(acik)
        secs: list[tuple[str, list[str]]] = []
        ol = outline(ptype, flags, _source_blob(form))
        for i, (rom, title) in enumerate(ol):
            body = chunks[i] if i < len(chunks) else ""
            body = re.sub(r"^\s*\d{1,2}[\.\-)]\s*", "", body).strip()
            if body:
                secs.append((title, [body]))
        if len(chunks) > len(ol):
            extra = [re.sub(r"^\s*\d{1,2}[\.\-)]\s*", "", c).strip() for c in chunks[len(ol) :]]
            if extra and secs:
                secs[-1][1].extend(x for x in extra if x)
        if secs:
            acik = render_roman(secs)
    ztab = _ziynet_table(form)
    if ztab and ztab not in acik and "Boşanma" in ptype:
        acik = (acik.rstrip() + "\n\n" + ztab).strip()
    ev = _relevant_evidence(form, pack, acik)
    ev_block = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(ev))
    ekler = ["Vekâletname"] + [e for e in ev if not re.search(r"(?i)^vek[aâ]letname", e or "")]
    ek_block = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(ekler))
    sign = (lawyer[0].split(" (")[0] if lawyer else "Av. ........................")
    extra = "\n".join(lawyer[1:]) if len(lawyer) > 1 else ""
    sarti = f"DAVA ŞARTI\n\n{mediation_header(form)}" if needs_mediation(form) else ""
    sonuc = (
        "Yukarıda açıklanan nedenlerle;\n\n"
        f"{req_block}\n\n"
        f"{len(reqs) + 1}) yargılama giderleri ile vekâlet ücretinin davalı tarafa yükletilmesine\n\n"
        "karar verilmesini vekâleten talep ederim."
    )
    return _tpl.assemble(
        court,
        banner,
        davaci,
        vekil,
        davali,
        konu,
        acik.strip(),
        ev_block,
        hukuki,
        sonuc,
        ek_block,
        _tr_date(),
        f"{sign}\nDavacı Vekili\n{extra}".strip(),
        sarti,
    )


def _format_petition_spacing(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    heads = (
        r"T\.C\.",
        r"DAVA D[İI]LEK[ÇC]ES[İI]",
        r"DAVACI(?:\s+VEK[İI]L[İI]?)?",
        r"VEK[İI]L[İI]?\s*:",
        r"DAVALI",
        r"DAVA\s+KONUSU\s*:",
        r"DAVA\s+[ŞS]ARTI\s*:",
        r"KONU\s*:",
        r"HARCA\s+ESAS",
        r"A[ÇC]IKLAMALAR",
        r"DEL[İI]LLER",
        r"HUKUK[İI]\s+(SEBEPLER|NEDENLER|DAYANAKLAR|DAYANAK)",
        r"SONU[CÇ]\s+VE\s+[İI]STEM",
        r"EKLER\s*:",
    )
    for h in heads:
        text = re.sub(rf"(?<!\n\n)^({h})", r"\n\n\1", text, flags=re.I | re.M)
    text = re.sub(r"\n(?!\n)(\d{1,2}[\.\)\-])\s+", r"\n\n\1 ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_acik(text: str) -> tuple[str, str, str]:
    m = re.search(r"(?im)^(AÇIKLAMALAR:)\s*\n+", text or "")
    if not m:
        return text or "", "", ""
    head = (text or "")[: m.end()]
    rest = (text or "")[m.end() :]
    end = re.search(r"(?im)^(DELİLLER:|HUKUKİ NEDENLER:|SONUÇ VE İSTEM:)", rest)
    if not end:
        return head, rest.strip(), ""
    return head, rest[: end.start()].strip(), rest[end.start() :]


def _next_vakia_no(acik: str) -> int:
    nums = [int(n) for n in re.findall(r"(?m)^\s*(\d{1,2})[\.\)]\s+", acik or "")]
    return (max(nums) + 1) if nums else 1


def _want_web_fluency(form: dict) -> bool:
    v = form.get("webFluency", True)
    if v in (False, 0, "0", "false", "False", "off"):
        return False
    return True


def _fluency_batches(acik: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n{2,}", acik or "") if p.strip()]
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for p in paras:
        if buf and size + len(p) > 2600:
            out.append("\n\n".join(buf))
            buf = [p]
            size = len(p)
        else:
            buf.append(p)
            size += len(p)
    if buf:
        out.append("\n\n".join(buf))
    return out


def _fluency_locked(old: str, new: str) -> bool:
    if not new or _has_instr_leak(new) or _has_book_subs(new) or _is_prompt_block(new):
        return False
    if len(new) < max(80, int(len(old) * 0.55)):
        return False
    old_c = set(re.findall(r"\d{4}\s*/\s*\d+", old or ""))
    new_c = set(re.findall(r"\d{4}\s*/\s*\d+", new or ""))
    if new_c - old_c:
        return False
    return True


def _web_fluency_pass(form: dict, text: str) -> str:
    return text
    if "İdare" in str(form.get("petitionType") or ""):
        return text
    if not _want_web_fluency(form) or not (text or "").strip():
        return text
    head, acik, tail = _split_acik(text)
    if not head or len(acik) < 180:
        return text
    emit("status", "İnternet dil kalıpları alınıyor; cümleler akıcılaştırılıyor…")
    live = False
    try:
        live = internet_reachable()
    except Exception:
        live = False
    try:
        hints, n = fetch_style_hints(str(form.get("petitionType") or ""))
    except Exception:
        hints, n = "", 0
    if live and n:
        emit("research", f"İnternet: {n} resmî dil kalıbı alındı. Olay metni dışarı gitmedi.")
    elif live:
        emit("research", "İnternet açık; kalıp az geldi, yerleşik resmî dil kullanılıyor.")
    else:
        emit("research", "İnternet yok; akıcı yazım yerelde yapılacak.")
        hints = hints or (
            "- Cümleler özne–yüklem uyumlu ve bağlaçları çeşitlendirilmiş olsun.\n"
            "- Aynı vakıayı tekrarlama; her paragraf meseleyi ilerletsin."
        )
    if _is_27b() and not _server_health():
        emit("status", "Akıcı yazım atlandı (27B sunucusu kapalı).")
        return text
    rewritten: list[str] = []
    batches = _fluency_batches(acik)
    for i, batch in enumerate(batches, 1):
        emit("status", f"Akıcı yazım {i}/{len(batches)}…")
        try:
            piece = generate(
                [
                    {
                        "role": "system",
                        "content": (
                            "Türk hukuk yazım editörüsün. Yalnızca verilen AÇIKLAMALAR parçasını "
                            "daha akıcı resmî Türkçeyle yeniden yazarsın. İsim, tarih, tutar, "
                            "madde ve esas/karar numarasını değiştirmezsin. Yeni vakıa veya "
                            "içtihat eklemezsin. Sistem veya üslup talimatını yazmazsın. "
                            f"Üslup: {hints[:700]}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": batch,
                    },
                ],
                n_predict=min(1400, max(400, len(batch) // 3 + 280)),
                n_ctx=PETITION_CTX,
                live=True,
                busy="Cümleler internet kalıbıyla akıcılaştırılıyor…",
                think=False,
                allow_cli=False,
            )
        except Exception as exc:
            emit("research", f"Akıcı yazım parçası atlandı ({exc}).")
            rewritten.append(batch)
            continue
        piece = _strip_instr_leaks(_polish_tr(_fix_word_spacing(_usable_text(piece) or _clean_llama_out(piece) or "")))
        piece = _extract_body(piece, "AÇIKLAMALAR") or piece
        if _fluency_locked(batch, piece):
            rewritten.append(piece)
        else:
            rewritten.append(batch)
    new_acik = _strip_instr_leaks("\n\n".join(rewritten).strip())
    if _has_instr_leak(new_acik) or _draft_wrong_track(form, new_acik):
        emit("research", "Akıcı yazım sızıntı yaptı; ilk metin kaldı.")
        return text
    if not _fluency_locked(acik, new_acik) and len(new_acik) < int(len(acik) * 0.7):
        emit("research", "Akıcı yazım koruma kilidine takıldı; ilk metin kaldı.")
        return text
    emit("status", "Akıcı yazım bitti.")
    return (head + new_acik + "\n\n" + tail).strip()


def _stretch_petition(form: dict, text: str, research: str) -> str:
    return text
    if "İdare" in str(form.get("petitionType") or ""):
        return text
    target = MIN_PETITION_CHARS
    if len(text or "") >= target:
        return text
    up = str(form.get("userPrompt") or "")[:2200]
    if _is_prompt_block(up):
        up = _prompt_search_hint(up)
    facts = _field(form, "caseSummary")[:1200]
    mem = _CASE_MEMORY or _load_case_memory()
    cites = "\n".join(f"- {c}" for c in (mem.get("cites") or _extract_cites(research) or [])[:4])
    holds = "\n".join(f"- {h}" for h in (mem.get("holdings") or [])[:3])
    extra = _field(form, "extraInstructions", "extra")[:800]
    if _is_27b() and not _server_health():
        emit("status", "27B sunucusu yok; model her turda yeniden yüklenmesin diye uzatma kesildi.")
        emit("research", "Uzatma atlandı (sunucu kapalı).")
        return text
    for rnd in range(1 if _is_27b() else 3):
        if len(text or "") >= target:
            break
        head, acik, tail = _split_acik(text)
        if not head:
            break
        nxt = _next_vakia_no(acik)
        emit("status", f"Açıklamalar 5 A4’e tamamlanıyor ({len(text)}/{target})…")
        emit("research", f"Açıklama uzatma turu {rnd + 1}")
        try:
            piece = generate(
                [
                    {
                        "role": "system",
                        "content": (
                            "Sen Türk avukat asistanısın. Yalnızca numaralı AÇIKLAMALAR devamı yazarsın. "
                            "İsim, TCKN, tutar, karar numarası uydurmazsın. Soru ve araştırma prompt’u yazmazsın. "
                            "Talimatı dilekçeye yapıştırmazsın.\n"
                            + FILL_ANATOMY
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Dilekçe henüz 5 A4 değil ({len(text)} karakter). "
                            f"{nxt}. paragraftan itibaren en az dört uzun vakıa paragrafı yaz. "
                            "Her paragraf somut olayı ilerletsin; aynı metni kopyalama. "
                            "Yeni vakıa uydurma. Formda olmayan tutarı yazma. "
                            "Ret kararını emsal gibi yazma.\n"
                            f"Yazım yönü:\n{up}\n\n"
                            f"Olay:\n{facts}\n\n"
                            f"Ek:\n{extra}\n\n"
                            f"Gerçek künye:\n{cites or '- yok'}\n"
                            f"Gerekçe özeti:\n{holds or '- yok'}\n\n"
                            f"Şimdiye kadarki açıklamalar:\n{acik[-2400:]}\n\n"
                            "Yalnızca devam numaralı paragrafları yaz."
                        ),
                    },
                ],
                n_predict=1400,
                n_ctx=PETITION_CTX,
                live=True,
                busy="Açıklamalar CUDA ile genişletiliyor…",
                think=False,
                allow_cli=False,
            )
        except Exception as exc:
            emit("status", f"Uzatma turu atlandı ({exc}).")
            break
        piece = _strip_instr_leaks(_fix_word_spacing(_usable_text(piece) or _clean_llama_out(piece) or ""))
        piece = _strip_instr_leaks(_polish_tr(_extract_body(piece, "AÇIKLAMALAR") or piece))
        if (
            _has_instr_leak(piece)
            or _has_book_subs(piece)
            or _is_prompt_block(piece)
            or _is_banner(piece)
            or _vakia_too_repetitive(piece)
            or _draft_wrong_track(form, piece)
            or len(piece) < 180
        ):
            continue
        acik = (acik.rstrip() + "\n\n" + piece.strip()).strip()
        text = (head + acik + "\n\n" + tail).strip()
    return text


def _score_floor_ok(form: dict, text: str) -> bool:
    t = text or ""
    ptype = str(form.get("petitionType") or "")
    if len(t) < 900:
        return False
    if not re.search(r"(?m)^DAVACI\b", t) or not re.search(r"(?m)^DAVALI\b", t):
        return False
    if not re.search(r"(?m)^KONU\b", t) and not re.search(r"(?m)^DAVA KONUSU", t):
        return False
    if not re.search(r"(?i)HUKUK[İI]\s+(SEBEPLER|DAYANAKLAR|NEDENLER)", t):
        return False
    if not re.search(r"(?m)^T\.C\.\s*$", t) or not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:900]):
        return False
    if not re.search(r"(?im)^\s*Delil\s*[:：]", t) or not re.search(r"(?im)^\s*Hukuki dayanak\s*[:：]", t):
        return False
    if re.search(r"(?m)^DAVACI\s*:\s*DAVALI", t):
        return False
    if _has_instr_leak(t) or _has_book_subs(t) or _vakia_too_repetitive(t):
        return False
    if re.search(r"(?i)Türk hukuk yazım editörü|Üslup:|davan[ıi]n reddine dayan", t):
        return False
    davaci_m = re.search(r"(?im)^Ad Soyad\s*:\s*(.+)$", t) or re.search(r"(?m)^DAVACI\s*:\s*(.+)$", t)
    davali_m = re.search(r"(?m)^DAVALI(?:\s*:\s*(.+)$|\s*$)", t)
    if davaci_m and (
        _party_blank(davaci_m.group(1))
        or re.search(r"(?i)^\s*(\[ad soyad\]|ad\s*soyad|\.{5,})", davaci_m.group(1))
    ):
        return False
    if re.search(r"(?i)Davacı Ad Soyad|formda yoksa uydurulmaz|işlemindır", t):
        return False
    if _urgent_flags(form).get("adli") and not re.search(r"(?i)adli yardım", t):
        return False
    if "İdare" in ptype:
        aym_row = _aym_memory_row()
        if aym_row and not re.search(r"(?i)(?:Anayasa Mahkemesi|AYM).{0,80}(?:B\.\s*No|Başvuru|E\.\s*\d{4})", t):
            return False
    if re.search(r"(?i)doğrulanacak|kesinleştirilmeden|Vekile Not|Araştırma Notu|\[DOĞRULANACAK|\*\*|wikipedia", t):
        return False
    if "İdare" in ptype:
        if not re.search(r"(?im)^KONU\b", t) and not re.search(r"(?im)^DAVA D[İI]LEK", t):
            return False
        if _urgent_flags(form).get("ivedi") and not re.search(r"(?i)nöbetçi", t[:500]):
            return False
        dval = (davali_m.group(1) or "") if davali_m else ""
        if dval and re.search(r"(?i)doğrulanacak|kesinleştir|araştırma", dval):
            return False
        if davaci_m and davaci_m.group(1) and _looks_public(davaci_m.group(1)):
            return False
        if dval and re.search(r"T\.C\. Kimlik No", dval):
            return False
        if re.search(r"(?i)ziynet", t):
            return False
    if "Boşanma" not in ptype and re.search(r"(?i)Ziynet alacağı döküm", t):
        return False
    if "İdare" not in ptype and re.search(r"(?i)7315 sayılı|Atama Uygunluk Kararı", t):
        return False
    if "Boşanma" not in ptype and re.search(r"(?i)TMK\s*m\.\s*166|evlilik birliğinin temelinden sars", t):
        return False
    huk = ""
    for lab in ("HUKUKİ SEBEPLER", "HUKUKİ DAYANAKLAR", "HUKUKİ NEDENLER"):
        if lab in t and "SONUÇ VE İSTEM" in t:
            huk = t[t.find(lab) : t.find("SONUÇ VE İSTEM")]
            break
    if "Boşanma" in ptype and re.search(r"m\.\s*164", huk) and re.search(r"m\.\s*166", huk):
        return False
    if not re.search(r"(?m)^\s*1[\.\-)]\s+", t):
        return False
    if "AÇIKLAMALAR" not in t or "SONUÇ VE İSTEM" not in t:
        return False
    if re.search(r"(?i)wikipedia|duckduckgo|üslup kalıp", t):
        return False
    mem = _CASE_MEMORY or _load_case_memory()
    if re.search(r"(?i)Resm[iî]\s+Gazete.{0,48}\d{4,5}", t) and not _rg_memory_real():
        return False
    if re.search(r"(?i)Anayasa Mahkemesi.{0,80}(B\.\s*No|Başvuru\s+No|E\.\s*\d{4})", t) and not (mem.get("aym") or []):
        return False
    return True


def _named_section(text: str, start: str, end: str) -> str:
    t = text or ""
    m = re.search(rf"(?im)^{re.escape(start)}\s*:?\s*$", t)
    if not m:
        return ""
    n = re.search(rf"(?im)^{re.escape(end)}\s*:?\s*$", t[m.end() :])
    body = t[m.end() : m.end() + n.start()] if n else t[m.end() :]
    return body.strip()


def _acik_section(text: str) -> str:
    return (
        _named_section(text, "AÇIKLAMALAR", "HUKUKİ SEBEPLER")
        or _named_section(text, "AÇIKLAMALAR", "DELİLLER")
        or _named_section(text, "AÇIKLAMALAR", "HUKUKİ DAYANAKLAR")
    )


def _huk_section(text: str) -> str:
    return (
        _named_section(text, "HUKUKİ SEBEPLER", "DELİLLER")
        or _named_section(text, "HUKUKİ SEBEPLER", "SONUÇ VE İSTEM")
        or _named_section(text, "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM")
        or _named_section(text, "HUKUKİ NEDENLER", "SONUÇ VE İSTEM")
    )


def _replace_named_section(text: str, start: str, end: str, new_body: str) -> str:
    pat = re.compile(
        rf"(?ims)^({re.escape(start)})\s*:?\s*\n+(.*?)(?=^{re.escape(end)}\s*:?\s*$)",
        re.M,
    )
    repl = rf"\1 :\n\n{new_body.strip()}\n\n"
    out, n = pat.subn(repl, text or "", count=1)
    return out if n else (text or "")


def _header_party(text: str, label: str) -> str:
    block = _named_section(text, label, "DAVACI VEKİLİ" if label == "DAVALI" else "DAVALI")
    if label == "DAVACI":
        block = _named_section(text, "DAVACI", "DAVALI") or block
    m = re.search(r"(?im)^(?:Ad Soyad|Unvan)\s*[:：]\s*(.+)$", block or "")
    return (m.group(1) if m else "").strip()


def _dedupe_banners(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for ln in (text or "").splitlines():
        if re.search(r"(?i)İVEDİ YARGILAMA|ADLİ YARDIM TALEPLİ|YÜRÜTMENİN DURDURULMASI TALEPLİ", ln):
            key = re.sub(r"\s+", " ", ln.strip().upper())
            if key in seen:
                continue
            seen.add(key)
        out.append(ln)
    return "\n".join(out)


def _petition_gaps(form: dict, text: str) -> list[str]:
    t = text or ""
    ptype = str(form.get("petitionType") or "")
    flags = _urgent_flags(form)
    gaps: list[str] = []
    if not re.search(r"(?m)^T\.C\.\s*$", t):
        gaps.append("T.C. başlığı yok")
    if not re.search(r"(?i)DAVA D[İI]LEK[ÇC]ES[İI]", t[:1500]):
        gaps.append("DAVA DİLEKÇESİ başlığı yok")
    for head in ("DAVACI", "DAVALI", "KONU", "AÇIKLAMALAR", "DELİLLER", "SONUÇ VE İSTEM"):
        if head == "KONU" and re.search(r"(?im)^(?:KONU|DAVA KONUSU)\b", t):
            continue
        if not re.search(rf"(?im)^{head}\b", t):
            gaps.append(f"{head} bölümü yok")
    if not re.search(r"(?i)HUKUK[İI]\s+(SEBEPLER|DAYANAKLAR|NEDENLER)", t):
        gaps.append("HUKUKİ SEBEPLER yok")
    if "AÇIKLAMALAR" in t:
        if not re.search(r"(?im)^\s*Delil\s*[:：]", t):
            gaps.append("Vakıa altında Delil satırı yok")
        if not re.search(r"(?im)^\s*Hukuki dayanak\s*[:：]", t):
            gaps.append("Vakıa altında Hukuki dayanak satırı yok")
        if not re.search(r"(?im)^\s*Hukuki sonuç\s*[:：]", t):
            gaps.append("Vakıa altında Hukuki sonuç satırı yok")
    if flags.get("adli") and not re.search(r"(?i)adli yardım", t):
        gaps.append("Adli yardım istenmiş; metinde yok")
    if flags.get("ivedi") and "İdare" in ptype and not re.search(r"(?i)nöbetçi", t[:600]):
        gaps.append("İvedi istenmiş; nöbetçi idare mahkemesi yok")
    if flags.get("yd") and "İdare" in ptype and not re.search(r"(?i)yürütmenin durdurul", t):
        gaps.append("YD istenmiş; metinde yok")
    huk = _huk_section(t)
    if huk:
        ay = huk[: huk.find("Kanunlar")] if "Kanunlar" in huk else huk[:180]
        if re.search(r"m\.\s*\d+", ay) and "(" not in ay:
            gaps.append("Anayasa maddelerinde ilke adı yok")
        for ln in huk.splitlines():
            if re.search(r"(?:E\.\s*\d{4}|B\.\s*No)", ln) and not re.search(r"—|–", ln):
                if not re.search(r"Yargıtay|Danıştay|Anayasa Mahkemesi|\bAYM\b", ln, re.I):
                    gaps.append("İçtihat satırında mahkeme / daire adı yok")
                    break
    if "İdare" in ptype:
        mem = _CASE_MEMORY or _load_case_memory()
        if (mem.get("aym") or _aym_memory_rows()) and not re.search(
            r"(?i)(?:Anayasa Mahkemesi|AYM).{0,80}(?:B\.\s*No|Başvuru|E\.\s*\d{4})", t
        ):
            gaps.append("AYM künyesi çekilmiş; gövde/dayanakta yok")
    if re.search(r"(?i)wikipedia|Vekile Not|\[DOĞRULANACAK|formda 164 ise|4\.\s*BÖLÜM", t):
        gaps.append("Motor / araştırma sızıntısı")
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", t):
        gaps.append("ISO tarih — gg.aa.yyyy olmalı")
    return gaps


def _petition_inconsistencies(form: dict, text: str) -> list[str]:
    t = text or ""
    ptype = str(form.get("petitionType") or "")
    blob = _source_blob(form)
    flags = _urgent_flags(form)
    konu = _named_section(t, "KONU", "AÇIKLAMALAR") or _named_section(t, "DAVA KONUSU", "AÇIKLAMALAR")
    acik = _acik_section(t)
    huk = _huk_section(t)
    son = _named_section(t, "SONUÇ VE İSTEM", "EKLER")
    issues: list[str] = []
    if "Boşanma" in ptype:
        g = _divorce_ground(form)
        if g == "166" and re.search(r"TMK\s*m\.\s*164", huk):
            issues.append("Form TMK 166; HUKUKİ SEBEPLER’de 164 var")
        if g == "164" and re.search(r"TMK\s*m\.\s*166", huk) and not re.search(r"TMK\s*m\.\s*164", huk):
            issues.append("Form TMK 164; HUKUKİ SEBEPLER’de 166 var")
        if re.search(r"(?i)nafaka", son) and not re.search(r"(?i)nafaka", acik):
            issues.append("SONUÇ’ta nafaka var; AÇIKLAMALAR’da yok")
        if re.search(r"(?i)velayet", son) and not re.search(r"(?i)çocuk|velayet", acik):
            issues.append("SONUÇ’ta velayet var; vakıada çocuk yok")
        if re.search(r"(?i)I[\.\)]\s*EVLİLİK", acik) and not re.search(
            r"(?i)evl[ie]n|nik[aâ]h|evlilik birliği", acik[:900]
        ):
            issues.append("Roma I evlilik başlığı; evlilik vakıası yok")
        if re.search(r"(?i)ziynet", son) and not re.search(r"(?i)ziynet|altın|takı", acik):
            issues.append("SONUÇ’ta ziynet var; AÇIKLAMALAR’da yok")
    if "İdare" not in ptype and re.search(r"(?i)7315 sayılı|Atama Uygunluk Kararı", t):
        issues.append("Bu dava türünde 7315 / atama uygunluk metni var")
    if "İdare" in ptype and re.search(r"(?i)ziynet|TMK\s*m\.\s*16[46]", t):
        issues.append("İdare dilekçesinde boşanma / ziynet sızıntısı")
    if re.search(r"(?i)HAGB|hükmün açıklanmasının geri", blob) and re.search(
        r"(?i)(?:HAGB|hükmün açıklanmasının geri).{0,60}mahk[ûu]miyet|mahk[ûu]m edilmiş.{0,50}HAGB",
        t,
    ):
        issues.append("HAGB mahkûmiyet gibi yazılmış")
    if flags.get("adli") and not re.search(r"(?i)adli yardım", son):
        issues.append("Adli yardım banerde/formda var; SONUÇ’ta yok")
    if flags.get("ivedi") and "İdare" in ptype and not re.search(r"(?i)ivedi|nöbetçi", t[:800]):
        issues.append("İvedi istenmiş; başlık/baner yok")
    if "İdare" in ptype:
        if re.search(r"(?i)iptal", konu) and not re.search(r"(?i)iptal", son):
            issues.append("KONU iptal; SONUÇ’ta iptal yok")
        if re.search(r"(?i)yürütmenin durdurul|YD", konu + t[:800]) and not re.search(
            r"(?i)yürütmenin durdurul", son
        ):
            issues.append("YD istenmiş; SONUÇ’ta yok")
        davali_h = _header_party(t, "DAVALI")
        if re.search(r"(?i)Emniyet Genel", davali_h) and re.search(
            r"(?i)(?:atayan|işlemi tesis|atıma).{0,40}(?:Adalet Bakanlığı|Ceza ve Tevkifevleri|CTE)",
            acik,
        ) and not re.search(r"(?i)husumet", acik):
            issues.append("DAVALI EGM; atayan idare Adalet/CTE — husumet açıklanmalı")
    src = _source_blob(form).casefold()
    davaci_form, davali_form = _resolved_parties(form)
    davaci_h = _header_party(t, "DAVACI")
    if davaci_form and davaci_h and davaci_form.split()[0].casefold() in src:
        a = re.sub(r"\s+", " ", davaci_form).casefold()
        b = re.sub(r"\s+", " ", davaci_h).casefold()
        if a.split()[0] not in b and b.split()[0] not in a:
            issues.append("DAVACI adı formdaki müvekkil ile uyuşmuyor")
    davali_h = _header_party(t, "DAVALI")
    if davali_form and davali_h and davali_form.split()[0].casefold() in src:
        vf = re.sub(r"\s+", " ", davali_form).casefold()
        vh = re.sub(r"\s+", " ", davali_h).casefold()
        if not any(w in vh for w in vf.split() if len(w) > 3):
            issues.append("DAVALI başlığı formdaki davalı ile uyuşmuyor")
    if len(re.findall(r"(?i)İVEDİ YARGILAMA", t)) > 1:
        issues.append("Çift ivedi baner")
    if re.search(r"(?i)formda 164 ise|çekilmemişse yazılmaz|4\.\s*BÖLÜM", t):
        issues.append("Motor notu sızıntısı")
    if is_labor(form):
        try:
            from bettersaul_mcp.quality import detect_claims

            kset = detect_claims(konu)
            sset = detect_claims(son)
            aset = detect_claims(acik)
            if kset and sset and kset != sset:
                issues.append("KONU ile SONUÇ talep kümesi çelişiyor")
            ghost = aset - sset
            if ghost & {
                "ise_iade", "kidem", "ihbar", "fazla", "bos_sure", "baslatmama",
            }:
                issues.append("Açıklamada SONUÇ'ta olmayan iş kalemi var")
        except Exception:
            pass
    return issues


def _score_petition(form: dict, text: str) -> dict:
    try:
        from bettersaul_mcp.quality import review as _qrev
        mem = _CASE_MEMORY or _load_case_memory()
        rev = _qrev(form, text, memory=mem)
        if isinstance(rev, dict) and "score" in rev:
            return rev
    except Exception:
        pass
    t = text or ""
    ptype = str(form.get("petitionType") or "")
    flags = _urgent_flags(form)
    gaps = _petition_gaps(form, t)
    inc = _petition_inconsistencies(form, t)
    sekil = 20
    for g in gaps:
        if any(x in g for x in ("bölümü yok", "ISO", "sızıntı")):
            sekil -= 3
    sekil = max(0, sekil)
    usul = 15
    if flags.get("adli") and not re.search(r"(?i)adli yardım", t):
        usul -= 4
    if flags.get("ivedi") and "İdare" in ptype and not re.search(r"(?i)nöbetçi", t[:600]):
        usul -= 4
    if any("husumet" in x or "DAVALI" in x or "DAVACI adı" in x for x in inc):
        usul -= 3
    usul = max(0, usul)
    vakia = 20
    acik = _acik_section(t)
    if len(acik) < 400:
        vakia -= 8
    elif len(acik) < 900:
        vakia -= 4
    if any("vakıa" in x or "AÇIKLAMALAR" in x or "Roma" in x for x in inc):
        vakia -= 5
    if re.search(r"(?i)müvekkil", acik):
        pass
    else:
        vakia -= 3
    vakia = max(0, vakia)
    hukuk = 20
    if any("TMK" in x or "7315" in x or "HAGB" in x or "ziynet sızıntı" in x for x in inc):
        hukuk -= 6
    if any("KONU iptal" in x or "YD istenmiş" in x or "nafaka" in x or "velayet" in x for x in inc):
        hukuk -= 4
    hukuk = max(0, hukuk)
    atif = 15
    huk = _huk_section(t)
    if not huk:
        atif -= 8
    else:
        ay_chunk = huk[: huk.find("Kanunlar")] if "Kanunlar" in huk else huk[:160]
        if "(" not in ay_chunk:
            atif -= 3
        bare = [ln for ln in huk.splitlines() if re.search(r"(?:E\.\s*\d{4}|B\.\s*No)", ln) and "—" not in ln]
        if bare:
            atif -= 4
        if not re.search(r"(?:E\.\s*\d{4}|B\.\s*No|Danıştay|Yargıtay|AYM)", huk):
            atif -= 2
    atif = max(0, atif)
    temizlik = 10
    if re.search(r"(?i)wikipedia|Vekile Not|formda 164|4\.\s*BÖLÜM|\[DOĞRULANACAK", t):
        temizlik -= 5
    if len(re.findall(r"(?i)İVEDİ YARGILAMA", t)) > 1:
        temizlik -= 2
    if _has_instr_leak(t) or _has_book_subs(t):
        temizlik -= 4
    temizlik = max(0, temizlik)
    score = sekil + usul + vakia + hukuk + atif + temizlik
    return {
        "score": score,
        "breakdown": {
            "Şekil": f"{sekil}/20",
            "Usul": f"{usul}/15",
            "Vakıa": f"{vakia}/20",
            "Hukuk": f"{hukuk}/20",
            "Atıf": f"{atif}/15",
            "Temizlik": f"{temizlik}/10",
        },
        "gaps": gaps,
        "inconsistencies": inc,
    }


def _filter_sonuc_to_claims(form: dict, text: str) -> str:
    if not is_labor(form):
        return text
    son = _named_section(text, "SONUÇ VE İSTEM", "EKLER")
    if not son:
        return text
    claims = _form_claims(form)
    pats = (
        ("ise_iade", r"işe iade|feshin geçersiz"),
        ("baslatmama", r"işe başlatmama"),
        ("bos_sure", r"boşta geçen"),
        ("kidem", r"kıdem tazmin"),
        ("ihbar", r"ihbar tazmin"),
        ("fazla", r"fazla (çalış|mesai)"),
        ("izin", r"yıllık izin"),
    )
    kept: list[str] = []
    for ln in son.splitlines():
        drop = False
        for code, pat in pats:
            if code in claims or not re.search(pat, ln, re.I):
                continue
            if any(c in claims and re.search(p, ln, re.I) for c, p in pats):
                continue
            if "ucret" in claims and re.search(r"ücret alaca|ödenmeyen ücret|eksik / ödenmeyen", ln, re.I):
                continue
            drop = True
            break
        if not drop:
            kept.append(ln)
    new = "\n".join(kept).strip()
    if not new:
        return text
    return _replace_named_section(text, "SONUÇ VE İSTEM", "EKLER", new)


def _apply_consistency_fixes(form: dict, pack: dict, text: str) -> str:
    t = _ensure_header(form, pack, _dedupe_banners(text or ""))
    if is_labor(form):
        t = _replace_named_section(t, "KONU", "AÇIKLAMALAR", labor_konu(form))
        t = _filter_sonuc_to_claims(form, t)
    huk_line = _hukuki_nedenler_line(form, pack)
    t2 = _replace_named_section(t, "HUKUKİ SEBEPLER", "DELİLLER", huk_line)
    t = t2 if t2 != t else _replace_named_section(t, "HUKUKİ DAYANAKLAR", "SONUÇ VE İSTEM", huk_line)
    ptype = str(form.get("petitionType") or "")
    if "İdare" not in ptype:
        t = re.sub(r"(?im)^.*7315 sayılı[^\n]*\n?", "", t)
        t = re.sub(r"(?im)^.*Atama Uygunluk Kararı[^\n]*\n?", "", t)
    if "İdare" in ptype:
        t = re.sub(r"(?im)^.*\bziynet\b[^\n]*\n?", "", t)
        t = re.sub(r"(?i)TMK\s*m\.\s*16[46][^\n]*", "", t)
    t = re.sub(r"(?i)\s*\(veya formda 164 ise yalnızca 164\)", "", t)
    t = re.sub(r"(?i)formda 164 ise[^.]*\.?", "", t)
    return _ensure_header(form, pack, t)


def _emit_review(rev: dict) -> None:
    try:
        from bettersaul_mcp.quality import format_report as _qfmt
        if rev.get("findings") is not None:
            emit("research", _qfmt(rev))
            crit = any(f.get("sev") == "kritik" for f in (rev.get("findings") or []))
            if rev.get("ok"):
                emit("status", f"Dilekçe testleri geçti ({rev.get('score')}/100).")
            elif crit:
                emit("status", f"Dilekçe {rev.get('score')}/100 — kritik hata mevcut; mahkemeye sunulmadan düzeltin.")
            else:
                emit("status", f"Dilekçe {rev.get('score')}/100 — kalite raporu notlara yazıldı.")
            return
    except Exception:
        pass
    br = rev.get("breakdown") or {}
    parts = " · ".join(f"{k} {v}" for k, v in br.items())
    emit("research", f"Dilekçe kalite testi: {rev.get('score', 0)}/100  ({parts})")
    gaps = rev.get("gaps") or []
    inc = rev.get("inconsistencies") or []
    if gaps:
        emit("research", "Eksikler:\n" + "\n".join(f"- {g}" for g in gaps[:12]))
    else:
        emit("research", "Eksik taraması: şekil/usul boşluğu yok.")
    if inc:
        emit("research", "Tutarsızlıklar:\n" + "\n".join(f"- {x}" for x in inc[:12]))
    else:
        emit("research", "Tutarsızlık testi geçti (TMK, husumet, HAGB, baner, KONU–SONUÇ, dayanak).")
    if int(rev.get("score") or 0) >= 80 and not inc:
        emit("status", f"Dilekçe testleri geçti ({rev.get('score')}/100).")
    else:
        emit("status", f"Dilekçe {rev.get('score')}/100 — eksik/tutarsızlık notlara işlendi.")


def _qa_after_write(form: dict, pack: dict, research: str, text: str) -> str:
    emit("status", "Dilekçe yazıldı. Veri / çelişki / madde / içtihat testi…")
    t = _apply_consistency_fixes(form, pack, text)
    t = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(t))))
    rev = _score_petition(form, t)
    leftover = rev.get("inconsistencies") or []
    crit = any(f.get("sev") == "kritik" for f in (rev.get("findings") or []))
    if leftover or crit or int(rev.get("score") or 0) < 80:
        t2 = _apply_consistency_fixes(form, pack, t)
        t2 = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(t2))))
        if t2 != t:
            emit("research", "Tutarsızlık düzeltmesi uygulandı; metin yeniden ölçüldü.")
            t = t2
            rev = _score_petition(form, t)
    if int(rev.get("score") or 0) < 80 and not _score_floor_ok(form, t):
        emit("research", "Puan 80 altında kaldı; vakıa kartı ile bir tur daha kuruluyor.")
        t = _ensure_score_floor(form, pack, research, t)
        t = _apply_consistency_fixes(form, pack, t)
        t = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(t))))
        rev = _score_petition(form, t)
    _emit_review(rev)
    return t


def _ensure_score_floor(form: dict, pack: dict, research: str, text: str) -> str:
    text = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(text or ""))))
    if _score_floor_ok(form, text):
        return text
    emit("research", "80 tabanı: model/sızıntı gövdesi atıldı, vakıa kartı yazıldı.")
    emit("status", "Dilekçe 80 puan tabanına çekiliyor…")
    acik = _narrative_aciklamalar(form, pack, research)
    rebuilt = _compose_petition(form, pack, acik, research)
    return _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(rebuilt))))


def _fact_raw_for_extract(form: dict) -> str:
    bits = [
        str(form.get("petitionType") or ""),
        str(form.get("court") or ""),
        str(form.get("parties") or ""),
        str(form.get("caseSummary") or ""),
        str(form.get("requests") or ""),
        str(form.get("lawyerName") or ""),
    ]
    up = str(form.get("userPrompt") or "")
    extra = str(form.get("extraInstructions") or "")
    if _is_prompt_block(up):
        bits.extend(_all_fact_sentences(up, extra))
    else:
        if up.strip():
            bits.append(up[:1800])
        if extra.strip() and not _is_prompt_block(extra):
            bits.append(extra[:800])
    return "\n".join(x for x in bits if str(x).strip())[:3500]


def _qwen_stage(messages: list[dict], *, n_predict: int, busy: str) -> str:
    if not _model_available():
        return ""
    if _is_27b() and not _server_health():
        return ""
    try:
        text = generate(
            messages,
            n_predict=_27b_predict(n_predict) if _is_27b() else min(n_predict, 1600),
            n_ctx=_27b_ctx(4096) if _is_27b() else min(PETITION_CTX, 8192),
            live=True,
            busy=busy,
            think=False,
            allow_cli=False if _is_27b() else True,
        )
    except Exception as exc:
        emit("research", f"Qwen aşaması atlandı ({exc}).")
        return ""
    return _strip_instr_leaks(_usable_text(text) or _clean_llama_out(text) or "")


def _pipe_extract(form: dict) -> dict:
    from bettersaul_mcp.motor.stages import case_from_model, fact_messages, parse_case_json

    emit("status", "1/4 Veri yapılandırılıyor…")
    raw = _fact_raw_for_extract(form)
    text = _qwen_stage(
        fact_messages(raw),
        n_predict=700,
        busy="Davacı, davalı, mahkeme, olay, talep çıkarılıyor…",
    )
    case = parse_case_json(text)
    if not (case.get("olaylar") or case.get("davaci", {}).get("ad")):
        try:
            from bettersaul_mcp.quality import extract_model

            case = case_from_model(extract_model(form, ""), form)
        except Exception:
            pass
    emit("research", "Yapılandırılmış dosya hazır. Dilekçe bu aşamada yazılmadı.")
    return case


def _pipe_generate(form: dict, pack: dict, research: str) -> str:
    from bettersaul_mcp.motor.stages import case_brief, generate_messages
    from bettersaul_mcp.templates import outline_text

    emit("status", "2/4 Dilekçe yazılıyor…")
    case = form.get("_case") or {}
    brief = case_brief(case)
    flags = _urgent_flags(form)
    ol = outline_text(str(form.get("petitionType") or ""), flags, _source_blob(form))
    hukuki = _hukuki_nedenler_line(form, pack)
    form["_hukuki_part"] = hukuki
    cites = _rich_ictihat_lines(form)
    court, banner = _header_bits(form, pack)
    text = _qwen_stage(
        generate_messages(brief, ol, cites, hukuki, court=court, banner=banner),
        n_predict=2200,
        busy="Dilekçe taslağı üretiliyor…",
    )
    text = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(text))))
    if not text or not _looks_like_petition(text) or _has_instr_leak(text) or _draft_wrong_track(form, text):
        emit("research", "Model taslağı kullanılamadı; karttan kuruldu. Kontrol sonra.")
        acik = _narrative_aciklamalar(form, pack, research)
        text = _compose_petition(form, pack, acik, research)
        text = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(text))))
    return _apply_consistency_fixes(form, pack, text)


def _pipe_check(form: dict, text: str) -> dict:
    from bettersaul_mcp.motor.stages import (
        case_brief,
        check_messages,
        format_check_report,
        parse_check_report,
    )

    emit("status", "3/4 Kalite kontrol…")
    case = form.get("_case") or {}
    raw = _qwen_stage(
        check_messages(case_brief(case), text),
        n_predict=500,
        busy="Talep / sonuç / açıklama / delil / tarih / hukuki sebep…",
    )
    report = parse_check_report(raw)
    emit("research", format_check_report(report))
    return report


def _pipe_repair(form: dict, pack: dict, text: str, report: dict) -> str:
    from bettersaul_mcp.motor.stages import case_brief, needs_repair, repair_messages

    if not needs_repair(report):
        emit("status", "4/4 Düzeltme gerekmedi.")
        return text
    emit("status", "4/4 Dilekçe düzeltiliyor…")
    fixed = _qwen_stage(
        repair_messages(case_brief(form.get("_case") or {}), text, report),
        n_predict=2200,
        busy="Yalnızca rapor maddeleri düzeltiliyor…",
    )
    fixed = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(fixed))))
    if not fixed or not _looks_like_petition(fixed) or _has_instr_leak(fixed) or _draft_wrong_track(form, fixed):
        emit("research", "Düzeltme metni alınamadı; önceki dilekçe korundu.")
        return text
    return _apply_consistency_fixes(form, pack, fixed)


def write_petition(form: dict) -> str:
    t0 = time.time()
    blocked = _hw_refuse()
    if blocked:
        emit("status", blocked)
        return blocked
    form = dict(form or {})
    try:
        return _write_petition_body(form, t0)
    except Exception:
        _save_prep_timing(form, time.time() - t0, False)
        raise


def _write_petition_body(form: dict, t0: float) -> str:
    _take_user_prompt(form)
    _hydrate_form_facts(form)
    form = align_form(form)
    emit("status", "BetterSaul MCP bağlanıyor…")
    boot: threading.Thread | None = None
    if _is_27b() and _model_available():
        emit("status", "CUDA sunucusu arka planda açılıyor; tarama aynı anda yürür…")
        boot = threading.Thread(target=lambda: _ensure_server(_27b_ctx(PETITION_CTX)), daemon=True)
        boot.start()
    elif not _model_available():
        emit("research", "Dilekçe BetterSaul MCP + karttan kurulacak. Claude Desktop eşzamanlı açık kalır.")
    tools = wait_mcp_tools(8)
    research = ""
    if tools:
        emit("status", f"Resmî kaynaklar {_rounds(form)} tur taranacak; GPU muhakeme bir kez, sonra dilekçe.")
        emit("research", f"{_rounds(form)} turlu tarama başladı. 1. turda dilekçe yok.")
        research = seed_research(form, tools)
    else:
        emit("research", "MCP bağlanamadı; içtihat numarası yazılmayacak.")
    if boot is not None:
        boot.join(timeout=240)
        if not _server_health():
            emit("status", "CUDA sunucusu ikinci kez deneniyor…")
            _ensure_server(_27b_ctx(PETITION_CTX))
    case = _pipe_extract(form)
    try:
        from bettersaul_mcp.motor.stages import merge_case_into_form

        form = merge_case_into_form(form, case)
    except Exception:
        form["_case"] = case
    form = align_form(form)
    pack = pack_for(str(form.get("petitionType") or ""))
    cites = _extract_cites(research)
    if cites:
        emit("research", "İşlenecek içtihat: " + " · ".join(cites[:5]))
    text = _pipe_generate(form, pack, research)
    text = _ensure_lawyer(text, form)
    report = _pipe_check(form, text)
    text = _pipe_repair(form, pack, text, report)
    text = _sanitize_petition(form, _strip_instr_leaks(_polish_tr(_format_petition_spacing(text))))
    text = _ensure_header(form, pack, text)
    text = _ensure_lawyer(text, form)
    _save_prep_timing(form, time.time() - t0, True)
    return text


def _field(m: dict, *names: str) -> str:
    for n in names:
        v = m.get(n)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def main() -> None:
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    emit("status", "Yerel motor hazır.")
    import atexit
    atexit.register(_stop_server)
    for line in sys.stdin:
        line = (line or "").strip().lstrip("\ufeff")
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            emit("status", "Komut satırı okunamadı, atlandı.")
            continue
        if not isinstance(msg, dict):
            emit("error", "Geçersiz komut")
            continue
        cmd = msg.get("cmd") or msg.get("Cmd")
        if cmd == "quit":
            _stop_server()
            break
        try:
            if cmd == "chat":
                emit("error", "Sohbet kaldırıldı. Dilekçe BetterSaul’da; araştırma Claude Desktop + BetterSaul MCP ile yürür.")
            elif cmd == "petition":
                form = msg.get("form") or {}
                text = write_petition(form)
                emit("done", text)
            else:
                emit("error", "Bilinmeyen komut")
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            emit("error", str(exc))


if __name__ == "__main__":
    main()
