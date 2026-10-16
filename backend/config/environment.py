"""Strict environment parsing; configuration errors stop startup."""
import os
from django.core.exceptions import ImproperlyConfigured


def boolean(name, default=False):
    value = os.environ.get(name, str(default)).strip().lower()
    if value not in {"true", "false"}:
        raise ImproperlyConfigured(f"{name} must be true or false")
    return value == "true"


def csv(name, default=""):
    return [part.strip() for part in os.environ.get(name, default).split(",") if part.strip()]


def positive_integer(name, default):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ImproperlyConfigured(f"{name} must be a positive integer")
    return value
