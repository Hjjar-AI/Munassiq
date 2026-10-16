"""Validate and store directory media; no private credential files are served here."""
import io
import secrets
import warnings
from pathlib import Path
from django.conf import settings
from PIL import Image, ImageOps
from pypdf import PdfReader
from rest_framework.exceptions import ValidationError
from .models import Asset


def path_for(asset):
    if Path(asset.name).name != asset.name:
        raise ValidationError('Invalid file reference.')
    return Path(settings.MEDIA_ROOT)/asset.name


def store(actor, upload, kind):
    if upload.size > 5*1024*1024:
        raise ValidationError('Maximum upload size is 5 MB.')
    content = upload.read(5*1024*1024+1)
    if not content or len(content) > 5*1024*1024:
        raise ValidationError('Empty or oversized file.')
    if kind == 'image':
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as image:
                    if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                        raise ValueError('Unsupported image')
                    image.verify()
                with Image.open(io.BytesIO(content)) as image:
                    image.load()
                    image = ImageOps.exif_transpose(image)
                    image = image.convert('RGB')
                    image.thumbnail((1600, 1600))
                    # Bound the final stored file even for noisy photographs.
                    while True:
                        stream = io.BytesIO()
                        image.save(stream, 'JPEG', quality=80)
                        if stream.tell() <= 1024*1024:
                            content = stream.getvalue()
                            break
                        image.thumbnail((max(1, image.width*3//4), max(1, image.height*3//4)))
            suffix, mime = '.jpg', 'image/jpeg'
        except Exception as exc:
            raise ValidationError('Upload a valid JPEG, PNG or WEBP image.') from exc
    else:
        try:
            if not content.startswith(b'%PDF-'):
                raise ValueError('Not PDF')
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or not len(reader.pages):
                raise ValueError('Unsupported PDF')
        except Exception as exc:
            raise ValidationError('Upload a valid, unencrypted PDF.') from exc
        suffix, mime = '.pdf', 'application/pdf'
    name = secrets.token_hex(24)+suffix
    path = Path(settings.MEDIA_ROOT)/name
    try:
        with path.open('xb') as stream:
            path.chmod(0o600)
            stream.write(content)
        return Asset.objects.create(owner=actor, name=name, kind=kind, content_type=mime, size=len(content))
    except Exception:
        path.unlink(missing_ok=True)
        raise
