"""BetterSaul MCP sunucusu — Streamable HTTP."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import anayasa, mevzuat, petition_tools, sources

server = MCPServer(
    "BetterSaul",
    instructions=(
        "Claude, ChatGPT ve Gemini’de aynı kural: dava, dilekçe, iptal, boşanma, "
        "işe iade, istem veya somut olay (mahkeme, davacı, davalı, vekil) gelince "
        "hemen dilekçeyi yaz, sonra biçimle. Ürün adı bekleme. "
        "Biçimlenen dilekçe BetterSaul Geçmiş’e kendiliğinden yazılır. "
        "Soru sorma; eksik bilgiyi uydurma. Araç adlarını sohbete ve dilekçeye yazma. "
        "Türk hukuk kaynakları: Bedesten, mevzuat.gov.tr, AYM, Resmî Gazete. "
        "Mahkeme 80 tabanı: T.C., ivedide Nöbetçi İdare, DAVA DİLEKÇESİ, iptalde maktu, "
        "DAVACI adı, DAVALI tek satır (araştırma notu yok), numaralı vakıa, gerçek künye. "
        "Sıra: kaynak tara → usul iskeleti → madde çek → Danıştay tara → "
        "idarede AYM tara (çekilen 1 künye) → RG (yoksa yazma) → "
        "örnek şablonla yaz (T.C. / mahkeme / DAVA DİLEKÇESİ / tür / DAVACI / VEKİLİ / DAVALI / KONU / "
        "AÇIKLAMALAR’da her vakıanın altında Delil / Hukuki dayanak / Hukuki sonuç / "
        "HUKUKİ SEBEPLER / DELİLLER / SONUÇ VE İSTEM / imza / EKLER; gövde müvekkil) → "
        "biçimle → kontrol et → kaliteyi ölç → geçmişe veya PDF kaydet. "
        "Adli yardım metinde/kutuda varsa baner+vakıa+istem. "
        "Vakıa, TCKN, tutar, esas-karar, RG/AYM uydurma. Markdown, Vekile Not, Wikipedia yok."
    ),
)


@server.tool(
    name="search_bedesten",
    description="Bedesten (adalet.gov.tr) üzerinden Yargıtay / Danıştay / yerel karar ara (çok sayfa).",
)
def search_bedesten(phrase: str, court_types: list[str] | None = None) -> str:
    from .license_gate import enforce
    enforce()
    return sources.search_bedesten(phrase, court_types)


@server.tool(
    name="search_corpus_deep",
    description="Birden fazla ifadeyle kilitli mahkeme taraması. İdari davada court_types=['DANISTAYKARAR'] zorunlu.",
)
def search_corpus_deep(
    phrases: list[str] | str,
    pages: int = 2,
    court_types: list[str] | None = None,
) -> str:
    return sources.search_corpus_deep(phrases, pages, court_types)


@server.tool(
    name="get_bedesten_document",
    description="Bedesten documentId ile karar metnini getir. Holding/özet uç noktası yoktur; özet yerelde çıkarılır.",
)
def get_bedesten_document(documentId: str) -> str:
    return sources.get_bedesten_document(documentId)


@server.tool(
    name="search_emsal",
    description="Emsal nitelikli yerel / istinaf / KYB kararlarını Bedesten üzerinden ara.",
)
def search_emsal(keyword: str, page_number: int = 1) -> str:
    return sources.search_emsal(keyword, page_number)


@server.tool(
    name="search_mevzuat",
    description="mevzuat.gov.tr katalog eşlemesi. Anahtar → kanun no (ör. güvenlik soruşturması → 7315).",
)
def search_mevzuat(query: str) -> str:
    return mevzuat.search_mevzuat(query)


@server.tool(
    name="get_mevzuat_article",
    description="Resmi madde özeti (madde + fıkra, ~800 karakter). Bulunamazsa yok/uydurma; metin uydurma.",
)
def get_mevzuat_article(kanun: str, madde: str) -> str:
    return mevzuat.get_mevzuat_article(kanun, madde)


@server.tool(
    name="list_mevzuat_catalog",
    description="Çekilebilir kanun kodları (Anayasa, İYUK, 7315, TMK, 4857, İİK, TKHK, HMK, TCK, CMK, 7036).",
)
def list_mevzuat_catalog() -> str:
    return mevzuat.list_mevzuat_catalog()


@server.tool(
    name="search_anayasa",
    description="AYM kamu araması. İdarede zorunlu. decision_type: bireysel_basvuru | norm_denetimi. En fazla 1 künye göm; uydurma.",
)
def search_anayasa(keywords: str, decision_type: str = "bireysel_basvuru") -> str:
    return anayasa.search_anayasa(keywords, decision_type)


@server.tool(
    name="get_anayasa_document",
    description="AYM karar metni / kısa ilke. url veya B. No (2014/4708) veya /BB/yıl/no.",
)
def get_anayasa_document(url_or_id: str) -> str:
    return anayasa.get_anayasa_document(url_or_id)


@server.tool(
    name="search_resmi_gazete",
    description="Resmî Gazete fihrist + başlık araması. date_start/date_end: YYYY-MM-DD (opsiyonel).",
)
def search_resmi_gazete(query: str, date_start: str = "", date_end: str = "") -> str:
    return sources.search_resmi_gazete(query, date_start, date_end)


@server.tool(
    name="get_resmi_gazete_fihrist",
    description="Belirli günün Resmî Gazete fihristi (fihrist?tarih= veya eskiler/YYYY/MM/YYYYMMDD.htm).",
)
def get_resmi_gazete_fihrist(date: str) -> str:
    return sources.get_resmi_gazete_fihrist(date)


@server.tool(
    name="get_resmi_gazete_document",
    description="Resmî Gazete belge düz metni. URL veya YYYY-MM-DD + kalem (20240115-3). 404/svg at.",
)
def get_resmi_gazete_document(url_or_date_and_item: str) -> str:
    return sources.get_resmi_gazete_document(url_or_date_and_item)


@server.tool(
    name="scan_source",
    description="Kullanıcı/form metninden müvekkil adı, adli yardım, ivedi/YD çıkar. Yazmadan önce çağır. Uydurmaz.",
)
def scan_source(source: str) -> str:
    return petition_tools.scan_source(source)


@server.tool(
    name="petition_guide",
    description="Dilekçe yazmadan önce usul iskeleti (T.C., DAVA DİLEKÇESİ, vakıa altında Delil/dayanak/sonuç).",
)
def petition_guide(petition_type: str = "") -> str:
    return petition_tools.petition_guide(petition_type)


@server.tool(
    name="petition_skeleton",
    description="Dava türüne göre boş dilekçe iskeleti. Yer tutucu bırakır; vakıa uydurmaz.",
)
def petition_skeleton(petition_type: str = "") -> str:
    return petition_tools.petition_skeleton(petition_type)


@server.tool(
    name="write_court_petition",
    description=(
        "Kullanıcı olay, dava veya dilekçe anlattığında bunu çağır. "
        "Tam dilekçe varsa text= ile gönder; yoksa source= kullanıcı mesajı. "
        "Biçimler ve BetterSaul Geçmiş’e kaydeder. Ürün adı bekleme."
    ),
)
def write_court_petition(
    source: str = "",
    text: str = "",
    court: str = "",
    title: str = "",
    petition_type: str = "",
) -> str:
    from .license_gate import enforce
    enforce()
    return petition_tools.write_court_petition(
        source=source,
        text=text,
        court=court,
        title=title,
        petition_type=petition_type,
    )


@server.tool(
    name="format_petition",
    description="Mahkeme biçimi: T.C., DAVA DİLEKÇESİ, sızıntı sil, gövde müvekkil. Bitince Geçmiş’e yazar. source=kullanıcı metni.",
)
def format_petition(
    text: str = "",
    court: str = "",
    title: str = "",
    source: str = "",
    body: str = "",
    petition: str = "",
    dilekce: str = "",
) -> str:
    from .license_gate import enforce
    enforce()
    raw = petition_tools._tool_text(text, body, petition, dilekce, source)
    return petition_tools.format_petition(raw, court=court, title=title, source=source)


@server.tool(
    name="check_petition",
    description="80 tabanı: boş DAVACI, davacı/müvekkil, AYM, adli yardım. source=kullanıcı metni. Yazmaz.",
)
def check_petition(
    text: str = "",
    petition_type: str = "",
    source: str = "",
    body: str = "",
    petition: str = "",
    dilekce: str = "",
) -> str:
    raw = petition_tools._tool_text(text, body, petition, dilekce, source)
    return petition_tools.check_court_ready(raw, petition_type, source)


@server.tool(
    name="review_petition",
    description=(
        "Yazılan dilekçeyi bağımsız kalite motorundan geçirir: dava türü ön değerlendirme, "
        "talep envanteri, KONU–AÇIKLAMA–DAYANAK–DELİL–SONUÇ zinciri, süre, hesap, faiz, "
        "usul, yetki, uydurma, içtihat, karşı taraf/hâkim notu ve ağırlıklı puan. "
        "Dilekçe metnine yazmaz. text= tam metin, source= kullanıcı formu."
    ),
)
def review_petition(
    text: str = "",
    petition_type: str = "",
    source: str = "",
    body: str = "",
    petition: str = "",
    dilekce: str = "",
) -> str:
    from . import quality as _q
    raw = petition_tools._tool_text(text, body, petition, dilekce)
    return _q.review_text(raw, petition_type=petition_type, source=source)


@server.tool(
    name="save_petition_history",
    description=(
        "Dilekçeyi BetterSaul Geçmiş’e kaydeder. Biçimleme zaten kaydeder; "
        "kullanıcı özellikle geçmişe yaz dese veya biçimlenmemiş metin varsa çağır. "
        "text= ile TAM dilekçe metnini gönder."
    ),
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
    return petition_tools.save_petition_history(
        text=text,
        title=title,
        petition_type=petition_type,
        body=body,
        petition=petition,
        dilekce=dilekce,
        content=content,
        source=source,
    )


@server.tool(
    name="save_petition_pdf",
    description=(
        "Dilekçeyi önce BetterSaul Geçmiş’e yazar, sonra PDF/HTML dener. "
        "Kullanıcı 'pdf yap / kaydet / uygulamada gör' dediğinde MUTLAKA çağır. "
        "text= (veya body=/dilekce=) ile TAM dilekçe metnini gönder; başlık yetmez. "
        "PDF patlasa bile geçmiş kaydı kalır."
    ),
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
    return petition_tools.save_petition_pdf(
        text,
        title=title,
        path=path,
        open_file=open_file,
        petition_type=petition_type,
        body=body,
        petition=petition,
        dilekce=dilekce,
        content=content,
        source=source,
        history_only=history_only,
    )


def run_stdio() -> None:
    from .license_gate import enforce
    enforce()
    server.run(transport="stdio")


def run_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    ssl_cert: str = "",
    ssl_key: str = "",
) -> None:
    from .license_gate import enforce
    enforce()
    if ssl_cert and ssl_key:
        import anyio
        import uvicorn

        app = server.streamable_http_app(
            streamable_http_path="/mcp",
            stateless_http=True,
            json_response=True,
            host=host,
        )
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            ssl_certfile=ssl_cert,
            ssl_keyfile=ssl_key,
        )
        anyio.run(uvicorn.Server(config).serve)
        return
    server.run(
        transport="streamable-http",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )
