# BetterSaul Web Migration — Worklog

Bu belge, BetterSaul projesinin masaüstü uygulamasından web tabanlı mimariye taşınması sürecindeki analiz, karar ve ilerlemeleri kayıt altına alır.

---

## Task ID: 1 — Engine Core Analysis

**Tarih:** 2025
**Kapsam:** `/app/engine/` dizinindeki 8 çekirdek dosyanın derinlemesine analizi
**Toplam satır sayımı (wc -l ile doğrulandı):**

| Dosya | Satır | Durum |
|---|---|---|
| `engine.py` | 7,857 | Doğrulandı (ANA MOTOR) |
| `legal_tracks.py` | 420 | Doğrulandı |
| `petition_packs.py` | 197 | Doğrulandı |
| `system_prompt.txt` | 22 | Doğrulandı |
| `petition_prompt.txt` | 112 | Doğrulandı |
| `turkish_reason.txt` | 13 | Doğrulandı |
| `requirements.txt` | 5 | Doğrulandı |
| `web_style.py` | 38 | Doğrulandı |
| **TOPLAM** | **8,664** | |

Ek olarak `engine/bettersaul_mcp/` alt paketinde tespit edilen destek modülleri (kullanıcı tarafından istenmedi ama motor tarafından import ediliyor): `sources.py`, `anayasa.py`, `mevzuat.py`, `petition_tools.py`, `quality.py`, `license_gate.py`, `templates.py`, `tls.py`, `ping.py`, `server.py`, `__main__.py` ve `motor/` (alt paket: `pipeline.py`, `stages.py`, `catalog.py`, `__init__.py`).

---

### 1. engine.py Genel Yapısı

**Dosya boyutu:** 7,857 satır, tek dosya. Bu, tek başına en büyük taşıma riskidir.

#### 1.1 Modülün Genel Mimarisi

`engine.py` bir **stdin/stdout JSON-line sunucu** olarak tasarlanmıştır (satır 7816 `main()`). WinForms (C#) görsel uygulamasından gelen her satır JSON komut (`{"cmd":"petition","form":{...}}`) parse edilir, çıktı `emit(event, text)` ile tekrar JSON olarak `stdout`'a basılır (satır 87-90). Yani **desktop UI ↔ engine** arayüzü bir pipe'tır, HTTP/socket değildir.

```python
# satır 87-90
def emit(event: str, text: str = "") -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps({"event": event, "text": text}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
```

```python
# satır 7816-7857 main() döngüsü
def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")  # 7818
    sys.stdout.reconfigure(encoding="utf-8", errors="replace") # 7819
    for line in sys.stdin:
        msg = json.loads(line)                                  # 7831
        cmd = msg.get("cmd")                                    # 7838
        if cmd == "petition":
            text = write_petition(msg.get("form") or {})        # 7847
            emit("done", text)                                  # 7848
```

#### 1.2 Ana Sınıflar ve Fonksiyonlar (imza + satır)

Yalnızca **1 sınıf** vardır; geri kalan tüm kod ~200 modül-seviye fonksiyondur.

| Sınıf/Fonksiyon | Satır | İmza | Rol |
|---|---|---|---|
| `LiveOut` | 495 | `class LiveOut:` | llama.cpp stdout stream parser; UI'a token-token akış (`emit("delta", ...)`). İç metotlar: `feed()` (507), `_queue()` (538), `flush()` (549). |
| `emit` | 87 | `emit(event: str, text: str = "")` | Tüm UI durum bildirimleri buradan geçer. |
| `write_petition` | 7746 | `write_petition(form: dict) -> str` | Dışarıdan çağrılan tek dilekçe API'si. |
| `_write_petition_body` | 7760 | `_write_petition_body(form, t0)` | Asıl dilekçe üretim pipeline'ı (8 aşamalı). |
| `run_agent` | 2978 | `run_agent(user_messages, system_prompt, n_predict, n_ctx, min_chars, form, research)` | Sohbet/agent turu; **kaldırılmış** (`cmd:"chat"` artık hata verir, satır 7843-7844). |
| `generate` | 2925 | `generate(messages, n_predict, n_ctx, live, busy, think, allow_cli)` | LLM dispatcher: 27B → server, 14B → llama-cpp-python, fallback → llama-cli. |
| `complete_server` | 2641 | `complete_server(messages, n_predict, live, busy)` | `llama-server` HTTP `/v1/chat/completions` streaming çağrısı. |
| `complete_cli` | 2822 | `complete_cli(messages, n_predict, n_ctx, live, busy)` | `llama-cli` subprocess (tek seferlik yükleme). |
| `complete_llamacpp` | 2222 | `complete_llamacpp(messages)` | `llama_cpp.Llama` Python binding (14B için). |
| `seed_research` | 2020 | `seed_research(form, tools) -> str` | Çok turlu MCP tarama orkestrasyonu (3 tur). |
| `mcp_call` | 925 | `mcp_call(name, args) -> str` | Local-first, sonra HTTP MCP çağrısı. |
| `_local_mcp_call` | 731 | `_local_mcp_call(name, args) -> str` | 19 MCP aracının yerel dağıtıcı tablosu. |
| `_local_tool_list` | 573 | `_local_tool_list() -> list[dict]` | 19 MCP aracının schema bildirimi. |
| `_research_queries` | 1391 | `_research_queries(form) -> list[str]` | Türe göre Yargıtay/Danıştay arama sorgusu üretimi. |
| `_think_next_queries` | 1576 | `_think_next_queries(form, raw, used, tur)` | Tur-bazlı sorgu daraltma (10 tura kadar dallanan plan). |
| `_llm_think_tour` | 1721 | `_llm_think_tour(form, tur, digest, used)` | GPU ile muhakeme turu (dilekçe yazmaz, yalnız sorgu üretir). |
| `_seed_official_sources` | 1917 | `_seed_official_sources(form, by_name) -> tuple[list, list, list]` | Mevzuat + AYM (en fazla 1) + Resmî Gazete tarama. |
| `_compose_petition` | 6793 | `_compose_petition(form, pack, acik, research) -> str` | Templates tabanlı iskeletten dilekçe kurulumu. |
| `_narrative_aciklamalar` | 5972 | `_narrative_aciklamalar(form, pack, research) -> str` | Açıklamalar gövdesi; idare/iş/boşanma/Genel dallanması. |
| `_idare_narrative` | 5751 | `_idare_narrative(form, pack, research)` | İdare dava türüne özel gövde üretimi. |
| `_labor_narrative` | 5639 | `_labor_narrative(form, pack, research)` | İş dava türüne özel gövde üretimi. |
| `_score_petition` | 7407 | `_score_petition(form, text) -> dict` | 6 boyutlu (Şekil/Usul/Vakıa/Hukuk/Atıf/Temizlik = 100) puanlama. |
| `_score_floor_ok` | 7129 | `_score_floor_ok(form, text) -> bool` | 80 puan tabanı geçer kontrolü. |
| `_petition_gaps` | 7266 | `_petition_gaps(form, text) -> list[str]` | Şekil eksiklik tespiti. |
| `_petition_inconsistencies` | 7318 | `_petition_inconsistencies(form, text) -> list[str]` | Çelişki tespiti (KONU↔SONUÇ, husumet, HAGB, baner). |
| `_pipe_extract` | 7658 | `_pipe_extract(form) -> dict` | 1/4: Veri yapılandırma (model → case JSON). |
| `_pipe_generate` | 7680 | `_pipe_generate(form, pack, research) -> str` | 2/4: Dilekçe taslağı üretimi. |
| `_pipe_check` | 7707 | `_pipe_check(form, text) -> dict` | 3/4: Kalite kontrol raporu. |
| `_pipe_repair` | 7727 | `_pipe_repair(form, pack, text, report)` | 4/4: Model düzeltme turu. |
| `_ensure_server` | 2536 | `_ensure_server(n_ctx: int) -> bool` | llama-server subprocess ömrü yönetimi. |
| `_gpu_layers` | 2419 | `_gpu_layers() -> str` | VRAM'e göre ngl hesabı (27B/14B/9B). |
| `_sanitize_petition` | 4062 | `_sanitize_petition(form, text) -> str` | Tür karışıklığı, prompt sızıntısı, off-track cümle temizliği. |
| `_strip_instr_leaks` | 3915 | `_strip_instr_leaks(text)` | Prompt/markör sızıntısı regex ile temizliği (~30 kural). |

#### 1.3 Kullanılan External Library'ler

`requirements.txt` (yalnızca 5 satır) çok minimal:

```
mcp>=1.6.0          # Model Context Protocol SDK
anyio>=4.0.0        # async runtime (MCP transport için)
httpx>=0.27.0       # HTTP client
truststore>=0.10.0  # Windows cert store
```

Fakat `engine.py` içinden **koşullu (try/except)** olarak daha fazla library yüklenir:

- `llama_cpp` (satır 2223, 2956) — Python binding, opsiyonel.
- `urllib.request` (satır 2482, 2647) — `llama-server` HTTP client (stdlib).
- `ctypes` (satır 2246, 2841) — Windows `kernel32` (`GetShortPathNameW`, `SetConsoleOutputCP`).
- `subprocess` (satır 8) — `llama-cli`, `llama-server.exe`, `nvidia-smi.exe`, `netstat`, `taskkill`.
- `threading` (satır 10) — `LiveOut` akış pump, CUDA boot thread (satır 7768).
- `pathlib`, `re`, `json`, `os`, `sys`, `time`, `traceback`, `datetime` — stdlib.

#### 1.4 Desktop'a Özel Bağımlılıklar

Bu bölüm web taşınabilirliği için **kritik engel** noktalarıdır:

| Bağımlılık | Satır | Kod Alıntısı | Web Sorunu |
|---|---|---|---|
| `LOCALAPPDATA` env var | 112, 1242 | `Path(os.environ.get("LOCALAPPDATA") or "") / "BetterSaul"` | Windows-only; webde yok. |
| `subprocess.Popen` (llama-server.exe) | 2586 | `_server_proc = subprocess.Popen(cmd, ...)` | Sunucuda GPU process spawn yasak. |
| `llama-cli` binary | 2822 | `complete_cli` → `_win_short(LLAMA)` | Local binary yok. |
| `nvidia-smi.exe` | 2302 | `_nvidia_smi()` → `r"C:\Windows\System32\nvidia-smi.exe"` | GPU yok. |
| `netstat`/`taskkill` (port kill) | 2489 | `subprocess.check_output(["netstat","-ano"])`, `taskkill /PID` | Windows-only. |
| `kernel32.GetShortPathNameW` | 2246 | `ctypes.windll.kernel32.GetShortPathNameW(path, buf, 520)` | Windows API. |
| `SetConsoleOutputCP(65001)` | 2841 | UTF-8 console zorlaması. | Webde console yok. |
| stdin/stdout JSON-line protocol | 7826 | `for line in sys.stdin: msg = json.loads(line)` | Webde HTTP/WS gerekir. |
| `TEMP` env (prompt tmp dosyası) | 2845 | `Path(os.environ.get("TEMP", cwd)) / f"bs-prompt-{os.getpid()}.txt"` | llama-cli'ye prompt dosyası yazımı. |
| `case_memory.json` disk write | 1252 | `_MEMORY_PATH.write_text(json.dumps(...))` | Webde DB gerekir. |
| `petition_timings.jsonl` disk write | 115 | `LOCALAPPDATA/BetterSaul/petition_timings.jsonl` | Webde DB gerekir. |

---

### 2. AI Sistemi

#### 2.1 Kullanılan AI Modelleri

**OpenAI, Gemini, Anthropic, Ollama KULLANILMIYOR.** Sistem **tamamen yerel**:

```python
# satır 2 (modül docstring)
"""Yerel Qwen 2.5 7B / Qwen 3 14B TR + BetterSaul MCP. WinForms stdin/stdout JSON satırları."""
```

Model tespiti `BS_MODEL_ID` ve `BS_MODEL` env var'larına bakar (satır 2340-2360):

| Fonksiyon | Satır | Tespit |
|---|---|---|
| `_is_qwen3` | 2344 | `qwen3`, `qwen35`, `qwen38`, `sungur`, `14b-tr`, `9b-tr`, `27b` |
| `_is_14b` | 2349 | `14b` (27B hariç) |
| `_is_27b` | 2353 | `27b`, `qwen38`, `3.8` (Qwen 3 14B/38B?) |
| `_is_9b` | 2358 | `9b`, `qwen35`, `3.5` |

**Sonuç:** Qwen 2.5 (7B/9B/14B) ve Qwen 3 (14B/27B) TR GGUF modelleri desteklenir. Hiçbir bulut API'si yoktur.

#### 2.2 Model Inference (Local, Hybrid, API?)

**Local-only, üç katmanlı hybrid:**

```python
# satır 2925-2965 generate() dispatch mantığı
def generate(messages, n_predict, n_ctx, live, busy, think, allow_cli=True):
    if _is_27b():
        n_ctx = _27b_ctx(n_ctx)              # 4096'ya kısalt
        n_predict = _27b_predict(n_predict)  # 256-4096 arası
        if _ensure_server(n_ctx):            # llama-server HTTP
            return complete_server(...)
        # fallback:
        if not allow_cli: raise RuntimeError(...)
        return complete_cli(...)             # tek seferlik llama-cli
    try:
        import llama_cpp                     # Python binding (14B)
        return complete_llamacpp(messages)
    except Exception:
        return complete_cli(...)             # son çare: llama-cli subprocess
```

**Üç inference yolu:**

1. **`llama-server.exe` + HTTP** (satır 2641 `complete_server`): `POST http://127.0.0.1:8742/v1/chat/completions`, SSE streaming. 27B için tercih edilen.
2. **`llama-cpp-python`** (satır 2222 `complete_llamacpp`): `Llama(model_path=..., n_gpu_layers=..., n_ctx=16384)`. 14B için tercih edilen.
3. **`llama-cli` subprocess** (satır 2822 `complete_cli`): Tek seferlik prompt dosyası (`bs-prompt-{pid}.txt`) yaz, llama-cli'yi çalıştır, stdout pump et. Fallback.

Server sabit port `8742` (satır 2280 `_SERVER_PORT = 8742`). Server ömrü `_ensure_server` (2536) ile yönetilir, `nvidia-smi` ile VRAM ölçülüp (satır 2326 `_vram_mb`), GPU katman sayısı (`-ngl`) dinamik ayarlanır (satır 2419 `_gpu_layers`).

#### 2.3 Prompt Sistemi

Üç prompt dosyası yüklenir ve runtime'da birleştirilir:

```python
# satır 48-65 modül init
PROMPT = (HERE / "system_prompt.txt").read_text(encoding="utf-8")               # sohbet/system
PETITION_PROMPT = (HERE / "petition_prompt.txt").read_text(encoding="utf-8")    # dilekçe
FILL_ANATOMY = "Yazım disiplini (metne yapıştırma): ..."                         # hardcoded (50-58)
TR_REASON = (HERE / "turkish_reason.txt").read_text(encoding="utf-8").strip()   # Türkçe muhakeme
if TR_REASON:
    PROMPT = PROMPT.rstrip() + "\n\n" + TR_REASON                              # 64
    PETITION_PROMPT = PETITION_PROMPT.rstrip() + "\n\n" + TR_REASON             # 65
```

- `system_prompt.txt` (22 satır): BetterSaul rol tanımı, MCP kullanım disiplini, dilekçe sıralaması, üslup, TDK yazım kuralları, halüsinasyon yasağı.
- `petition_prompt.txt` (112 satır): 13 bölümlü gizli dilekçe disiplini (A–M): HMK m.119/İYUK m.3 iskeleti, makam, taraflar, konu, harca esas, açıklamalar, tür karışmazlığı, deliller, hukuki nedenler, sonuç-istem, imza, dil, uzunluk.
- `turkish_reason.txt` (13 satır): Türkçe muhakeme adımları (günlük dil → hukuki dil sözlüğü: "aldatma → sadakat yükümlülüğünün ihlali", "kovmak → fesih" vb.).

**Petition prompt birleştirme örneği** (`petition_messages`, satır 3427-3483): `petition_prompt.txt` + `FILL_ANATOMY` + form verileri (mahkeme, taraflar, olay, talepler) + `pack_for(ptype)` vakıa iskeleti + delil listesi + dayanak maddeleri tek user mesajında toplanır.

#### 2.4 AI Tur Sayısı (Single-turn, Multi-turn, Agentic?)

**Agentic + multi-turn hybrid.** İki ayrı tur yapısı var:

**A) Araştırma turları (`seed_research`, satır 2020):**

