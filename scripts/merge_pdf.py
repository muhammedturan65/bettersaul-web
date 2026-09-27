"""Merge cover PDF + body PDF into final deliverable."""
import os
from pypdf import PdfReader, PdfWriter

A4_W, A4_H = 595.28, 841.89  # A4 in points


def normalize_page_to_a4(page):
    """Force scale every page to exact A4 dimensions for consistency."""
    box = page.mediabox
    w, h = float(box.width), float(box.height)
    if abs(w - A4_W) > 0.1 or abs(h - A4_H) > 0.1:
        page.scale_to(A4_W, A4_H)
    return page


def merge(cover_pdf, body_pdf, output_pdf):
    writer = PdfWriter()
    # Cover as page 1
    cover_page = PdfReader(cover_pdf).pages[0]
    writer.add_page(normalize_page_to_a4(cover_page))
    # Body pages follow
    body_reader = PdfReader(body_pdf)
    for page in body_reader.pages:
        writer.add_page(normalize_page_to_a4(page))
    # Metadata
    writer.add_metadata({
        '/Title': 'BetterSaul Web Platform Migration — Teknik Analiz Raporu',
        '/Author': 'Z.ai Migration Team',
        '/Creator': 'Z.ai',
        '/Subject': 'BetterSaul mevcut sistem analizi ve Next.js + PostgreSQL migration planı',
        '/Keywords': 'BetterSaul, Legal Intelligence, MCP, Next.js, PostgreSQL, pgvector, migration, semantic search',
    })
    with open(output_pdf, 'wb') as f:
        writer.write(f)
    print(f'Merged PDF: {output_pdf}')
    print(f'Total pages: {len(writer.pages)}')
    print(f'Size: {os.path.getsize(output_pdf) / 1024:.1f} KB')


if __name__ == '__main__':
    merge(
        '/home/z/my-project/scripts/cover.pdf',
        '/home/z/my-project/scripts/body.pdf',
        '/home/z/my-project/download/BetterSaul_Web_Platform_Migration_Analiz_Raporu.pdf',
    )
