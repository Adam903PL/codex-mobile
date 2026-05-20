from __future__ import annotations

from rest_framework.views import exception_handler

from .dev_logs import record_api_error


def devlink_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = getattr(exc, "default_code", "error")
    message = "Wystąpił błąd."
    details = response.data

    if isinstance(response.data, dict):
        detail = response.data.get("detail")
        if detail:
            message = str(detail)
        else:
            message = _first_error_message(response.data) or message
    elif response.data:
        message = str(response.data)

    response.data = {
        "code": str(code).upper(),
        "message": _public_message(str(code).upper(), message),
        "details": details,
        "request_id": context["request"].headers.get("X-Request-ID", ""),
    }
    record_api_error(context.get("request"), response.status_code, response.data)
    return response


def _public_message(code: str, message: str) -> str:
    token_markers = ("TOKEN_NOT_VALID", "token_not_valid", "Given token not valid")
    if code == "TOKEN_NOT_VALID" or any(marker in message for marker in token_markers):
        return "Sesja wygasla. Zaloguj sie ponownie."
    return message


def _first_error_message(value):
    if isinstance(value, dict):
        for item in value.values():
            message = _first_error_message(item)
            if message:
                return message
    if isinstance(value, list):
        for item in value:
            message = _first_error_message(item)
            if message:
                return message
    if value:
        return str(value)
    return ""