```python
# satır 77-78
MAX_TURNS = 8
RESEARCH_ROUNDS = 3
```

- İlk turda `_research_queries(form)` ile 6-12 önceden tanımlı sorgu (satır 1391).
- 2. ve 3. turlarda `_think_next_queries(form, raw, used, tur)` (satır 1576) ile tur-bazlı sorgu daraltma: tur 2 = daire + core; tur 3 = statutes + core; tur 4 = rare words + emsal; tur 5-10 = giderek derinleşen Qwen 9 HD / Danıştay sorguları.
- Son turda `_llm_think_tour` (satır 1721) GPU muhakemesi: model TEZ/BOSLUK/SORULAR/PLAN formatında çıktı üretir, **dilekçe yazmaz**, yalnız sonraki sorgu önerir.

**B) Agent döngüsü (`run_agent`, satır 2978-3120):**

```python
# satır 3062-3083
for turn in range(2 if _is_27b() else MAX_TURNS):
    text = generate(history, n_predict, n_ctx, live=True, busy=busy, think=True)
    m = TOOL_RE.search(text)                  # {"name":...,"arguments":...} bloğu ara
    if not m:
        final = TOOL_RE.sub("", text).strip()
        break
    spec = json.loads(m.group(1))
    result = mcp_call(spec["name"], spec["arguments"])
    history.append({"role":"assistant","content":text})
    history.append({"role":"user","content":f"Araç sonucu ({name}):\n{result}"})
```

`TOOL_RE = re.compile(r"\s*(\{.*?\})\s*", re.S)` (satır 2219). Yani model JSON tool-call bloğu yazınca motor çağırır, sonucu history'ye ekler. 27B'de 2 tur, diğer modellerde 8 tur.

**C) Uzatma turları (`run_agent`, satır 3084-3110):** `min_chars` altındaysa 6 ek tur ile dilekçe uzatılır (`extra_round < 6`).

#### 2.5 AI Karar Verme Noktaları

| Karar | Fonksiyon | Satır | Yöntem |
|---|---|---|---|
| Dava türü tespiti | `legal_tracks.detect_track` | 34 | Regex + keyword blob |
| Boşanma sebebi (164/166) | `_divorce_ground` | 1371 | Regex (`tmk m. 164`, `terk davası`, `temelinden sars`) |
| Mahkeme türü düzeltme | `legal_tracks.court_override` | 147 | Track'e göre (`idare`, `is`, `bosanma`) |
| Arabuluculuk dava şartı | `legal_tracks.needs_mediation` | 121 | Track = `is` (iş kazası hariç) veya `tuketici` |
| İşçilik talep kümesi | `_form_claims` | 3165 | `bettersaul_mcp.quality.form_claims` (delege) |
| Araştırma sorgusu üretimi | `_research_queries` | 1391 | Türe göre statik map + extra_map + labor claims |
| Tur-bazlı sorgu daraltma | `_think_next_queries` | 1576 | Hardcoded 10-tur stratejisi |
| İçtihat seçimi | `_prefer_chamber_cites` | 5469 | Türe göre daire filtresi (2 HD, 9 HD, 12 HD, Danıştay) |
| İçtihat gerçeklik kontrolü | `_filter_cites` | 5562 | `_holding_helps` + `_is_portal_junk` + 404 kontrol |
| AYM sorgu planı | `_aym_search_plan` | 1887 | Regex blob eşleştirme (HAGB, 7315, kişisel veri) |
| Sonuç-istem filtreleme | `_filter_sonuc_to_claims` | 7491 | İşçilikte form-olmayan kalemleri düşür |
| Intent detection (sohbet) | `_looks_legal_query` | 1322 | Regex (`içtihat|yargıtay|dava|dilekçe|tmk|tbk|...`) |
| Ptype tahmini (sohbet) | `_guess_ptype` | 1337 | Keyword eşleştirme |

#### 2.6 System Prompt İçerik Özeti

`system_prompt.txt` (22 satır) dört ana bölüm:

1. **Rol tanımı:** "BetterSaul — Türk hukukunda uzman, kıdemli avukat gibi düşünen yapay zekâ hukuk asistanısı" (satır 1).
2. **Araç kullanımı (satır 3-9):** BetterSaul MCP ile resmi kaynak arama, 10 tur taratma, her turda sorguyu daraltma, 404/svg yazmama, boşanmada TMK 164/166 karıştırmama. Tool-call formatı: `{"name": "ARAC_ADI", "arguments": { }}`.
3. **Dilekçe (satır 11-18):** HMK m.119 sırası (T.C. → makam → DAVA DİLEKÇESİ → ... → imza+EK), her vakıa altında Delil/Hukuki dayanak/Hukuki sonuç, tür karışmazlığı, "vekâleten talep ederim".
4. **Üslup (satır 20-22):** Türkçe muhakeme, TDK Yazım Kılavuzu (de/da ayrı, hâl eki bitişik, ki ayrı, mi/mı/mu/mü ayrı, kesme: HMK'nın). İçtihat uydurma yasağı.

---

### 3. Araştırma Akışı (Research Pipeline)

#### 3.1 Kullanıcı Sorusu → Cevap Adımları

`write_petition(form)` (satır 7746) → `_write_petition_body` (satır 7760) çağrısı. **8 aşamalı pipeline:**

```
Form (JSON)
  │
  ├─[1] _take_user_prompt(form)              satır 3126, 7761
  │      userPrompt / extraInstructions / WEB_FLUENCY flag ayrıştırma
  │
  ├─[2] _hydrate_form_facts(form)            satır 3386, 7762
  │      _hydrate_parties → prompt'tan davacı/davalı/tckn/adres çıkarma
  │      caseSummary boşsa prompt'tan doldur
  │
  ├─[3] align_form(form)                     satır 7763 (legal_tracks.py satır 99)
  │      detect_track → petitionType normalize → _on_degerlendirme (motor.pipeline.classify)
  │
  ├─[4] wait_mcp_tools(8)                    satır 7772
  │      BetterSaul MCP bağlantısı (local-first, sonra HTTP)
  │
  ├─[5] seed_research(form, tools)           satır 2020, 7777
  │      3 turlu tarama + LLM muhakeme turu + mevzuat/AYM/RG
  │
  ├─[6] _pipe_extract(form)                  satır 7658, 7785
  │      1/4: Model → case JSON (davacı, davalı, mahkeme, olay, talep)
  │
  ├─[7] _pipe_generate(form, pack, research) satır 7680, 7797
  │      2/4: Model → dilekçe taslağı (templates.outline + cites + hukuki)
  │      Başarısızsa: _compose_petition (iskeletten kart kurulumu)
  │
  ├─[8] _pipe_check(form, text)              satır 7707, 7799
  │      3/4: Model → kalite kontrol raporu (talep/sonuç/açıklama/delil/tarih)
  │
  ├─[9] _pipe_repair(form, pack, text, rep)  satır 7727, 7800
  │      4/4: Model → düzeltme (yalnızca rapor maddeleri)
  │
  ├─[10] _sanitize + _strip_instr_leaks + _polish_tr + _format_petition_spacing
  │       satır 7801
  │
  ├─[11] _ensure_header(form, pack, text)    satır 7802
  │       T.C. / mahkeme / baner / DAVA DİLEKÇESI üstte
  │
  └─[12] _ensure_lawyer(text, form)          satır 7803
         Vekil bloğu ve imza eklenir
```

#### 3.2 Dava Türü Tespiti

`legal_tracks.detect_track` (satır 34-80) **regex tabanlı blob eşleştirme**:

```python
# legal_tracks.py satır 34-80
def detect_track(form: dict) -> str:
    blob = _blob(form)  # caseSummary + extraInstructions + requests + parties + title + petitionType + userPrompt
    ptype = str(form.get("petitionType") or "")
    if "İdare" in ptype or _has(blob, r"idari islem|iyuk|2577|danistay|7315|..."):
        return "idare"
    family = _has(blob, r"bosan|evlilik|velayet|yoksulluk|istirak nafaka|ziynet|sadakat")
    labor = _has(blob, r"(?<![a-z])(is\s*yeri|isyeri|isci|isveren)(?![a-z])|kidem|ihbar tazmin|...")
    if "Boşanma" in ptype or (family and not labor): return "bosanma"
    if labor and not family: return "is"
    if _has(blob, r"kira|tahliye|kiracı|kiralayan"): return "kira"
    if _has(blob, r"tüketici|ayıplı|garanti"): return "tuketici"
    if _has(blob, r"icra|ödeme emri|itirazın iptali"): return "icra"
    if _has(blob, r"katılan|sanık|şüpheli|kamu davası"): return "ceza"
    if _has(blob, r"haksız fiil|trafik kaza|darp|manevi zarar") and not labor: return "tazminat"
    # ... 9 dal daha
    return "diger"
```

**10 dava türü** desteklenir: `idare`, `bosanma`, `is`, `kira`, `tuketici`, `icra`, `ceza`, `tazminat`, `alacak`, `diger`.

#### 3.3 Araştırma Sorgusu Üretimi

`_research_queries` (satır 1391-1517) türe göre **statik sorgu havuzu** üretir:

```python
# satır 1410-1463 by_type map
"Boşanma Davası": [
    "Yargıtay 2 Hukuk Dairesi evlilik birliği temelinden sarsılması TMK 166",
    "Yargıtay 2 HD sadakat yükümlülüğü TMK 185 boşanma",
    "Yargıtay 2 HD ortak hayat çekilmez TMK 166 kusur",
],
"İş Davası": [
    "Yargıtay 9 Hukuk Dairesi ücret alacağı 4857 m 32",
    "Yargıtay 9 HD ödenmeyen ücret en yüksek mevduat faizi",
    "Yargıtay 9 HD 7036 m 3 arabuluculuk dava şartı son tutanak",
    # ... 6 sorgu
],
"İdare Hukuku": [
    "Danıştay güvenlik soruşturması 7315 soyut gerekçe iptal",
    "Danıştay değerlendirme komisyonu atama uygunluk",
    # ... 4 sorgu
],
# ... 9 tür daha
```

İşçilikte `_form_claims(form)` ile formdan çıkarılan talep kodlarına göre sorgu üretimi (satır 1488-1502): `ise_iade`, `kidem`, `ihbar`, `fazla`, `ucret` her biri için ayrı 2024/2025/2026 tarihli Yargıtay 9 HD sorgusu.

`extra_map` (satır 1465-1484) ile olay blob'ında geçen keyword'lere göre ek sorgu: velayet, nafaka, ziynet, 6284, kıdem, ihbar, işe iade, fazla mesai, itirazın iptali, tahliye, ayıplı, manevi tazminat, ücret alacağı, güvenlik soruşturması, atama uygunluk, HAGB, infaz ve koruma, 657 memuriyet.

#### 3.4 Mevzuat/İçtihat/AYM/Resmî Gazete Sıralaması

`seed_research` (satır 2020) ve `_seed_official_sources` (satır 1917) içinde **kesin sıra**:

```
[1] İçtihat turları (3 tur):            satır 2114-2145
    search_corpus_deep / search_bedesten / search_emsal
    court_types: "YARGITAYKARARI" veya "DANISTAYKARAR"
    
[2] _pull_holdings (karar metni çekme): satır 2146
    get_bedesten_document (en fazla 2 doc ID)
    
[3] _seed_official_sources:             satır 2148, 1917
    ├─ Mevzuat (mevzuat.gov.tr):         satır 1928-1952
    │   _mz.default_pulls(form) → get_mevzuat_article(kanun, madde)
    │   JSON parse → statutes[] (label, ozet)
    │
    ├─ AYM (en fazla 4, idare türünde):  satır 1954-1999
    │   _aym_search_plan(form) → search_anayasa + get_anayasa_document
    │   helpful_list → row (kunye, ilke, url)
    │
    └─ Resmî Gazete (1 kayıt):           satır 2001-2016
        _rg_query_for(form) → search_resmi_gazete
        recs[0] alır; yoksa {"sonuc": "taranamadı"}
```

**Kritik sıralama:** İçtihat her zaman önce, sonra mevzuat, sonra AYM (yalnızca idare), sonra RG. AYM "en fazla 1" kuralı prompt'ta teyit edilir: `AYM (en fazla 1; yoksa uydurma)` (satır 1306-1307 memory_brief).

#### 3.5 Source Verification (Halüsinasyon Önleme)

Çok katmanlı doğrulama:

| Fonksiyon | Satır | Kontrol |
|---|---|---|
| `_is_portal_junk` | 1182 | SVG, 404, "Bilgi İşlem Genel Müdürlüğü", "içerik mevcut değildir" tespiti |
| `_strip_portal_junk` | 1197 | Bu metinleri regex ile silme |
| `_usable_holding` | 1809 | 40 karakter altı, "Araç yanıt", "HTTP ", "Belge alınamadı" reddi |
| `_extract_cite_rows` | 1094 | İç içe JSON walk; her satırda esas/karar/kunye doğrulaması (`_cite_from_mapping`) |
| `_cite_from_mapping` | 1053 | esas/karar/bno'dan en az biri yoksa `None` |
| `_doc_ids` | 1230 | `documentId` JSON field'ından çeker; regex fallback |
| `_FETCHED_DOCS` set | 1244, 1824, 2146 | Aynı doc ID iki kez çekilmez |
| `_filter_cites` | 5562 | `_holding_helps` ile içtihat tutarlılık kontrolü |
| `_prefer_chamber_cites` | 5469 | Türe göre daire filtresi (idare → Danıştay, iş → 9 HD, boşanma → 2 HD) |
| `_rg_memory_real` | 6769 | `sonuc != "taranamadı"` ve `baslik/url` varsa gerçek |
| `_aym_memory_row` | 6764 | En fazla 1 AYM satırı |

#### 3.6 Citation Collection Mantığı

`_extract_cites` (satır 1156) ve `_extract_cite_rows` (satır 1094):

```python
# satır 1094-1153
def _extract_cite_rows(research: str) -> list[dict]:
    """İç içe JSON dahil künye çıkarır. Uydurmaz."""
    # JSONDecoder.raw_decode ile iç içe JSON objeleri gezilir
    # Her dict için _cite_from_mapping denemiş; esas/karar/kunye yoksa None
    # En fazla 24 satır döner
    # Fallback: regex ile {"esasNo":...} tarzı blob'lar
```

`_row_kunye` (satır 1018) ile satır → künye string:
```python
"Yargıtay 2. Hukuk Dairesi, E. 2023/1234, K. 2023/5678, 12.05.2023"
```

`_bind_holdings_to_rows` (satır 5434) ile künye ↔ karar metni eşleştirme: aynı `esas/karar` pair'ı ile.

`_prefer_recent_cites` (satır 5512) ile yıl çıkarımı (`_cite_year`, satır 5500) ve son yıllar tercihi.

---

### 4. Dilekçe (Petition) Sistemi

#### 4.1 Dilekçe Oluşturma Akışı

`write_petition` (satır 7746) → `_write_petition_body` (satır 7760) çağrısı. **4 aşamalı pipeline (`_pipe_*`):**

```
Form (JSON)
  │
  ├─[1] _pipe_extract(form)              satır 7658, 7785
  │      _qwen_stage(fact_messages(raw), n_predict=700)
  │      → case JSON (davacı, davalı, mahkeme, olaylar, talepler)
  │      merge_case_into_form(form, case)
  │
  ├─[2] _pipe_generate(form, pack, research)  satır 7680, 7797
  │      _qwen_stage(generate_messages(brief, ol, cites, hukuki, court, banner),
  │                  n_predict=2200)
  │      → dilekçe taslağı
  │      Başarısızsa (_draft_wrong_track / _has_instr_leak):
  │        acik = _narrative_aciklamalar(form, pack, research)
  │        text = _compose_petition(form, pack, acik, research)
  │
  ├─[3] _pipe_check(form, text)          satır 7707, 7799
  │      _qwen_stage(check_messages(case_brief, text), n_predict=500)
  │      → parse_check_report (talep/sonuç/açıklama/delil/tarih/hukuki sebep)
  │
  └─[4] _pipe_repair(form, pack, text, report)  satır 7727, 7800
         needs_repair(report) ise:
           _qwen_stage(repair_messages(brief, text, report), n_predict=2200)
         değilse: text olduğu gibi döner
```

`_qwen_stage` (satır 7637) model yoksa ya da 27B sunucusu kapalıysa **boş string** döner (graceful degradation). Bu durumda `_compose_petition` iskeletten kurulum devreye girer.

#### 4.2 Petition Packs nedir, ne içerir

`petition_packs.py` (197 satır) bir **statik şablon kütüphanesidir**. 10 dava türü için:

```python
# petition_packs.py satır 3-193
PACKS: dict[str, dict] = {
    "Boşanma Davası": {
        "court": "… Aile Mahkemesi'ne",
        "konu": "Türk Medeni Kanunu m. 166 uyarınca evlilik birliğinin...",
        "statutes": ["TMK m. 166", "TMK m. 174", "TMK m. 175", "TMK m. 182", ...],
        "vakia": ["Davanın hukuki dayanağı", "Evlilik birliği ve müşterek çocuk", ...],
        "evidence": ["Nüfus kayıt örneği ve evlilik cüzdanı fotokopisi", ...],
        "vakia_delil": [...],   # her vakıa için varsayılan delil
        "requests": ["Tarafların TMK m. 166 uyarınca boşanmalarına", ...],
    },
    "İş Davası": { "court": "… İş Mahkemesi'ne", "statutes": [...], ... },
    "Alacak Davası": { ... },
    "İcra Hukuku": { ... },
    "İdare Hukuku": { ... },
    "Tazminat Davası": { ... },
    "Ceza Hukuku": { ... },
    "Kira / Tahliye": { ... },
    "Tüketici Hukuku": { ... },
    "Diğer": { ... },
}

# satır 196-197
def pack_for(petition_type: str) -> dict:
    return PACKS.get((petition_type or "").strip()) or PACKS["Diğer"]
```

Her pack 6 alan içerir: `court` (makam), `konu` (konu şablonu), `statutes` (dayanak maddeler), `vakia` (vakıa başlıkları), `evidence` (delil listesi), `vakia_delil` (vakıa-delil eşleştirme), `requests` (varsayılan talepler).

`_compose_petition` (satır 6793) bu pack'i kullanarak iskeletten dilekçe kurar: `_court_line`, `_resolved_parties` → `client_block`/`defendant_block`/`lawyer_block` (templates.py), `_konu_line`, `_expand_requests` → talep bloğu, `_hukuki_nedenler_line` → hukuki sebepler, `_book_vakia_block` → roman numaralı (I./II./III.) vakıa blokları, `_relevant_evidence` → delil listesi, son olarak `templates.assemble(...)` ile birleştirme.

#### 4.3 Petition Prompt Yapısı

`petition_prompt.txt` (112 satır) **13 bölümlü gizli disiplin**:

| Bölüm | Satır | İçerik |
|---|---|---|
| A) Şekil | 5-19 | HMK m.119 / İYUK m.3 iskeleti, 11 maddeli sıra, "vekâleten talep ederim" |
| B) Makam | 22-27 | T.C. ortalanmış, "...MAHKEMESİ'NE" vs "...BAŞKANLIĞI'NA", ivedi/YD baner |
| C) Taraflar | 29-37 | DAVACI/VEKİL/DAVALI blok, kimlik alanları, eksik alan uydurmaz |
| D) Konu | 39-44 | Tek cümle, hukuki nitelendirme + talep türü, 166/164 karışmazlığı |
| E) Harca esas | 46-51 | Nispi/maktu, nafaka toplanmaz, idare maktu, ziynet yok |
| F) Açıklamalar | 53-69 | Numaralı vakıa, her altında Delil/Hukuki dayanak/Hukuki sonuç |
| G) Türler karışmaz | 71-80 | İdare ≠ boşanma, ceza ≠ idari işlem, HAGB ≠ mahkumiyet |
| H) Deliller | 82-87 | Numaralı, açıklamada anılan her belge, celp yeri, uydurma yok |
| I) Hukuki nedenler | 89-92 | Dayanak maddeler + taranmış gerçek künye, 404 yok |
| J) Sonuç ve istem | 94-98 | Maddeli, KONU ile birebir örtüşme, HMK 119 nispi kuralı |
| K) İmza ve ekler | 100-102 | Yazım günü tarihi, EKLER delil listesiyle örtüşür |
| L) Dil | 104-108 | TDK kuralları, amiyane yasak, doğru/yanlış örnek |
| M) Uzunluk | 110-112 | ~5 A4 nitelikli geliştirme, tekrar/doldurma yasak |

