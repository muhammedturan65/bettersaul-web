"""
BetterSaul Web Platform Migration — Teknik Analiz Raporu
PDF Body Generator (ReportLab)

Generates the 18-section body PDF using ReportLab + TocDocTemplate.
Cover is generated separately via html2poster.js, merged at the end.
"""
import os
import sys
import hashlib
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ─── PDF skill scripts in path for install_font_fallback ───
PDF_SKILL_DIR = '/home/z/my-project/skills/pdf'
sys.path.insert(0, os.path.join(PDF_SKILL_DIR, 'scripts'))
from pdf import install_font_fallback  # type: ignore

# ─── Cascade Palette (auto-generated) ──────────────────────────────
PAGE_BG       = colors.HexColor('#f1f1f0')
SECTION_BG    = colors.HexColor('#efefee')
CARD_BG       = colors.HexColor('#ecebe7')
TABLE_STRIPE  = colors.HexColor('#f1f0ef')
HEADER_FILL   = colors.HexColor('#746b4f')
COVER_BLOCK   = colors.HexColor('#5c5542')
BORDER        = colors.HexColor('#d6d2c5')
ICON          = colors.HexColor('#ae9446')
ACCENT        = colors.HexColor('#897128')
ACCENT_2      = colors.HexColor('#61a9c1')
TEXT_PRIMARY  = colors.HexColor('#21201e')
TEXT_MUTED    = colors.HexColor('#87847d')
SEM_SUCCESS   = colors.HexColor('#548c66')
SEM_WARNING   = colors.HexColor('#a18140')
SEM_ERROR     = colors.HexColor('#8e4f49')
SEM_INFO      = colors.HexColor('#486684')

TABLE_HEADER_COLOR = HEADER_FILL
TABLE_HEADER_TEXT  = colors.white
TABLE_ROW_EVEN     = colors.white
TABLE_ROW_ODD      = TABLE_STRIPE

# ─── Font Registration ────────────────────────────────────────────
FONT_DIR = '/usr/share/fonts'
pdfmetrics.registerFont(TTFont('NotoSerifSC',      os.path.join(FONT_DIR, 'truetype/noto-serif-sc/NotoSerifSC-Regular.ttf')))
pdfmetrics.registerFont(TTFont('NotoSerifSC-Bold', os.path.join(FONT_DIR, 'truetype/noto-serif-sc/NotoSerifSC-Bold.ttf')))
# NotoSansSC is a variable font ([wght].ttf) - skip; NotoSerifSC handles CJK fallback
pdfmetrics.registerFont(TTFont('FreeSerif',        os.path.join(FONT_DIR, 'truetype/freefont/FreeSerif.ttf')))
pdfmetrics.registerFont(TTFont('FreeSerif-Bold',   os.path.join(FONT_DIR, 'truetype/freefont/FreeSerifBold.ttf')))
pdfmetrics.registerFont(TTFont('FreeSerif-Italic', os.path.join(FONT_DIR, 'truetype/freefont/FreeSerifItalic.ttf')))
pdfmetrics.registerFont(TTFont('FreeSans',         os.path.join(FONT_DIR, 'truetype/freefont/FreeSans.ttf')))
pdfmetrics.registerFont(TTFont('FreeSans-Bold',    os.path.join(FONT_DIR, 'truetype/freefont/FreeSansBold.ttf')))
pdfmetrics.registerFont(TTFont('DejaVuSansMono',   os.path.join(FONT_DIR, 'truetype/dejavu/DejaVuSansMono.ttf')))

registerFontFamily('FreeSerif', normal='FreeSerif', bold='FreeSerif-Bold', italic='FreeSerif-Italic', boldItalic='FreeSerif-Bold')
registerFontFamily('FreeSans',  normal='FreeSans',  bold='FreeSans-Bold')
registerFontFamily('NotoSerifSC', normal='NotoSerifSC', bold='NotoSerifSC-Bold')

# Install font fallback for mixed TR/Latin text
install_font_fallback()

# ─── Page Geometry ────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
LEFT_M = 22 * mm
RIGHT_M = 22 * mm
TOP_M = 22 * mm
BOTTOM_M = 22 * mm
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M  # ~ 451pt

# ─── Styles ───────────────────────────────────────────────────────
S_H1 = ParagraphStyle('H1', fontName='FreeSans-Bold', fontSize=22, leading=28, textColor=TEXT_PRIMARY, spaceBefore=4, spaceAfter=14, alignment=TA_LEFT)
S_H1_NUM = ParagraphStyle('H1Num', fontName='FreeSans-Bold', fontSize=11, leading=14, textColor=ACCENT, spaceBefore=0, spaceAfter=4, alignment=TA_LEFT)
S_H2 = ParagraphStyle('H2', fontName='FreeSans-Bold', fontSize=15, leading=20, textColor=COVER_BLOCK, spaceBefore=18, spaceAfter=8, alignment=TA_LEFT)
S_H3 = ParagraphStyle('H3', fontName='FreeSans-Bold', fontSize=12, leading=16, textColor=TEXT_PRIMARY, spaceBefore=12, spaceAfter=6, alignment=TA_LEFT)
S_BODY = ParagraphStyle('Body', fontName='FreeSerif', fontSize=10.5, leading=16.5, textColor=TEXT_PRIMARY, spaceBefore=0, spaceAfter=8, alignment=TA_JUSTIFY, firstLineIndent=0)
S_BODY_NOINDENT = ParagraphStyle('BodyNI', parent=S_BODY, alignment=TA_LEFT)
S_BULLET = ParagraphStyle('Bullet', fontName='FreeSerif', fontSize=10.5, leading=16, textColor=TEXT_PRIMARY, spaceBefore=0, spaceAfter=4, alignment=TA_LEFT, leftIndent=18, bulletIndent=6)
S_QUOTE = ParagraphStyle('Quote', fontName='FreeSerif-Italic', fontSize=10.5, leading=16, textColor=COVER_BLOCK, spaceBefore=8, spaceAfter=8, alignment=TA_LEFT, leftIndent=22, rightIndent=12, borderColor=ACCENT, borderWidth=0, borderPadding=0)
S_CODE = ParagraphStyle('Code', fontName='DejaVuSansMono', fontSize=8.5, leading=12, textColor=TEXT_PRIMARY, spaceBefore=4, spaceAfter=8, alignment=TA_LEFT, leftIndent=10, rightIndent=10, backColor=CARD_BG, borderPadding=8)
S_CAPTION = ParagraphStyle('Caption', fontName='FreeSans', fontSize=9, leading=12, textColor=TEXT_MUTED, spaceBefore=4, spaceAfter=14, alignment=TA_CENTER)
S_TABLE_HEADER = ParagraphStyle('TH', fontName='FreeSans-Bold', fontSize=9.5, leading=12, textColor=colors.white, alignment=TA_LEFT)
S_TABLE_HEADER_C = ParagraphStyle('THC', parent=S_TABLE_HEADER, alignment=TA_CENTER)
S_TABLE_CELL = ParagraphStyle('TC', fontName='FreeSerif', fontSize=9, leading=12.5, textColor=TEXT_PRIMARY, alignment=TA_LEFT)
S_TABLE_CELL_C = ParagraphStyle('TCC', parent=S_TABLE_CELL, alignment=TA_CENTER)
S_TABLE_CELL_MONO = ParagraphStyle('TCM', fontName='DejaVuSansMono', fontSize=8, leading=11, textColor=TEXT_PRIMARY, alignment=TA_LEFT)
S_TABLE_CELL_SMALL = ParagraphStyle('TCS', fontName='FreeSerif', fontSize=8.5, leading=11.5, textColor=TEXT_PRIMARY, alignment=TA_LEFT)
S_TOC1 = ParagraphStyle('TOC1', fontName='FreeSans-Bold', fontSize=11, leading=18, textColor=TEXT_PRIMARY, leftIndent=0, spaceBefore=4, spaceAfter=2)
S_TOC2 = ParagraphStyle('TOC2', fontName='FreeSerif', fontSize=10, leading=15, textColor=COVER_BLOCK, leftIndent=18, spaceBefore=1, spaceAfter=1)
S_EXEC_SUMMARY = ParagraphStyle('Exec', fontName='FreeSerif', fontSize=10.5, leading=17, textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=10)
S_KICKER = ParagraphStyle('Kicker', fontName='FreeSans-Bold', fontSize=8.5, leading=11, textColor=ACCENT, alignment=TA_LEFT, spaceAfter=2)

# ─── TocDocTemplate ───────────────────────────────────────────────
class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, 'bookmark_name'):
            level = getattr(flowable, 'bookmark_level', 0)
            text = getattr(flowable, 'bookmark_text', '')
            key = getattr(flowable, 'bookmark_key', '')
            self.notify('TOCEntry', (level, text, self.page, key))


def H1(text, story, chapter_num=None):
    """Add H1 with bookmark."""
    key = f'h1_{hashlib.md5(text.encode()).hexdigest()[:8]}'
    if chapter_num:
        story.append(Paragraph(f'BÖLÜM {chapter_num}', S_H1_NUM))
    p = Paragraph(f'<a name="{key}"/>{text}', S_H1)
    p.bookmark_name = key
    p.bookmark_level = 0
    p.bookmark_text = text
    p.bookmark_key = key
    story.append(p)
    story.append(HRFlowable(width=70, thickness=2, color=ACCENT, spaceBefore=2, spaceAfter=10, hAlign='LEFT'))


def H2(text, story):
    key = f'h2_{hashlib.md5(text.encode()).hexdigest()[:8]}'
    p = Paragraph(f'<a name="{key}"/>{text}', S_H2)
    p.bookmark_name = key
    p.bookmark_level = 1
    p.bookmark_text = text
    p.bookmark_key = key
    story.append(p)


def H3(text, story):
    story.append(Paragraph(text, S_H3))


def P(text, story=None, style=None):
    if style is None:
        style = S_BODY
    p = Paragraph(text, style)
    if story is not None:
        story.append(p)
    return p


def Bul(items, story, style=None):
    if style is None:
        style = S_BULLET
    for item in items:
        story.append(Paragraph(f'• {item}', style))


def Code(text, story):
    """Add a code block."""
    # ReportLab Paragraph doesn't preserve newlines natively, use <br/>
    safe = text.replace('\n', '<br/>').replace(' ', '&nbsp;')
    story.append(Paragraph(safe, S_CODE))


def TableStyled(data, col_widths, story, repeat_rows=1, caption=None, row_styles=None):
    """Add a styled table with caption."""
    t = Table(data, colWidths=col_widths, hAlign='CENTER', repeatRows=repeat_rows)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'FreeSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
    ]
    # Alternating row colors
    for i in range(1, len(data)):
        bg = TABLE_ROW_ODD if (i % 2 == 1) else TABLE_ROW_EVEN
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    if row_styles:
        style_cmds.extend(row_styles)
    t.setStyle(TableStyle(style_cmds))
    story.append(Spacer(1, 6))
    story.append(t)
    if caption:
        story.append(Spacer(1, 4))
        story.append(Paragraph(caption, S_CAPTION))
    else:
        story.append(Spacer(1, 14))


