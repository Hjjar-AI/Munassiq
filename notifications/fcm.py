"""FCM HTTP v1 adapter. Never logs credentials, registration tokens or responses."""
from django.conf import settings


class PushError(Exception):
    def __init__(self, code, retryable=False, retry_after=0):
        self.code, self.retryable, self.retry_after = code, retryable, retry_after
        super().__init__(code)


class Sender:
    def __init__(self):
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        import requests

        class BoundedRequest(Request):
            def __call__(self, *args, **kwargs):
                kwargs['timeout'] = 10
                return super().__call__(*args, **kwargs)

        self.credentials = service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_FILE,
            scopes=['https://www.googleapis.com/auth/firebase.messaging'])
        self.auth_request = BoundedRequest()
        self.session = requests.Session()

    def send(self, message):
        try:
            if not self.credentials.valid:
                self.credentials.refresh(self.auth_request)
            response = self.session.post(
                f'https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send',
                headers={'Authorization': 'Bearer '+self.credentials.token},
                json={'message': message}, timeout=10, allow_redirects=False)
        except Exception:
            raise PushError('transport', retryable=True) from None
        if response.status_code == 200:
            return
        try:
            details = response.json().get('error', {}).get('details', [])
            codes = [row.get('errorCode') for row in details if row.get('@type') == 'type.googleapis.com/google.firebase.fcm.v1.FcmError']
        except (ValueError, AttributeError, TypeError):
            codes = []
        if 'UNREGISTERED' in codes:
            raise PushError('unregistered')
        try:
            delay = min(86400, max(0, int(response.headers.get('Retry-After', 0))))
        except ValueError:
            delay = 60
        if response.status_code in (401, 403, 429) or response.status_code >= 500:
            raise PushError('provider_retry', retryable=True, retry_after=delay)
        raise PushError('provider_rejected')