Prompt **gizlidir**: "Aşağıdaki yazım disiplini gizlidir. Kitap adı, yazar adı, 'gizli prompt', 'anatomi', 'talimat' ve bu metnin kendisi dilekçeye, sohbete ve PDF'ye YAZILMAZ" (satır 3).

`_strip_instr_leaks` (satır 3915) ile ~30 farklı regex bu sızıntıyı temizler: `Sen Türk avukat asistanısın`, `## Türkçe muhakeme`, `Dilekçe henüz 5 A4 değil`, `Yazmadan önce Türkçe düşün`, `aldatma → sadakat` vb.

#### 4.4 Dilekçe Formatlama (PDF/DOCX?)

**engine.py PDF/DOCX üretmez.** PDF üretimi `bettersaul_mcp/petition_tools.py` içinde `save_petition_pdf` (satır 836-849 dispatch; gerçek impl. `petition_tools.py`'da). engine.py yalnızca **düz metin** döndürür:

```python
# satır 7804
_save_prep_timing(form, time.time() - t0, True)
return text  # düz metin
```

Formatlama işlevleri:

| Fonksiyon | Satır | İş |
|---|---|---|
| `_format_petition_spacing` | 6882 | Bölüm başlıkları arasında boş satır, vakıa numaralandırma |
| `_ensure_header` | 3831 | T.C. / mahkeme / baner / DAVA DİLEKÇESİ üstte |
| `_ensure_lawyer` | 447 | Vekil bloğu ve imza ekleme |
| `_court_line` | 3788 | "...MAHKEMESİ'NE" / "...BAŞKANLIĞI'NA" düzeltme |
| `_header_bits` | 3822 | court + banner (templates.combined_banner) |
| `_format_party_card` | 3646 | DAVACI/DAVALI blok formatı |
| `_kunye_tr` | 412 | ISO 2022-10-06 → 06.10.2022 |
| `_tr_date` | 403 | Tarih "12 Mayıs 2025" formatında |

PDF kaydetme isteği C# tarafında `_local_mcp_call("save_petition_pdf", {...})` (satır 836-849) ile yapılır; motor `save_petition_history` (satır 825) ve `save_petition_pdf` (satır 836) araçlarını expose eder.

#### 4.5 Kalite Kontrol Noktaları

**Çok katmanlı kalite kontrol:**

```
_pipe_generate çıktısı
  ↓
_apply_consistency_fixes (satır 7527)  — KONU/HUKUKİ/SONUÇ yeniden yazım, tür karışıklık temizliği
  ↓
_sanitize_petition (satır 4062)        — off-track cümle silme, HAGB düzeltme, placeholder temizlik
  ↓
_strip_instr_leaks (satır 3915)        — prompt sızıntısı regex temizliği
  ↓
_polish_tr (satır 5273)                — TDK imla düzeltmeleri (vekalet→vekâlet, herşey→her şey)
  ↓
_format_petition_spacing (satır 6882)  — boş satır standardizasyonu
  ↓
_pipe_check (satır 7707)               — model kalite kontrol raporu
  ↓
_pipe_repair (satır 7727)              — model düzeltme
  ↓
_qa_after_write (satır 7581)           — son tekrar: consistency + sanitize + score
  ↓
_score_petition (satır 7407)           — 6 boyutlu puanlama (toplam 100)
  ↓
_ensure_score_floor (satır 7605)       — 80 altındaysa _compose_petition ile yeniden kurulum
```

---

### 5. legal_tracks.py

#### 5.1 Legal Tracks Nedir

`legal_tracks.py` (420 satır) **dava türü tespiti ve dilekçe usul kuralları** modülüdür. Üç ana rol:

1. **Track tespiti** (`detect_track`, satır 34): Form verisinden dava türünü regex ile belirler.
2. **Form hizalama** (`align_form`, satır 99): Track'i normalize eder, `petitionType`'ı sabitler, `_on_degerlendirme` (motor.pipeline.classify) çağırır.
3. **Usul kuralları** (`PROMPT_RULES`, satır 405-420): İşçilik/boşanma/İdare için hardcoded usul metni. Modele gömülür.

Modül başlığında "Kitap metni veya telifli eser değildir. 7036 s. K. m. 3 ve m. 5, 4857 s. K., HMK m. 119 özet kurallarıdır. GGUF modeli yeniden eğitilmez; motor bu kurallara uyar." (satır 1-5).

#### 5.2 Desteklenen Dava Türleri

10 dava türü `detect_track` (satır 34-80) tarafından desteklenir:

| Track | resolved_type | Tespit pattern'leri |
|---|---|---|
| `idare` | "İdare Hukuku" | `idari islem|iyuk|2577|danistay|7315|guvenlik sorustur|...` |
| `bosanma` | "Boşanma Davası" | `bosan|evlilik|velayet|yoksulluk|istirak nafaka|ziynet|sadakat` |
| `is` | "İş Davası" | `isci|isveren|kidem|ihbar tazmin|fazla mesai|is sozles|4857|maas|...` |
| `kira` | "Kira / Tahliye" | `kira|tahliye|kiracı|kiralayan` |
| `tuketici` | "Tüketici Hukuku" | `tüketici|ayıplı|garanti` |
| `icra` | "İcra Hukuku" | `icra|ödeme emri|itirazın iptali` |
| `ceza` | "Ceza Hukuku" | `katılan|sanık|şüpheli|kamu davası` |
| `tazminat` | "Tazminat Davası" | `haksız fiil|trafik kaza|darp|manevi zarar` (işçi değilse) |
| `alacak` | "Alacak Davası" | `ticari alacak|cari hesap|haksiz rekabet|asliye ticaret` |
| `diger` | "Diğer" | fallback |

#### 5.3 Her Track'in Araştırma Stratejisi

`legal_tracks.py` doğrudan araştırma stratejisi içermez, ancak `_research_queries` (engine.py satır 1391) track'e göre stratejiyi engine.py içinde barındırır. `legal_tracks.py` ise usul kurallarını sağlar:

| Track | Usul Kuralı Kaynağı | Fonksiyonlar |
|---|---|---|
| `is` | `PROMPT_RULES` (satır 405-420), `labor_hukuk` (satır 379), `labor_konu` (satır 342), `labor_wage_claim` (satır 166), `mediation_vakia` (satır 223), `mediation_header` (satır 203), `is_work_accident` (satır 117), `labor_evidence` (satır 248) | 7036 m.3 arabuluculuk dava şartı, 7036 m.5 görev, 4857 m.32/34 ücret, m.41 fazla çalışma, m.53/59 izin, m.17 ihbar, m.18/20/21 işe iade, 1475 m.14 kıdem, HMK m.107 belirsiz alacak |
| `bosanma` | `PROMPT_RULES` (satır 405), `_divorce_ground` (engine.py satır 1371) | TMK m.164 (terk) vs m.166 (sarsılma) ayrımı; açıkça 164 istenmedikçe 166 |
| `idare` | `PROMPT_RULES`, `court_override` (satır 147) | İYUK m.2/7, 2577 s.K., 7315 güvenlik soruşturması, atama uygunluk, HAGB |
| `tuketici` | `needs_mediation` (satır 121) | Arabuluculuk dava şartı |
| Diğer | `PROMPT_RULES` genel | HMK m.119 iskelet |

`PROMPT_RULES` (satır 405-420) tüm modellere gömülen ortak usul metnidir:
```
Görev vakıaya göredir (kamu düzeni). İşçi-işveren ücret/kıdem/ihbar/mesai: 7036 m. 5 İş Mahkemesi
(iş mahkemesi yoksa iş mahkemesi sıfatıyla asliye hukuk). Asliye hukuk + TBK haksız fiil yazılmaz.
İşçilik alacağı haksız fiil maddi/manevi tazminatı değildir; manevi tazminat istenmediyse eklenmez.
KONU, AÇIKLAMALAR, HUKUKİ SEBEPLER ve SONUÇ aynı kalem kümesi olmalı...
```

---

### 6. Halüsinasyon Kontrolü ve Kalite

#### 6.1 Halüsinasyon Önleme Mekanizmaları

**Çok katmanlı savunma:**

| Mekanizma | Fonksiyon | Satır | Teknik |
|---|---|---|---|
| Prompt leak engeli | `_LEAK_MARKERS` (tuple) | 124-170 | 45 farklı sızıntı metni (Wikipedia, DuckDuckGo, "Sen BetterSaul", "<|im_start|>", "içerik mevcut değildir") |
| Prompt leak tespiti | `_is_prompt_leak` | 241 | `_LEAK_MARKERS` üyeliği |
| Prompt leak temizliği | `_strip_instr_leaks` | 3915 | ~30 regex ile kalıp silme |
| Banner/meta temizliği | `_junk_line`, `_meta_line`, `_is_banner` | 248, 224, 212 | llama.cpp CLI banner, `build :`, `b9999-`, box-drawing karakterleri |
| Output cleaning | `_clean_llama_out` | 317 | `<|im_start|>assistant` blok extract, `available commands` atlama, leak line silme |
| Usable text check | `_usable_text`, `_looks_like_petition`, `_looks_like_answer` | 353, 207, 234 | Min 36 harf, T.C./MAHKEME/DAVACI varsa dilekçe |
| Portal junk tespiti | `_is_portal_junk` | 1182 | `image/svg`, `404`, "Bilgi İşlem Genel Müdürlüğü" |
| Portal junk temizliği | `_strip_portal_junk` | 1197 | Regex ile svg/404 silme |
| Karar metni doğrulama | `_usable_holding` | 1809 | 40 karakter altı, "Araç yanıt"/"HTTP " reddi |
| Doc ID dedup | `_FETCHED_DOCS` set | 1244 | Aynı doc ID iki kez çekilmez |
| Citation gerçeklik | `_cite_from_mapping` | 1053 | esas/karar/bno'dan en az biri yoksa None |
| Citation yıl kontrolü | `_cite_year`, `_prefer_recent_cites` | 5500, 5512 | Son yıllar tercihi |
| AYM en fazla 1 | `_aym_memory_row` | 6764 | `aym[:1]` |
| RG gerçeklik | `_rg_memory_real` | 6769 | `sonuc != "taranamadı"` ve baslik/url var |
| Hafıza brief kuralı | `_memory_brief` | 1270 | "İçtihat uydurma. Yalnızca aşağıdaki gerçek kayıtları kullan." |
| Şüpheli tutar | `_blank_tl()` | 4686 | "........................ TL" placeholder; uydurulan rakam yok |
| Şüpheli isim/TCKN | `_party_blank`, `_is_placeholder` | 3174, 3566 | `[...]`, `Ad Soyad`, 10+ nokta → boş |
| Şüpheli tarih | `_kunye_tr` | 412 | ISO → gg.aa.yyyy; uydurmaz |
| Tarih-ay çelişkisi | `reconcile_date_span` | 292 | İki tarih ile "N aylık" çelişirse uydurmaz |

**Prompt açıkça halüsinasyon yasağı koyar** (`system_prompt.txt` satır 4):
```
Elindeki BetterSaul MCP araçlarıyla Türk hukuk kaynaklarında arama yap. Uydurma. ... 
404 / svg / "içerik mevcut değildir" metni yazma.
```

`petition_prompt.txt` satır 91: "İçtihat yoksa numara uydurulmaz. 404 / svg / 'içerik mevcut değildir' yazılmaz." ve satır 67: "Yeni olay, isim, TCKN, tanık, tutar, karar no uydurulmaz."

#### 6.2 Quality Check Mekanizmaları

İki paralel QC sistemi:

**A) Yerel rule-based QC (`_score_petition`, satır 7407):**

