from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from .models import Session
from .services import digest


class SessionAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b'bearer':
            raise AuthenticationFailed('Invalid authorization header.')
        try:
            token = header[1].decode('ascii')
        except UnicodeDecodeError:
            raise AuthenticationFailed('Invalid access token.')
        session = Session.objects.select_related('user').filter(
            access_hash=digest(token), revoked_at=None,
            access_expires_at__gt=timezone.now(), expires_at__gt=timezone.now()).first()
        if not session or not session.user.is_active:
            raise AuthenticationFailed('Session expired or revoked.')
        return session.user, session

    def authenticate_header(self, request):
        return 'Bearer'


class SessionSchema(OpenApiAuthenticationExtension):
    target_class = 'accounts.authentication.SessionAuthentication'
    name = 'BearerSession'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'description': 'Revocable opaque access token'}
