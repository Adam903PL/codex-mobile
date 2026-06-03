from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

IGNORED_FILE_INDEX_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    "out",
    "coverage",
    ".expo",
    ".turbo",
    ".cache",
    "target",
    "__pycache__",
}

def codex_available() -> bool:
    return shutil.which("codex") is not None


def codex_login_status() -> str:
    result = _run_codex(["login", "status"])
    if result is None:
        return "unable to check"
    output = (result.stdout or result.stderr).strip()
    return output or f"exit code {result.returncode}"


def is_git_repository(project_path: str) -> bool:
    git_marker = Path(project_path) / ".git"
    return git_marker.is_dir() or git_marker.is_file()


def codex_command_preview(project_path: str) -> list[str]:
    return ["codex", "exec", "--cd", project_path, "--json", "--sandbox", "workspace-write", "-"]


def collect_capabilities(projects: list[dict[str, Any]] | None = None, probe_usage_limits: bool = False) -> dict[str, Any]:
    version = codex_version()
    models_raw = codex_debug_models()
    models = parse_models(models_raw)
    mcp_raw = codex_mcp_list()
    features_raw = codex_features_list()
    config = read_codex_config()
    plugin_inventory = discover_plugins()
    usage_limits = latest_codex_usage_limits()
    diagnostics_payload = diagnostics(version)
    diagnostics_payload["models_count"] = len(models)
    if not models:
        diagnostics_payload["models_error"] = "codex debug models returned no parseable models"
        diagnostics_payload["models_raw_preview"] = models_raw[:500]
    if probe_usage_limits and usage_limits_missing_or_stale(usage_limits):
        probed_usage_limits = probe_codex_usage_limits(projects or [])
        if probed_usage_limits:
            probed_usage_limits["stale"] = False
            usage_limits = probed_usage_limits
        else:
            diagnostics_payload["usage_limits_error"] = "codex usage probe returned no rate_limits"
            diagnostics_payload["usage_limits_probe_at"] = datetime.now(timezone.utc).isoformat()
    if usage_limits:
        diagnostics_payload["usage_limits_source"] = str(usage_limits.get("source") or "")
    return {
        "codex": {
            "available": codex_available(),
            "version": version,
            "login_status": codex_login_status() if version else "",
        },
        "cli_commands": codex_command_capabilities(),
        "models": models,
        "models_raw": models_raw,
        "model_context_windows": model_context_windows(models_raw),
        "mcp": {"raw": mcp_raw},
        "mcp_servers": parse_mcp_servers(mcp_raw),
        "features": parse_features(features_raw),
        "features_raw": features_raw,
        "profiles": sorted((config.get("profiles") or {}).keys()) if isinstance(config.get("profiles"), dict) else [],
        "config_summary": summarize_config(config),
        "plugin_marketplaces": plugin_inventory["marketplaces"],
        "installed_plugins": plugin_inventory["plugins"],
        "plugins": plugin_inventory["plugins"],
        "slash_commands": slash_command_capabilities(),
        "codex_sessions": codex_sessions(),
        "codex_usage_limits": usage_limits,
        "diagnostics": diagnostics_payload,
        "skills": discover_codex_skills(),
        "project_git": collect_project_git(projects or []),
        "project_files": collect_project_files(projects or []),
        "platform": platform.platform(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def codex_version() -> str:
    result = _run_codex(["--version"])
    if result is None:
        return ""
    return (result.stdout or result.stderr).strip()


def codex_command_capabilities() -> list[dict[str, str]]:
    result = _run_codex(["--help"])
    raw = _combined_output(result)
    known = [
        "exec", "review", "login", "logout", "mcp", "plugin", "mcp-server", "app-server",
        "remote-control", "app", "completion", "update", "sandbox", "debug", "apply",
        "resume", "fork", "cloud", "exec-server", "features", "help",
    ]
    commands: list[dict[str, str]] = []
    for name in known:
        if name in raw:
            commands.append({"id": f"codex.{name}", "name": name, "source": "codex --help"})
    return commands


def codex_debug_models() -> str:
    result = _run_codex(["debug", "models"])
    return _combined_output(result)


def codex_mcp_list() -> str:
    result = _run_codex(["mcp", "list", "--json"])
    return _combined_output(result)


def codex_features_list() -> str:
    result = _run_codex(["features", "list"])
    return _combined_output(result)


def codex_plugin_marketplaces() -> str:
    result = _run_codex(["plugin", "marketplace", "list"])
    return _combined_output(result)


def normalize_codex_usage_limits(value: Any, source: str = "live_event") -> dict[str, Any]:
    rate_limits = _find_rate_limits(value)
    if not isinstance(rate_limits, dict):
        return {}

    five_hour = _normalize_usage_window(rate_limits.get("primary"), "five_hour", source)
    weekly = _normalize_usage_window(rate_limits.get("secondary"), "weekly", source)
    if not five_hour and not weekly:
        return {}

    observed_at = datetime.now(timezone.utc).isoformat()
    normalized: dict[str, Any] = {
        "source": source,
        "observed_at": observed_at,
        "plan_type": rate_limits.get("plan_type") or "",
        "rate_limit_reached_type": rate_limits.get("rate_limit_reached_type"),
    }
    if five_hour:
        normalized["five_hour"] = five_hour
    if weekly:
        normalized["weekly"] = weekly
    return normalized


def latest_codex_usage_limits(max_files: int = 80) -> dict[str, Any]:
    files = _recent_codex_session_files(max_files=max_files)
    newest: tuple[datetime, dict[str, Any]] | None = None
    for path in files:
        for line in _read_lines_reverse(path):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage_limits = normalize_codex_usage_limits(event, source="session_file")
            if not usage_limits:
                continue
            observed_at = _timestamp_from_event(event) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            usage_limits["observed_at"] = observed_at.isoformat()
            usage_limits["stale"] = usage_limits_missing_or_stale(usage_limits)
            if newest is None or observed_at > newest[0]:
                newest = (observed_at, usage_limits)
            break
    return newest[1] if newest else {}


def usage_limits_missing_or_stale(usage_limits: dict[str, Any] | None, max_age_minutes: int = 1) -> bool:
    if not usage_limits or not usage_limits.get("five_hour") or not usage_limits.get("weekly"):
        return True
    observed_at = _parse_datetime(str(usage_limits.get("observed_at") or ""))
    if not observed_at:
        return True
    return datetime.now(timezone.utc) - observed_at > timedelta(minutes=max_age_minutes)


def probe_codex_usage_limits(projects: list[dict[str, Any]]) -> dict[str, Any]:
    project_path = _probe_project_path(projects)
    if not project_path:
        return {}
    result = _run_codex(
        [
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "--cd",
            project_path,
            "Reply exactly: ok",
        ],
        timeout=90,
    )
    raw = _combined_output(result)
    newest: dict[str, Any] = {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage_limits = normalize_codex_usage_limits(event, source="probe")
        if usage_limits:
            newest = usage_limits
    return newest


def _find_rate_limits(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        candidate = value.get("rate_limits")
        if isinstance(candidate, dict):
            return candidate
        for nested in value.values():
            found = _find_rate_limits(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_rate_limits(item)
            if found:
                return found
    return None


def _normalize_usage_window(value: Any, label: str, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    used_percent = _number(value.get("used_percent"))
    window_minutes = _number(value.get("window_minutes"))
    resets_at = _timestamp_to_iso(value.get("resets_at"))
    if used_percent is None and window_minutes is None and not resets_at:
        return {}
    normalized = {
        "used_percent": max(0.0, min(100.0, float(used_percent or 0.0))),
        "remaining_percent": max(0.0, min(100.0, 100.0 - float(used_percent or 0.0))),
        "window_minutes": int(window_minutes or (300 if label == "five_hour" else 10080)),
        "resets_at": resets_at,
        "source": source,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    return normalized


def _recent_codex_session_files(max_files: int = 80) -> list[Path]:
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    roots = [home / "sessions", home / "archived_sessions"]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*.jsonl") if path.is_file())
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:max_files]


def _read_lines_reverse(path: Path, max_lines: int = 500) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return list(reversed(lines[-max_lines:]))


def _timestamp_from_event(event: dict[str, Any]) -> datetime | None:
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        return None
    return _parse_datetime(timestamp)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_to_iso(value: Any) -> str:
    numeric = _number(value)
    if numeric is None:
        return ""
    try:
        return datetime.fromtimestamp(float(numeric), tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _probe_project_path(projects: list[dict[str, Any]]) -> str:
    for project in projects:
        path = str(project.get("local_path") or "")
        if path and Path(path).exists():
            return path
    return str(Path.cwd())


def parse_models(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    parsed: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        slug = str(model.get("slug") or "").strip()
        if not slug:
            continue
        parsed.append(
            {
                "id": slug,
                "name": str(model.get("display_name") or slug),
                "description": str(model.get("description") or ""),
                "default_reasoning_level": str(model.get("default_reasoning_level") or ""),
                "supported_reasoning_levels": model.get("supported_reasoning_levels") or [],
                "context_window": _model_context_window(model),
            }
        )
    return parsed


def model_context_windows(raw: str) -> dict[str, int]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return {}
    windows: dict[str, int] = {}
    for model in models:
        if not isinstance(model, dict):
            continue
        slug = str(model.get("slug") or model.get("id") or "").strip()
        window = _model_context_window(model)
        if slug and window:
            windows[slug] = window
    return windows


def _model_context_window(model: dict[str, Any]) -> int:
    for key in ("context_window", "context_window_tokens", "max_context_tokens", "max_context_window"):
        value = model.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def parse_lines(raw: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in raw.splitlines():
        text = line.strip()
        if text:
            items.append({"id": text, "name": text})
    return items


def parse_mcp_servers(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return parse_lines(raw)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("servers") or payload.get("mcp_servers") or [payload]
    return []


def parse_features(raw: str) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        features.append(
            {
                "id": parts[0],
                "name": parts[0],
                "maturity": parts[1] if len(parts) > 1 else "",
                "enabled": parts[-1].lower() == "true" if len(parts) > 2 else None,
            }
        )
    return features


def read_codex_config() -> dict[str, Any]:
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        with config_path.open("rb") as handle:
            return tomllib.load(handle)
    except Exception:
        return {}


def summarize_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": config.get("model", ""),
        "model_provider": config.get("model_provider", ""),
        "approval_policy": config.get("approval_policy", ""),
        "sandbox_mode": config.get("sandbox_mode", ""),
        "profiles": sorted((config.get("profiles") or {}).keys()) if isinstance(config.get("profiles"), dict) else [],
        "mcp_server_count": len(config.get("mcp_servers") or {}) if isinstance(config.get("mcp_servers"), dict) else 0,
    }


def discover_plugins() -> dict[str, list[dict[str, Any]]]:
    cache_root = Path.home() / ".codex" / "plugins" / "cache"
    marketplaces: list[dict[str, Any]] = []
    plugins: list[dict[str, Any]] = []
    if not cache_root.exists():
        return {"marketplaces": marketplaces, "plugins": plugins}
    for marketplace in cache_root.iterdir():
        if not marketplace.is_dir():
            continue
        marketplaces.append(
            {
                "id": marketplace.name,
                "name": marketplace.name,
                "path": str(marketplace),
                "installed": True,
            }
        )
        for plugin_json in marketplace.rglob("plugin.json"):
            plugin_dir = plugin_json.parent.parent if plugin_json.parent.name == ".codex-plugin" else plugin_json.parent
            metadata = _read_json(plugin_json)
            plugin_id = str(metadata.get("id") or metadata.get("name") or plugin_dir.name)
            plugins.append(
                {
                    "id": plugin_id,
                    "name": str(metadata.get("name") or plugin_id),
                    "description": str(metadata.get("description") or ""),
                    "marketplace": marketplace.name,
                    "path": str(plugin_dir),
                    "enabled": True,
                    "installed": True,
                }
            )
    return {"marketplaces": marketplaces, "plugins": plugins}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def slash_command_capabilities() -> list[dict[str, str]]:
    names = [
        "permissions", "sandbox-add-read-dir", "agent", "apps", "plugins", "hooks", "clear", "compact",
        "copy", "diff", "exit", "experimental", "feedback", "init", "logout", "mcp", "mention",
        "model", "fast", "plan", "goal", "personality", "ps", "stop", "fork", "side", "resume",
        "new", "quit", "review", "status", "debug-config", "statusline", "title", "keymap",
    ]
    return [{"id": name, "name": f"/{name}"} for name in names]


def codex_sessions(limit: int = 40) -> list[dict[str, Any]]:
    session_index = Path.home() / ".codex" / "session_index.jsonl"
    sessions: list[dict[str, Any]] = []
    if not session_index.exists():
        return sessions
    try:
        lines = session_index.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return sessions
    for line in reversed(lines[-limit:]):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            sessions.append(value)
    return sessions


def diagnostics(version: str) -> dict[str, Any]:
    return {
        "codex_available": codex_available(),
        "codex_version": version,
        "config_path": str(Path.home() / ".codex" / "config.toml"),
        "plugins_cache": str(Path.home() / ".codex" / "plugins" / "cache"),
    }


def collect_project_git(projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for project in projects:
        project_id = str(project.get("id") or "")
        path = str(project.get("local_path") or "")
        if not project_id or not path:
            continue
        states[project_id] = git_state(path)
    return states


def collect_project_files(projects: list[dict[str, Any]], limit_per_project: int = 2000) -> dict[str, list[dict[str, str]]]:
    indexed: dict[str, list[dict[str, str]]] = {}
    for project in projects:
        project_id = str(project.get("id") or "")
        path = Path(str(project.get("local_path") or ""))
        if not project_id or not path.exists() or not path.is_dir():
            continue
        indexed[project_id] = index_project_files(path, limit=limit_per_project)
    return indexed


def index_project_files(root: Path, limit: int = 2000) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_FILE_INDEX_DIRS and not dirname.endswith(".egg-info")
        ]
        current_path = Path(current)
        for filename in filenames:
            if len(files) >= limit:
                return files
            absolute = current_path / filename
            try:
                relative = absolute.relative_to(root)
            except ValueError:
                continue
            relative_text = str(relative).replace("\\", "/")
            suffix = absolute.suffix.lstrip(".")
            files.append(
                {
                    "path": str(absolute),
                    "name": filename,
                    "relative_path": relative_text,
                    "extension": suffix,
                    "kind": "image" if suffix.lower() in {"png", "jpg", "jpeg", "gif", "webp"} else "file",
                }
            )
    return files


def git_state(project_path: str) -> dict[str, Any]:
    branch = _git_output(project_path, ["branch", "--show-current"])
    status = _git_output(project_path, ["status", "--porcelain"])
    upstream = _git_output(project_path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    branches_raw = _git_output(project_path, ["branch", "--format=%(refname:short)"])
    branches = [line.strip() for line in branches_raw.splitlines() if line.strip()]
    return {
        "branch": branch,
        "dirty": bool(status.strip()),
        "upstream": upstream,
        "branches": branches,
        "status": status,
    }


def _git_output(project_path: str, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", project_path, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def discover_codex_skills(limit: int = 200) -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for root in _skill_roots():
        if not root.exists():
            continue
        for skill_file in root.rglob("SKILL.md"):
            normalized = str(skill_file.resolve())
            if normalized in seen_paths:
                continue
            seen_paths.add(normalized)
            metadata = _read_skill_metadata(skill_file)
            name = metadata.get("name") or skill_file.parent.name
            description = metadata.get("description") or ""
            skills.append(
                {
                    "id": _skill_id(skill_file),
                    "name": name,
                    "description": description,
                    "path": normalized,
                    "source": _skill_source(root),
                }
            )
            if len(skills) >= limit:
                return skills
    return skills


def _run_codex(args: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str] | None:
    codex_path = shutil.which("codex")
    if not codex_path:
        return None
    try:
        return subprocess.run(
            [codex_path, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except Exception:
        return None


def _combined_output(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return ""
    return "\n".join(part for part in ((result.stdout or "").strip(), (result.stderr or "").strip()) if part)


def _skill_roots() -> list[Path]:
    home = Path.home()
    env_roots = [
        Path(path)
        for path in os.environ.get("DEVLINK_CODEX_SKILL_ROOTS", "").split(os.pathsep)
        if path
    ]
    return [
        *env_roots,
        home / ".codex" / "skills",
        home / ".agents" / "skills",
        home / ".codex" / "plugins" / "cache",
    ]


def _read_skill_metadata(skill_file: Path) -> dict[str, str]:
    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    metadata: dict[str, str] = {}
    for raw_line in content[3:end].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def _skill_id(skill_file: Path) -> str:
    metadata = _read_skill_metadata(skill_file)
    name = metadata.get("name")
    if name:
        return name
    return hashlib.sha1(str(skill_file.resolve()).encode("utf-8")).hexdigest()[:12]


def _skill_source(root: Path) -> str:
    root_text = str(root)
    if ".codex" in root_text and "plugins" in root_text:
        return "plugin"
    if ".agents" in root_text:
        return "repo_or_user"
    return "user"
