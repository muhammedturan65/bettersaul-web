from __future__ import annotations

import calendar
import hashlib
import hmac
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

DOWNLOAD_URL = "https://bettersaul.ai/masaustu"
MESSAGE = (
    "Bu sürümün kullanım süresi doldu. Yeni sürüm ücretsizdir; "
    "yalnızca size daha iyi bir sürüm sunmak için bu tarihte güncelleme istiyoruz. "
    "BetterSaul.ai/masaustu sitesinden yeni versiyonu ücretsiz indirin."
)
_LOCK_FILE = "runtime-16.lock"
_LOCK_REG = "lock16"
_KEY = bytes(
    [0x42, 0x53, 0x6D, 0x61, 0x73, 0x61, 0x32, 0x30, 0x32, 0x36, 0x11, 0xE7, 0x4A, 0x9C, 0x08, 0x73]
)


def _add_months(dt: datetime, months: int) -> datetime:
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return dt.replace(year=y, month=m, day=d)


def _build_expiry() -> tuple[datetime, datetime] | None:
    build = datetime(2026, 9, 20, tzinfo=timezone.utc)
    expiry = _add_months(build, 2)
    if build.year != 2026 or build.month != 9 or build.day != 20:
        return None
    if expiry.year != 2026 or expiry.month != 11 or expiry.day != 20:
        return None
    return build, expiry


def _data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BetterSaul"
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(root) / "BetterSaul"


def _hmac(sec: int) -> str:
    return hmac.new(_KEY, f"bs-masa|{sec}".encode("utf-8"), hashlib.sha256).hexdigest()


def _format_stamp(dt: datetime) -> str:
    sec = int(dt.timestamp())
    return f"{sec}|{_hmac(sec)}"


def _parse_stamp(raw: str) -> datetime | None:
    parts = (raw or "").strip().split("|")
    if len(parts) != 2:
        return None
    try:
        sec = int(parts[0])
    except ValueError:
        return None
    if not hmac.compare_digest(_hmac(sec), parts[1].strip().lower()):
        return None
    return datetime.fromtimestamp(sec, tz=timezone.utc)


def _reg_get(name: str) -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BetterSaul") as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v) if v is not None else None
    except Exception:
        return None


def _reg_set(name: str, value: str) -> None:
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\BetterSaul") as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    except Exception:
        pass


def _read_last() -> datetime | None:
    best: datetime | None = None
    path = _data_dir() / "runtime.stamp"
    try:
        if path.is_file():
            best = _parse_stamp(path.read_text(encoding="utf-8"))
    except OSError:
        pass
    parsed = _parse_stamp(_reg_get("rt") or "")
    if parsed is not None and (best is None or parsed > best):
        best = parsed
    return best


def _write(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def _persist_expired() -> None:
    line = _format_stamp(datetime.now(timezone.utc))
    d = _data_dir()
    _write(d / _LOCK_FILE, line)
    _write(d / "runtime.stamp", line)
    _reg_set(_LOCK_REG, "1")
    _reg_set("rt", line)


def _lock_present() -> bool:
    lock = _data_dir() / _LOCK_FILE
    try:
        if lock.is_file() and _parse_stamp(lock.read_text(encoding="utf-8")):
            return True
    except OSError:
        pass
    return _reg_get(_LOCK_REG) == "1"


def _clear_lock() -> None:
    try:
        (_data_dir() / _LOCK_FILE).unlink(missing_ok=True)
    except OSError:
        pass
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\BetterSaul", 0, winreg.KEY_SET_VALUE
        ) as k:
            winreg.DeleteValue(k, _LOCK_REG)
    except Exception:
        pass


def _file_times() -> datetime | None:
    best: datetime | None = None
    d = _data_dir()
    for name in ("archive.db", "runtime.stamp", _LOCK_FILE, "logs/mcp.log"):
        p = d / name
        try:
            if not p.is_file():
                continue
            t = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
            if best is None or t > best:
                best = t
        except OSError:
            continue
    return best


def _network_utc() -> datetime | None:
    try:
        req = urllib.request.Request(
            "https://bettersaul.ai/",
            method="HEAD",
            headers={"User-Agent": "BetterSaulDesktop/1.5"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.headers.get("Date")
        if not raw:
            return None
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        if dt.year < 2026:
            return None
        return dt
    except Exception:
        return None


def blocked() -> bool:
    pair = _build_expiry()
    if pair is None:
        _persist_expired()
        return True
    build, expiry = pair

    # İnternet tarih ve saati belirleyicidir: internet varken yalnızca gerçek
    # tarihe bakılır. Eski test damgaları, ileri alınmış yerel saat veya yanlış
    # kalmış kilit, süresi dolmamış sürümü kilitleyemez.
    net = _network_utc()
    if net is not None:
        line = _format_stamp(net)
        _write(_data_dir() / "runtime.stamp", line)
        _reg_set("rt", line)
        if net >= expiry:
            _persist_expired()
            return True
        _clear_lock()
        return False

    # İnternet yokken: kilit ve saat geri alma denetimleri.
    if _lock_present():
        _persist_expired()
        return True

    local = datetime.now(timezone.utc)
    last = _read_last()
    files = _file_times()

    if last is not None and local + timedelta(hours=6) < last:
        _persist_expired()
        return True
    if files is not None and local + timedelta(hours=6) < files:
        _persist_expired()
        return True

    trusted = local
    for extra in (last, files):
        if extra is not None and extra > trusted:
            trusted = extra
    if trusted < build:
        trusted = build

    line = _format_stamp(trusted)
    _write(_data_dir() / "runtime.stamp", line)
    _reg_set("rt", line)

    if trusted >= expiry:
        _persist_expired()
        return True
    return False


def enforce() -> None:
    if blocked():
        print(MESSAGE, file=sys.stderr, flush=True)
        raise SystemExit(2)
