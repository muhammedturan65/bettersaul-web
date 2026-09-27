"""Convert diagram PDFs to PNGs for ReportLab embedding."""
import pypdfium2 as pdfium
import os

for name in ['current_arch', 'proposed_arch']:
    pdf_path = f'/home/z/my-project/scripts/diagrams/{name}.pdf'
    png_path = f'/home/z/my-project/scripts/diagrams/{name}.png'
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[0]
    # 2x scale for print quality
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil()
    pil_image.save(png_path, 'PNG', optimize=True)
    print(f'{name}: {pil_image.size[0]}x{pil_image.size[1]} -> {png_path}')
    pdf.close()