6 boyutlu puanlama (toplam 100):

| Boyut | Max | Puanlama kriteri | Satır |
|---|---|---|---|
| Şekil | 20 | T.C., DAVA DİLEKÇESİ, DAVACI/DAVALI/KONU/AÇIKLAMALAR/DELİLLER/SONUÇ VE İSTEM başlıkları; her eksik −3 | 7421-7425 |
| Usul | 15 | Adli yardım/ivedi/nöbetçi, husumet, DAVACI adı form ile uyumu | 7426-7433 |
| Vakıa | 20 | AÇIKLAMALAR uzunluğu (<400 → −8, <900 → −4), "müvekkil" geçmiyorsa −3 | 7434-7446 |
| Hukuk | 20 | TMK 164/166, 7315, HAGB, ziynet sızıntısı, KONU-Sonuç nafaka/velayet çelişkisi | 7447-7452 |
| Atıf | 15 | HUKUKİ SEBEPLER varlığı, Anayasa maddelerinde ilke adı, içtihat satırında daire | 7453-7466 |
| Temizlik | 10 | Wikipedia/Vekile Not/formda 164/4. BÖLÜM sızıntısı, çift baner, prompt leak | 7467-7474 |

**B) Model tabanlı QC (`_pipe_check`, satır 7707):**

```python
# satır 7707-7724
def _pipe_check(form: dict, text: str) -> dict:
    raw = _qwen_stage(check_messages(case_brief(case), text), n_predict=500)
    report = parse_check_report(raw)  # talep/sonuç/açıklama/delil/tarih/hukuki sebep
    return report
```

`bettersaul_mcp.quality.review` (satır 7409) ile `findings` listesi (her finding `sev: "kritik"` veya başka). `_emit_review` (satır 7547) ile rapor UI'a yazılır.

**80 puan tabanı (`_score_floor_ok`, satır 7129):** 30+ koşulun hepsi geçmeli:
- `len(t) >= 900`
- DAVACI, DAVALI, KONU, HUKUKİ SEBEPLER, T.C., DAVA DİLEKÇESİ, AÇIKLAMALAR, SONUÇ VE İSTEM başlıkları
- `^\s*Delil\s*:` ve `^\s*Hukuki dayanak\s*:` satırları
- `^\s*1[\.\-)]\s+` ilk vakıa numarası
- `_has_instr_leak`, `_has_book_subs`, `_vakia_too_repetitive` false
- İdare: AYM künyesi varsa gövdede olmalı
- `wikipedia|duckduckgo|üslup kalıp` yok
- Resmî Gazete künyesi varsa `_rg_memory_real()` true olmalı

80 altındaysa `_ensure_score_floor` (satır 7605) `_compose_petition` ile iskeletten yeniden kurulum yapar.

#### 6.3 Tutarlılık Kontrolü

`_petition_inconsistencies` (satır 7318) **22 çelişki kuralı**:

```python
# satır 7328-7404 özet
- Boşanma: form 166 → HUKUKİ SEBEPLER'de 164 var (veya tersi)
- Boşanma: SONUÇ'ta nafaka var ama AÇIKLAMALAR'da yok
- Boşanma: SONUÇ'ta velayet var ama vakıada çocuk yok
- Boşanma: SONUÇ'ta ziynet var ama AÇIKLAMALAR'da yok
- İdare (olmayan): "7315 sayılı" / "Atama Uygunluk Kararı" var
- İdare: dilekçede ziynet / TMK 164/166 sızıntısı
- HAGB: "mahkûm edilmiş ... HAGB" yazılmış (mahkumiyet gibi)
- Adli yardım banerde var ama SONUÇ'ta yok
- İdare ivedi: baner yok
- İdare: KONU iptal ama SONUÇ'ta iptal yok
- İdare: YD istenmiş ama SONUÇ'ta yok
- İdare: DAVALI EGM ama atayan Adalet/CTE — husumet açıklanmalı
- DAVACI adı formdaki müvekkil ile uyuşmuyor
- DAVALI başlığı formdaki davalı ile uyuşmuyor
- Çift ivedi baner
- Motor notu sızıntısı
- İşçilik: KONU ile SONUÇ talep kümesi çelişiyor (detect_claims)
- İşçilik: Açıklamada SONUÇ'ta olmayan iş kalemi var
```

`_apply_consistency_fixes` (satır 7527) ile otomatik düzeltme: KONU'yu `labor_konu` ile değiştir, HUKUKİ SEBEPLER'i `_hukuki_nedenler_line` ile yeniden yaz, SONUÇ'u `_filter_sonuc_to_claims` ile talep kümesine göre filtrele, idare dışı 7315/Atama Uygunluk Kararı satırlarını sil, idarede ziynet/TMK 164-166 satırlarını sil.

#### 6.4 Hukuki Dayanak Kontrolü

- `_hukuki_nedenler_line` (satır 6725): pack'ten `statutes` + işçilikte `labor_hukuk` + taranmış içtihat `_rich_ictihat_lines` birleştirir.
- `_rich_ictihat_lines` (satır 6674): `_aym_memory_rows` + `_cite_holdings` ile gerçek taranmış içtihatları listeler. Boşsa hiçbir şey eklemez (uydurma yok).
- `_label_anayasa_line` (satır 6540), `_label_kanun_line` (satır 6554): madde numarasının yanına ilke adı ekler.
- `_default_cite_expl` (satır 6619): içtihat için varsayılan açıklama; `_dayanak_expl` (satır 6611) ile çıkarılır.

#### 6.5 İçtihat Kontrolü

- `_filter_cites` (satır 5562): `_holding_helps` ile içtihat tutarlılık kontrolü; `_is_portal_junk` filtresi.
- `_prefer_chamber_cites` (satır 5469): Türe göre daire filtresi (idare → Danıştay, iş → 9 HD, boşanma → 2 HD, icra → 12 HD, tazminat → 4 HD, kira/tüketici → 3 HD).
- `_prefer_recent_cites` (satır 5512): Yıl çıkarımı, son yıllar tercihi.
- `_emsal_in_flow` (satır 5579): En fazla 2 gerçek emsal cümle içine gömülü.
- `petition_prompt.txt` satır 91: "İçtihat yoksa numara uydurulmaz."

#### 6.6 Talep Kontrolü

- `_expand_requests` (satır 4924): Formdaki `requests` listesini genişletir. İşçilikte yalnızca `_form_claims` içindeki kalemler (ucret, kidem, ihbar, fazla, izin, ise_iade, bos_sure, baslatmama) eklenir; formda olmayan kalemler düşürülür.
- `_filter_sonuc_to_claims` (satır 7491): İşçilikte SONUÇ bölümünü form talep kümesine göre filtreler.
- `_split_combo_claim` (satır 5066): "maddi ve manevi tazminat" → iki ayrı kalem.
- `_soften_nafaka` (satır 5051): Nafaka tutarı yoksa "(miktarın takdiri mahkemeye aittir)" ekler; uydurmaz.
- `_ensure_claim_amount` (satır 4903): Tazminat/alacak/ücret/bedel satırlarında tutar yoksa "........................ TL" placeholder.
- `_apply_claim_amounts` (satır 4841): Formdaki `claimValues` (maddi/manevi/kidem/ihbar/ziynet) ile talep satırlarını doldurur.
- `_nispi_sum` (satır 4878): HMK m.119 nispi harç için kalemleri toplar.
- `petition_prompt.txt` satır 95: "Açıklamada olmayan talep eklenmez." satır 96: "HMK m. 119: tutarsız nispi kalem yazılmaz."

---

### 7. Web'e Taşınabilirlik Analizi

#### 7.1 Doğrudan Taşınabilir Fonksiyonlar (Pure Python, No Desktop Dep)

Bu fonksiyonlar **koşulsuz** web'e taşınabilir (~%60 kod):

| Kategori | Fonksiyonlar | Satır aralığı |
|---|---|---|
| **Temizleyiciler** | `_clean_llama_out`, `_usable_text`, `_drop_echo`, `_strip_open_think`, `_think_snippet`, `_junk_line`, `_meta_line`, `_is_banner`, `_looks_like_petition`, `_looks_like_answer`, `_is_prompt_leak`, `_leak_lines` | 124-361 |
| **Türkçe utils** | `_tr_date`, `_tr_upper`, `_fold_tr`, `_kunye_tr`, `_decode_tr`, `_polish_tr`, `_reason_tr_pass`, `_fix_word_spacing`, `_looks_spaced` | 403-5325 |
| **Hukuki utils** | `_aym_weave`, `_short_admin`, `_normalize_court_name`, `_row_kunye`, `_yk_pair`, `_cite_from_mapping`, `_extract_cite_rows`, `_extract_cites`, `_json_strs`, `_json_field`, `_brief_hits` | 421-1179 |
| **Portal junk** | `_is_portal_junk`, `_strip_portal_junk`, `_extract_ozetler`, `_doc_ids` | 1182-1239 |
| **Form helpers** | `_form_blob`, `_divorce_ground`, `_field`, `_source_blob`, `_intent_blob`, `_form_claims`, `_party_blank`, `_clean_person_name`, `_extract_person_names`, `_extract_admin_name`, `_labeled_party_value`, `_find_tckn`, `_find_addr`, `_davali_from_prompt`, `_extract_idare_act`, `_hydrate_parties`, `_hydrate_form_facts`, `_prompt_search_hint`, `_party_heading`, `_value_from_party_block`, `_split_party_blocks`, `_is_placeholder`, `_child_line`, `_looks_public`, `_strip_party_label`, `_resolved_parties`, `_format_party_card`, `_lab`, `_city_from_text`, `_infer_city`, `_urgent_flags`, `_banner_lines`, `_court_honorific`, `_court_line`, `_header_bits` | 1364-3829 |
| **Track & claims** | `detect_track`, `resolved_type`, `align_form`, `is_labor`, `is_work_accident`, `needs_mediation`, `wants_tazminat`, `court_override`, `labor_wage_claim`, `labor_toxic`, `mediation_bits`, `mediation_header`, `mediation_vakia`, `labor_evidence`, `drop_unrelated_evidence`, `reconcile_date_span`, `strip_template_notes`, `labor_konu`, `labor_hukuk`, `_labor_claim_set` | legal_tracks.py: tümü |
| **Petition logic** | `_looks_legal_query`, `_guess_ptype`, `_research_queries`, `_find_tool`, `_issue_labels`, `_uniq_keep`, `_think_next_queries`, `_parse_think_queries`, `_think_note_brief`, `_llm_think_tour`, `_cite_holdings`, `_usable_holding`, `_pull_holdings`, `_rg_query_for`, `_aym_query_for`, `_aym_queries_for`, `_aym_search_plan`, `_seed_official_sources`, `seed_research`, `_model_research_brief` | 1322-2216 |
| **Petition composition** | `_extract_body`, `_has_numbered_vakia`, `_has_book_subs`, `_has_instr_leak`, `_strip_instr_leaks`, `_draft_wrong_track`, `_vakia_too_repetitive`, `_strip_book_subs`, `_offtrack_sentence`, `_sanitize_petition`, `_split_facts`, `_extract_vakia_map`, `_sentences`, `_is_prompt_block`, `_is_petition_question`, `_is_request_noise`, `_title_keys`, `_vakia_kind`, `_facts_for_vakia`, `_fact_source`, `_all_fact_sentences`, `_hukuki_dil`, `_weave_facts`, `_delil_for`, `_strip_disclaimers`, `_legal_wrap`, `_case_paragraph`, `_hukuki_sonuc`, `_clean_req`, `_find_amounts`, `_blank_tl`, `_fmt_user_tl`, `_tl_number`, `_fmt_sum_tl`, `_claim_vals`, `_ziynet_rows`, `_ziynet_table`, `_amount_near`, `_claim_amount`, `_with_amount`, `_apply_claim_amounts`, `_is_blank_money`, `_nispi_sum`, `_ensure_claim_amount`, `_expand_requests`, `_soften_nafaka`, `_split_combo_claim`, `_separate_money_claims`, `_needs_harc`, `_harc_line`, `_claim_labels`, `_konu_line`, `_chrono_sents`, `_plot_why`, `_prefer_chamber_rows`, `_bind_holdings_to_rows`, `_prefer_chamber_cites`, `_cite_year`, `_prefer_recent_cites`, `_rank_cite_rows`, `_prefer_family_cites`, `_clean_holding`, `_holding_helps`, `_filter_cites`, `_emsal_in_flow`, `_pick_sents`, `_labor_narrative`, `_idare_fact_bits`, `_acm_facts`, `_idare_narrative`, `_draft_quality_ok`, `_idare_draft_ok`, `_narrative_aciklamalar`, `_generic_floor_narrative`, `_add_usul_vakia`, `_split_vakia_blocks`, `_batch_vakia_blocks`, `_part_type_guard`, `_model_rewrite_part`, `_fill_vakias_with_model`, `_book_vakia_block`, `_evidence_from_text`, `_relevant_evidence`, `_statute_labels`, `_label_anayasa_line`, `_label_kanun_line`, `_cite_person_name`, `_insert_cite_person`, `_dayanak_expl`, `_default_cite_expl`, `_format_ictihat_line`, `_format_dayanak_from_case`, `_rich_ictihat_lines`, `_hukuki_nedenler_line`, `_aym_memory_rows`, `_aym_memory_row`, `_rg_memory_real`, `_card_bits`, `_compose_petition`, `_format_petition_spacing`, `_split_acik`, `_next_vakia_no`, `_want_web_fluency`, `_fluency_batches`, `_fluency_locked`, `_web_fluency_pass`, `_stretch_petition`, `_score_floor_ok`, `_named_section`, `_acik_section`, `_huk_section`, `_replace_named_section`, `_header_party`, `_dedupe_banners`, `_petition_gaps`, `_petition_inconsistencies`, `_score_petition`, `_filter_sonuc_to_claims`, `_apply_consistency_fixes`, `_emit_review`, `_qa_after_write`, `_ensure_score_floor`, `_fact_raw_for_extract` | 3864-7635 |
| **Petition packs** | `pack_for` ve `PACKS` dict | petition_packs.py: tümü |

