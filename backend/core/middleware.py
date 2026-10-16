"""Only a configured loopback proxy may supply the client's address."""
from ipaddress import ip_address
from django.conf import settings
from django.http import HttpResponseBadRequest


class ClientAddressMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.TRUST_LOCAL_PROXY:
            try:
                peer = ip_address(request.META.get('REMOTE_ADDR', ''))
                if not peer.is_loopback:
                    return HttpResponseBadRequest('Local proxy required.')
                if peer.is_loopback:
                    address = ip_address(request.META.get('HTTP_X_REAL_IP', ''))
                    request.META['REMOTE_ADDR'] = str(address)
            except ValueError:
                return HttpResponseBadRequest('Invalid proxy address.')
        return self.get_response(request)
