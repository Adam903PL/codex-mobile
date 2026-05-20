from __future__ import annotations

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import Device, hash_device_token


class DeviceTokenAuthentication(BaseAuthentication):
    keyword = b"Device"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header or header[0] != self.keyword:
            return None
        if len(header) != 2:
            raise AuthenticationFailed("Niepoprawny nagłówek autoryzacji urządzenia.")

        token = header[1].decode("utf-8")
        token_hash = hash_device_token(token)

        try:
            device = Device.objects.select_related("owner").get(token_hash=token_hash)
        except Device.DoesNotExist as exc:
            raise AuthenticationFailed("Nieprawidłowy token urządzenia.") from exc

        if device.status == Device.Status.REVOKED:
            raise AuthenticationFailed("Urządzenie zostało odłączone.")

        return (device.owner, device)