#### 7.2 Desktop Bağımlılığı İçeren Fonksiyonlar (Web için Adapter Gerekir)

| Fonksiyon | Satır | Desktop Dep | Web Adapter |
|---|---|---|---|
| `main()` | 7816 | stdin/stdout JSON-line protocol | → FastAPI/Flask HTTP endpoint veya WebSocket |
| `emit()` | 87 | `sys.stdout.write` + flush | → SSE / WebSocket broadcast |
| `LiveOut.feed()` | 507 | `emit("delta", ...)` streaming | → WebSocket token stream |
| `_save_prep_timing()` | 103 | `LOCALAPPDATA/BetterSaul/petition_timings.jsonl` | → DB / object storage |
| `_save_case_memory()` | 1247 | `LOCALAPPDATA/BetterSaul/case_memory.json` | → Redis / DB |
| `_load_case_memory()` | 1257 | Aynı disk yolu | → Redis / DB |
| `write_petition()` | 7746 | `_hw_refuse` çağrır (artık no-op) | OK |
| `_write_petition_body()` | 7760 | `threading.Thread(_ensure_server)` boot | → Celery/async task |
| `warmup_model()` | 910 | `generate()` çağırır | → Backend warmup |

#### 7.3 Yeniden Yazılması Gereken Fonksiyonlar (LLM Stack Değişikliği)

Webde yerel llama.cpp olmayacağı için **tüm LLM katmanı yeniden yazılmalı**:

| Fonksiyon | Satır | Şu an | Web için |
|---|---|---|---|
| `generate()` | 2925 | 27B→server, 14B→llama-cpp-python, fallback→llama-cli | → OpenAI/Anthropic/Together API call |
| `complete_server()` | 2641 | `urllib.request` → `http://127.0.0.1:8742/v1/chat/completions` SSE | → OpenAI SDK streaming (chunked) |
| `complete_cli()` | 2822 | `subprocess.Popen([llama-cli, ...])` + `_run_llama` pump | → Tamamen silinmeli |
| `complete_llamacpp()` | 2222 | `Llama(model_path=...)` | → Tamamen silinmeli |
| `_build_prompt()` | 2612 | `<|im_start|>{role}\n{content}<|im_end|>\n` Qwen chat template | → API'nin chat formatı |
| `_chat_messages()` | 2629 | `/think` `/no_think` token ekleme | → reasoning parametresi |
| `_ensure_server()` | 2536 | `subprocess.Popen(llama-server.exe, ...)` | → Silinmeli (sunucu yok) |
| `_stop_server()` | 2456 | `proc.terminate()` / `taskkill` | → Silinmeli |
| `_server_health()` | 2480 | `urllib.request.urlopen("/health")` | → Silinmeli |
| `_kill_port()` | 2489 | `netstat`, `taskkill /F /T` | → Silinmeli |
| `_has_gpu_backend()` | 2289 | `*.dll` glob + `backend.txt` | → False döner |
| `_nvidia_smi()` | 2302 | `subprocess.run([nvidia-smi.exe, ...])` | → Silinmeli |
| `_vram_mb()` | 2326 | `_nvidia_smi()` parse | → Sabit değer veya silinmeli |
| `_gpu_layers()` | 2419 | VRAM bazlı ngl hesabı | → Silinmeli |
| `_cpu_threads()` | 2363 | `os.cpu_count()` | → Silinmeli |
| `_think_flags()` | 2389 | `--reasoning on/off --reasoning-budget 128` | → API reasoning_effort param |
| `_speed_flags()` | 2395 | `-t`, `-fa`, `-ctk q4_0` | → Silinmeli |
| `_is_qwen3/14b/27b/9b()` | 2344-2360 | `BS_MODEL_ID` env parse | → Sabit model seçimi |
| `_model_available()` | 70 | `os.path.isfile(BS_MODEL)` | → API key varlığı |
| `_27b_ctx`, `_27b_predict` | 2378-2383 | 4096 kısaltma | → Silinmeli (API sınırları farklı) |
| `_run_llama()` | 2713 | `subprocess.Popen` + 2 pump thread | → Silinmeli |
| `_decode_tr()` | 2255 | bytes → utf-8/cp1254 fallback | → API direkt str döner |
| `_win_short()` | 2241 | `GetShortPathNameW` | → Silinmeli |
| `_qwen_stage()` | 7637 | `generate()` + 27B server health | → API call wrapper |
| `_pipe_extract/generate/check/repair` | 7658-7743 | `_qwen_stage` çağırır | → Adapter ile çağrılır |
| `_hw_refuse()` | 2968 | `_hw_local_ok()` (artık True) | → Silinmeli |
| `_hw_local_ok()` | 2374 | Sabit True | → Silinmeli |
| `_reason_tr_pass()` | 5328 | `_server_health()` kontrol | → API ile çağrılır |
| `_stretch_petition()` | 7044 | `return text` (ilk satırda disabled!) | → Aktive edilebilir |
| `_web_fluency_pass()` | 6962 | `return text` (ilk satırda disabled!) | → Aktive edilebilir |

**`web_style.py`** (38 satır) zaten web için "dummy" hale getirilmiş: `fetch_style_hints(kind) -> ("", 0)` (satır 36-38) ve `internet_reachable()` yalnızca `mevzuat.gov.tr`/`resmigazete.gov.tr` HEAD kontrolü (satır 24-33). Wikipedia/DuckDuckGo kapatılmış (satır 37: "Wikipedia / DDG kapalı; dilekçe ve sohbete üslup kalıbı gitmez").

#### 7.4 MCP Bağlantısı Web'de

`mcp_call` (satır 925) ve `mcp_tools` (satır 853) iki yolu destekler:

1. **Local-first** (`_local_mcp`, satır 563): `bettersaul_mcp.sources` direkt import → aynı process'te çalışır. **Webde ideal yol**: MCP tool'ları backend'de FastAPI route olarak expose edilir.
2. **HTTP MCP** (satır 858-886): `bettersaul_mcp.tls.open_mcp(MCP_URL)` ile `https://127.0.0.1:8000/mcp` MCP SDK ClientSession. **Webde sorunlu**: localhost MCP sunucusu container'da olmaz; MCP'nin backend service olarak ayrı container'a taşınması gerekir.

`MCP_URL = os.environ.get("BS_MCP_URL", "https://127.0.0.1:8000/mcp")` (satır 75). Bu env var değiştirilerek remote MCP servis point edilebilir.

#### 7.5 Taşınabilirlik Özeti

| Toplam kod | ~7,857 satır (engine.py) + 638 (diğer 7 dosya) = **~8,495 satır** |
|---|---|
| Doğrudan taşınabilir (pure Python) | ~5,100 satır (~%60) — temizleyiciler, Türkçe utils, hukuki utils, form helpers, track logic, petition composition, QC, packs |
| Adapter gerekir (I/O bağımlı) | ~600 satır (~%7) — `emit`, `main`, `LiveOut`, memory save/load, timing |
| Tamamen yeniden yazılmalı (LLM stack) | ~1,800 satır (~%21) — `generate`, `complete_*`, `_ensure_server`, GPU/VRAM/CPU tespit, llama-cli subprocess |
| Çevre/OS bağımlı (silinecek) | ~350 satır (~%4) — Windows API, nvidia-smi, netstat/taskkill, GetShortPathNameW |
| Disabled/dead code (zaten `return` ilk satırda) | ~250 satır (~%3) — `_web_fluency_pass`, `_stretch_petition` |
| Prompt ve statik veri | ~395 satır (~%5) — system_prompt, petition_prompt, turkish_reason, PACKS, PROMPT_RULES |

**Önerilen web mimarisi:**

1. **Backend (FastAPI + Celery)**: `engine.py`'nin pure Python kısmı (~5,100 satır) aynen import edilir.
2. **LLM Adapter**: `generate()` fonksiyonu OpenAI/Anthropic SDK çağrısı olarak yeniden yazılır (50 satır). `_build_prompt` Qwen template yerine API chat format kullanır.
3. **MCP Service**: `bettersaul_mcp/` paketi ayrı container olarak çalışır; backend `MCP_URL` env ile bağlanır. Alternatif: MCP tool'ları backend içine direkt import (local-first zaten destekleniyor).
4. **Frontend (Next.js)**: WinForms yerine. `emit()` → SSE/WebSocket broadcast.
5. **DB**: `case_memory.json` ve `petition_timings.jsonl` → Redis/PostgreSQL.
6. **Quality pipeline**: 4-aşamalı `_pipe_*` (extract/generate/check/repair) Celery task chain olarak.
7. **Streaming**: `LiveOut` → SSE token stream (API SDK streaming chunk).

**Kritik riskler:**
- 7,857 satırlık tek dosya (`engine.py`) modülerleştirilmeli. Önerilen split: `engine/cleaner.py` (LLM output cleaning), `engine/research.py` (MCP tarama), `engine/petition.py` (composition + QC), `engine/llm.py` (inference adapter), `engine/main.py` (API entry).
- 200+ modül-seviye fonksiyon → sınıflara refactor (ResearchPipeline, PetitionComposer, QualityScorer).
- `_LEAK_MARKERS` (45 marker), `_strip_instr_leaks` (~30 regex) ve `_has_instr_leak` prompt sızıntı savunması model değişince (Qwen → GPT-4/Claude) farklı çalışabilir; tüm regex'ler unit test ile güncellenmeli.
- `petition_packs.py` ve `legal_tracks.py` (~617 satır) webde **olduğu gibi** çalışır; ilk taşınacak modüller.
- `_compose_petition` iskeletten dilekçe kurulumu (model başarısız olursa fallback) **kritik** web güvenlik ağıdır; mutlaka korunmalı.

---

### Sonraki Adımlar

1. **Task 2:** `bettersaul_mcp/` alt paketinin analiz edilmesi (`sources.py`, `anayasa.py`, `mevzuat.py`, `petition_tools.py`, `quality.py`, `templates.py`, `motor/stages.py`, `motor/pipeline.py`).
2. **Task 3:** LLM adapter spesifikasyonu (OpenAI/Anthropic SDK + streaming).
3. **Task 4:** FastAPI endpoint tasarımı (`/petition` POST → SSE stream).
4. **Task 5:** DB şema tasarımı (`case_memory`, `petition_timings`, `petition_history`).
5. **Task 6:** `engine.py` modülerleştirme planı.
6. **Task 7:** Prompt sızıntı regex'lerinin güncellenmesi (model değişikliği için).

---

## Task ID: 4 - UI & Database Analysis

**Tarih:** 2025-09-27
**Kapsam:** `app/ui/index.html` (446 satır, 34KB), `app/ui/app.js` (1790 satır, 73KB), `app/ui/app.css` (772 satır, 28KB), `app/ui/net.js` (137 satır, 4KB), `app/ui/pro-ornek.html` (132 satır, 27KB), `app/ui/mark.svg` (9.5KB), `app/.payload-version` (=`1.6.26-arac-onarim`), `archive.db` (SQLite 24KB), `runtime.stamp`, `session.bin` (614B), `certs/`, `webview/EBWebView/`, `connect/`

---

### 1. UI Mimarisi (index.html + app.js + app.css)

#### 1.1 HTML yapısı (446 satır, 399 element, 41 unique tag, 104 unique id)

**Toplam HTML element sayısı:** 399 (41 farklı tag). En sık kullanılanlar: `<p>` (65), `<b>` (57), `<button>` (44), `<li>` (41), `<div>` (40), `<small>` (22), `<label>` (16). İki adet `<form>` var (`form-login`, `form-reg`), bir `<canvas id="nn">`, bir `<dialog id="kvkkDialog">` (KVKK popup), iki `<details>` (KVKK metni + setup log).

