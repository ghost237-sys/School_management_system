from io import BytesIO
from django.http import HttpResponse


def pdf_response_from_rows(filename: str, title: str, header_rows: list[list[str]], columns: list[str], rows: list[list[str]], landscape_mode: bool = True) -> HttpResponse:
    """Generate a simple PDF table response.

    Lazy-imports reportlab to avoid crashing app startup when the dependency
    is missing. If reportlab is unavailable, returns a 500 response with a
    helpful message instead of raising ImportError during URL import.
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape  # type: ignore
        from reportlab.lib import colors  # type: ignore
        from reportlab.lib.styles import getSampleStyleSheet  # type: ignore
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle  # type: ignore
    except Exception:
        resp = HttpResponse(
            "PDF generation is unavailable: 'reportlab' is not installed. Please install it (pip install reportlab).",
            content_type='text/plain',
            status=500,
        )
        return resp

    buffer = BytesIO()
    pagesize = landscape(A4) if landscape_mode else A4
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = []

    # Header block (school info)
    for line in header_rows or []:
        if not line:
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(str(line[0]), styles['Heading4']))
    if header_rows:
        story.append(Spacer(1, 6))

    # Title
    if title:
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 10))

    # Build table data
    data = [columns] + rows

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#111827')),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d1d5db')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
    ]))

    story.append(table)

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    resp.write(pdf)
    return resp
