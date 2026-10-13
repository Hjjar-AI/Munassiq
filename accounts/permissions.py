from django.conf import settings
from ipaddress import ip_address, ip_network
from rest_framework.permissions import BasePermission


class Administrator(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.has_role('admin'):
            return False
        if not settings.ADMIN_IP_RESTRICTION:
            return True
        try:
            address = ip_address(request.META.get('REMOTE_ADDR', ''))
            return any(address in ip_network(value) for value in settings.ADMIN_ALLOWED_NETWORKS)
        except ValueError:
            return False


class Reviewer(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and (request.user.has_role('moderator') or request.user.has_role('admin')))


class VerifiedUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_active and request.user.verified_at)