# ─── Header/Footer ────────────────────────────────────────────────
def header_footer(canvas, doc):
    canvas.saveState()
    # Top thin rule
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_M, PAGE_H - 14 * mm, PAGE_W - RIGHT_M, PAGE_H - 14 * mm)
    # Top-left title
    canvas.setFont('FreeSans-Bold', 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(LEFT_M, PAGE_H - 11 * mm, 'BETTERSaul  ·  Web Platform Migration Report')
    # Top-right section indicator
    canvas.drawRightString(PAGE_W - RIGHT_M, PAGE_H - 11 * mm, 'Phase 1 · Technical Analysis')
    # Bottom thin rule
    canvas.line(LEFT_M, 14 * mm, PAGE_W - RIGHT_M, 14 * mm)
    # Page number bottom-right
    canvas.setFont('DejaVuSansMono', 8)
    canvas.setFillColor(TEXT_MUTED)
    page_str = f'{doc.page}'
    canvas.drawRightString(PAGE_W - RIGHT_M, 10 * mm, page_str)
    # Bottom-left brand
    canvas.setFont('FreeSans', 8)
    canvas.drawString(LEFT_M, 10 * mm, 'Z.ai · Legal Intelligence Platform · 2026')
    canvas.restoreState()


# ─── Build Story ──────────────────────────────────────────────────
def build_story():
    story = []

    # ════════════════════════════════════════════════════════════
    # PAGE 1 — TABLE OF CONTENTS (cover is merged separately)
    # ════════════════════════════════════════════════════════════
    story.append(Paragraph('İçindekiler', S_H1))
    story.append(HRFlowable(width=70, thickness=2, color=ACCENT, spaceBefore=2, spaceAfter=14, hAlign='LEFT'))

    toc = TableOfContents()
    toc.levelStyles = [S_TOC1, S_TOC2]
    story.append(toc)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # YÖNETİCİ ÖZETİ
    # ════════════════════════════════════════════════════════════
    H1('Yönetici Özeti', story)
    P("""BetterSaul projesi, Türkiye hukuk kaynakları üzerinde çalışan yerel (desktop) bir AI destekli hukuk araştırma ve dilekçe üretim platformudur. Mevcut sistem; <b>15.318 satır Python kodu</b>, 7.857 satırlık tek bir <i>engine.py</i> dosyası, 21 MCP aracı, 6 farklı hukuk portalı entegrasyonu (Yargıtay, Danıştay, Emsal, AYM, Resmî Gazete, mevzuat.gov.tr), tamamen yerel Qwen 2.5/3 modelleri ve Edge WebView2 tabanlı bir masaüstü arayüzünden oluşmaktadır.""", story)

    P("""Bu rapor, mevcut mimarinin derinlemesine analizini yapmakta ve Next.js + TypeScript + PostgreSQL + pgvector tabanlı modern, ölçeklenebilir bir web platformuna dönüşüm planını sunmaktadır. Analiz sonucunda tespit edilen <b>kritik bulgular</b>: (1) Mevcut sistemde <b>semantic search tamamen yok</b> — embedding, vektör veritabanı, BM25, reranking veya query expansion mekanizmalarının hiçbiri mevcut değil; arama tamamen Yargıtay/Danıştay gibi uzak portallara HTTP POST delege edilmiştir. (2) AI inference tamamen yerel Qwen modellerine bağlıdır — hiçbir sağlayıcı çeşitliliği (OpenAI, Gemini, Anthropic) yoktur. (3) archive.db SQLite veritabanı yalnızca 2 tablodan oluşmakta, çok-kullanıcılı mimari, audit log, soft-delete veya versiyonlama desteklenmemektedir. (4) engine.py'nin 7.857 satırlık tek dosya yapısı bakım ve test açısından yüksek risk taşımaktadır.""", story)

    P("""Buna karşılık, mevcut sistem <b>korunması gereken değerli varlıklara</b> da sahiptir: 17 boyutta puanlama yapan deterministik kalite kontrol motoru (regex-tabanlı, LLM-as-judge bağımlılığı yok), halüsinasyon kontrolü (TCKN/tanık/tutar uydurma tespiti), 10 dava türü otomatik tespiti, 12 dilekçe şablonu, prompt sızıntısı tespiti ve içtihat doğrulama. Bu bileşenlerin tamamı saf Python olup, doğrudan FastAPI endpoint'lerine sarılarak web platformunda yeniden kullanılabilir.""", story)

    P("""Önerilen migration planı <b>19 faz</b>dan oluşmaktadır ve toplam 5-7 ay sürmesi öngörülmektedir. İlk 3 faz (Kod Analizi, DB Şema, Python Engine Servisleştirme) tamamlanmıştır veya bu raporla başlatılmıştır. Kritik dönüşüm alanları: (a) PostgreSQL + pgvector ile gerçek <b>hybrid search</b> (semantic + keyword + reranking), (b) AI <b>provider abstraction</b> katmanı, (c) <b>multi-tenant</b> auth ve RBAC, (d) <b>versiyonlu mevzuat</b> ve dilekçe sürüm geçmişi, (e) <b>research trace</b> ile AI şeffaflığı, (f) <b>document upload</b> ile kullanıcının kendi belgeleri üzerinde semantic search.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 1 — MEVCUT MİMARİ
    # ════════════════════════════════════════════════════════════
    H1('Mevcut Mimari', story, chapter_num=1)

    P("""BetterSaul, Windows platformuna özel olarak geliştirilmiş, üç katmanlı bir masaüstü uygulamasıdır. Üst katmanda .NET (C#) ile yazılmış bir WinForms ana uygulama ve gömülü Microsoft Edge WebView2 bulunur. Orta katmanda, kullanıcıdan bağımsız bir süreç olarak çalışan Python 3.12 engine yer alır. Alt katmanda ise SQLite tabanlı yerel arşiv ve 6 hukuk portalına yapılan HTTP çağrıları bulunur. Tüm bu katmanlar, <b>stdin/stdout JSON-line IPC</b> ile birbirleriyle haberleşir — HTTP/socket kullanılmaz.""", story)

    H2('1.1 IPC Mimarisi (stdin/stdout JSON-line)', story)
    P("""engine.py'nin <b>main()</b> fonksiyonu (satır 7816) bir stdin döngüsüdür. WinForms uygulamasından gelen her satır JSON komut olarak parse edilir, dispatch edilir ve sonuç <b>emit()</b> fonksiyonu (satır 87-90) ile tekrar JSON olarak stdout'a yazılır. Bu mimari, bir Unix pipe'ına benzer şekilde çalışır:""", story)

    Code("""# engine.py satır 87-90
def emit(event: str, text: str = "") -> None:
    with _emit_lock:
        sys.stdout.write(json.dumps({"event": event, "text": text}, ensure_ascii=False) + "\\n")
        sys.stdout.flush()""", story)

    P("""WinForms tarafı bu stdout satırlarını okur, JSON parse eder ve WebView2'ye <i>postMessage</i> ile iletir. <b>app.js</b> (73KB, 1790 satır IIFE) bu mesajları dinler ve DOM günceller. Bu mimarinin web'e taşınması için IPC katmanının tamamen kaldırılıp REST/SSE/WebSocket ile değiştirilmesi gerekir.""", story)

    H2('1.2 Dizin Yapısı', story)
    TableStyled(
        [
            [Paragraph('<b>Dizin</b>', S_TABLE_HEADER), Paragraph('<b>İçerik</b>', S_TABLE_HEADER), Paragraph('<b>Boyut / Satır</b>', S_TABLE_HEADER_C)],
            [Paragraph('<font face="DejaVuSansMono">app/engine/</font>', S_TABLE_CELL_MONO), Paragraph('Ana Python motoru (engine.py + prompts + legal_tracks + petition_packs)', S_TABLE_CELL), Paragraph('8.664 satır', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">app/engine/bettersaul_mcp/</font>', S_TABLE_CELL_MONO), Paragraph('MCP paketi: server, sources, anayasa, mevzuat, petition_tools, quality, templates, motor/', S_TABLE_CELL), Paragraph('5.131 satır', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">app/ui/</font>', S_TABLE_CELL_MONO), Paragraph('Vanilla JS SPA: index.html + app.js + app.css + net.js', S_TABLE_CELL), Paragraph('~110KB / 1790 satır JS', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">archive.db</font>', S_TABLE_CELL_MONO), Paragraph('SQLite: 2 tablo (chats, petitions)', S_TABLE_CELL), Paragraph('24KB · 0 satır veri', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">runtime/python/</font>', S_TABLE_CELL_MONO), Paragraph('Bundled Python 3.12 Windows AMD64 + uvicorn + mcp SDK', S_TABLE_CELL), Paragraph('~150MB', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">webview/EBWebView/</font>', S_TABLE_CELL_MONO), Paragraph('Edge WebView2 user data dizini (cache, cookies, GPU)', S_TABLE_CELL), Paragraph('~80MB', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">certs/</font>', S_TABLE_CELL_MONO), Paragraph('Self-signed TLS: mcp-cert.pem, mcp-key.pem', S_TABLE_CELL), Paragraph('CN=BetterSaul MCP', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">connect/</font>', S_TABLE_CELL_MONO), Paragraph('5 AI ajan MCP config: Claude, ChatGPT, Cursor, Gemini (JSON+TOML)', S_TABLE_CELL), Paragraph('5 dosya', S_TABLE_CELL_C)],
            [Paragraph('<font face="DejaVuSansMono">logs/mcp.log</font>', S_TABLE_CELL_MONO), Paragraph('MCP server runtime log', S_TABLE_CELL), Paragraph('852 byte · 28 satır', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.28, CONTENT_W * 0.52, CONTENT_W * 0.20],
        story=story,
        caption='Tablo 1.1 — BetterSaul proje dizin yapısı'
    )

    H2('1.3 Mimari Diyagram (Mevcut)', story)
    P("""Aşağıdaki diyagram, mevcut BetterSaul mimarisinin 7 katmanını özetlemektedir: UI katmanı (WebView2), Python engine, MCP paketi, kalite kontrol motoru, AI inference, veri ve arama katmanı, desktop runtime bağımlılıkları. Kırmızı ile işaretli katmanlar web'e taşırken kritik risk taşıyan bölümleri gösterir.""", story)

    img_current = Image('/home/z/my-project/scripts/diagrams/current_arch.png', width=CONTENT_W, height=CONTENT_W * (2448/2100))
    story.append(img_current)
    story.append(Paragraph('Şekil 1.1 — Mevcut BetterSaul mimari diyagramı', S_CAPTION))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 2 — MEVCUT ÖZELLİKLER
    # ════════════════════════════════════════════════════════════
    H1('Mevcut Özellikler', story, chapter_num=2)

    P("""BetterSaul'ün mevcut sürümü, hukuk araştırması ve dilekçe üretimi için geniş bir özellik seti sunar. Aşağıda her özellik grubu, dosya:satır referanslarıyla birlikte listelenmiştir. Bu özelliklerin korunması ve web platformunda yeniden sunulması, migration'ın temel hedefidir.""", story)

    H2('2.1 Dava Türü Tespiti (10 tür)', story)
    P("""<b>legal_tracks.py</b> (satır 34, <i>detect_track()</i>) regex tabanlı bir dava türü sınıflandırıcıdır. 10 dava alanı tanır: iş, boşanma, kira, tüketici, alacak, tazminat, icra, idare, vergi, tapu/miras. Her track için <b>PROMPT_RULES</b> (satır 405-420) usul kurallarını barındırır; örneğin işçilikte 7036 m.3/5, 4857 m.32/34/41/17/18/20/21, 1475 m.14 ve HMK m.107 atıfları modele gömülür. Bu kurallar, dilekçe üretimi sırasında AI'ya hangi mevzuatı kullanması gerektiğini söyleyen bir usul rehberi görevi görür.""", story)

    H2('2.2 Dilekçe Üretimi (12 tür)', story)
    P("""<b>templates.py</b> (satır 8-197, <i>KINDS</i> sözlüğü) 12 dava türü için şablon tanımlar: idare, boşanma, iş, icra, tüketici, kira, tazminat, ceza, alacak, diğer, tapu, miras. Her tür; mahkeme başlığı, iptal flag'i (yalnızca idare), sections (koşullu bloklar), anayasa maddeleri ve ilgili kanun maddelerini içerir. <b>petition_packs.py</b> (197 satır) ise 10 dava türü için statik hazır şablonlar sunar — bu, AI'nin sıfırdan yazmasını gerektirmeyen, doldurulan form'a göre özelleştirilen hazır metinlerdir.""", story)

    P("""Dilekçe üretim akışı 4 aşamalıdır: <b>_pipe_extract</b> (satır 7658) → <b>_pipe_generate</b> (satır 7681) → <b>_pipe_check</b> (satır 7711) → <b>_pipe_repair</b> (satır 7743). İlk aşamada kullanıcı formundan yapılandırılmış kart çıkarılır, ikinci aşamada LLM dilekçe metni üretir, üçüncü aşamada 17-boyut kalite kontrol çalışır, dördüncü aşamada ise skoru düşükse LLM'den düzeltme istenir.""", story)

    H2('2.3 Kalite Kontrol (17 boyut)', story)
    P("""<b>quality.py</b> (1.049 satır) + <b>motor/pipeline.py</b> (807 satır) birlikte 17 boyutta puanlama yapan bir kalite kontrol sistemi oluşturur. Boyutlar: taraf tutarlılığı, tutar çelişkileri, mevzuat grafiği, talep-KONU-SONUÇ üçlüsü, dayanak-talep uyumu, iddia-delil eşleşmesi, kronoloji, yetki/görev, usul ön şartları, çelişkiler, halüsinasyon, içtihat doğrulama, içtihat-kalem uyumu, vakıa-hukuk-delil-talep zinciri, KVKK/kişisel veri, prompt sızıntısı, zorunlu alan eksikleri. Genel puan 0-100 arası, KRİTİK bulgu varsa ≤79.""", story)

    H2('2.4 Halüsinasyon Kontrolü', story)
    P("""Halüsinasyon kontrolü tamamen <b>kaynak-karşılaştırma</b> yöntemiyle yapılır — LLM-as-judge kullanılmaz. İki yerde uygulanır: <b>_invent_findings</b> (quality.py satır 744-787) ve <b>_hallucination</b> (pipeline.py satır 487-509). TCKN (11 haneli) regex ile yakalanır, form'da olup olmadığı kontrol edilir; tanık adları regex ile çıkarılır, fold edilmiş form içeriğinde aranır; ISO tarihler yakalanır; <b>PROMPT_LEAK</b> tablosu (catalog.py satır 421-426: "prompt", "AI", "wikipedia", "Vekile Not", "[DOĞRULANACAK", "Yargı MCP" vb.) ile sistem mesajı sızıntısı tespit edilir.""", story)

    H2('2.5 İçtihat Doğrulama', story)
    P("""<b>_cite_findings</b> (quality.py satır 790) dışarıdan verilen <i>memory</i> sözlüğündeki <b>cites</b> ve <b>aym</b> listeleriyle dilekçe metnindeki tüm <i>E.\\s*\\d{4}/\\d+,?\\s*K\\.\\s*\\d{4}/\\d+</i> veya <i>B.\\s*No\\s*[:：]?\\s*\\d{4}/\\d+</i> numaralarını karşılaştırır. Memory'de kayıtlı olmayan numara → YÜKSEK "doğrulanmamış içtihat" uyarısı. Bu mekanizma, AI'nin uydurma karar numarası üretmesini engeller. <b>Ancak</b> bu mekanizma <b>semantic içtihat araması yapmaz</b> — yalnızca bire-bir esas-no eşleşmesi yapar.""", story)

    H2('2.6 Hukuk Kaynağı Araştırması (6 kaynak)', story)
    TableStyled(
        [
            [Paragraph('<b>Kaynak</b>', S_TABLE_HEADER), Paragraph('<b>URL / Endpoint</b>', S_TABLE_HEADER), Paragraph('<b>Erişim</b>', S_TABLE_HEADER_C), Paragraph('<b>Dosya</b>', S_TABLE_HEADER_C)],
            [Paragraph('Yargıtay', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">karararama.yargitay.gov.tr</font>', S_TABLE_CELL_MONO), Paragraph('HTTP POST + HTML scrape', S_TABLE_CELL_C), Paragraph('sources.py satır 600', S_TABLE_CELL_C)],
            [Paragraph('Danıştay', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">danistaydergiler.adalet.gov.tr</font>', S_TABLE_CELL_MONO), Paragraph('HTTP POST + HTML scrape', S_TABLE_CELL_C), Paragraph('sources.py', S_TABLE_CELL_C)],
            [Paragraph('Emsal (UYAP)', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">emsal.uyap.gov.tr</font>', S_TABLE_CELL_MONO), Paragraph('HTTP POST + HTML scrape', S_TABLE_CELL_C), Paragraph('sources.py satır 691', S_TABLE_CELL_C)],
            [Paragraph('Anayasa Mahkemesi', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">anayasa.gov.tr/api/core/public/search</font>', S_TABLE_CELL_MONO), Paragraph('JSON API', S_TABLE_CELL_C), Paragraph('anayasa.py satır 147', S_TABLE_CELL_C)],
            [Paragraph('Resmî Gazete', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">resmigazete.gov.tr</font>', S_TABLE_CELL_MONO), Paragraph('HTTP scrape', S_TABLE_CELL_C), Paragraph('sources.py satır 828', S_TABLE_CELL_C)],
            [Paragraph('Mevzuat', S_TABLE_CELL), Paragraph('<font face="DejaVuSansMono">mevzuat.gov.tr</font>', S_TABLE_CELL_MONO), Paragraph('HTTP scrape (11 hardcoded kanun)', S_TABLE_CELL_C), Paragraph('mevzuat.py', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.18, CONTENT_W * 0.35, CONTENT_W * 0.27, CONTENT_W * 0.20],
        story=story,
        caption='Tablo 2.1 — BetterSaul tarafından desteklenen hukuk kaynakları'
    )

    H2('2.7 PDF Üretimi (browser subprocess)', story)
    P("""<b>petition_tools.py</b> satır 1046-1096 (<i>_print_pdf</i>) PDF üretimi için sistemdeki Edge veya Chrome browser'ı <i>--headless</i> modda subprocess olarak çağırır. Bu yöntem web ortamında çalışamaz — bunun yerine WeasyPrint veya Playwright + page.pdf() kullanılmalıdır. <b>DOCX çıktısı yoktur</b>; HTML ve plain text çıktısı mevcuttur.""", story)

    H2('2.8 AI Ajan Entegrasyonları (4 ajan)', story)
    P("""<b>connect/</b> klasörü 5 farklı AI ajan için MCP config dosyası içerir: Claude Desktop, ChatGPT Desktop (JSON + TOML), Cursor, Gemini. Hepsi aynı <i>run_mcp.py --stdio</i> script'ine işaret eder. HTTP endpoint olarak <i>https://127.0.0.1:8000/mcp</i> (self-signed TLS) kullanılır. <b>chatgpt.toml</b> dosyasında <i>default_tools_approval_mode = "auto"</i> ayarı vardır — yani ChatGPT kullanıcı onayı olmadan MCP araçlarını çağırabilir. Bu, web platformunda güvenlik açısından dikkatle ele alınmalıdır.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 3 — SEMANTIC SEARCH DURUMU
    # ════════════════════════════════════════════════════════════
    H1('Semantic Search Durumu', story, chapter_num=3)

    P("""Bu bölüm raporun <b>en kritik</b> bölümüdür. Kullanıcının beklentileri ve modern hukuk araştırma platformlarının gereksinimleri doğrultusunda, mevcut BetterSaul sisteminde semantic search altyapısının <b>hiç olmadığı</b> tespit edilmiştir. Aşağıdaki tablo, modern bir hukuk araştırma platformunda bulunması beklenen tüm arama bileşenlerini ve BetterSaul'deki durumlarını listeler.""", story)

    H2('3.1 Modern Arama Bileşenleri — Mevcut Durum', story)
    TableStyled(
        [
            [Paragraph('<b>Bileşen</b>', S_TABLE_HEADER), Paragraph('<b>BetterSaul Durumu</b>', S_TABLE_HEADER_C), Paragraph('<b>Açıklama</b>', S_TABLE_HEADER)],
            [Paragraph('Keyword Search (yerel)', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Yerel FTS5/Whoosh yok; phrase uzak portala delege edilir', S_TABLE_CELL_SMALL)],
            [Paragraph('Semantic Search', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Hiçbir vektör/semantic eşleştirme yok', S_TABLE_CELL_SMALL)],
            [Paragraph('Embedding', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('OpenAI/Cohere/BGE/e5/mxbai çağrısı yok', S_TABLE_CELL_SMALL)],
            [Paragraph('Vector Database', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('pgvector/Chroma/Faiss/Pinecone/Weaviate/Qdrant yok', S_TABLE_CELL_SMALL)],
            [Paragraph('BM25', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('rank_bm25/bm25_okapi yok, TF-IDF hesabı yok', S_TABLE_CELL_SMALL)],
            [Paragraph('Reranking', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Cross-encoder/LLM-rerank/Cohere-rerank yok', S_TABLE_CELL_SMALL)],
            [Paragraph('Metadata Filtering (yerel)', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Yerel post-filter yok; court_types uzak portal filtresi', S_TABLE_CELL_SMALL)],
            [Paragraph('Query Expansion', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Ne LLM-rewrite ne thesaurus; sadece stop-word temizliği', S_TABLE_CELL_SMALL)],
            [Paragraph('Hybrid Search', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Sparse+dense birleştirme yok', S_TABLE_CELL_SMALL)],
            [Paragraph('Belge Chunking', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Kararlar/metinler chunklanmıyor', S_TABLE_CELL_SMALL)],
            [Paragraph('Caching', S_TABLE_CELL), Paragraph('<font color="#8e4f49"><b>YOK</b></font>', S_TABLE_CELL_C), Paragraph('Her seferinde uzak portal çağrılır', S_TABLE_CELL_SMALL)],
        ],
        col_widths=[CONTENT_W * 0.28, CONTENT_W * 0.16, CONTENT_W * 0.56],
        story=story,
        caption='Tablo 3.1 — Modern arama bileşenleri ve BetterSaul durumu',
        row_styles=[
            ('TEXTCOLOR', (1, 1), (1, -1), SEM_ERROR),
            ('FONTNAME', (1, 1), (1, -1), 'FreeSans-Bold'),
        ]
    )

    H2('3.2 Mevcut Arama Stratejisi: Uzak Portala Delege', story)
    P("""BetterSaul'de yerel bir arama motoru yoktur. <b>sources.py::search_corpus()</b> (satır 600) kullanıcıdan gelen phrase'i doğrudan Yargıtay portalına POST'lar; cevap JSON/HTML olarak parse edilir ve sonuçlar olduğu sırayla döndürülür. <b>search_corpus_deep()</b> (satır 619) sayfa sayfa dolaşarak daha fazla sonuç toplar; <b>search_bedesten()</b> (satır 661) Bedesten (Yargıtay+Danıştay+Emsal) pazarlama adıyla aynı işi yapar. <b>anayasa.py::_search_api()</b> (satır 147) AYM'nin resmi JSON API'sine POST yapar.""", story)

    P("""Bu yaklaşımın <b>4 kritik dezavantajı</b> vardır: (1) <b>Portal bağımlılığı</b> — Yargıtay/Danıştay siteleri erişime kapanırsa veya yapı değişirse sistem çalışmaz. (2) <b>Hız</b> — her sorgu 3-15 saniye sürer (ağ + parse + rate-limit cooldown). (3) <b>Esneklik yok</b> — "güvenlik soruşturması nedeniyle atanamama" sorgusu yalnızca aynı kelimeleri içeren kararları getirir; "arşiv araştırması", "memuriyet", "ölçülülük" gibi anlamsal bağlantılı kavramlar bulunamaz. (4) <b>Sıralama opak</b> — uzak portalın kendi sıralaması kullanılır, yerel rerank yok.""", story)

    H2('3.3 Memory Mekanizması (Yerel Cache)', story)
    P("""Sistemde yerel bir cache mekanizması olarak <b>case_memory.json</b> dosyası kullanılır (<i>quality._load_memory</i> satır 926). Bu dosya macOS'ta <i>~/Library/Application Support/BetterSaul/</i>, Windows'ta <i>%LOCALAPPDATA%/BetterSaul/</i> altında saklanır. Memory, daha önceki oturumda çekilmiş içtihat künyelerini ve AYM karar numaralarını tutar. <b>quality.review</b> fonksiyonu bu memory'yi alır ve dilekçedeki tüm atıfları memory'deki listede arar. Bu bir cache'dir, semantic bir index değildir.""", story)

    H2('3.4 Web Platformu İçin Gereken Yeni Arama Katmanı', story)
    P("""Mevcut sisteme semantic search eklemek, sıfırdan yeni bir katman yazmayı gerektirir. Önerilen pipeline: <b>Document</b> → cleaning → normalization → chunking (ör. 512 token, 50 overlap) → metadata extraction (court, chamber, decision_no, date, type, source) → embedding (multilingual-e5-large 1024d veya OpenAI text-embedding-3-large 1536d) → PostgreSQL + pgvector (HNSW index). Sorgu zamanı: <b>kullanıcı sorgusu</b> → query expansion (LLM ile sinonim/kavram genişletme) → parallel (a) semantic search pgvector'dan, (b) keyword search PostgreSQL FTS'den, (c) metadata filter → sonuçları birleştir → cross-encoder rerank (top-50 → top-10) → kullanıcıya döndür.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 4 — AI SİSTEMİ DURUMU
    # ════════════════════════════════════════════════════════════
    H1('AI Sistemi Durumu', story, chapter_num=4)

    P("""BetterSaul'ün AI katmanı tamamen <b>yerel (local) inference</b>'a dayanır. Bulut AI sağlayıcıları (OpenAI, Google Gemini, Anthropic) hiç kullanılmaz. Bu tasarım kararı, gizlilik ve veri主权 açısından güçlü olmakla birlikte, donanım bağımlılığı ve ölçeklenebilirlik açısından zayıftır. Web platformuna taşırken <b>provider abstraction</b> katmanı eklenmesi kritik bir gereksinimdir.""", story)

    H2('4.1 Kullanılan Modeller', story)
    P("""Sistem <b>Qwen 2.5</b> serisinden 7B, 9B ve 14B parametreli modeller ile <b>Qwen 3</b> serisinden 14B ve 27B parametreli modelleri destekler. Model seçimi <i>runtime/config</i>'ten yapılır. Bu modeller Türkçe için optimize edilmiş olup, hukuk alanında makul performans gösterir. Ancak GPT-4o veya Claude 3.5 Sonnet gibi frontier modellere kıyasla karmaşık akıl yürütme ve uzun bağlam görevlerinde geridedirler.""", story)

    H2('4.2 Üç Inference Yolu', story)
    P("""engine.py üç farklı yoldan LLM çağrısı yapabilir. Bu, donanım ve işletim sistemi uyumluluğu için bir yedekleme mekanizması sağlar:""", story)

    TableStyled(
        [
            [Paragraph('<b>Yöntem</b>', S_TABLE_HEADER), Paragraph('<b>Mekanizma</b>', S_TABLE_HEADER), Paragraph('<b>Konum</b>', S_TABLE_HEADER_C)],
            [Paragraph('llama-server HTTP', S_TABLE_CELL), Paragraph('C++ binary ayrı process, HTTP API (OpenAI uyumlu)', S_TABLE_CELL), Paragraph('engine.py satır 2641', S_TABLE_CELL_C)],
            [Paragraph('llama-cpp-python', S_TABLE_CELL), Paragraph('Python binding, doğrudan process içinde GGUF yükle', S_TABLE_CELL), Paragraph('engine.py satır 2222', S_TABLE_CELL_C)],
            [Paragraph('llama-cli subprocess', S_TABLE_CELL), Paragraph('CLI çağrısı, stdin/stdout pipe', S_TABLE_CELL), Paragraph('engine.py satır 2822', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.25, CONTENT_W * 0.50, CONTENT_W * 0.25],
        story=story,
        caption='Tablo 4.1 — Üç inference yolu'
    )

    H2('4.3 Agentic Multi-Turn (MAX_TURNS=8)', story)
    P("""engine.py <b>agentic multi-turn</b> bir mimari kullanır. <i>MAX_TURNS=8</i> sabiti (engine.py başı) bir kullanıcı sorgusunda AI'nin en fazla 8 tur araç çağırabileceğini belirtir. <i>RESEARCH_ROUNDS=3</i> ise araştırma turlarının sayısıdır — her turda AI sırayla içtihat, mevzuat, AYM ve Resmî Gazete kaynaklarını tarar. Tool dispatch mekanizması <b>TOOL_RE</b> regex'i ile yapılır (satır 2219): AI'nin cevabındaki <i>{"tool": "search_corpus", "args": {...}}</i> gibi JSON blokları regex ile yakalanır ve ilgili fonksiyon çağrılır.""", story)

    H2('4.4 Prompt Sistemi', story)
    P("""Prompt sistemi 4 bileşenden runtime'da birleştirilir: (1) <b>system_prompt.txt</b> (22 satır) — temel sistem rolü; (2) <b>petition_prompt.txt</b> (112 satır, A-M bölümlü) — dilekçe yazma disiplini; (3) <b>turkish_reason.txt</b> (13 satır) — Türkçe akıl yürütme kuralları; (4) <b>FILL_ANATOMY</b> — runtime'da form verisinden oluşturulan dava bilgileri. Bu birleştirme engine.py içinde yapılır ve LLM'e tek bir system mesajı olarak gönderilir.""", story)

    H2('4.5 AI Karar Verme Noktaları', story)
    Bul([
        '<b>Dava türü tespiti</b>: <i>legal_tracks.detect_track()</i> regex ile (satır 34) — AI bağımsız değil',
        "<b>Araştırma sorgusu üretimi</b>: LLM, kullanıcı olayından 3-5 arama phrase'i üretir",
        '<b>Kaynak seçimi</b>: <i>legal_tracks.PROMPT_RULES</i> (satır 405-420) regex-tabanlı zorunlu atıflar',
        '<b>Araştırma turları</b>: AI sırayla içtihat (3 tur) → mevzuat → AYM (idare türünde 1) → Resmî Gazete',
        '<b>Sonuç filtreleme</b>: <i>_is_portal_junk()</i> (satır 1182) ile portal junk sonuçları elenir',
        '<b>Citation gerçeklik</b>: <i>_cite_from_mapping()</i> (satır 1053) ile yalnızca gerçek künyeler kullanılır',
        '<b>Dilekçe üretimi</b>: 4 aşamalı pipeline (extract → generate → check → repair)',
        '<b>Kalite onayı</b>: 17-boyut puanlama, 80 puan altı repair tetikler',
    ], story)

    H2('4.6 Web Platformu İçin AI Provider Abstraction', story)
    P("""Mevcut sistemdeki Qwen-only yaklaşımı web platformunda sürdürmek pratik değildir. Çünkü: (a) Her kullanıcının donanımı LLM çalıştırmak için yeterli değildir; (b) Server-side GPU maliyeti yüksektir; (c) Farklı görevler için farklı modeller optimumdur (ör. araştırma için GPT-4o, dilekçe için Claude). Önerilen <b>provider abstraction</b> katmanı şu sağlayıcıları desteklemelidir: OpenAI, Google Gemini, Anthropic, OpenRouter, Ollama (legacy Qwen uyumluluğu için). Sağlayıcı seçimi <i>AI_PROVIDER</i> env değişkeni ile yapılır. <b>API anahtarları asla frontend'e gönderilmez</b> — yalnızca backend'te tutulur.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 5 — MCP DURUMU
    # ════════════════════════════════════════════════════════════
    H1('MCP Durumu', story, chapter_num=5)

    P("""Model Context Protocol (MCP), BetterSaul'ün dış AI ajanlarına (Claude Desktop, ChatGPT Desktop, Cursor, Gemini) araç sağlamak için kullandığı standarttır. <b>server.py</b> (348 satır) MCP SDK üzerine kurulu tek bir <i>server</i> nesnesi tanımlar ve 21 aracı <i>@server.tool</i> dekoratörü ile kaydeder. Sınıf yapısı yoktur — tüm araçlar fonksiyon olarak tanımlanır.""", story)

    H2('5.1 MCP Server Mimarisi', story)
    P("""Server üç transport modu destekler: (1) <b>stdio</b> — <i>run_stdio()</i> satır 307, stdin/stdout üzerinden; (2) <b>http</b> — satır 313-348, <i>stateless_http=True, json_response=True</i>; (3) <b>https</b> — uvicorn+SSL ile satır 321-339. Endpoint sabit olarak <i>/mcp</i> kullanılır. <b>mcp.log</b> dosyasından anlaşılan: her HTTP request sonrası session kapanıyor (stateless mod), 21 "Terminating session" mesajı görülüyor.""", story)

    H2('5.2 Kayıtlı 21 MCP Aracı', story)
    TableStyled(
        [
            [Paragraph('<b>Araç</b>', S_TABLE_HEADER), Paragraph('<b>İşlev</b>', S_TABLE_HEADER), Paragraph('<b>Web API Karşılığı</b>', S_TABLE_HEADER)],
            [Paragraph('search_bedesten', S_TABLE_CELL_MONO), Paragraph('Yargıtay+Danıştay+Emsal araması', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/bedesten</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_corpus', S_TABLE_CELL_MONO), Paragraph('Yargıtay içtihat araması', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/yargitay</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_corpus_deep', S_TABLE_CELL_MONO), Paragraph('Sayfa sayfa derin arama', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/deep</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_emsal', S_TABLE_CELL_MONO), Paragraph('Emsal karar arama', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/emsal</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_mevzuat', S_TABLE_CELL_MONO), Paragraph('Mevzuat arama (11 kanun)', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/mevzuat</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_anayasa', S_TABLE_CELL_MONO), Paragraph('AYM kararı arama (BB/ND)', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/aym</font>', S_TABLE_CELL_MONO)],
            [Paragraph('search_resmi_gazete', S_TABLE_CELL_MONO), Paragraph('Resmî Gazete arama', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/legal/search/resmi-gazete</font>', S_TABLE_CELL_MONO)],
            [Paragraph('get_bedesten_document', S_TABLE_CELL_MONO), Paragraph('Belge detayı ID ile', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">GET /api/legal/document/{id}</font>', S_TABLE_CELL_MONO)],
            [Paragraph('write_court_petition', S_TABLE_CELL_MONO), Paragraph('Dilekçe oluştur', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/petitions/generate</font>', S_TABLE_CELL_MONO)],
            [Paragraph('review_petition', S_TABLE_CELL_MONO), Paragraph('Dilekçe kalite kontrol', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/petitions/review</font>', S_TABLE_CELL_MONO)],
            [Paragraph('save_petition_pdf', S_TABLE_CELL_MONO), Paragraph('PDF üret (browser subprocess)', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/petitions/{id}/export-pdf</font>', S_TABLE_CELL_MONO)],
            [Paragraph('save_petition_history', S_TABLE_CELL_MONO), Paragraph('Dilekçe arşivle (SQLite)', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">POST /api/petitions/{id}/save</font>', S_TABLE_CELL_MONO)],
            [Paragraph('ping / echo', S_TABLE_CELL_MONO), Paragraph('Sağlık kontrolü', S_TABLE_CELL_SMALL), Paragraph('<font face="DejaVuSansMono">GET /api/health</font>', S_TABLE_CELL_MONO)],
            [Paragraph('(diğer 8 araç)', S_TABLE_CELL_MONO), Paragraph('Yardımcı araçlar (license, version vb.)', S_TABLE_CELL_SMALL), Paragraph('Çeşitli endpoint\'ler', S_TABLE_CELL_MONO)],
        ],
        col_widths=[CONTENT_W * 0.25, CONTENT_W * 0.35, CONTENT_W * 0.40],
        story=story,
        caption='Tablo 5.1 — 21 MCP aracı ve REST API karşılıkları'
    )

    H2('5.3 Connect Konfigürasyonları', story)
    P("""<b>connect/</b> klasörü 5 AI ajan için MCP entegrasyon config dosyası içerir. Hepsi aynı <i>run_mcp.py --stdio</i> script'ine işaret eder. <b>chatgpt.toml</b> dosyasındaki <i>default_tools_approval_mode = "auto"</i> ayarı, ChatGPT'nin kullanıcıdan onay almadan MCP araçlarını çağırabileceği anlamına gelir — bu güvenlik açısından risklidir ve web platformunda dikkatle ele alınmalıdır.""", story)

    H2('5.4 Web\'e Taşınabilirlik', story)
    P("""21 MCP aracından <b>18\'i doğrudan REST API\'ye çevrilebilir</b> — saf Python, OS bağımsız, hiçbir desktop bağımlılığı yok. Yalnızca <b>3 araç desktop bağımlıdır</b>: (1) <i>write_court_petition</i> — SQLite archive.db'ye yazar; (2) <i>save_petition_history</i> — aynı şekilde SQLite; (3) <i>save_petition_pdf</i> — Edge/Chrome browser'ı subprocess olarak çağırır ve Windows <i>os.startfile</i> kullanır. Bu üç araç, PostgreSQL + WeasyPrint kullanılarak yeniden yazılmalıdır.""", story)

    P("""MCP sisteminin tamamen kaldırılması zorunlu değildir. İleride dış AI ajanlarının (Claude Desktop vb.) BetterSaul web platformunu kullanabilmesi için <b>ayrı bir MCP endpoint</b> korunabilir. Bu endpoint, REST API'lerin üzerine bir MCP adapter katmanı olarak implemente edilir. Böylece hem insan kullanıcılar REST API'yi kullanır hem de AI ajanları MCP üzerinden erişir.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 6 — VERİ MODELİ
    # ════════════════════════════════════════════════════════════
    H1('Veri Modeli', story, chapter_num=6)

    P("""BetterSaul'ün veri katmanı, <b>archive.db</b> adlı 24KB'lık bir SQLite veritabanından ibarettir. Bu veritabanı yalnızca 2 tablo içerir: <i>chats</i> ve <i>petitions</i>. Toplam 0 satır veri, 0 foreign key, 0 trigger, 0 view barındırır. WAL mode aktif, page_size 4096, user_version 0 (migration yok). İki basit index vardır: <i>idx_chats_created</i> ve <i>idx_petitions_created</i> (created_at DESC).""", story)

    H2('6.1 Mevcut SQLite Şema', story)
    Code("""-- Tablo 1: chats (7 kolon)
CREATE TABLE chats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    messages    TEXT,            -- JSON array
    track       TEXT,            -- dava türü
    summary     TEXT
);
CREATE INDEX idx_chats_created ON chats(created_at DESC);

-- Tablo 2: petitions (23 kolon - AŞIRI DENORMALİZE)
CREATE TABLE petitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    petition_type   TEXT,
    petitioner_name TEXT,
    petitioner_tckn TEXT,
    petitioner_address TEXT,
    defendant_name  TEXT,
    defendant_address TEXT,
    court           TEXT,
    case_no         TEXT,
    subject         TEXT,
    facts           TEXT,
    legal_basis     TEXT,
    requests        TEXT,
    evidence        TEXT,
    body_text       TEXT,
    quality_score   INTEGER,
    quality_report  TEXT,        -- JSON
    status          TEXT,
    pdf_path        TEXT,
    notes           TEXT,
    metadata        TEXT         -- JSON grab-bag
);
CREATE INDEX idx_petitions_created ON petitions(created_at DESC);""", story)

    H2('6.2 Mevcut Şemanın Sorunları', story)
    Bul([
        '<b>Çok-kullanıcılı mimari yok</b>: user_id kolonu yok, tüm dilekçeler tek kullanıcıya ait varsayılıyor',
        '<b>Organizasyon/tenant yok</b>: multi-tenant SaaS için altyapı yok',
        '<b>Versiyonlama yok</b>: dilekçe güncellendiğinde eski sürüm kaybolur (no petition_versions tablosu)',
        '<b>Audit log yok</b>: kim ne zaman ne değiştirdi takip edilmiyor',
        '<b>Soft-delete yok</b>: silinen kayıt geri alınamaz',
        '<b>FK yok</b> : case-petition-document ilişkisi yok',
        '<b>Denormalize</b>: petitions tablosu 23 kolon, lawyer/taraflar/deliller gömülü',
        '<b>Vector/embedding yok</b>: pgvector veya benzeri hiç yok',
        '<b>Legal source verisi yok</b>: içtihat/mevzuat/AYM kararları saklanmıyor, her seferinde uzaktan çekiliyor',
        '<b>Subscription/plan yok</b>: SaaS iş modeli için altyapı yok',
    ], story)

    H2('6.3 PostgreSQL Migration Stratejisi', story)
    P("""Mevcut 2 tablo yaklaşımı, web platformunda <b>18+ tabloya</b> bölünmelidir. <i>petitions</i> tablosu en az 4 tabloya ayrılır: <i>petitions</i> (ana kayıt), <i>lawyer_profiles</i> (vekıl bilgileri), <i>petition_claims</i> (talep kalemleri), <i>petition_research_items</i> (AI araştırma sonuçları). Ayrıca eksik tablolar eklenir: <i>users</i>, <i>organizations</i>, <i>subscriptions</i>, <i>api_keys</i>, <i>cases</i>, <i>case_parties</i>, <i>documents</i>, <i>document_chunks</i>, <i>document_embeddings</i>, <i>legal_sources</i>, <i>legal_decisions</i>, <i>statutes</i>, <i>statute_articles</i>, <i>citations</i>, <i>research_sessions</i>, <i>petition_versions</i>, <i>petition_reviews</i>, <i>ai_runs</i>, <i>audit_logs</i>. Detaylı şema Bölüm 11'de verilmiştir.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 7 — WEB'E TAŞINABİLİR KODLAR
    # ════════════════════════════════════════════════════════════
    H1('Web\'e Taşınabilir Kodlar', story, chapter_num=7)

    P("""BetterSaul kod tabanının yaklaşık <b>%60-65'i doğrudan web platformuna taşınabilir</b>. Bu bölüm, hangi modüllerin/fonksiyonların nasıl taşınacağını detaylandırır. Taşınabilirlik değerlendirmesi 4 kategoriye ayrılır: (a) doğrudan taşınabilir (saf Python, OS bağımsız), (b) adapter ile taşınabilir (küçük değişiklik), (c) yeniden tasarlanması gereken (büyük değişiklik), (d) silinecek (desktop-only).""", story)

    H2('7.1 Doğrudan Taşınabilir Modüller', story)
    TableStyled(
        [
            [Paragraph('<b>Modül / Fonksiyon</b>', S_TABLE_HEADER), Paragraph('<b>Satır</b>', S_TABLE_HEADER_C), Paragraph('<b>Taşınma Stratejisi</b>', S_TABLE_HEADER)],
            [Paragraph('<font face="DejaVuSansMono">quality.review()</font>', S_TABLE_CELL_MONO), Paragraph('945', S_TABLE_CELL_C), Paragraph('Saf Python, sync. FastAPI endpoint\'e sar: <i>await run_in_threadpool(quality.review, ...)</i>', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">quality.preflight()</font>', S_TABLE_CELL_MONO), Paragraph('1026', S_TABLE_CELL_C), Paragraph('Aynı — preflight endpoint', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">quality.format_report()</font>', S_TABLE_CELL_MONO), Paragraph('988', S_TABLE_CELL_C), Paragraph('Saf Python, hiç I/O yok', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">quality.extract_model()</font>', S_TABLE_CELL_MONO), Paragraph('323', S_TABLE_CELL_C), Paragraph('Form → yapılandırılmış kart çıkarımı', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">motor.pipeline.analyze()</font>', S_TABLE_CELL_MONO), Paragraph('681', S_TABLE_CELL_C), Paragraph('19 sync aşama, threadpool\'da çalıştır', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">motor.pipeline.classify()</font>', S_TABLE_CELL_MONO), Paragraph('132', S_TABLE_CELL_C), Paragraph('Naif keyword sınıflandırıcı, doğrudan taşınabilir', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">motor.catalog.*</font>', S_TABLE_CELL_MONO), Paragraph('1-426', S_TABLE_CELL_C), Paragraph('Sabit veri modülü, JSON olarak DB\'ye yüklenebilir', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">templates.assemble()</font>', S_TABLE_CELL_MONO), Paragraph('438', S_TABLE_CELL_C), Paragraph('Plain text dilekçe üretimi, saf Python', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">templates.skeleton()</font>', S_TABLE_CELL_MONO), Paragraph('527', S_TABLE_CELL_C), Paragraph('Dilekçe iskelet, saf Python', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">templates.outline()</font>', S_TABLE_CELL_MONO), Paragraph('256', S_TABLE_CELL_C), Paragraph('Outline üretimi, saf Python', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">templates.guide()</font>', S_TABLE_CELL_MONO), Paragraph('484', S_TABLE_CELL_C), Paragraph('AI usul rehberi metni, saf Python', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">motor.stages.*</font>', S_TABLE_CELL_MONO), Paragraph('1-391', S_TABLE_CELL_C), Paragraph('LLM prompt builder (pasif), bağlanarak kullanılabilir', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">legal_tracks.detect_track()</font>', S_TABLE_CELL_MONO), Paragraph('34', S_TABLE_CELL_C), Paragraph('Regex dava türü tespiti, saf Python', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">petition_packs.*</font>', S_TABLE_CELL_MONO), Paragraph('1-197', S_TABLE_CELL_C), Paragraph('Statik şablon verisi, JSON\'a taşınabilir', S_TABLE_CELL_SMALL)],
            [Paragraph('<font face="DejaVuSansMono">18/21 MCP aracı</font>', S_TABLE_CELL_MONO), Paragraph('—', S_TABLE_CELL_C), Paragraph('Doğrudan FastAPI router\'lara çevrilebilir (Bölüm 12)', S_TABLE_CELL_SMALL)],
        ],
        col_widths=[CONTENT_W * 0.30, CONTENT_W * 0.10, CONTENT_W * 0.60],
        story=story,
        caption='Tablo 7.1 — Doğrudan taşınabilir modüller (~%60-65)'
    )

    H2('7.2 Adapter İle Taşınabilir Modüller', story)
    P("""Bu modüller küçük adaptasyonlarla web'e taşınabilir:""", story)
    Bul([
        '<b>sources.py (907 satır)</b>: sync <i>httpx.Client</i> → async <i>httpx.AsyncClient</i>; global <i>_LIMITED_UNTIL</i> → Redis; desktop UA korunabilir',
        '<b>anayasa.py (342 satır)</b>: aynı async dönüşümü, <i>_KUNYE</i> regex korunur',
        '<b>mevzuat.py (355 satır)</b>: async dönüşüm, hardcoded 11 kanun katalogu veritabanına taşınabilir',
        '<b>tls.py (48 satır)</b>: <i>truststore.SSLContext</i> → certifi (sunucu tarafında OS truststore gerekmez)',
        '<b>ping.py (40 satır)</b>: doğrudan taşınabilir, health endpoint',
    ], story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 8 — YENİDEN YAZILMASI GEREKEN KODLAR
    # ════════════════════════════════════════════════════════════
    H1('Yeniden Yazılması Gereken Kodlar', story, chapter_num=8)

    P("""Bu bölüm, mevcut BetterSaul kod tabanında <b>yeniden tasarlanması veya baştan yazılması</b> gereken bileşenleri listeler. Bu bileşenler ya desktop-only bağımlılıklar içeriyor ya da web ölçeğinde çalışmayacak mimari kararlar barındırıyor.""", story)

    H2('8.1 engine.py — 7.857 Satırlık Tek Dosya', story)
    P("""Bu en büyük taşıma riskidir. 7.857 satırlık tek bir Python dosyası, modüler olmayan yapıda, ~200 fonksiyon içerir. Web platformunda bu dosya <b>modüllere bölünmelidir</b>: <i>engine/main.py</i> (orchestrator), <i>engine/llm.py</i> (AI inference + provider abstraction), <i>engine/research.py</i> (araştırma pipeline), <i>engine/petition.py</i> (dilekçe pipeline), <i>engine/cleaner.py</i> (prompt sızıntısı temizleme), <i>engine/citation.py</i> (citation gerçeklik kontrolü). Her modül ~500-1500 satır olmalıdır.""", story)

    H2('8.2 LLM Hattı — Provider Abstraction', story)
    P("""Mevcut sistem yalnızca Qwen 2.5/3 modellerini (llama-server/llama-cpp/llama-cli) destekler. Web platformunda <b>provider abstraction</b> katmanı yazılmalıdır. Bu katman, tüm sağlayıcıları (OpenAI, Gemini, Anthropic, OpenRouter, Ollama) tek bir arayüz altında birleştirir. <b>engine.py satır 2222, 2641, 2822</b>'deki 3 inference yolu bu abstraction ile değiştirilir. Sağlayıcı seçimi <i>AI_PROVIDER</i> env değişkeni ile runtime'da yapılır.""", story)

    H2('8.3 Memory Katmanı — JSON Path → PostgreSQL/Redis', story)
    P("""<b>quality._load_memory</b> (satır 926-942) desktop path'lerden <i>case_memory.json</i> yükler. Bu dosya macOS'ta <i>~/Library/Application Support/BetterSaul/</i>, Windows'ta <i>%LOCALAPPDATA%/BetterSaul/</i> altındadır. Web platformunda bu veri <b>PostgreSQL JSONB kolonunda veya Redis'te</b> saklanmalıdır. Çok-kullanıcılı olduğunda session/tenant ayrımı gerekir.""", story)

    H2('8.4 HTML/PDF/DOCX Render — Yeni Katman', story)
    P("""<b>templates.assemble()</b> yalnızca plain text üretir — HTML, PDF, DOCX renderlayıcı <b>yok</b>. Web platformunda bu 3 renderer eklenmelidir: (a) <b>Jinja2</b> — HTML şablonlar; (b) <b>WeasyPrint</b> — HTML→PDF (mevcut <i>_print_pdf</i> browser subprocess yerine); (c) <b>python-docx</b> — DOCX üretimi (yoktan var edilecek). Bu üç bileşen <i>petition-renderer</i> servisinde toplanır.""", story)

    H2('8.5 IPC/WebView → REST/SSE', story)
    P("""Mevcut UI ile backend arasındaki <b>stdin/stdout JSON-line IPC</b> tamamen kaldırılmalıdır. Yerine: (a) <b>REST API</b> — Next.js API routes üzerinden; (b) <b>SSE (Server-Sent Events)</b> — AI chat streaming için (chat-delta, petition-done event'leri); (c) <b>WebSocket</b> — opsiyonel, real-time collaborative editing için. <i>app.js</i>'deki 30 IPC komutu → REST endpoint'lerine, 30 event → SSE event'lerine çevrilir.""", story)

    H2('8.6 license_gate.py — Kaldırılmalı', story)
    P("""<b>license_gate.py</b> (245 satır) Windows <i>winreg</i>, hardcoded build tarihi (2026-09-20), 2 ay expiry, HMAC imza ve anti-rollback (internet zamanı) kullanır. Web platformunda bu mekanizma <b>tamamen kaldırılmalıdır</b>. Yerine SaaS subscription modeli (Stripe ile entegre) + JWT tabanlı auth gelir. Aktivasyon mekanizması yoktur — zaten desktop'ta da tam çalışmıyordur.""", story)

    H2('8.7 Search-Motor Entegrasyonu — Yok → Eklenecek', story)
    P("""Mevcut durumda <b>motor tarama yapmaz</b>. <i>motor.pipeline.analyze</i> ve <i>motor.stages</i> modüllerinin hiçbir fonksiyonu <i>sources.py</i>'i çağırmaz. <i>quality._cite_findings</i> bir <i>memory</i> argümanı alır ama bu memory dışarıdan verilir; motor kendisi tarama yapmaz. Kullanıcı manuel arar, sonuçları <i>case_memory.json</i>'a kaydeder, sonra <i>quality.review</i> memory'yi okur. Web platformunda bu akış <b>otomatikleştirilmelidir</b>: form doldurulur → motor otomatik içtihat taraması yapar → sonuçları review'a besler.""", story)

    H2('8.8 Semantic Search — Sıfırdan Yazılacak', story)
    P("""Mevcut sistemde semantic search <b> tamamen yok</b> (Bölüm 3). Web platformunda bu <b>tamamen yeni bir katman</b> olarak eklenmelidir. Bileşenler: (a) embedding pipeline (multilingual-e5-large veya OpenAI text-embedding-3-large); (b) PostgreSQL + pgvector (HNSW index); (c) hybrid search orchestrator (semantic + keyword + metadata); (d) cross-encoder reranker (bge-reranker-tr); (e) query expansion (LLM tabanlı sinonim/kavram genişletme). Mevcut kodda bu katmanın hiçbir iskeleti yoktur.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 9 — RİSKLER VE RİSK MATRİSİ
    # ════════════════════════════════════════════════════════════
    H1('Riskler ve Risk Matrisi', story, chapter_num=9)

    P("""Aşağıdaki tablo, migration sürecinde karşılaşılabilecek riskleri <b>etki (Impact)</b> ve <b>olasılık (Probability)</b>维度 değerinde matris olarak sunar. Her risk için azaltma stratejisi (mitigation) önerilmiştir. Risk kodu: <b>K</b>=Kritik, <b>Y</b>=Yüksek, <b>O</b>=Orta, <b>D</b>=Düşük.""", story)

    TableStyled(
        [
            [Paragraph('<b>#</b>', S_TABLE_HEADER_C), Paragraph('<b>Risk</b>', S_TABLE_HEADER), Paragraph('<b>Etki</b>', S_TABLE_HEADER_C), Paragraph('<b>Olasılık</b>', S_TABLE_HEADER_C), Paragraph('<b>Azaltma Stratejisi</b>', S_TABLE_HEADER)],
            [Paragraph('R1', S_TABLE_CELL_C), Paragraph('engine.py tek dosya 7.857 satır — bakım/test riski', S_TABLE_CELL_SMALL), Paragraph('<font color="#8e4f49"><b>K</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('İlk sprint\'te modüllere böl: main/llm/research/petition/cleaner/citation', S_TABLE_CELL_SMALL)],
            [Paragraph('R2', S_TABLE_CELL_C), Paragraph('Semantic search eksikliği — kullanıcı beklentisi karşılanmıyor', S_TABLE_CELL_SMALL), Paragraph('<font color="#8e4f49"><b>K</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('pgvector + e5-large + cross-encoder rerank ile sıfırdan ekle', S_TABLE_CELL_SMALL)],
            [Paragraph('R3', S_TABLE_CELL_C), Paragraph('Uzak portal scraping bağımlılığı (Yargıtay/Danıştay)', S_TABLE_CELL_SMALL), Paragraph('<font color="#8e4f49"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('Belge cache + Redis rate-limit + proxy rotation + monitoring', S_TABLE_CELL_SMALL)],
            [Paragraph('R4', S_TABLE_CELL_C), Paragraph('Local LLM donanım bağımlılığı — server GPU maliyeti', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('Provider abstraction ile OpenAI/Gemini fallback; Ollama opsiyonel', S_TABLE_CELL_SMALL)],
            [Paragraph('R5', S_TABLE_CELL_C), Paragraph('Windows path hardcoded (LOCALAPPDATA, winreg)', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('Path yerine environment-driven config + PostgreSQL storage', S_TABLE_CELL_SMALL)],
            [Paragraph('R6', S_TABLE_CELL_C), Paragraph('license_gate Windows-only (winreg)', S_TABLE_CELL_SMALL), Paragraph('<font color="#548c66"><b>D</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#8e4f49"><b>K</b></font>', S_TABLE_CELL_C), Paragraph('Tamamen kaldır, SaaS subscription (Stripe) ile değiştir', S_TABLE_CELL_SMALL)],
            [Paragraph('R7', S_TABLE_CELL_C), Paragraph('HTML/PDF rendering browser subprocess (Edge/Chrome)', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('WeasyPrint + python-docx ile değiştir', S_TABLE_CELL_SMALL)],
            [Paragraph('R8', S_TABLE_CELL_C), Paragraph('Tek-kullanıcılı archive.db — multi-tenant yok', S_TABLE_CELL_SMALL), Paragraph('<font color="#8e4f49"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('PostgreSQL 18+ tablo + org_id partitioning + RBAC', S_TABLE_CELL_SMALL)],
            [Paragraph('R9', S_TABLE_CELL_C), Paragraph('Prompt sızıntısı regex ile yakalanma — yeni pattern\'ler kaçabilir', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('LLM-as-judge opsiyonel ikinci katman (motor.stages.check_messages)', S_TABLE_CELL_SMALL)],
            [Paragraph('R10', S_TABLE_CELL_C), Paragraph('9M+ belge import sırasında embed maliyeti', S_TABLE_CELL_SMALL), Paragraph('<font color="#8e4f49"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('Async job queue + batch processing + increment indexing', S_TABLE_CELL_SMALL)],
            [Paragraph('R11', S_TABLE_CELL_C), Paragraph('ChatGPT default_tools_approval_mode="auto" — güvenlik', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('Web platformunda her tool çağrısı için explicit user consent', S_TABLE_CELL_SMALL)],
            [Paragraph('R12', S_TABLE_CELL_C), Paragraph('TOOL_RE regex ile tool dispatch — JSON parse hatası', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('OpenAI function calling veya structured output kullan', S_TABLE_CELL_SMALL)],
            [Paragraph('R13', S_TABLE_CELL_C), Paragraph('Türkçe hukuk terminolojisi için embedding kalitesi', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('multilingual-e5-large + Türkçe fine-tune veya BGE-m3', S_TABLE_CELL_SMALL)],
            [Paragraph('R14', S_TABLE_CELL_C), Paragraph('Uzak portal 429 rate-limit cooldown 50 sn — UX yavaş', S_TABLE_CELL_SMALL), Paragraph('<font color="#a18140"><b>O</b></font>', S_TABLE_CELL_C), Paragraph('<font color="#a18140"><b>Y</b></font>', S_TABLE_CELL_C), Paragraph('Redis cooldown + proxy pool + cache sonuçlar', S_TABLE_CELL_SMALL)],
        ],
        col_widths=[CONTENT_W * 0.05, CONTENT_W * 0.35, CONTENT_W * 0.10, CONTENT_W * 0.13, CONTENT_W * 0.37],
        story=story,
        caption='Tablo 9.1 — Risk matrisi (Etki/Olasılık) ve azaltma stratejileri'
    )

    H2('9.1 Risk Önceliklendirme', story)
    P("""<b>Kritik (K) etkiye sahip riskler</b>: R1 (engine.py modülerleştirme), R2 (semantic search eksikliği). Bunlar migration'ın başarısı için <b>ilk 3 sprintte</b> çözülmelidir. <b>Yüksek etki + Yüksek olasılık</b> riskleri (R3, R4, R8, R10) orta vadede (sprint 4-10) ele alınmalıdır. <b>Düşük etki</b> riskleri (R6) erken kaldırılmalı; <b>Orta etki</b> riskleri (R5, R7, R9, R12) kademeli olarak iyileştirilmelidir.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 10 — ÖNERİLEN NEXT.JS MİMARİSİ
    # ════════════════════════════════════════════════════════════
    H1('Önerilen Next.js Mimarisi', story, chapter_num=10)

    P("""Önerilen web platformu mimarisi, 8 katmandan oluşur: (1) Client katmanı (Next.js), (2) API Gateway, (3) Python Legal Engine Service, (4) AI Provider Abstraction, (5) Hybrid Search Engine, (6) PostgreSQL + pgvector, (7) Async Job Queue, (8) Storage & Infrastructure. Her katmanın belirli sorumlulukları vardır ve birbirinden bağımsız olarak ölçeklendirilebilir.""", story)

    H2('10.1 Mimari Diyagram (Önerilen)', story)
    P("""Aşağıdaki diyagram, önerilen mimarinin tüm katmanlarını ve veri akışını gösterir. Yeşil ile işaretli katmanlar mevcut sistemde olmayan <b>yeni</b> bileşenlerdir.""", story)

    img_proposed = Image('/home/z/my-project/scripts/diagrams/proposed_arch.png', width=CONTENT_W * 0.78, height=CONTENT_W * 0.78 * (3515/2100))
    img_proposed.hAlign = 'CENTER'
    story.append(img_proposed)
    story.append(Paragraph('Şekil 10.1 — Önerilen Next.js + PostgreSQL + pgvector mimari diyagramı', S_CAPTION))

    H2('10.2 Katman Sorumlulukları', story)
    Bul([
        '<b>Client (Next.js 16 + React + TypeScript + Tailwind + shadcn/ui)</b>: 6 ana sayfa — dashboard, search, petitions, research/[id], chat, documents',
        '<b>API Gateway (Next.js API Routes)</b>: 6 endpoint grubu — auth, legal-search, petitions, research, documents, admin. RBAC + rate limit + input validation',
        '<b>Python Legal Engine (FastAPI container)</b>: 5 modül — engine-wrapper (modülerleştirilmiş engine.py), mcp-adapter (21→REST), quality-engine, petition-renderer (WeasyPrint+docx), source-connectors (async httpx)',
        '<b>AI Provider Abstraction</b>: 5 sağlayıcı — OpenAI, Gemini, Anthropic, OpenRouter, Ollama. Env-driven seçim, fallback, retry, cost-aware routing',
        '<b>Hybrid Search Engine</b>: 5 bileşen — Semantic (pgvector), Keyword (FTS+BM25), Metadata Filter, Cross-encoder Reranker, Query Expansion (LLM)',
        '<b>PostgreSQL 16 + pgvector</b>: 18+ tablo, partitioned legal_decisions (yıllara göre), HNSW index, JSONB metadata',
        '<b>Async Job Queue (Redis + BullMQ)</b>: 4 worker tipi — Import Pipeline (9M+ belge), Source Sync (scheduled), Document Upload (user), AI Research (long-running)',
        '<b>Storage & Infra</b>: S3-compatible (MinIO), Redis cache, Vercel/Docker, Python container, observability (Sentry+OTel+Grafana)',
    ], story)

    H2('10.3 İletişim Akışı', story)
    P("""Tipik bir araştırma senaryosunda veri akışı: <b>Browser</b> → HTTPS → <b>Next.js API route</b> → (sync) <b>Python service</b> (HTTP) → (async) <b>Job Queue</b> → <b>PostgreSQL + pgvector</b>. SSE ile ilerleme tarayıcıya stream edilir. AI chat için: Browser → SSE → API route → Python service → AI provider (OpenAI/Gemini) → tool dispatch → source-connectors → sonuçlar AI'ya → AI cevabı SSE ile stream.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 11 — POSTGRESQL + PGVECTOR MİMARİ
    # ════════════════════════════════════════════════════════════
    H1('PostgreSQL + pgvector Mimari', story, chapter_num=11)

    P("""Önerilen veritabanı şeması, 18+ tablodan oluşur ve mevcut SQLite'ın 2 tabloluk yapısının yerine çok-kullanıcılı, audit-logged, versiyonlu, semantically-searchable bir sistem sunar. Aşağıda her tablonun DDL benzeri yapı verilmiştir.""", story)

    H2('11.1 Auth & Tenant Tabloları', story)
    Code("""CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,          -- bcrypt/argon2
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'user',  -- admin/lawyer/user/org_admin
    bar_no          TEXT,                   -- avukat sicil no
    email_verified  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_login_at   TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ             -- soft delete
);

CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,
    plan            TEXT DEFAULT 'free',    -- free/pro/enterprise
    seat_count      INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE organization_members (
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id          UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,          -- org_admin/lawyer/paralegal
    PRIMARY KEY (user_id, org_id)
);

CREATE TABLE subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES organizations(id),
    stripe_cust_id  TEXT,
    stripe_sub_id   TEXT,
    plan            TEXT,
    status          TEXT,
    current_period_end TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    key_hash        TEXT NOT NULL,
    name            TEXT,
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    org_id          UUID,
    action          TEXT NOT NULL,          -- create_petition, search, export, login
    entity_type     TEXT,                   -- petition, case, document
    entity_id       UUID,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_audit_user_time ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);""", story)

    H2('11.2 Case & Document Tabloları', story)
    Code("""CREATE TABLE cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES organizations(id),
    title           TEXT NOT NULL,
    case_no         TEXT,                   -- mahkeme esas no
    court           TEXT,
    track           TEXT,                   -- iş/boşanma/idare/...
    status          TEXT DEFAULT 'open',    -- open/closed/archived
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_cases_org ON cases(org_id, created_at DESC);

CREATE TABLE case_parties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID REFERENCES cases(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,          -- plaintiff/defendant/witness
    name            TEXT,
    tckn            TEXT,
    address         TEXT,
    metadata        JSONB
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES organizations(id),
    case_id         UUID REFERENCES cases(id),
    user_id         UUID REFERENCES users(id),
    filename        TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      BIGINT,
    s3_key          TEXT,                   -- S3/MinIO object key
    parsed_text     TEXT,
    parse_status    TEXT,                   -- pending/parsed/failed
    source          TEXT,                   -- user_upload/court/scrape
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    chunk_text      TEXT NOT NULL,
    metadata        JSONB,                  -- page, section, heading
    UNIQUE (document_id, chunk_index)
);

-- pgvector: 1536d OpenAI text-embedding-3-large
CREATE TABLE document_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    embedding       vector(1536) NOT NULL,
    model           TEXT DEFAULT 'text-embedding-3-large',
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_doc_emb_hnsw ON document_embeddings
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);""", story)

    H2('11.3 Legal Source Tabloları (9M+ karar)', story)
    Code("""CREATE TABLE legal_sources (
    id              SERIAL PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,   -- yargitay/danistay/emsal/aym/resmi_gazete/mevzuat
    base_url        TEXT,
    api_url         TEXT,
    scraper_config  JSONB,                  -- rate_limit, headers, parser
    last_synced_at  TIMESTAMPTZ,
    enabled         BOOLEAN DEFAULT TRUE
);

-- Partitioned by year for 9M+ decisions
CREATE TABLE legal_decisions (
    id              BIGSERIAL,
    source_id       INT REFERENCES legal_sources(id),
    source_doc_id   TEXT,                   -- portal-side unique ID
    court           TEXT,
    court_chamber   TEXT,                   -- 9. HD, 10. HD, vs.
    decision_number TEXT,                   -- E.2024/123 K.2024/456
    case_number     TEXT,
    decision_date   DATE,
    document_type   TEXT,                   -- decision/ruling/verdict
    title           TEXT,
    full_text       TEXT,
    summary         TEXT,
    metadata        JSONB,
    scraped_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, decision_date)
) PARTITION BY RANGE (decision_date);

CREATE TABLE legal_decisions_2024 PARTITION OF legal_decisions
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
-- ... diğer yıllar

CREATE TABLE legal_decision_chunks (
    id              BIGSERIAL PRIMARY KEY,
    decision_id     BIGINT,
    chunk_index     INT,
    chunk_text      TEXT,
    metadata        JSONB
) PARTITION BY RANGE (chunk_index);

CREATE TABLE legal_decision_embeddings (
    id              BIGSERIAL PRIMARY KEY,
    chunk_id        BIGINT REFERENCES legal_decision_chunks(id) ON DELETE CASCADE,
    embedding       vector(1536) NOT NULL,
    model           TEXT DEFAULT 'multilingual-e5-large',
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_legal_emb_hnsw ON legal_decision_embeddings
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE statutes (
    id              SERIAL PRIMARY KEY,
    name             TEXT NOT NULL,         -- 4857 sayılı İş Kanunu
    statute_no       TEXT,                  -- 4857
    source_url       TEXT,
    current_version_id INT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE statute_articles (
    id              SERIAL PRIMARY KEY,
    statute_id      INT REFERENCES statutes(id),
    article_no      TEXT,                   -- 18, 20/A
    version         INT DEFAULT 1,          -- v1, v2, v3
    title           TEXT,
    body_text       TEXT,
    effective_from  DATE,
    effective_to    DATE,                   -- null = current
    source_url      TEXT,
    UNIQUE (statute_id, article_no, version)
);
CREATE INDEX idx_statute_current ON statute_articles(statute_id)
    WHERE effective_to IS NULL;""", story)

    H2('11.4 Petition & Research Tabloları', story)
    Code("""CREATE TABLE petitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES organizations(id),
    case_id         UUID REFERENCES cases(id),
    user_id         UUID REFERENCES users(id),
    petition_type   TEXT,                   -- idare/bosanma/is/...
    current_version_id UUID,                -- FK to petition_versions
    status          TEXT DEFAULT 'draft',   -- draft/reviewed/final/exported
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_petitions_org_user ON petitions(org_id, user_id, created_at DESC);

CREATE TABLE petition_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    petition_id     UUID REFERENCES petitions(id) ON DELETE CASCADE,
    version_no      INT NOT NULL,
    body_text       TEXT NOT NULL,
    form_data       JSONB,                  -- structured user input
    quality_score   INT,
    quality_report  JSONB,
    ai_run_id       UUID,                   -- AI generation run reference
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (petition_id, version_no)
);

CREATE TABLE petition_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    petition_version_id UUID REFERENCES petition_versions(id),
    review_type     TEXT,                   -- auto_regex/llm_judge/user
    score           INT,
    findings        JSONB,
    reviewed_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE research_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES organizations(id),
    user_id         UUID REFERENCES users(id),
    case_id         UUID REFERENCES cases(id),
    petition_id     UUID REFERENCES petitions(id),
    query           TEXT,
    track           TEXT,
    status          TEXT DEFAULT 'running', -- running/completed/failed
    started_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE research_traces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES research_sessions(id) ON DELETE CASCADE,
    step_order      INT,
    step_type       TEXT,                   -- intent_detect/query_gen/search/verify
    step_name       TEXT,
    input_data      JSONB,
    output_data     JSONB,
    duration_ms     INT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE TABLE citations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    petition_version_id UUID REFERENCES petition_versions(id),
    source_type     TEXT,                   -- yargitay/danistay/aym/statute
    source_id       TEXT,
    citation_text   TEXT,                   -- "Yargıtay 9. HD. E.2024/123 K.2024/456"
    page_ref        TEXT,
    verified        BOOLEAN DEFAULT FALSE,
    metadata        JSONB
);

CREATE TABLE ai_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    session_id      UUID REFERENCES research_sessions(id),
    provider        TEXT,                   -- openai/gemini/anthropic/ollama
    model           TEXT,                   -- gpt-4o, claude-3-5-sonnet, qwen-14b
    input_tokens    INT,
    output_tokens   INT,
    cost_usd        DECIMAL(10,4),
    duration_ms     INT,
    status          TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);""", story)

    H2('11.5 pgvector Index Stratejisi', story)
    P("""HNSW (Hierarchical Navigable Small World) index tercih edilmiştir. Parametreler: <b>m=16</b> (her node'un bağlantı sayısı), <b>ef_construction=64</b> (inşaat sırası arama genişliği). Bu parametreler 1M-10M vektör için optimal kabul edilir. Sorgu zamanında <b>ef_search</b> (varsayılan 40) ayarlanabilir — daha yüksek değer daha doğru sonuç ama daha yavaş sorgu. Cosine similarity (<i>vector_cosine_ops</i>) kullanılır çünkü e5/OpenAI embedding'leri normalize edilmiştir.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 12 — API TASLAĞI
    # ════════════════════════════════════════════════════════════
    H1('API Taslağı', story, chapter_num=12)

    P("""Önerilen REST API, 6 endpoint grubundan ve toplam ~50 endpoint'ten oluşur. Tüm endpoint'ler <b>JWT auth</b> gerektirir (health ve login hariç), <b>RBAC</b> ile korunur, <b>rate limit</b>'e tabidir. Input validation Zod şemaları ile yapılır. AI streaming endpoint'leri SSE kullanır.""", story)

    H2('12.1 Auth Endpoints', story)
    TableStyled(
        [
            [Paragraph('<b>Method</b>', S_TABLE_HEADER_C), Paragraph('<b>Endpoint</b>', S_TABLE_HEADER), Paragraph('<b>İşlev</b>', S_TABLE_HEADER), Paragraph('<b>Auth</b>', S_TABLE_HEADER_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/register</font>', S_TABLE_CELL_MONO), Paragraph('Email + password ile kayıt. Email verification gönderir.', S_TABLE_CELL_SMALL), Paragraph('Public', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/login</font>', S_TABLE_CELL_MONO), Paragraph('Login → JWT access + refresh token', S_TABLE_CELL_SMALL), Paragraph('Public', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/refresh</font>', S_TABLE_CELL_MONO), Paragraph('Refresh token → yeni access token', S_TABLE_CELL_SMALL), Paragraph('Refresh', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/logout</font>', S_TABLE_CELL_MONO), Paragraph('Token blacklist\'e ekle', S_TABLE_CELL_SMALL), Paragraph('JWT', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/verify-email</font>', S_TABLE_CELL_MONO), Paragraph('Email verification token', S_TABLE_CELL_SMALL), Paragraph('Public', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/reset-password</font>', S_TABLE_CELL_MONO), Paragraph('Şifre sıfırlama talebi + yeni şifre', S_TABLE_CELL_SMALL), Paragraph('Public', S_TABLE_CELL_C)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/me</font>', S_TABLE_CELL_MONO), Paragraph('Mevcut kullanıcı bilgisi', S_TABLE_CELL_SMALL), Paragraph('JWT', S_TABLE_CELL_C)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/auth/oauth/[provider]</font>', S_TABLE_CELL_MONO), Paragraph('Google/GitHub OAuth (opsiyonel)', S_TABLE_CELL_SMALL), Paragraph('Public', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.10, CONTENT_W * 0.32, CONTENT_W * 0.43, CONTENT_W * 0.15],
        story=story,
        caption='Tablo 12.1 — Auth endpoints'
    )

    H2('12.2 Legal Search Endpoints', story)
    TableStyled(
        [
            [Paragraph('<b>Method</b>', S_TABLE_HEADER_C), Paragraph('<b>Endpoint</b>', S_TABLE_HEADER), Paragraph('<b>İşlev</b>', S_TABLE_HEADER), Paragraph('<b>Rate</b>', S_TABLE_HEADER_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/bedesten</font>', S_TABLE_CELL_MONO), Paragraph('Yargıtay+Danıştay+Emsal araması (sync, portal)', S_TABLE_CELL_SMALL), Paragraph('10/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/deep</font>', S_TABLE_CELL_MONO), Paragraph('Sayfa sayfa derin arama (async job başlatır)', S_TABLE_CELL_SMALL), Paragraph('5/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/mevzuat</font>', S_TABLE_CELL_MONO), Paragraph('Mevzuat arama (versiyonlu)', S_TABLE_CELL_SMALL), Paragraph('20/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/aym</font>', S_TABLE_CELL_MONO), Paragraph('AYM kararı arama (BB/ND)', S_TABLE_CELL_SMALL), Paragraph('20/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/resmi-gazete</font>', S_TABLE_CELL_MONO), Paragraph('Resmî Gazete arama (tarih aralığı)', S_TABLE_CELL_SMALL), Paragraph('20/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/semantic</font>', S_TABLE_CELL_MONO), Paragraph('Semantic search (pgvector + rerank)', S_TABLE_CELL_SMALL), Paragraph('30/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/search/hybrid</font>', S_TABLE_CELL_MONO), Paragraph('Hybrid: semantic + keyword + metadata + rerank', S_TABLE_CELL_SMALL), Paragraph('30/dk', S_TABLE_CELL_C)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/document/[source]/[id]</font>', S_TABLE_CELL_MONO), Paragraph('Belge detayı (Yargıtay/Danıştay/AYM)', S_TABLE_CELL_SMALL), Paragraph('60/dk', S_TABLE_CELL_C)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/legal/expand-query</font>', S_TABLE_CELL_MONO), Paragraph('AI query expansion (sinonim/kavram)', S_TABLE_CELL_SMALL), Paragraph('10/dk', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.10, CONTENT_W * 0.35, CONTENT_W * 0.42, CONTENT_W * 0.13],
        story=story,
        caption='Tablo 12.2 — Legal search endpoints'
    )

    H2('12.3 Petition & Research Endpoints', story)
    TableStyled(
        [
            [Paragraph('<b>Method</b>', S_TABLE_HEADER_C), Paragraph('<b>Endpoint</b>', S_TABLE_HEADER), Paragraph('<b>İşlev</b>', S_TABLE_HEADER)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions</font>', S_TABLE_CELL_MONO), Paragraph('Yeni dilekçe oluştur (form data ile)', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions</font>', S_TABLE_CELL_MONO), Paragraph('Kullanıcı/org dilekçelerini listele (pagination)', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]</font>', S_TABLE_CELL_MONO), Paragraph('Dilekçe detayı (current version)', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/generate</font>', S_TABLE_CELL_MONO), Paragraph('AI ile dilekçe metni üret (SSE stream)', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/review</font>', S_TABLE_CELL_MONO), Paragraph('17-boyut kalite kontrol çalıştır', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/repair</font>', S_TABLE_CELL_MONO), Paragraph('AI ile düşük skorlu dilekçeyi düzelt', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/versions</font>', S_TABLE_CELL_MONO), Paragraph('Versiyon listesi (v1, v2, v3...)', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/versions/[v]</font>', S_TABLE_CELL_MONO), Paragraph('Belirli versiyon metni', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/versions/compare</font>', S_TABLE_CELL_MONO), Paragraph('İki versiyon diff (unified diff format)', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/export-pdf</font>', S_TABLE_CELL_MONO), Paragraph('PDF üret (WeasyPrint), S3\'e yükle', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/petitions/[id]/export-docx</font>', S_TABLE_CELL_MONO), Paragraph('DOCX üret (python-docx)', S_TABLE_CELL_SMALL)],
            [Paragraph('POST', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/research/sessions</font>', S_TABLE_CELL_MONO), Paragraph('Yeni AI araştırma oturumu başlat', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/research/sessions/[id]</font>', S_TABLE_CELL_MONO), Paragraph('Oturum durumu + trace adımları', S_TABLE_CELL_SMALL)],
            [Paragraph('GET', S_TABLE_CELL_C), Paragraph('<font face="DejaVuSansMono">/api/research/sessions/[id]/stream</font>', S_TABLE_CELL_MONO), Paragraph('SSE: gerçek zamanlı trace adımları', S_TABLE_CELL_SMALL)],
        ],
        col_widths=[CONTENT_W * 0.10, CONTENT_W * 0.40, CONTENT_W * 0.50],
        story=story,
        caption='Tablo 12.3 — Petition & Research endpoints'
    )

    H2('12.4 Document, Chat & Admin Endpoints', story)
    Bul([
        '<b>POST <font face="DejaVuSansMono">/api/documents/upload</font></b> — PDF/DOCX/TXT yükle, async parse job\'ı başlat',
        '<b>GET <font face="DejaVuSansMono">/api/documents</font></b> — Kullanıcı belgeleri listesi',
        '<b>POST <font face="DejaVuSansMono">/api/documents/[id]/search</font></b> — Belge içinde semantic search',
        '<b>DELETE <font face="DejaVuSansMono">/api/documents/[id]</font></b> — Belge + embedding sil',
        '<b>POST <font face="DejaVuSansMono">/api/chat/sessions</font></b> — Yeni chat oturumu',
        '<b>POST <font face="DejaVuSansMono">/api/chat/sessions/[id]/messages</font></b> — Mesaj gönder (SSE stream)',
        '<b>GET <font face="DejaVuSansMono">/api/chat/sessions/[id]/messages</font></b> — Mesaj geçmişi',
        '<b>GET <font face="DejaVuSansMono">/api/admin/users</font></b> — Kullanıcı listesi (admin only)',
        '<b>GET <font face="DejaVuSansMono">/api/admin/audit-logs</font></b> — Audit log sorgu (admin only)',
        '<b>GET <font face="DejaVuSansMono">/api/admin/ai-runs</font></b> — AI kullanım istatistikleri (admin only)',
        '<b>GET <font face="DejaVuSansMono">/api/admin/sources</font></b> — Hukuk kaynağı sync durumu (admin only)',
        '<b>GET <font face="DejaVuSansMono">/api/health</font></b> — Health check (public, /api/health/simple)',
    ], story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 13 — MİGRASYON PLANI (19 FAZ)
    # ════════════════════════════════════════════════════════════
    H1('Migration Planı (19 Faz)', story, chapter_num=13)

    P("""Migration planı, 19 fazdan oluşur ve toplam <b>5-7 ay</b> sürmesi öngörülür. Faz 1 (Kod Analizi) bu raporla tamamlanmıştır. Her faz, belirli çıktılara sahiptir ve bir sonraki fazın başlaması için bağımlılık teşkil eder. Kritik yol (critical path): Faz 2 → Faz 3 → Faz 4 → Faz 5 → Faz 7 → Faz 8 → Faz 10 → Faz 11.""", story)

    TableStyled(
        [
            [Paragraph('<b>Faz</b>', S_TABLE_HEADER_C), Paragraph('<b>Adı</b>', S_TABLE_HEADER), Paragraph('<b>Süre</b>', S_TABLE_HEADER_C), Paragraph('<b>Çıktı / Teslimat</b>', S_TABLE_HEADER), Paragraph('<b>Bağımlılık</b>', S_TABLE_HEADER_C)],
            [Paragraph('1', S_TABLE_CELL_C), Paragraph('Kod Analizi & Mimari Doküman', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Bu rapor (TAMAMLANDI)', S_TABLE_CELL_SMALL), Paragraph('—', S_TABLE_CELL_C)],
            [Paragraph('2', S_TABLE_CELL_C), Paragraph('Database Şema (PostgreSQL + pgvector)', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Prisma schema, 18+ tablo, migration SQL', S_TABLE_CELL_SMALL), Paragraph('F1', S_TABLE_CELL_C)],
            [Paragraph('3', S_TABLE_CELL_C), Paragraph('Legal Source Abstraction (Python)', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Async httpx source-connectors modülü', S_TABLE_CELL_SMALL), Paragraph('F1', S_TABLE_CELL_C)],
            [Paragraph('4', S_TABLE_CELL_C), Paragraph('Python Engine API Service (FastAPI)', S_TABLE_CELL_SMALL), Paragraph('3 hf', S_TABLE_CELL_C), Paragraph('engine-wrapper, mcp-adapter (18/21 araç), Dockerfile', S_TABLE_CELL_SMALL), Paragraph('F2, F3', S_TABLE_CELL_C)],
            [Paragraph('5', S_TABLE_CELL_C), Paragraph('Next.js Application Scaffold', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Next.js 16, TypeScript, Tailwind, shadcn/ui, Prisma', S_TABLE_CELL_SMALL), Paragraph('F2', S_TABLE_CELL_C)],
            [Paragraph('6', S_TABLE_CELL_C), Paragraph('Authentication (NextAuth + JWT + RBAC)', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Login/register/verify/reset, 4 rol', S_TABLE_CELL_SMALL), Paragraph('F5', S_TABLE_CELL_C)],
            [Paragraph('7', S_TABLE_CELL_C), Paragraph('Legal Search (Mevcut araçların REST\'e çevrimi)', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('5 search endpoint, Redis rate-limit', S_TABLE_CELL_SMALL), Paragraph('F4, F6', S_TABLE_CELL_C)],
            [Paragraph('8', S_TABLE_CELL_C), Paragraph('Semantic Search (pgvector)', S_TABLE_CELL_SMALL), Paragraph('3 hf', S_TABLE_CELL_C), Paragraph('Embedding pipeline, HNSW index, semantic endpoint', S_TABLE_CELL_SMALL), Paragraph('F2, F7', S_TABLE_CELL_C)],
            [Paragraph('9', S_TABLE_CELL_C), Paragraph('Hybrid Search + Reranking', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('BM25+vector+rerank orchestrator', S_TABLE_CELL_SMALL), Paragraph('F8', S_TABLE_CELL_C)],
            [Paragraph('10', S_TABLE_CELL_C), Paragraph('AI Orchestration (Provider Abstraction)', S_TABLE_CELL_SMALL), Paragraph('3 hf', S_TABLE_CELL_C), Paragraph('5 provider, env-driven router, fallback', S_TABLE_CELL_SMALL), Paragraph('F4', S_TABLE_CELL_C)],
            [Paragraph('11', S_TABLE_CELL_C), Paragraph('Dilekçe Sistemi', S_TABLE_CELL_SMALL), Paragraph('3 hf', S_TABLE_CELL_C), Paragraph('Generate/review/repair, 12 şablon, AI stream', S_TABLE_CELL_SMALL), Paragraph('F7, F10', S_TABLE_CELL_C)],
            [Paragraph('12', S_TABLE_CELL_C), Paragraph('Research Trace UI', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Şeffaf AI adım gösterimi, SSE stream', S_TABLE_CELL_SMALL), Paragraph('F11', S_TABLE_CELL_C)],
            [Paragraph('13', S_TABLE_CELL_C), Paragraph('Document Upload + Parse + Embed', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('PDF/DOCX/TXT, OCR, async job, user index', S_TABLE_CELL_SMALL), Paragraph('F8', S_TABLE_CELL_C)],
            [Paragraph('14', S_TABLE_CELL_C), Paragraph('Versioning (Petition + Statute)', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Versiyon geçmişi, diff, rollback, mevzuat v1/v2/current', S_TABLE_CELL_SMALL), Paragraph('F11', S_TABLE_CELL_C)],
            [Paragraph('15', S_TABLE_CELL_C), Paragraph('PDF/DOCX Export', S_TABLE_CELL_SMALL), Paragraph('1 hf', S_TABLE_CELL_C), Paragraph('WeasyPrint + python-docx, S3 storage', S_TABLE_CELL_SMALL), Paragraph('F11', S_TABLE_CELL_C)],
            [Paragraph('16', S_TABLE_CELL_C), Paragraph('Admin Panel', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('User mgmt, audit logs, usage, source sync', S_TABLE_CELL_SMALL), Paragraph('F6, F7', S_TABLE_CELL_C)],
            [Paragraph('17', S_TABLE_CELL_C), Paragraph('Performance Optimization', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('Cache, query plan, index tuning, load test', S_TABLE_CELL_SMALL), Paragraph('F9, F11', S_TABLE_CELL_C)],
            [Paragraph('18', S_TABLE_CELL_C), Paragraph('Security Audit', S_TABLE_CELL_SMALL), Paragraph('2 hf', S_TABLE_CELL_C), Paragraph('CSRF/XSS/SQLi/SSRF, prompt injection, rate limit', S_TABLE_CELL_SMALL), Paragraph('F16', S_TABLE_CELL_C)],
            [Paragraph('19', S_TABLE_CELL_C), Paragraph('Production Deployment', S_TABLE_CELL_SMALL), Paragraph('1 hf', S_TABLE_CELL_C), Paragraph('CI/CD, monitoring, runbook, backup strategy', S_TABLE_CELL_SMALL), Paragraph('F17, F18', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.05, CONTENT_W * 0.27, CONTENT_W * 0.08, CONTENT_W * 0.45, CONTENT_W * 0.15],
        story=story,
        caption='Tablo 13.1 — 19 fazlık migration yol haritası'
    )

    H2('13.1 Kritik Yol (Critical Path)', story)
    P("""<b>F1 (Kod Analizi) → F2 (DB) → F4 (Python Service) → F5 (Next.js) → F7 (Legal Search) → F8 (Semantic) → F9 (Hybrid) → F10 (AI) → F11 (Dilekçe) → F12 (Research Trace) → F15 (PDF/DOCX) → F19 (Deploy)</b>. Bu kritik yol yaklaşık 27 hafta (~6.5 ay) sürer. Paralel yapılabilecek fazlar: F3 || F5 || F6, F8 || F10, F12 || F13 || F14 || F16.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 14 — TAHMİNİ MODÜL LİSTESİ
    # ════════════════════════════════════════════════════════════
    H1('Tahmini Modül Listesi', story, chapter_num=14)

    P("""Önerilen web platformu üç ana katmanda organize edilir: <b>Frontend (Next.js)</b>, <b>Backend (Next.js API + Python Service)</b>, <b>Shared (Types & Schemas)</b>. Aşağıda her katmanın modül listesi ve dosya yapısı özeti verilmiştir.""", story)

    H2('14.1 Frontend Modülleri (app/)', story)
    Code("""app/
├── (auth)/
│   ├── login/page.tsx
│   ├── register/page.tsx
│   ├── verify-email/page.tsx
│   └── reset-password/page.tsx
├── (dashboard)/
│   ├── layout.tsx                    # Sidebar + topbar
│   ├── page.tsx                      # /dashboard ana sayfa
│   ├── search/
│   │   ├── page.tsx                  # /search
│   │   └── [resultId]/page.tsx       # /search/[id]
│   ├── petitions/
│   │   ├── page.tsx                  # Liste
│   │   ├── new/page.tsx              # Yeni dilekçe
│   │   ├── [id]/
│   │   │   ├── page.tsx              # Detay/editör
│   │   │   ├── versions/page.tsx     # Versiyon geçmişi
│   │   │   └── compare/page.tsx      # Diff
│   ├── research/
│   │   ├── page.tsx                  # Oturum listesi
│   │   └── [id]/page.tsx             # Trace görselleştirme
│   ├── chat/
│   │   ├── page.tsx                  # Chat listesi
│   │   └── [id]/page.tsx             # Chat ekranı (SSE)
│   ├── documents/
│   │   ├── page.tsx                  # Liste
│   │   └── [id]/page.tsx             # Detay + search
│   └── settings/
│       ├── profile/page.tsx
│       ├── organization/page.tsx
│       └── api-keys/page.tsx
├── admin/
│   ├── users/page.tsx
│   ├── audit-logs/page.tsx
│   ├── sources/page.tsx
│   └── ai-usage/page.tsx
└── api/                              # API routes (Bölüm 12)""", story)

    H2('14.2 Backend Modülleri', story)
    P("""<b>Next.js API katmanı</b> 6 modülden oluşur: <i>auth</i> (NextAuth config + JWT), <i>cases</i> (case CRUD), <i>legal-search</i> (5 search endpoint), <i>petitions</i> (generate/review/versions/export), <i>research</i> (sessions/traces), <i>documents</i> (upload/parse/search), <i>chat</i> (sessions/messages), <i>admin</i> (users/audit/sources), <i>ai-provider</i> (provider abstraction), <i>embeddings</i> (queue trigger), <i>queue</i> (BullMQ config).""", story)

    P("""<b>Python servis modülleri</b> 5 ana modülden oluşur: (1) <i>engine-wrapper</i> — modülerleştirilmiş engine.py (engine/main.py, engine/llm.py, engine/research.py, engine/petition.py, engine/cleaner.py, engine/citation.py); (2) <i>mcp-adapter</i> — 21 MCP aracının FastAPI router'lara çevrilmesi; (3) <i>quality-engine</i> — quality.py + motor/pipeline.py (sync→threadpool); (4) <i>petition-renderer</i> — WeasyPrint + python-docx + Jinja2; (5) <i>source-connectors</i> — async httpx + Redis rate-limiter.""", story)

    H2('14.3 Shared Modüller', story)
    Bul([
        '<b>types/</b> — TypeScript tip tanımları (User, Case, Petition, Document, LegalDecision, Citation, vb.)',
        '<b>schemas/</b> — Zod input validation şemaları (her API endpoint için request/response)',
        '<b>db/</b> — Prisma schema + client + migration scripts',
        '<b>lib/auth/</b> — JWT utilities, RBAC helpers, session management',
        '<b>lib/ai/</b> — Provider abstraction interface, OpenAI/Gemini/Anthropic/OpenRouter/Ollama implementations',
        '<b>lib/search/</b> — Hybrid search orchestrator, BM25, reranker wrapper',
        '<b>lib/embeddings/</b> — Embedding pipeline, chunking utilities',
        '<b>lib/queue/</b> — BullMQ job definitions (import, source-sync, doc-upload, ai-research)',
    ], story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # BÖLÜM 15 — İLK SPRINT GÖREVLERİ
    # ════════════════════════════════════════════════════════════
    H1('İlk Sprint Görevleri', story, chapter_num=15)

    P("""Sprint 1, migration'ın temelini atan kritik bir sprint'tir. <b>2-3 hafta</b> sürmesi öngörülür ve 8 ana görevden oluşur. Bu sprint'in başarısı, sonraki tüm fazların sağlam bir temel üzerinde inşa edilmesini sağlar.""", story)

    TableStyled(
        [
            [Paragraph('<b>#</b>', S_TABLE_HEADER_C), Paragraph('<b>Görev</b>', S_TABLE_HEADER), Paragraph('<b>Süre</b>', S_TABLE_HEADER_C), Paragraph('<b>Çıktı</b>', S_TABLE_HEADER), Paragraph('<b>Sorumlu</b>', S_TABLE_HEADER_C)],
            [Paragraph('S1.1', S_TABLE_CELL_C), Paragraph('Next.js proje scaffold + Prisma + PostgreSQL kurulumu', S_TABLE_CELL_SMALL), Paragraph('2 gün', S_TABLE_CELL_C), Paragraph('Çalışan Next.js 16 + DB connection', S_TABLE_CELL_SMALL), Paragraph('Frontend', S_TABLE_CELL_C)],
            [Paragraph('S1.2', S_TABLE_CELL_C), Paragraph('DB şema migration (18 tablo, Prisma)', S_TABLE_CELL_SMALL), Paragraph('3 gün', S_TABLE_CELL_C), Paragraph('schema.prisma + migration SQL', S_TABLE_CELL_SMALL), Paragraph('Backend', S_TABLE_CELL_C)],
            [Paragraph('S1.3', S_TABLE_CELL_C), Paragraph('Python engine containerization', S_TABLE_CELL_SMALL), Paragraph('3 gün', S_TABLE_CELL_C), Paragraph('Dockerfile + docker-compose + FastAPI skeleton', S_TABLE_CELL_SMALL), Paragraph('Python', S_TABLE_CELL_C)],
            [Paragraph('S1.4', S_TABLE_CELL_C), Paragraph('Auth temel (email/password + JWT)', S_TABLE_CELL_SMALL), Paragraph('3 gün', S_TABLE_CELL_C), Paragraph('register/login/refresh + RBAC middleware', S_TABLE_CELL_SMALL), Paragraph('Backend', S_TABLE_CELL_C)],
            [Paragraph('S1.5', S_TABLE_CELL_C), Paragraph('Mevcut MCP araçlarının REST\'e çevrilmesi (18/21)', S_TABLE_CELL_SMALL), Paragraph('4 gün', S_TABLE_CELL_C), Paragraph('5 search endpoint + document endpoint', S_TABLE_CELL_SMALL), Paragraph('Python+Backend', S_TABLE_CELL_C)],
            [Paragraph('S1.6', S_TABLE_CELL_C), Paragraph('Temel dashboard UI', S_TABLE_CELL_SMALL), Paragraph('3 gün', S_TABLE_CELL_C), Paragraph('/dashboard sayfası + sidebar + topbar', S_TABLE_CELL_SMALL), Paragraph('Frontend', S_TABLE_CELL_C)],
            [Paragraph('S1.7', S_TABLE_CELL_C), Paragraph('Legal search UI mockup', S_TABLE_CELL_SMALL), Paragraph('2 gün', S_TABLE_CELL_C), Paragraph('/search sayfası (mock data)', S_TABLE_CELL_SMALL), Paragraph('Frontend', S_TABLE_CELL_C)],
            [Paragraph('S1.8', S_TABLE_CELL_C), Paragraph('PDF export (WeasyPrint) iskelet', S_TABLE_CELL_SMALL), Paragraph('2 gün', S_TABLE_CELL_C), Paragraph('/api/petitions/[id]/export-pdf', S_TABLE_CELL_SMALL), Paragraph('Python', S_TABLE_CELL_C)],
        ],
        col_widths=[CONTENT_W * 0.06, CONTENT_W * 0.32, CONTENT_W * 0.10, CONTENT_W * 0.37, CONTENT_W * 0.15],
        story=story,
        caption='Tablo 15.1 — Sprint 1 görevleri (2-3 hafta)'
    )

    H2('15.1 Sprint 2 Önizleme', story)
    P("""<b>Sprint 2</b> (3-4 hafta) odak alanları: (a) Semantic search altyapısı (pgvector + multilingual-e5-large + HNSW index); (b) 9M+ karar import pipeline'ı (async job queue, batch processing, increment indexing); (c) AI provider abstraction (OpenAI/Gemini/Anthropic); (d) Petition generate pipeline (engine.py modülerleştirilmiş hali); (e) Research trace SSE streaming.""", story)

    H2('15.2 Sprint 3 Önizleme', story)
    P("""<b>Sprint 3</b> (3-4 hafta) odak alanları: (a) Hybrid search (BM25+vector+rerank); (b) Query expansion (LLM tabanlı); (c) Document upload + parse + embed; (d) Versiyonlama (petition + statute); (e) DOCX export; (f) Admin panel iskelet; (g) Performance optimization ilk tur.""", story)

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════
    # SONUÇ VE SONRAKİ ADIMLAR
    # ════════════════════════════════════════════════════════════
    H1('Sonuç ve Sonraki Adımlar', story)

    P("""BetterSaul projesi, Türkiye hukuk kaynakları üzerinde çalışan olgun bir regex-tabanlı hukuk AI motorudur. Mevcut sistem <b>mühendislik açısından değerli</b> (17-boyut kalite kontrol, halüsinasyon kontrolü, 21 MCP aracı, 6 hukuk kaynağı entegrasyonu) ancak <b>mimari açısından web ölçeğine uygun değil</b> (tek-kullanıcılı, semantic search yok, desktop-only bağımlılıklar, Qwen-only AI).""", story)

    P("""Migration'ın <b>4 kritik dönüşümü</b>: (1) Semantic search eklenmesi — pgvector + multilingual-e5 + cross-encoder rerank ile; (2) Python motorunun servisleştirilmesi — FastAPI container, mevcut 21 MCP aracının 18'i doğrudan REST'e çevrilir; (3) Çok-kullanıcılı mimari — PostgreSQL 18+ tablo, RBAC, multi-tenant; (4) AI provider abstraction — OpenAI/Gemini/Anthropic/OpenRouter/Ollama tek arayüz altında. Toplam migration süresi <b>5-7 ay</b> (19 faz).""", story)

    H2('Hemen Başlanacak İlk 3 Adım', story)
    Bul([
        '<b>1. Sprint 1 başlat</b>: Next.js scaffold + PostgreSQL + Prisma + Python FastAPI container. Bu rapordaki 18-tablo şemasını Prisma\'ya çevir, Docker Compose ile local dev ortamı kur.',
        '<b>2. engine.py modülerleştir</b>: 7.857 satırlık tek dosyayı 6 modüle böl (main/llm/research/petition/cleaner/citation). Bu, sonraki tüm Python servis çalışmasının temelidir.',
        '<b>3. Semantic search iskelet</b>: pgvector extension kur, multilingual-e5-large embedding pipeline yaz, ilk 100K kararı indexle. Bu, kullanıcıların ilk göreceği "vay be" deneyimini yaratacak özelliktir.',
    ], story)

    H2('Korunması Gereken Değerler (Hatırlatma)', story)
    Bul([
        '<b>quality.py + motor/pipeline.py</b> — 17-boyut regex kalite kontrolü (saf Python, doğrudan taşınabilir)',
        '<b>Halüsinasyon kontrolü</b> — TCKN/tanık/tutar/prompt sızıntısı tespiti (kaynak-karşılaştırma)',
        '<b>21 MCP aracı</b> — 18\'i doğrudan REST\'e çevrilebilir, 3\'ü adaptasyon gerektirir',
        '<b>10 dava türü tespiti</b> — legal_tracks.detect_track() regex sınıflandırıcı',
        '<b>12 dilekçe şablonu</b> — templates.py KINDS sözlüğü + petition_packs.py',
        '<b>6 hukuk kaynağı entegrasyonu</b> — Yargıtay/Danıştay/Emsal/AYM/RG/Mevzuat scraper',
        '<b>Prompt disiplini</b> — system_prompt.txt + petition_prompt.txt (112 satır A-M bölümlü)',
    ], story)

    P("""<b>Hedef ürün</b>: "BetterSaul'un web sitesine çevrilmiş hali" değil; <b>Türkiye hukuk kaynakları üzerinde çalışan AI destekli Legal Research + Legal Intelligence Platform</b>. Modern, özgün, hızlı, kaynak gösteren, semantic search destekli, AI destekli, hukuk araştırmasına odaklı, dilekçe oluşturabilen, milyonlarca belgeyle ölçeklenebilen, güvenli, production-ready.""", story)

    return story


def main():
    output = '/home/z/my-project/scripts/body.pdf'

    doc = TocDocTemplate(
        output,
        pagesize=A4,
        leftMargin=LEFT_M, rightMargin=RIGHT_M,
        topMargin=TOP_M, bottomMargin=BOTTOM_M,
        title='BetterSaul Web Platform Migration — Teknik Analiz Raporu',
        author='Z.ai Migration Team',
        creator='Z.ai',
        subject='BetterSaul mevcut sistem analizi ve Next.js + PostgreSQL migration planı',
    )

    story = build_story()
    doc.multiBuild(story, onFirstPage=header_footer, onLaterPages=header_footer)

    print(f'Body PDF generated: {output}')
    print(f'Pages: {doc.page}')


if __name__ == '__main__':
    main()