**Ana bölümler** (iki kök view, bir overlay):
- `#view-login` — Giriş/kayıt ekranı. Hero (sol) + auth card (sağ) grid layout. Marka, KVKK aydınlatma metni, kayıt formu.
- `#view-app` — Ana uygulama. İçinde 4 sekme (panel) var:
  - `#tab-guide` — Kılavuz (Claude/ChatGPT/Gemini kurulum kartları + kopyalanabilir prompt'lar)
  - `#tab-history` — Geçmiş (sol liste `#histList` + sağ detay `#histDetail`)
  - `#tab-setup` — Kurulum wizard (4 aşamalı `#setupSteps` + `#setupLog` canlı log)
  - `#tab-pro` — BetterSaul Pro satış sayfası (PDF scan mockup'ı ile)
- `#updateWall` — Tam ekran zorunlu güncelleme overlay'i (`position: fixed; inset:0; z-index:80`)
- `#kvkkDialog` — `<dialog>` modal (KVKK metni popup'ı)

**Tab sistemi** (app.js `switchTab(id)` line 872-885):
```javascript
function switchTab(id) {
  ["guide", "history", "setup", "pro"].forEach(function (t) {
    var el = document.getElementById("tab-" + t);
    if (el) el.hidden = t !== id;
  });
  ...
  if (id === "setup") { send({ cmd: "mcp-status" }); send({ cmd: "mcp-export" }); }
  if (id === "history") loadHistory();
}
```

#### 1.2 JavaScript mimarisi (1790 satır)

**Tamamen vanilla JS**, IIFE pattern (line 1 `(function () {` → line 1790 `})();`). Framework yok (React/Vue/Svelte/Alpine yok). State yönetimi modül seviyesinde `var`'larla: `var mode = "log"`, `var chatBusy`, `var petBusy`, `var setupBusy`, `var lastUser`, `var lastConnect`, `var histItems` vb. (line 2-27).

**Mimari pattern:** View-rotasyonlu tek-dosya SPA. State → DOM mutasyonu hep `document.getElementById(...)` + `.textContent` / `.hidden` / `.innerHTML` ile elle yapılıyor. Sanal DOM diffing yok, reactive binding yok. Reaktivite yok; her şey event-driven.

**app.js'in ana fonksiyonları:**
- `send(msg)` (line 44-62) — WebView köprüsüne JSON mesaj gönderir (ana IPC kanalı)
- `webview()` (line 40-42) — `window.chrome.webview` döndürür
- `loginViaBridge(email, password)` (line 1137-1148) — Senkron köprü yedeği: `wv.hostObjects.sync.bs.Login(email, password)` çağrısı; asenkron mesaj 7 sn içinde yanıt vermezse devreye girer
- `applySession(s)` (line 112-147) — Login sonrası tüm UI state'ini doldurur (user, templates, hardware, mcp, history listesi)
- `onMsg(m)` (line 1554-1757) — Tek devasa mesaj işleyici; 30 farklı event tipini switch-if zinciriyle ele alır
- `petitionHtml(raw)` (line 307-462) — Plain-text dilekçeyi parse edip renkli/segmentli HTML'e çevirir (party lines, sections, vakia'lar, signature)
- `renderPetition(raw)` (line 464-467) — `petitionHtml` çıktısını `#pout` içine basar
- `fillLawyer(user)` (line 154-166) — localStorage'daki `bs.lawyer` profiliyle form alanlarını doldurur
- `hmk119Gaps()` (line 684-708) — HMK m. 119 zorunlu alan denetimi (kıdem/ihbar/mesai/UBGT/izin/alacak/ziynet/harca-esas)
- `syncHarc()` (line 653-662) — Tüm claim kutularını toplayıp `#pamt-harc` alanına otomatik yazar
- `loadHistory()` (line 986-989) — `archive-list` komutuyla native hosttan istiyor
- `paintHistList(items)` (line 999-1022) — Geçmiş listesini render eder
- `paintHistItem(item)` (line 1024-1080) — Seçili dilekçe/chat detayını render eder, PDF/DOCX/UDF butonlarını bağlar

#### 1.3 API çağrıları — TAMAMEN WebView2 IPC, fetch/XHR yok

**Backend ile iletişim kanalı:** Microsoft Edge WebView2 native messaging. Ne `fetch()`, ne `XMLHttpRequest`, ne `WebSocket`, ne `EventSource` kullanılıyor. Tüm trafik tek kanaldan:

```javascript
// app.js line 40-62
function webview() {
  return window.chrome && window.chrome.webview ? window.chrome.webview : null;
}
function send(msg) {
  var wv = webview();
  if (!wv) { failAuth("Uygulama köprüsü yok. BetterSaul.exe içinden açın."); return false; }
  try { wv.postMessage(JSON.stringify(msg)); return true; }
  catch (err) { try { wv.postMessage(msg); return true; } catch (err2) { ... } }
}
```

Ters yön (native → JS):
```javascript
// app.js line 1782-1789
var wv = webview();
if (wv) {
  wv.addEventListener("message", function (ev) { onMsg(ev.data); });
  send({ cmd: "ready" });
} else {
  show("login");
  document.getElementById("lerr").textContent = "Bu sayfa BetterSaul.exe içinde açılmalı.";
}
```

**Mesaj protokolü:** JSON tabanlı, iki yön de:
- JS → Native: `{cmd: "...", ...payload}` (30 farklı cmd)
- Native → JS: `{event: "...", ...payload}` (30 farklı event)

**Tüm 30 komut** (`cmd:` values from app.js):
| Komut | Satır | İşlev |
|---|---|---|
| `ready` | 1785 | Açılışta host'a "UI hazır" sinyali |
| `login`, `register`, `logout` | 1162, 1180, 1191 | Auth |
| `petition` | 1253 | Dilekçe üretimi tetikleme (15+ alan yollanır) |
| `save-pdf` | 1286 | Petition PDF export |
| `export-petition` | 1063 | PDF/DOCX/UDF export (history'den) |
| `archive-list`, `archive-get`, `archive-delete` | 988, 1019, 1038/1078 | Geçmiş CRUD |
| `setup` | 144, 1540 | Runtime kurulumu başlat |
| `mcp-start`, `mcp-stop`, `mcp-test`, `mcp-status`, `mcp-save`, `mcp-export` | 1326-1336 | MCP server kontrol |
| `mcp-install-claude`, `mcp-install-chatgpt`, `mcp-install-gemini` | 1411, 1440, 1469 | Desktop app config yazma |
| `launch-claude`, `launch-chatgpt`, `launch-gemini` | 896, 903, 910, 1430... | Desktop app'i kapat+yeniden başlat |
| `desk-remove` | 1494 | Desktop config'ten BetterSaul kaydını sil |
| `open-site`, `open-forgot`, `open-update`, `open-claude-download`, `open-chatgpt-download`, `open-gemini-download` | 840, 851, 108, 1420, 1449, 1478 | External URL aç |

**Tüm 30 event** (`event ===` matches from app.js):
`boot`, `session`, `update-required`, `login-ok`, `login-err`, `logout-ok`, `chat-delta`, `chat-status`, `chat-research`, `chat-done`, `chat-err`, `petition-delta`, `petition-research`, `petition-status`, `petition-done`, `petition-err`, `pdf-ok`, `pdf-err`, `export-ok`, `export-err`, `archive-list`, `archive-item`, `archive-deleted`, `archive-err`, `setup-log`, `setup-progress`, `setup-done`, `hw-status`, `mcp-connect`, `mcp-status`.

**Senkron köprü yedeği** (line 1137-1148): WebView2'ün `hostObjects.sync` özelliği kullanılarak C# tarafındaki `bs.Login(email, password)` metodu **senkron** çağrılıyor — asenkron `postMessage` 7 saniyede yanıt vermezse devreye giriyor (line 1163-1168):
```javascript
function loginViaBridge(email, password) {
  try {
    var wv = webview();
    var host = wv && wv.hostObjects && wv.hostObjects.sync && wv.hostObjects.sync.bs;
    if (!host || !host.Login) return false;
    var raw = host.Login(email, password);  // senkron C# çağrısı
    onMsg(typeof raw === "string" ? JSON.parse(raw) : raw);
    return true;
  } catch (e) { return false; }
}
```

**localStorage kullanımı** (client-side persistence):
- `bs.lawyer` (line 150, 177) — Avukat profili (ad, baro, sicil, telefon, adres)
- `bs.petitionTimings` (line 267, 270, 283) — Son 80 dilekçe hazırlama süresi kaydı

#### 1.4 app.css tasarım dili (772 satır, 28KB)

**Renk paleti:** Tamamen koyu tema. 18 CSS custom property (`:root` line 1-20):
- Ink skalası (gri tonlar): `--ink-50: #fafafa` → `--ink-1000: #000` (10 adet)
- Marka: `--mark: #ffffff`, `--mark-onlight: #0a0a0a`
- Tehlike: `--danger: #b91c1c`
- Neural-net animasyonu için: `--nn-ink: 10,10,10`, `--nn-accent: 255,255,255`, `--nn-accent-dark: 255,255,255`

**Toplam 31 farklı hex renk.** Vurgu renkleri:
- Gold/Pro: `#f5e6c8`, `#d4af6e` (line 672-673 — `.pro-teaser` border/gradient)
- Yeşil (success): `#34d399`, `#6ee7b7` (line 575, 602, 616)
- Kırmızı (error): `#b91c1c`, `#fca5a5` (line 617, 174)
- Beyaz (ana metin): `#fff`, `#ffffff`

**Fontlar:**
- `--font-sans: "Segoe UI", system-ui, sans-serif` (UI metinleri)
- `--font-serif: "Times New Roman", Georgia, serif` (hero h1, wizard h2, mcp-box h3, pdf-page — hukuki/dilekçe temalı başlıklar)

**Layout grid:**
- `display: grid` 7 yerde; en önemli: `.hero` (`grid-template-columns: 1.15fr .85fr`, line 118) ve `.pro-page` (`grid-template-columns: minmax(260px, 380px) 1fr`, line 679-685)
- `display: flex` 25 yerde (top bar, tabs, mcp-actions, auth-links, hist-kinds vb.)
- `position: fixed` 3 (`#nn` canvas, `.vignette`, `#updateWall`)
- `backdrop-filter: blur` 7 yerde (glassmorphism — top-light, .card, .kvkk-pop vb.)

**Responsive:** 5 adet `@media` query — 900px (wizard/history grid'i kapat), 1100px (pro-page tek kolon), 980px (hero tek kolon), `@media print` (pro-ornek.html için A4 print).

**Animasyonlar:** `@keyframes` **YOK**. Tek animasyon `transition` ile veya JS ile canvas (net.js).

#### 1.5 Desktop WebView bağımlılıkları

**Microsoft Edge WebView2** kullanılıyor. Kanıtlar:
- `app.js` line 40-41: `window.chrome && window.chrome.webview`
- `app.js` line 1140: `wv.hostObjects.sync.bs.Login(...)` — WebView2'in .NET host object binding özelliği
- `webview/EBWebView/` klasöründe tam Edge WebView2 user-data dizini: `Default/` profili, `GPUCache/`, `Code Cache/js/`, `Network/Cookies`, `Local State`, `Last Version`, `SmartScreen/`, `PKIMetadata/`, `TrustTokenKeyCommitments/`, `hyphen-data/` (Chrome bileşenleri)
- `mcp.json` (root): `{"Url": "https://127.0.0.1:8000/mcp", "Port": 8000, "AutoStart": true}` — yerel MCP server

**Native runtime = Windows-only**: Tüm `connect/*.json` dosyaları `C:\Users\user\AppData\Local\BetterSaul\` yoluna işaret ediyor; runtime/python altında Windows AMD64 Python 3.12 binary'leri (`python.exe`, `python312.dll`, `*.pyd`, `libcrypto-3.dll`).

---

### 2. net.js Ağ Katmanı — YANLIŞ İSİMLENDİRME: Ağ katmanı DEĞİL

**`net.js` bir ağ katmanı / API client DEĞİLDİR.** 137 satırın tamamı bir canvas animasyonudur — ismindeki "net" neural network (sinir ağı) görselini ifade eder.

İçerik (line 1-137):
- 42 hareketli node + 140 yıldız üretir (`COUNT = 42`, `STARS = 140`, `LINK = 140`)
- Mouse 180px yakınında node'ları iter (`if (d < 180 && d > 1) { a.vx -= (dx/d)*0.018; ... }`, line 85-88)
- ~48ms'de bir frame çizer (`if (now - last < 48) { requestAnimationFrame(tick); return; }`, line 57)
- CSS değişkenlerinden renk okur: `cssRgb("--nn-accent", "201, 162, 39")` (line 14-17, 59-60)
- `<canvas id="nn">` elementine basar (line 2)

**Endpoint, fetch, XHR, WebSocket, retry, auth, error handling YOKTUR.** Tamamen dekoratif bir arkaplan scriptidir. Gerçek ağ katmanı **WebView2 IPC**'dir (bkz. bölüm 1.3).

---

### 3. pro-ornek.html — Bağımsız dilekçe örneği

**132 satır, 27KB bağımsız HTML dosyası.** `<head>` içinde inline `<style>` ile A4 print formatı:
```css
@page { size: A4; margin: 18mm 18mm 18mm 20mm; }
html, body { background: #fff; color: #000; }
body, .sheet { font-family: "Times New Roman", Times, serif; font-size: 12pt; }
```

**İçerik:** Gerçek bir idare hukuku dilekçesi örneği — **Ankara Nöbetçi İdare Mahkemesi'ne** açılmış, **7315 sayılı Güvenlik Soruşturması ve Arşiv Araştırması Kanunu** kapsamında "Atama Uygunluk Kararı"nın iptali talebi. Dava konusu: HAGB (Hükmün Açıklanmasının Geri Bırakılması) kararına dayalı olarak infaz ve koruma memurluğuna atamanın reddi.

**Yapı (10 bölüm):**
1. Adli yardım talebi (HMK m. 334, İYUK m. 31/1)
2. Dava konusu işlemin tespiti
3. Müvekkil hakkındaki ceza dosyasının hukuki niteliği (HAGB)
4. Şekil unsuru yönünden hukuka aykırılık (gerekçesizlik)
5. Sebep unsuru yönünden hukuka aykırılık
6. 7315 sayılı Kanun çerçevesinde Değerlendirme Komisyonu'nun sınırlı takdir yetkisi
7. Masumiyet karinesi ve kamu hizmetine girme hakkı
8. Ölçülülük ilkesi (elverişlilik/gereklilik/orantılılık)
9. Konu ve maksat unsurları yönünden hukuka aykırılık
10. Yürütmenin durdurulması talebi

Sonra `DELİLLER`, `HUKUKİ DAYANAKLAR`, `SONUÇ VE İSTEM` (5 maddelik talep), `EKLER` (10 madde).

**İçtihatlar:** 4 AYM kararı + 1 Danıştay kararı referansı (İhsan KILIÇ B.2019/38905, İdris ERTAŞ B.2018/21949, E.2021/60 K.2024/200, Turgut DUMAN B.2014/15365, Danıştay 2. Daire E.2025/2199 K.2026/367).

**Kullanım amacı:** app.js içinde **referansı yok** — `pro-ornek.html` string'i app.js'te geçmez. Bu dosya bağımsız bir örnek/şablon olarak kullanıcıya "Pro sürümde üretilen dilekçe nasıl görünür" demek için tasarlanmış, muhtemelen doğrudan tarayıcıda/pro sayfasında iframe ile açılmak üzere. CSS sınıfları (`.p-tc`, `.p-court`, `.p-banner`, `.row`, `.sec`, `.p`, `.q`, `.sign`) app.js'teki `petitionHtml()` çıktısıyla **birebir aynı** (line 307-462) — yani aynı parser çıktısı hem app içinde hem bu örnekte kullanılıyor.

---

### 4. SQLite Veritabanı (archive.db)

#### 4.1 Tüm tablolar + CREATE TABLE şemaları

`sqlite3 archive.db ".schema"` çıktısı (Python sqlite3 ile alındı, çünkü `sqlite3` CLI yüklü değil):

```sql
CREATE TABLE chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  user_email TEXT,
  prompt TEXT,
  reply TEXT,
  model_id TEXT,
  model_name TEXT
);

CREATE TABLE petitions (
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
);

CREATE INDEX idx_chats_created ON chats(created_at DESC);
CREATE INDEX idx_petitions_created ON petitions(created_at DESC);
```

**Nesne envanteri** (`sqlite_master`):
- 3 tablo: `chats`, `petitions`, `sqlite_sequence` (SQLite internal)
- 2 index: `idx_chats_created`, `idx_petitions_created`
- **0 view**, **0 trigger**, **0 foreign key**

#### 4.2 Tabloların amacı

**`chats` (7 kolon):** Sohbet geçmişi. AI ile yapılan tek seferlik soru-cevap çiftlerini saklar. `prompt` + `reply` tam metin, `model_id`/`model_name` (örn. `claude-3-5-sonnet`, `gpt-4o`), `user_email` ile sahiplik.

**`petitions` (23 kolon):** Üretilen dilekçelerin tam arşivi. Bu tablo **aşırı denormalize** — tek satırda dilekçenin tamamı:
- İçerik: `title`, `petition_type`, `court`, `parties`, `case_summary`, `requests`, `extra_instructions`, `prompt`, `research` (içtihat tarama metni), `body` (üretilen dilekçe tam metni)
- Avukat: `lawyer_name`, `lawyer_bar`, `lawyer_bar_no`, `lawyer_address`, `lawyer_phone`, `lawyer_email` (6 kolon)
- Şablon: `template_name`
- Model: `model_id`, `model_name`
- Çıktı: `pdf_path` (yerel dosya yolu)
- Meta: `id`, `created_at`, `user_email`, `user_name`

#### 4.3 Tablolar arası ilişkiler (foreign keys)

**HİÇBİR foreign key YOK.** `PRAGMA foreign_keys` = 0 (kapalı). `PRAGMA foreign_key_list('chats')` ve `PRAGMA foreign_key_list('petitions')` boş döner.

İki tablo arasında mantıksal bağ `user_email` alanı üzerinden (her iki tabloda da var), ama referential integrity yok. `petitions` ve `chats` birbirinden bağımsız — `petitions.chat_id` gibi bir back-reference bile yok.

#### 4.4 Mevcut veri miktarı

```
chats: 0 rows
petitions: 0 rows
sqlite_sequence: 0 rows
```

**Veritabanı tamamen boş** — bu bir fresh-install/demo kopyası. 24KB'lık dosya boyutu yalnızca şema + WAL + page allocation'dan geliyor.

#### 4.5 Index yapısı

Sadece 2 index, ikisi de aynı pattern:
- `idx_chats_created ON chats(created_at DESC)` — Geçmiş listesi tarihe göre tersten
- `idx_petitions_created ON petitions(created_at DESC)` — Aynı

`user_email` üzerinde index **YOK** — kullanıcı bazlı filtreleme full-table-scan. `petition_type` üzerinde index **YOK**.

#### 4.6 DB parametreleri

- `journal_mode`: **WAL** (Write-Ahead Logging)
- `page_size`: 4096 byte
- `user_version`: 0 (migration sistemi yok)
- `application_id`: 0

#### 4.7 Bu DB'nin amacı

**Yerel arşiv/cache.** Tek-kullanıcılı, tek-cihazlı. `archive.db` adı ve app.js'teki `archive-list`/`archive-get`/`archive-delete` komutları (line 988, 1019, 1038, 1078) bu DB'ye hitap eder. Native host (BetterSaul.exe) SQL çalıştırır; UI sadece mesajlaşır.

**Mimari kısıtlar:**
- Multi-user yok (sadece `user_email` alanı ile soft-separation)
- Concurrent write yok (WAL olsa da tek-yazıcı varsayımı)
- Migration yok (`user_version=0`)
- Audit log yok
- Soft-delete yok (`archive-delete` gerçekten siler)
- Encryption yok (plain SQLite dosya)

---

### 5. Desktop Runtime Bağımlılıkları

#### 5.1 `runtime/` klasörü — Windows-a özel bundled Python

`runtime/python/` altında **Python 3.12 Windows AMD64 portable dağıtımı**:
- `python.exe`, `pythonw.exe`, `python312.dll`, `python.cat`, `python312._pth` (path isolation)
- Tüm modüller `.pyd` (Windows DLL): `_sqlite3.pyd`, `_ssl.pyd`, `_hashlib.pyd`, `_asyncio.pyd`, `_socket.pyd` vb.
- `Lib/site-packages/` altında yüklü paketler: **`mcp`** (Model Context Protocol SDK — `mcp.server.fastmcp`, `mcp.server.streamable_http`, `mcp.server.sse`, `mcp.client.*`), **`uvicorn`** (ASGI server), **`pydantic_core`** (Rust-backed validation), **`httpx`**, **`sse_starlette`**, **`pywin32`** (Windows COM/API), **`certifi`**, **`jsonschema`**, **`cffi`**

`runtime/pip-24.0-py3-none-any.whl` — pip installer wheel (kurulum sırasında kullanılır).

**MCP server'ı bu runtime ile çalışıyor:** `mcp.json` `{"Url": "https://127.0.0.1:8000/mcp", "Port": 8000, "AutoStart": true}` ve `logs/mcp.log` çıktısı:
```
BetterSaul MCP https://127.0.0.1:8000/mcp
INFO:     Uvicorn running on https://127.0.0.1:8000 (Press CTRL+C to quit)
StreamableHTTP session manager started
```
Uvicorn + StreamableHTTP transport'lu MCP server, yerel HTTPS (8443 değil 8000) üzerinde.

#### 5.2 `runtime.stamp` — Runtime integrity damgası

İçerik: `1790246496|1bcc20bb40da699ac7aec43a5068d41b336a0c76bb6cbeed4771ddd55fc6b2b7`

Format: `<Unix-timestamp>|<SHA256-hash>`. `1790246496` = 2026-09-24 13:41:36 UTC (dosya tarihçesiyle uyumlu). SHA256 muhtemelen `runtime/python/` ağacının özetidir — native launcher açılışta bu damgayı doğrular, bozuksa runtime'ı yeniden indirir.

#### 5.3 `session.bin` — Windows DPAPI ile şifrelenmiş blob

614 byte. İlk 64 byte hex: `01000000 d08c9ddf 0115d111 8c7a00c0 4fc297eb 01000000 95d4b574 118f2d47 905decbd 58aff695 00000000 02000000 00001066 00000001 00002000 0000d2e2`

**Magic bytes `01 00 00 00 D0 8C 9D DF 01 15 D1 11 8C 7A 00 C0 4F C2 97 EB`** = standart **Windows DPAPI** (Data Protection API) blob başlığı (CLSID `df9d8cd0-1501-11d1-8c7a-00c04fc297eb`). Bu, Windows'un `CryptProtectData()` API'sinin ürettiği format. İçerik muhtemelen auth token / refresh token / user credentials — sadece aynı Windows kullanıcı hesabı + makine altında çözülebilir.

#### 5.4 `webview/EBWebView/` — Microsoft Edge WebView2 user-data

Tam bir Edge/Chromium user-data dizini (Default profil). Önemli alt klasörler:
- `Default/History`, `Default/Cookies`, `Default/Login Data` — Chromium SQLite'ları
- `Default/Local Storage/leveldb/` — localStorage
- `Default/Session Storage/` — sessionStorage
- `Default/Code Cache/js/` — V8 bytecode cache
- `Default/GPUCache/`, `DawnGraphiteCache/`, `DawnWebGPUCache/` — GPU shader cache
- `Default/Network/Cookies`, `Default/Network/Reporting and NEL` — ağ katmanı
- `EBWebView/Crashpad/` — crash raporlama
- `EBWebView/SmartScreen/` — Microsoft SmartScreen local cache
- `EBWebView/PKIMetadata/`, `EBWebView/TrustTokenKeyCommitments/` — sertifika/PKI
- `EBWebView/Last Version` — Chromium sürümü (muhtemelen 138.x)
- `EBWebView/Local State` — Chromium master config (encrypted)

**Bu klasör web migrasyonuyla tamamen yok olacak** — web tarafında tarayıcı kendi user-data'sını yönetir.

#### 5.5 `certs/` — MCP server self-signed TLS sertifikası

- `mcp-cert.pem` (1106 byte) — self-signed X.509 cert
- `mcp-key.pem` (1703 byte) — private key

OpenSSL çıktısı:
```
subject= CN=BetterSaul MCP (yerel)
issuer= CN=BetterSaul MCP (yerel)    (self-signed)
notBefore= Sep 23 10:30:59 2026 GMT
notAfter=  Sep 24 10:30:59 2031 GMT  (5 yıl geçerli)
```

Amaç: Yerel MCP server `https://127.0.0.1:8000/mcp` HTTPS'ini sonlandırır. WebView2 bu sertifikaya güvenmek için native host tarafında certificate trust kurar (açıksa Windows certificate store'a yüklenir).

#### 5.6 `connect/` — Desktop AI entegrasyon şablonları

6 dosya:
- `README.txt` — Kullanıcıya yönelik kurulum kılavuzu
- `claude_desktop.json` — Claude Desktop config şablonu (yol: `%APPDATA%\Claude\claude_desktop_config.json`)
- `chatgpt.json` — ChatGPT Desktop MCP config şablonu
- `chatgpt.toml` — ChatGPT Desktop `config.toml` formatı (yol: `%USERPROFILE%\.codex\config.toml`)
- `cursor-mcp.json` — Cursor editor MCP config
- `gemini.json` — Gemini Desktop `settings.json` (yol: `%USERPROFILE%\.gemini\settings.json`)

Tüm JSON'lar aynı içeriğe sahip:
```json
{
  "mcpServers": {
    "BetterSaul": {
      "command": "C:\\Users\\user\\AppData\\Local\\BetterSaul\\runtime\\python\\python.exe",
      "args": ["C:\\Users\\user\\AppData\\Local\\BetterSaul\\app\\engine\\run_mcp.py", "--stdio"],
      "cwd": "C:\\Users\\user\\AppData\\Local\\BetterSaul\\app\\engine",
      "env": { "PYTHONPATH": "...\\app\\engine", "PYTHONUTF8": "1" }
    }
  }
}
```

`chatgpt.toml` (Codex formatı):
```toml
cp_servers.BetterSaul]
command = 'C:\Users\user\AppData\Local\BetterSaul\runtime\python\python.exe'
args = ['C:\Users\user\AppData\Local\BetterSaul\app\engine\run_mcp.py', '--stdio']
startup_timeout_sec = 120
tool_timeout_sec = 120
enabled = true
default_tools_approval_mode = "auto"
```

Not: `default_tools_approval_mode = "auto"` — ChatGPT Desktop'ta BetterSaul MCP araçları **kullanıcı onayı olmadan otomatik** çalışır. Bu önemli bir güvenlik notu.

---

### 6. Desktop vs Web Analysis

#### 6.1 Doğrudan web'e taşınabilir UI özellikleri

| Özellik | Web karşılığı | Çaba |
|---|---|---|
| HTML yapısı (`index.html` 446 satır) | Doğrudan kopyalanabilir | 1 saat |
| `app.css` (772 satır, dark theme) | Doğrudan kopyalanabilir; `--nn-*` canvas renkleri korunabilir | 1 saat |
| `net.js` canvas animasyonu | Doğrudan kopyalanabilir (browser-agnostic) | 5 dk |
| `petitionHtml()` parser (line 307-462) | Doğrudan — saf JS string/regex | 5 dk |
| `pro-ornek.html` | Doğrudan statik dosya | 5 dk |
| Form validasyonu (`hmk119Gaps`, `parseTl`) | Doğrudan | 5 dk |
| localStorage (`bs.lawyer`, `bs.petitionTimings`) | Tarayıcıda zaten çalışır; multi-device için server'a senkronize edilmeli | 1 gün |
| Tab/view switching (`switchTab`, `show`) | Doğrudan | 5 dk |
| KVKK dialog (`<dialog>`) | Doğrudan (modern tarayıcı destek) | 5 dk |

#### 6.2 Yeniden tasarlanması gerekenler

| Desktop özelliği | Web karşılığı | Çaba |
|---|---|---|
| WebView2 IPC `send({cmd:...})` (30 komut) | REST API (`fetch`) + SSE (streaming için `chat-delta`/`petition-status`) | 3-5 gün |
| `hostObjects.sync.bs.Login()` senkron köprü | JWT/OAuth login endpoint | 1 gün |
| `session.bin` (DPAPI encrypted) | Server-side httpOnly secure cookie + refresh token DB | 2 gün |
| `archive.db` (local SQLite) | PostgreSQL (multi-tenant, server-side) | 2-3 gün (bkz. bölüm 7) |
| `save-pdf`/`export-petition` (native PDF render) | WeasyPrint / puppeteer server-side; download response | 2 gün |
| `mcp-start`/`mcp-stop`/`mcp-status` | Backend MCP server lifecycle — kullanıcıya şeffaf; web'de kullanıcı MCP'yi görmez, doğrudan `/api/petition` çağırır | 3 gün |
| `mcp-install-claude/chatgpt/gemini` | **Web'de anlamsız** — backend zaten MCP'yi çalıştırıyor. Kaldırılır ya da "Desktop kullanıyorsanız şablon indir" sayfasına dönüşür | 1 gün |
| `launch-claude/chatgpt/gemini` | **Web'de imkânsız** — tarayıcı lokal app başlatamaz. Tamamen kaldırılmalı | — |
| `open-claude-download` vb. | Dış bağlantı (`<a target="_blank">`) — doğrudan | 5 dk |
| `setup` / `setup-progress` (Python runtime kurulumu) | **Web'de yok** — kullanıcı runtime kurmaz. Setup wizard tamamen kaldırılır | — |
| `update-required` wall | Web'de deployment anında tüm kullanıcılar yeni sürümü görür — wall gerekmez; opsiyonel maintenance banner yeter | 1 saat |
| Local `mcp.json` (`127.0.0.1:8000`) | Backend MCP server, kullanıcıdan gizli | — |
| `certs/` self-signed TLS | Backend'de Let's Encrypt / gerçek sertifika | — |

#### 6.3 app.js'in ne kadarı web'de çalışır

**1790 satırın ~%40'ı doğrudan web'de çalışır** (UI rendering, form parsing, petition parser, tab/view switching, CSS class toggle, localStorage, clipboard).

**~%30'u adapte edilmeli** (30 `send({cmd})` çağrısının tamamı → `fetch()` veya SSE; 30 event handler → SSE/WebSocket event handlers).

**~%30'u tamamen kaldırılmalı** (setup wizard logic `markPhase`/`phaseOf`/`startSetupClock` ~50 satır, `mcp-install-*` consent flows ~150 satır, `launch-*` handlers ~60 satır, `loginViaBridge` ~12 satır, `hostObjects.sync` ~10 satır, `renderClaude`/`renderDesk`/`bindDeskRemove` ~120 satır).

**Web için yeni eklenmesi gerekenler:** JWT auth flow + refresh, SSE subscriber for `chat-delta`/`petition-status`/`petition-research`, error toast component (yok), loading state component (yok), file upload for PDF/DOCX/UDF download.

#### 6.4 IPC/WebView mesajlaşması → Web mapping

| Desktop mesajı | Web karşılığı |
|---|---|
| `send({cmd:"login",email,password})` → `event:"login-ok"` | `POST /api/auth/login` → `{token, user}` |
| `send({cmd:"petition",...})` → `event:"petition-delta/research/status/done"` | `POST /api/petitions` → SSE `/api/petitions/{id}/stream` |
| `send({cmd:"archive-list",kind,q})` → `event:"archive-list"` | `GET /api/petitions?q=...&kind=...` |
| `send({cmd:"archive-get",id})` → `event:"archive-item"` | `GET /api/petitions/{id}` |
| `send({cmd:"save-pdf"})` → `event:"pdf-ok"` | `POST /api/petitions/{id}/export?fmt=pdf` → `application/pdf` blob |
| `send({cmd:"chat",...})` → `event:"chat-delta/done"` | `POST /api/chat` → SSE stream |
| `send({cmd:"logout"})` → `event:"logout-ok"` | `POST /api/auth/logout` (cookie sil) |
| `send({cmd:"ready"})` → `event:"boot/session"` | `GET /api/me` (initial load) |

---

### 7. Veritabanı Migration Planı (SQLite → PostgreSQL)

#### 7.1 Doğrudan migrate edilebilir tablolar

**`chats` tablosu** — doğrudan PostgreSQL'e taşınabilir:
```sql
CREATE TABLE chats (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- user_email → user_id FK
  prompt TEXT NOT NULL DEFAULT '',
  reply TEXT NOT NULL DEFAULT '',
  model_id TEXT,
  model_name TEXT
);
CREATE INDEX idx_chats_user_created ON chats(user_id, created_at DESC);
```

Değişiklikler: `user_email TEXT` → `user_id BIGINT FK` (normalizasyon), `created_at TEXT` → `TIMESTAMPTZ` (timezone-aware), `AUTOINCREMENT` → `BIGSERIAL`, composite index (`user_id, created_at`) eklendi.

#### 7.2 Yeniden tasarlanması gereken tablolar

**`petitions` tablosu** (23 kolon) bölünmeli:

```sql
-- Ana dilekçe
CREATE TABLE petitions (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  petition_type TEXT NOT NULL,
  court TEXT,
  parties TEXT,                    -- JSONB önerilir: {"davaci":{...}, "davali":{...}}
  case_summary TEXT,
  requests TEXT,                   -- JSONB önerilir: ["1) ...", "2) ..."]
  extra_instructions TEXT,
  user_prompt TEXT,
  research_text TEXT,              -- MCP tarama çıktısı (uzun metin)
  body TEXT NOT NULL,              -- üretilen dilekçe tam metni
  model_id TEXT,
  model_name TEXT,
  pdf_path TEXT,                   -- S3 URL'si olmalı: s3://bucket/petitions/{id}.pdf
  status TEXT NOT NULL DEFAULT 'completed',  -- 'draft'|'generating'|'completed'|'failed'
  generation_seconds INT,
  CONSTRAINT petitions_status_chk CHECK (status IN ('draft','generating','completed','failed'))
);
CREATE INDEX idx_petitions_user_created ON petitions(user_id, created_at DESC);
CREATE INDEX idx_petitions_type ON petitions(petition_type) WHERE status = 'completed';

-- Avukat profili (ayrı tablo — petitions içinde 6 lawyer_* kolon tekrarı var)
CREATE TABLE lawyer_profiles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  lawyer_name TEXT NOT NULL,
  lawyer_bar TEXT,
  lawyer_bar_no TEXT,
  lawyer_address TEXT,
  lawyer_phone TEXT,
  lawyer_email TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dilekçe-avukat ilişkisi (snapshot — o anki avukat bilgisi)
CREATE TABLE petition_lawyers (
  petition_id BIGINT PRIMARY KEY REFERENCES petitions(id) ON DELETE CASCADE,
  lawyer_profile_id BIGINT REFERENCES lawyer_profiles(id),
  lawyer_name TEXT NOT NULL,      -- snapshot
  lawyer_bar TEXT, lawyer_bar_no TEXT,
  lawyer_address TEXT, lawyer_phone TEXT, lawyer_email TEXT
);

-- Şablon
CREATE TABLE petition_templates (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  template_body JSONB NOT NULL,   -- yapılandırılmış şablon
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);
ALTER TABLE petitions ADD COLUMN template_id BIGINT REFERENCES petition_templates(id);

-- Dilekçe claim değerleri (HMK m. 119 — ziynet, kıdem, ihbar vb.)
CREATE TABLE petition_claims (
  petition_id BIGINT NOT NULL REFERENCES petitions(id) ON DELETE CASCADE,
  claim_type TEXT NOT NULL,        -- 'maddi'|'manevi'|'kidem'|'ihbar'|'mesai'|'ziynet'|...
  amount NUMERIC(14,2),
  currency CHAR(3) NOT NULL DEFAULT 'TRY',
  metadata JSONB,                  -- ziynet için: {cins, adet, ayar, gram}
  PRIMARY KEY (petition_id, claim_type)
);

-- İçtihat/research tarama kayıtları (ayrı tablo — petitions.research TEXT yerine)
CREATE TABLE petition_research_items (
  id BIGSERIAL PRIMARY KEY,
  petition_id BIGINT NOT NULL REFERENCES petitions(id) ON DELETE CASCADE,
  source TEXT NOT NULL,            -- 'yargitay'|'danistay'|'aym'|'resmi_gazete'|'emsal'|'bedesten'|'mevzuat'
  source_id TEXT,                  -- karar no / RG sayı
  title TEXT,
  excerpt TEXT,
  url TEXT,
  relevance_score REAL,
  embedding VECTOR(1536),          -- pgvector — semantic search için
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_research_petition ON petition_research_items(petition_id);
CREATE INDEX idx_research_embedding ON petition_research_items USING ivfflat (embedding vector_cosine_ops);
```

#### 7.3 Eksik tablolar (web SaaS için yeni)

```sql
-- Kullanıcı (yok)
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,     -- argon2id
  name TEXT NOT NULL,
  phone TEXT,
  role TEXT NOT NULL DEFAULT 'user',  -- 'user'|'admin'|'lawyer'
  email_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT users_role_chk CHECK (role IN ('user','admin','lawyer'))
);

-- Organization (yok — çok kullanıcılı hukuk büroları için)
CREATE TABLE organizations (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  plan TEXT NOT NULL DEFAULT 'free'  -- 'free'|'pro'|'team'|'enterprise'
);

CREATE TABLE organization_members (
  org_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member',  -- 'owner'|'admin'|'member'
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (org_id, user_id)
);

-- Subscription (yok — Stripe/Lemon Squeezy entegrasyonu için)
CREATE TABLE subscriptions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  org_id BIGINT REFERENCES organizations(id),
  provider TEXT NOT NULL,          -- 'stripe'|'lemonsqueezy'
  provider_sub_id TEXT NOT NULL UNIQUE,
  plan TEXT NOT NULL,
  status TEXT NOT NULL,            -- 'active'|'past_due'|'canceled'|'trialing'
  current_period_end TIMESTAMPTZ,
  credits_remaining INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- API keys (yok — public API için)
CREATE TABLE api_keys (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_hash TEXT NOT NULL UNIQUE,   -- SHA256(api_key)
  label TEXT,
  last_used_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Kredi/usage tracking (yok — her dilekçe üretimi kredi yer)
CREATE TABLE usage_events (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  event_type TEXT NOT NULL,        -- 'petition'|'chat'|'research'|'pdf_export'
  credits_used INT NOT NULL DEFAULT 0,
  model_id TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_user_created ON usage_events(user_id, created_at DESC);

-- Audit log (yok — KVKK uyumu için zorunlu)
CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT,
  action TEXT NOT NULL,            -- 'login'|'petition_create'|'petition_delete'|'export'|...
  resource_type TEXT,
  resource_id BIGINT,
  ip_address INET,
  user_agent TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_logs(action, created_at DESC);

-- Refresh tokens (yok — JWT refresh için)
CREATE TABLE refresh_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address INET,
  user_agent TEXT
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);

-- Mevzuat / içtihat cache (yok — sources.py scraping sonuçlarını cache için)
CREATE TABLE legal_sources (
  id BIGSERIAL PRIMARY KEY,
  source_type TEXT NOT NULL,       -- 'yargitay'|'danistay'|'aym'|'resmi_gazete'|'mevzuat'
  source_id TEXT NOT NULL,         -- karar no, RG sayı, mevzuat no
  title TEXT,
  body TEXT NOT NULL,
  url TEXT,
  published_at DATE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  embedding VECTOR(1536),          -- pgvector
  metadata JSONB,
  UNIQUE(source_type, source_id)
);
CREATE INDEX idx_legal_sources_type ON legal_sources(source_type, source_id);
CREATE INDEX idx_legal_sources_embedding ON legal_sources USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

#### 7.4 pgvector kullanımı — semantic search için

Mevcut sistemde **hiçbir semantic search yok** (diğer task'larda tespit edildi). pgvector migration ile eklenen vektör indeksleri:

1. **`legal_sources.embedding`** — Yargıtay/Danıştay/AYM kararları, Resmî Gazete, mevzuat metinleri için 1536-boyutlu embedding (OpenAI `text-embedding-3-small` veya `nomic-embed-text`). Kullanıcı dilekçe özetini arar → en alakalı içtihatları getirir. **Bu mevcut "yerel indeks yok" sorununun çözümüdür.**

2. **`petition_research_items.embedding`** — Daha önce üretilmiş dilekçeler için çekilmiş içtihatların embedding'i. Aynı konuda yeni dilekçe üretirken "bu kullanıcının önceki dilekçelerinde hangi içtihatları kullanmıştık" sorgusu hızlanır.

3. **`petitions.case_summary` embedding (opsiyonel)** — Tüm üretilmiş dilekçelerin vektörü; "benzer davaları göster" özelliği için.

#### 7.5 Migration sırası

1. **Faz 1 (PoC):** `users`, `lawyer_profiles`, `petitions` (sadece ana kolonlar), `chats`, `petition_templates`, `usage_events`, `audit_logs`, `refresh_tokens` — temel web app çalışsın
2. **Faz 2:** `organizations`, `organization_members`, `subscriptions`, `api_keys` — SaaS katmanı
3. **Faz 3:** `petition_claims`, `petition_lawyers`, `petition_research_items` — refactor (petitions tablosu bölünür)
4. **Faz 4:** `legal_sources` + pgvector — semantic search (en yüksek değer, en son)
5. **Faz 5 (opsiyonel):** Eski `archive.db`'den veri taşıma (kullanıcı başına export → import script). Mevcut DB boş olduğu için acil değil.

---

### 8. Özet Teknik Bulgular

| # | Bulgu | Etki |
|---|---|---|
| 1 | UI **tamamen vanilla JS**, framework yok | Web'e taşımak düşük çaba; refactor gerektirmez |
| 2 | Tüm backend iletişim **WebView2 IPC** (`window.chrome.webview.postMessage`) | Web'de 30 komut → REST/SSE'ye rewrite gerekiyor |
| 3 | `loginViaBridge` senkron .NET hostObject çağrısı var (line 1137) | Web'de anlamsız, JWT ile değiştir |
| 4 | `net.js` ağ katmanı DEĞİL — neural-net canvas animasyonu (137 satır) | Doğrudan web'e taşınır |
| 5 | `archive.db` 2 tablolu, **0 veri**, 0 FK, 0 trigger, 0 view | Boş şema → PostgreSQL redesign serbest |
| 6 | `petitions` 23 kolon aşırı denormalize (6 lawyer_*, prompt+research+body) | Bölünmeli: petitions + lawyer_profiles + petition_claims + petition_research_items |
| 7 | `session.bin` = Windows DPAPI encrypted blob (magic `01000000 D08C9DDF...`) | Web'de JWT + httpOnly cookie, DPAPI yok |
| 8 | `runtime/python/` = Python 3.12 Windows AMD64 + MCP SDK + uvicorn | Web'de server-side, kullanıcı görmez |
| 9 | `webview/EBWebView/` = tam Edge WebView2 user-data | Web'de tamamen yok, tarayıcı yönetir |
| 10 | `certs/mcp-key.pem` + `mcp-cert.pem` = self-signed, CN=BetterSaul MCP (yerel), 5 yıl geçerli | Web'de Let's Encrypt; kullanıcıya şeffaf |
| 11 | `connect/*.json` + `chatgpt.toml` = 4 desktop AI entegrasyon şablonu | Web'de anlamsız; opsiyonel "desktop kullananlar için şablon indir" sayfası |
| 12 | `mcp.json` = `https://127.0.0.1:8000/mcp` + `AutoStart:true` | Web'de backend MCP server; kullanıcıdan gizli |
| 13 | `runtime.stamp` = `<unix>|<sha256>` — runtime integrity | Web'de yok (deployment hash ile yönetilir) |
| 14 | `app/.payload-version` = `1.6.26-arac-onarim` — semver + branch tag | Web'de `package.json` version yeter |
| 15 | `pro-ornek.html` = gerçek idare hukuku dilekçesi örneği (Ankara Nöbetçi İdare Mahkemesi, 7315 sayılı Kanun) | Şablon/reference, doğrudan taşınır |
| 16 | CSS: dark theme, 18 custom property, 0 `@keyframes`, 7 `backdrop-filter` | Doğrudan taşınır |
| 17 | localStorage: `bs.lawyer`, `bs.petitionTimings` | Multi-device için server sync gerekiyor |
| 18 | MCP araçları ChatGPT Desktop'ta `default_tools_approval_mode = "auto"` — kullanıcı onayı yok | Web'de tools backend'de, kullanıcı tool'ları görmez |

### 9. Sonraki Aksiyonlar

- **Task (UI Migration):** `app.js` → web refactor planı (30 komut → REST/SSE mapping dokümanı, hata/loading komponentleri, SSE subscriber abstraction)
- **Task (DB Migration):** PostgreSQL şema migration script'i (`schema.sql` + Alembic) yazımı
- **Task (Auth Migration):** `session.bin` (DPAPI) → JWT + httpOnly secure cookie + refresh_tokens tablosu tasarımı
- **Task (MCP Backend):** `app/engine/run_mcp.py` MCP server'ın FastAPI'ye taşınması; stdio↔HTTP transport değişimi
- **Task (Petition Renderer):** `pro-ornek.html` parser'ını `/api/petitions/{id}/html` endpoint'ine bağlama; server-side PDF/DOCX render (WeasyPrint/python-docx)

---

## Task ID: 5 — Final PDF Report Generation

**Tarih:** 2026-09-27
**Agent:** Main (Z.ai)
**Task:** 15 bölümlük teknik analiz raporunu PDF olarak üret

### Work Log:
- 4 paralel Explore agent ile kod tabanı analizi tamamlandı (Task ID 1-4)
- Outline tool ile 18 bölümlük rapor yapısı belirlendi (cover + TOC + 15 bölüm + sonuç)
- PDF skill yüklendi, report brief okundu, palette.cascade ile renk paleti üretildi
- Template 01 (HUD Data Terminal) tabanlı cover HTML yazıldı ve html2poster.js ile PDF'e renderlandı
- 2 mimari diyagram HTML yazıldı (mevcut + önerilen), html2poster.js ile PDF, pypdfium2 ile PNG'ye çevrildi
- ReportLab + TocDocTemplate ile 42 sayfalık body PDF üretildi (multiBuild, TOC, tablolar, kod blokları, görseller)
- pypdf ile cover + body birleştirildi, metadata eklendi, A4 normalizasyonu yapıldı
- pdf_qa.py ile kalite kontrol: 10/10 pass, 0 error, 4 minor warning (CJK punctuation + cover asymmetry - kabul edilebilir)

### Stage Summary:
- **Final deliverable:** `/home/z/my-project/download/BetterSaul_Web_Platform_Migration_Analiz_Raporu.pdf`
- **43 sayfa**, 1.5 MB, Türkçe, A4
- **İçerik:** Cover + TOC + Yönetici Özeti + 15 Bölüm + Sonuç
- **Görseller:** 2 mimari diyagram (mevcut + önerilen), 13 tablo, 12 kod bloğu (DDL şemalar dahil)
- **Kritik bulgular:** Semantic search YOK, LLM Qwen-only, 2 tablolu SQLite, 7857 satır tek engine.py
- **Önerilen mimari:** Next.js 16 + PostgreSQL + pgvector + Python FastAPI container + AI provider abstraction
- **19 fazlık migration planı:** 5-7 ay tahmini süre
- **Sprint 1:** 8 görev, 2-3 hafta (Next.js scaffold + DB + Python container + Auth + 18 MCP→REST + Dashboard + Search UI + PDF export)
