from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir
from pydantic import BaseModel, Field

APP_NAME = "devlink"
SERVICE_NAME = "devlink-cli"


class DevLinkConfig(BaseModel):
    api_url: str = "http://192.168.0.238:8000/api"
    device_id: str | None = None
    device_token_fallback: str | None = Field(default=None, repr=False)
    last_device_status: str | None = None
    last_heartbeat_at: str | None = None

    @property
    def is_paired(self) -> bool:
        return bool(self.device_id and self.get_device_token())

    def get_device_token(self) -> str | None:
        token = read_keyring_token(self.device_id) if self.device_id else None
        return token or self.device_token_fallback


def config_path() -> Path:
    root = Path(user_config_dir(APP_NAME))
    root.mkdir(parents=True, exist_ok=True)
    return root / "config.json"


def load_config() -> DevLinkConfig:
    path = config_path()
    if not path.exists():
        return DevLinkConfig()
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    return DevLinkConfig.model_validate(data)


def save_config(config: DevLinkConfig) -> None:
    path = config_path()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def store_device_token(device_id: str, token: str, config: DevLinkConfig) -> DevLinkConfig:
    if write_keyring_token(device_id, token):
        config.device_token_fallback = None
    else:
        config.device_token_fallback = token
    config.device_id = device_id
    save_config(config)
    return config


def clear_config() -> None:
    config = load_config()
    if config.device_id:
        delete_keyring_token(config.device_id)
    path = config_path()
    if path.exists():
        path.unlink()


def read_keyring_token(device_id: str | None) -> str | None:
    if not device_id:
        return None
    try:
        import keyring

        return keyring.get_password(SERVICE_NAME, device_id)
    except Exception:
        return None


def write_keyring_token(device_id: str, token: str) -> bool:
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, device_id, token)
        return True
    except Exception:
        return False


def delete_keyring_token(device_id: str) -> None:
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, device_id)
    except Exception:
        return
