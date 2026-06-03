from __future__ import annotations

from html import escape

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


def wants_html(request: HttpRequest) -> bool:
    accept = request.headers.get("Accept", "")
    content_type = request.headers.get("Content-Type", "")
    return request.method == "GET" or ("text/html" in accept and "application/json" not in content_type)


def login_page(message: str = "", status: int = 200) -> HttpResponse:
    escaped_message = escape(message)
    message_html = f'<p class="error">{escaped_message}</p>' if escaped_message else ""
    html = f"""<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevLink Login</title>
  <style>
    :root {{
      color-scheme: dark;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0a0a0a;
      color: #f0f0f0;
    }}
    body {{
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      background: radial-gradient(circle at 50% 0%, #181818 0, #0a0a0a 46%);
    }}
    main {{
      width: min(420px, 100%);
      border: 1px solid #2a2a2a;
      border-radius: 16px;
      background: #111;
      padding: 24px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
    }}
    p {{
      color: #a0a0a0;
      line-height: 1.5;
      margin: 0 0 18px;
    }}
    label {{
      display: block;
      color: #a0a0a0;
      font-size: 13px;
      margin: 14px 0 6px;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #2a2a2a;
      border-radius: 10px;
      background: #181818;
      color: #f0f0f0;
      font: inherit;
      padding: 12px;
    }}
    button {{
      width: 100%;
      margin-top: 18px;
      border: 0;
      border-radius: 10px;
      padding: 12px 14px;
      background: #f0f0f0;
      color: #0a0a0a;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    code {{
      color: #e2e8f0;
      background: #181818;
      border: 1px solid #2a2a2a;
      border-radius: 6px;
      padding: 2px 5px;
    }}
    .error {{
      color: #fca5a5;
      background: #2d1515;
      border: 1px solid #5a1414;
      border-radius: 10px;
      padding: 10px 12px;
      margin-bottom: 14px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>DevLink Backend</h1>
    <p>Panel logowania API. Aplikacja mobilna dalej uzywa JSON pod <code>/api/auth/login/</code>.</p>
    {message_html}
    <form method="post">
      <label for="username">Username</label>
      <input id="username" name="username" autocomplete="username" required>
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
      <button type="submit">Login</button>
    </form>
  </main>
</body>
</html>"""
    return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")


@csrf_exempt
def token_obtain_pair(request: HttpRequest):
    if not wants_html(request):
        return TokenObtainPairView.as_view()(request)

    if request.method == "GET":
        return login_page()

    serializer = TokenObtainPairSerializer(data=request.POST)
    if not serializer.is_valid():
        return login_page("Nieprawidlowy login albo haslo.", status=400)

    return login_page("Logowanie poprawne. W aplikacji mobilnej token zostanie obsluzony przez JSON API.")
