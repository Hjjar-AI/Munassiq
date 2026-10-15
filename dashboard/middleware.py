from django.conf import settings
from django.utils import timezone, translation
from accounts.models import Session
from accounts.services import digest, refresh
from rest_framework.exceptions import APIException

ACCESS = 'munassiq_access'
REFRESH = 'munassiq_refresh'


def put_tokens(response, tokens):
    options = dict(httponly=True, secure=not settings.DEBUG, samesite='Lax', path='/')
    response.set_cookie(ACCESS, tokens['access_token'], max_age=tokens['expires_in'], **options)
    response.set_cookie(REFRESH, tokens['refresh_token'], max_age=settings.SESSION_DAYS*86400, **options)


def clear_tokens(response):
    response.delete_cookie(ACCESS, path='/', samesite='Lax')
    response.delete_cookie(REFRESH, path='/', samesite='Lax')


class DashboardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # API routes continue to accept bearer headers only, never ambient cookies.
        if request.path.startswith('/api/') or request.path.startswith('/static/'):
            return self.get_response(request)
        request.dashboard_access = request.COOKIES.get(ACCESS, '')
        request.dashboard_user = None
        rotated = None
        if request.dashboard_access:
            session = Session.objects.select_related('user').filter(
                access_hash=digest(request.dashboard_access), revoked_at=None,
                access_expires_at__gt=timezone.now(), expires_at__gt=timezone.now(), user__is_active=True).first()
            if session:
                request.dashboard_user = session.user
        if not request.dashboard_user and request.COOKIES.get(REFRESH):
            try:
                rotated = refresh(request.COOKIES[REFRESH])
            except APIException:
                request.dashboard_access = ''
            else:
                request.dashboard_access = rotated['access_token']
                request.dashboard_user = Session.objects.select_related('user').get(access_hash=digest(request.dashboard_access)).user
        if not request.dashboard_user:
            request.dashboard_access = ''
        language = request.COOKIES.get('munassiq_language')
        if language not in ('ar', 'en'):
            language = request.dashboard_user.language if request.dashboard_user else 'ar'
        request.dashboard_language = language
        with translation.override(language):
            response = self.get_response(request)
        if rotated and not getattr(response, 'dashboard_tokens_handled', False):
            put_tokens(response, rotated)
        for key,morsel in getattr(request,'dashboard_api_cookies',{}).items():
            response.cookies[key]=morsel
        response['Cache-Control'] = 'no-store'
        response.setdefault('Referrer-Policy', 'same-origin')
        response['X-Content-Type-Options'] = 'nosniff'
        return response
