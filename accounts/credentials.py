"""Credential storage is private and must be excluded from backups."""
import io
import secrets
import warnings
from pathlib import Path
from django.conf import settings
from PIL import Image
from pypdf import PdfReader
from rest_framework.exceptions import ValidationError

MAX_SIZE = 5 * 1024 * 1024


def validate_credential(upload):
    if upload.size > MAX_SIZE:
        raise ValidationError({'credential': 'Maximum size is 5 MB.'})
    content = upload.read(MAX_SIZE + 1)
    if not content or len(content) > MAX_SIZE:
        raise ValidationError({'credential': 'Empty file or exceeds 5 MB.'})
    if content.startswith(b'%PDF-'):
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or not len(reader.pages) or len(reader.pages) > 50:
                raise ValueError('Unsupported document')
        except Exception as exc:
            raise ValidationError({'credential': 'Invalid, encrypted or oversized PDF document.'}) from exc
        return content, 'application/pdf', '.pdf'
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {'JPEG', 'PNG'}:
                    raise ValueError('Unsupported photo')
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                image.thumbnail((1600, 1600))
                output = io.BytesIO()
                image.convert('RGB').save(output, 'JPEG', quality=85)
                # Re-encoding strips metadata and untrusted trailing data.
                return output.getvalue(), 'image/jpeg', '.jpg'
    except Exception as exc:
        raise ValidationError({'credential': 'Upload a valid JPEG, PNG or PDF.'}) from exc


def save_credential(content, extension):
    root = Path(settings.PRIVATE_CREDENTIAL_ROOT)
    name = secrets.token_hex(24) + extension
    with (root / name).open('xb') as stream:
        (root / name).chmod(0o600)
        stream.write(content)
    return name


def credential_path(name):
    if not name or Path(name).name != name:
        raise ValidationError('Invalid credential reference.')
    return Path(settings.PRIVATE_CREDENTIAL_ROOT) / name
