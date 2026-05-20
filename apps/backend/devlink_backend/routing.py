from django.urls import re_path

from sessions.consumers import SessionTimelineConsumer
from terminals.consumers import TerminalConsumer

websocket_urlpatterns = [
    re_path(r"^ws/sessions/(?P<session_id>[0-9a-f-]+)/$", SessionTimelineConsumer.as_asgi()),
    re_path(r"^ws/terminal/(?P<terminal_id>[0-9a-f-]+)/$", TerminalConsumer.as_asgi()),
]
