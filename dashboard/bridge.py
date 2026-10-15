"""Call existing REST views locally; never expose browser tokens to JavaScript."""
from uuid import uuid4
from django.http import HttpRequest, QueryDict
from django.urls import resolve
from rest_framework.renderers import JSONRenderer


def call(request, path, method='GET', data=None, files=None):
    # Paths are selected exclusively by dashboard code, never a browser-supplied URL.
    if not path.startswith('/api/v1/'):
        raise ValueError('Only the local API may be called')
    child = HttpRequest()
    child.method = method
    child._read_started = False
    child.path = child.path_info = path.split('?')[0]
    child.GET = QueryDict(path.partition('?')[2])
    child.COOKIES = request.COOKIES.copy()
    child.META = {key: value for key, value in request.META.items()
        if key in ('REMOTE_ADDR', 'HTTP_HOST', 'SERVER_NAME', 'SERVER_PORT', 'wsgi.url_scheme', 'HTTP_ACCEPT_LANGUAGE')}
    child.META['HTTP_ACCEPT'] = 'application/json'
    token = getattr(request, 'dashboard_access', '')
    if token:
        child.META['HTTP_AUTHORIZATION'] = 'Bearer '+token
    if files:
        boundary = 'Munassiq'+uuid4().hex
        parts = []
        for name, value in (data or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, upload in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="upload"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+upload.read()+b'\r\n')
        child._body = b''.join(parts)+f'--{boundary}--\r\n'.encode()
        child.META['CONTENT_TYPE'] = 'multipart/form-data; boundary='+boundary
    else:
        child._body = JSONRenderer().render(data or {})
        child.META['CONTENT_TYPE'] = 'application/json'
    child.META['CONTENT_LENGTH'] = str(len(child._body))
    from io import BytesIO
    child._stream = BytesIO(child._body)
    match = resolve(child.path_info)
    response = match.func(child, *match.args, **match.kwargs)
    if not hasattr(request,'dashboard_api_cookies'):
        request.dashboard_api_cookies={}
    for key,morsel in response.cookies.items():
        request.dashboard_api_cookies[key]=morsel
        request.COOKIES[key]=morsel.value
    return response


def values(response):
    return getattr(response, 'data', None)
