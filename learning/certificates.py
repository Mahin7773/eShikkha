import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from core.models import PlatformSettings


def _fit_font(c, text, font, max_size, max_width, min_size=14):
    size = max_size
    while size > min_size and c.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _draw_logo_mark(c, x, y, size):
    # same shapes as static/img/logo-mark.svg
    s = size / 32.0

    def pt(px, py):  # SVG coords (y down) -> PDF coords (y up)
        return x + px * s, y + (32 - py) * s

    c.saveState()
    c.setFillColor(colors.HexColor('#12564a'))
    c.roundRect(x, y, size, size, 9 * s, stroke=0, fill=1)
    c.setFillColor(colors.HexColor('#f2a477'))
    c.circle(*pt(16, 8), 2.4 * s, stroke=0, fill=1)
    for color, pts in (('#ffffff', [(5.5, 13.2), (15.5, 14), (15.5, 25), (5.5, 24.2)]),
                       ('#cfe5dd', [(26.5, 13.2), (16.5, 14), (16.5, 25), (26.5, 24.2)])):
        path = c.beginPath()
        path.moveTo(*pt(*pts[0]))
        for p in pts[1:]:
            path.lineTo(*pt(*p))
        path.close()
        c.setFillColor(colors.HexColor(color))
        c.drawPath(path, stroke=0, fill=1)
    c.restoreState()


def render_certificate_pdf(certificate, verify_url):
    settings = PlatformSettings.load()
    accent = colors.HexColor(settings.certificate_accent_color)
    ink = colors.HexColor('#1d2433')
    muted = colors.HexColor('#5b6475')

    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setTitle(f'{settings.certificate_title} - {certificate.course_title}')
    c.setAuthor(settings.site_name)

    c.setFillColor(colors.HexColor('#fbfaf7'))
    c.rect(0, 0, width, height, stroke=0, fill=1)
    c.setStrokeColor(accent)
    c.setLineWidth(6)
    c.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    c.setLineWidth(0.8)
    c.rect(16 * mm, 16 * mm, width - 32 * mm, height - 32 * mm)

    cx = width / 2
    _draw_logo_mark(c, cx - 7 * mm, height - 33 * mm, 14 * mm)
    c.setFillColor(accent)
    c.setFont('Helvetica-Bold', 20)
    c.drawCentredString(cx, height - 40 * mm, settings.site_name)
    c.setFillColor(muted)
    c.setFont('Helvetica', 10)
    c.drawCentredString(cx, height - 46 * mm, settings.tagline)

    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 30)
    c.drawCentredString(cx, height - 66 * mm, settings.certificate_title.upper())

    c.setFillColor(muted)
    c.setFont('Helvetica', 13)
    c.drawCentredString(cx, height - 80 * mm, 'This is to certify that')

    c.setFillColor(ink)
    name_size = _fit_font(c, certificate.student_name, 'Helvetica-Bold', 34, width - 80 * mm)
    c.setFont('Helvetica-Bold', name_size)
    c.drawCentredString(cx, height - 96 * mm, certificate.student_name)
    c.setStrokeColor(accent)
    c.setLineWidth(1)
    c.line(cx - 80 * mm, height - 100 * mm, cx + 80 * mm, height - 100 * mm)

    c.setFillColor(muted)
    c.setFont('Helvetica', 13)
    c.drawCentredString(cx, height - 112 * mm, 'has successfully completed the course')
    c.setFillColor(ink)
    title_size = _fit_font(c, certificate.course_title, 'Helvetica-Bold', 22, width - 80 * mm, 12)
    c.setFont('Helvetica-Bold', title_size)
    c.drawCentredString(cx, height - 124 * mm, certificate.course_title)
    c.setFillColor(muted)
    c.setFont('Helvetica', 12)
    c.drawCentredString(cx, height - 133 * mm, f'taught by {certificate.instructor_name}')

    # footer
    base = 34 * mm
    left = 40 * mm
    c.setFillColor(ink)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(left, base + 6 * mm, certificate.issued_at.strftime('%d %B %Y'))
    c.setStrokeColor(muted)
    c.line(left, base + 4 * mm, left + 60 * mm, base + 4 * mm)
    c.setFont('Helvetica', 9)
    c.setFillColor(muted)
    c.drawString(left, base, 'Date of issue')

    sig_x = cx - 30 * mm
    c.setFillColor(ink)
    c.setFont('Helvetica-Oblique', 13)
    c.drawCentredString(sig_x + 30 * mm, base + 6 * mm, settings.certificate_signatory_name)
    c.line(sig_x, base + 4 * mm, sig_x + 60 * mm, base + 4 * mm)
    c.setFont('Helvetica', 9)
    c.setFillColor(muted)
    c.drawCentredString(sig_x + 30 * mm, base, settings.certificate_signatory_title)

    c.setFont('Helvetica', 8.5)
    c.drawCentredString(cx, 21 * mm, f'Certificate ID: {certificate.certificate_number}   ·   Verify at {verify_url}')

    if settings.certificate_show_qr:
        try:
            import qrcode
            from reportlab.lib.utils import ImageReader

            img = qrcode.make(verify_url, box_size=6, border=1)
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            size = 30 * mm
            c.drawImage(ImageReader(img_buffer), width - 40 * mm - size, base - 4 * mm, size, size)
        except ImportError:
            pass  # qrcode is optional; the verification URL is still printed

    c.showPage()
    c.save()
    return buffer.getvalue()
