"""Private registrant exports with Unicode/Arabic support and CSV formula protection."""
import csv
import io
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from .models import Registration
from .services import is_reviewer


def require_registrant_access(actor, occurrence):
    if actor.has_role('admin') or (actor.has_role('organizer') and occurrence.event.owner_id == actor.pk):
        return
    owner = occurrence.event.owner
    stewardship = owner is None or not owner.is_active or not owner.has_role('organizer')
    if is_reviewer(actor) and stewardship:
        return
    raise PermissionDenied('Only the organizer, admin or authorized steward can access registrants.')


def registrants(occurrence, state=None):
    states = ['registered', 'pending_reconfirm']
    if state is not None:
        if state not in ['registered', 'pending_reconfirm', 'waitlisted']:
            raise ValidationError({'state': 'Choose registered, pending_reconfirm or waitlisted.'})
        states = [state]
    return Registration.objects.filter(occurrence=occurrence, state__in=states).select_related('user').order_by('queued_at', 'pk')


def safe_csv(value):
    # Spreadsheets must treat user-supplied names/emails as text, never formulas.
    return "'"+value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def export_csv(rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['name', 'email'])
    for row in rows:
        writer.writerow([safe_csv(row.user.name), safe_csv(row.user.email)])
    response = HttpResponse('\ufeff'+stream.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="registrants.csv"'
    response['Cache-Control'] = 'no-store'
    return response


def export_pdf(rows):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from bidi.algorithm import get_display
    import arabic_reshaper
    font_path = Path(settings.EXPORT_FONT_PATH) if settings.EXPORT_FONT_PATH else None
    if not font_path or not font_path.is_file():
        error = APIException('Configure EXPORT_FONT_PATH with an Arabic-capable TrueType font before PDF export.')
        error.status_code = 503
        raise error
    # Font names include the configured path so a deployment change cannot reuse a stale font.
    import hashlib
    font_name = 'Directory-'+hashlib.sha256(str(font_path).encode()).hexdigest()[:16]
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    stream = io.BytesIO()
    document = canvas.Canvas(stream, pagesize=(595, 842))
    document.setTitle('Munassiq registrants')

    def header():
        document.setFont(font_name, 12)
        document.drawString(36, 800, 'Munassiq / '+get_display(arabic_reshaper.reshape('المسجلون')))

    def wrapped(value, max_width=520):
        line = ''
        for char in value:
            candidate = line+char
            shaped = get_display(arabic_reshaper.reshape(candidate))
            if line and pdfmetrics.stringWidth(shaped, font_name, 11) > max_width:
                yield get_display(arabic_reshaper.reshape(line))
                line = char
            else:
                line = candidate
        if line:
            yield get_display(arabic_reshaper.reshape(line))

    header()
    y = 770
    for row in rows:
        for value in (row.user.name, row.user.email):
            for line in wrapped(value):
                if y < 50:
                    document.showPage()
                    header()
                    y = 770
                document.setFont(font_name, 11)
                document.drawString(36, y, line)
                y -= 16
        y -= 10
    document.save()
    response = HttpResponse(stream.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="registrants.pdf"'
    response['Cache-Control'] = 'no-store'
    return response
