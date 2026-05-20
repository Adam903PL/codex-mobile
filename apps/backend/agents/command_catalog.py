from __future__ import annotations

from typing import Any


def command_catalog() -> list[dict[str, Any]]:
    commands = [
        _cmd("codex.exec", "chat", "Exec run", "Run Codex non-interactively in the selected workspace.", "stable", "medium", True, False, ["prompt", "model", "profile", "sandbox", "web_search", "images", "add_dirs", "oss", "local_provider", "skip_git_repo_check", "ephemeral", "ignore_user_config", "ignore_rules", "output_schema", "output_last_message", "color", "config", "enable", "disable"]),
        _cmd("codex.exec.resume", "chat", "Exec resume", "Resume a previous non-interactive Codex session.", "stable", "medium", True, False, ["session_id", "last", "all", "prompt", "images"]),
        _cmd("codex.resume", "chat", "Resume chat", "Continue an interactive Codex session by ID or most recent.", "stable", "medium", True, False, ["session_id", "last", "all", "include_non_interactive", "prompt", "model", "profile", "sandbox", "remote"]),
        _cmd("codex.fork", "chat", "Fork chat", "Fork an existing Codex session into a new thread.", "stable", "medium", True, False, ["session_id", "last", "all", "prompt"]),
        _cmd("codex.review", "git", "Review working tree", "Ask Codex to review local changes.", "stable", "medium", True, False, ["prompt", "model", "profile", "sandbox"]),
        _cmd("codex.apply", "git", "Apply cloud diff", "Apply a Codex Cloud task diff to the local working tree.", "stable", "high", True, True, ["task_id"]),
        _cmd("git.branch.switch", "git", "Switch branch", "Switch the local project branch.", "stable", "medium", True, True, ["branch"]),
        _cmd("git.branch.create", "git", "Create branch", "Create and switch to a local project branch.", "stable", "medium", True, True, ["branch", "base"]),
        _cmd("codex.session.settings.update", "settings", "Apply risky session settings", "Apply session access settings that require explicit approval.", "stable", "high", True, True, ["sandbox", "approval_policy", "add_dirs", "bypass_approvals_and_sandbox"]),
        _cmd("codex.login.status", "setup", "Login status", "Read Codex authentication status.", "stable", "low", False, False, []),
        _cmd("codex.login.device", "setup", "Login with device auth", "Start Codex OAuth device authentication locally.", "stable", "high", False, True, []),
        _cmd("codex.login.api_key", "setup", "Login with API key", "Read an API key from stdin and store Codex credentials.", "stable", "critical", False, True, ["api_key_env"]),
        _cmd("codex.logout", "setup", "Logout Codex", "Remove local Codex credentials.", "stable", "high", False, True, []),
        _cmd("codex.capabilities.refresh", "setup", "Refresh capabilities", "Refresh local Codex models, plugins, skills, MCP and Git state.", "stable", "low", False, False, []),
        _cmd("codex.update", "setup", "Update Codex", "Run Codex self-update when supported.", "stable", "high", False, True, []),
        _cmd("codex.features.list", "debug", "List features", "Show known Codex feature flags and current state.", "stable", "low", False, False, []),
        _cmd("codex.features.enable", "debug", "Enable feature", "Persistently enable a Codex feature flag.", "stable", "high", False, True, ["feature", "profile"]),
        _cmd("codex.features.disable", "debug", "Disable feature", "Persistently disable a Codex feature flag.", "stable", "high", False, True, ["feature", "profile"]),
        _cmd("codex.debug.models", "debug", "Model catalog", "Print the model catalog Codex sees.", "experimental", "low", False, False, ["bundled"]),
        _cmd("codex.debug.app_server.send_message_v2", "debug", "Debug app-server message", "Send one V2 message through Codex app-server test client.", "experimental", "medium", False, False, ["user_message"]),
        _cmd("codex.completion", "debug", "Shell completion", "Generate shell completion for a selected shell.", "stable", "low", False, False, ["shell"]),
        _cmd("codex.help", "debug", "Codex help", "Print Codex help for a command path.", "stable", "low", False, False, ["command"]),
        _cmd("codex.version", "debug", "Codex version", "Print the installed Codex CLI version.", "stable", "low", False, False, []),
        _cmd("codex.mcp.list", "mcp", "List MCP servers", "List configured MCP servers.", "experimental", "low", False, False, ["json"]),
        _cmd("codex.mcp.get", "mcp", "Get MCP server", "Show one MCP server configuration.", "experimental", "low", False, False, ["name", "json"]),
        _cmd("codex.mcp.add", "mcp", "Add MCP server", "Register a stdio or HTTP MCP server.", "experimental", "high", False, True, ["name", "url", "command", "env", "bearer_token_env_var"]),
        _cmd("codex.mcp.remove", "mcp", "Remove MCP server", "Remove an MCP server configuration.", "experimental", "high", False, True, ["name"]),
        _cmd("codex.mcp.login", "mcp", "Login MCP server", "Start OAuth login for an MCP server.", "experimental", "high", False, True, ["name", "scopes"]),
        _cmd("codex.mcp.logout", "mcp", "Logout MCP server", "Remove stored OAuth credentials for an MCP server.", "experimental", "high", False, True, ["name"]),
        _cmd("codex.plugin.list", "plugins", "List plugins", "Read installed plugins from the local Codex cache and config.", "experimental", "low", False, False, []),
        _cmd("codex.plugin.marketplace.add", "plugins", "Add marketplace", "Install a plugin marketplace from Git or local source.", "experimental", "high", False, True, ["source", "ref", "sparse"]),
        _cmd("codex.plugin.marketplace.upgrade", "plugins", "Upgrade marketplace", "Refresh one or all plugin marketplaces.", "experimental", "high", False, True, ["name"]),
        _cmd("codex.plugin.marketplace.remove", "plugins", "Remove marketplace", "Remove a configured plugin marketplace.", "experimental", "high", False, True, ["name"]),
        _cmd("codex.cloud.list", "cloud", "List cloud tasks", "List recent Codex Cloud tasks.", "experimental", "medium", False, False, ["env", "limit", "cursor", "json"]),
        _cmd("codex.cloud.exec", "cloud", "Run cloud task", "Submit a Codex Cloud task.", "experimental", "critical", False, True, ["query", "env", "attempts"]),
        _cmd("codex.sandbox.run", "debug", "Sandbox command", "Run a command inside Codex-provided sandbox helper.", "experimental", "high", True, True, ["platform", "permissions_profile", "include_managed_config", "allow_unix_socket", "log_denials", "command", "cd", "config"]),
        _cmd("codex.app", "setup", "Open desktop app", "Launch Codex desktop app for a workspace.", "stable", "low", True, False, ["path", "download_url"]),
        _cmd("codex.app-server", "debug", "App server", "Launch Codex app-server locally.", "experimental", "critical", False, True, ["listen", "ws_auth", "ws_token_file", "ws_shared_secret_file", "ws_issuer", "ws_audience"]),
        _cmd("codex.remote-control", "debug", "Remote control", "Run Codex remote-control helper when supported by the installed CLI.", "experimental", "critical", False, True, ["listen"]),
        _cmd("codex.exec-server", "debug", "Exec server", "Run Codex exec-server when supported by the installed CLI.", "experimental", "critical", False, True, ["listen"]),
        _cmd("codex.mcp-server", "mcp", "Codex MCP server", "Run Codex as an MCP server over stdio.", "experimental", "critical", False, True, []),
    ]
    return [_with_schema(command) for command in commands]


def slash_commands() -> list[dict[str, Any]]:
    names = [
        ("/permissions", "permissions", "Set approval and sandbox presets."),
        ("/sandbox-add-read-dir", "permissions", "Grant Windows sandbox read access to a directory."),
        ("/agent", "chat", "Switch active agent thread."),
        ("/apps", "plugins", "Browse connectors and insert app mentions."),
        ("/plugins", "plugins", "Browse installed and discoverable plugins."),
        ("/hooks", "debug", "Review lifecycle hooks."),
        ("/clear", "chat", "Clear visible terminal and start a fresh chat."),
        ("/compact", "chat", "Summarize transcript to free context."),
        ("/copy", "chat", "Copy latest completed response."),
        ("/diff", "git", "Show working tree diff."),
        ("/exit", "chat", "Exit the CLI."),
        ("/experimental", "debug", "Toggle experimental features."),
        ("/feedback", "debug", "Send feedback and diagnostics."),
        ("/init", "workspace", "Generate AGENTS.md scaffold."),
        ("/logout", "setup", "Sign out of Codex."),
        ("/mcp", "mcp", "List configured MCP tools."),
        ("/mention", "workspace", "Attach files or folders to the conversation."),
        ("/model", "chat", "Choose active model and reasoning effort."),
        ("/fast", "chat", "Toggle fast mode."),
        ("/plan", "chat", "Switch conversation into plan mode."),
        ("/goal", "chat", "Set or inspect an experimental task goal."),
        ("/personality", "chat", "Change communication style."),
        ("/ps", "debug", "Show background terminals."),
        ("/stop", "debug", "Stop background terminals."),
        ("/fork", "chat", "Fork current conversation."),
        ("/side", "chat", "Start an ephemeral side conversation."),
        ("/resume", "chat", "Resume saved conversation."),
        ("/new", "chat", "Start a new conversation."),
        ("/quit", "chat", "Exit the CLI."),
        ("/review", "git", "Review working tree."),
        ("/status", "debug", "Inspect active session status."),
        ("/debug-config", "debug", "Inspect config layers."),
        ("/statusline", "settings", "Configure TUI footer items."),
        ("/title", "settings", "Configure terminal title items."),
        ("/keymap", "settings", "Remap TUI shortcuts."),
    ]
    return [{"id": name[1:], "name": name, "group": group, "description": description} for name, group, description in names]


def get_command(command_id: str) -> dict[str, Any] | None:
    return next((command for command in command_catalog() if command["id"] == command_id), None)


def _cmd(command_id: str, group: str, label: str, description: str, maturity: str, risk: str, requires_project: bool, requires_approval: bool, args: list[str]) -> dict[str, Any]:
    return {
        "id": command_id,
        "group": group,
        "label": label,
        "description": description,
        "maturity": maturity,
        "risk_level": risk,
        "requires_project": requires_project,
        "requires_approval": requires_approval,
        "supported_surface": ["mobile", "local_cli"],
        "local_cli_min_version": "",
        "args": args,
        "command_template": command_id.replace(".", " "),
    }


def _with_schema(command: dict[str, Any]) -> dict[str, Any]:
    args = command.pop("args")
    command["args_schema"] = [_arg_schema(arg, command["risk_level"]) for arg in args]
    return command


def _arg_schema(name: str, risk_level: str) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "name": name,
        "type": "string",
        "required": False,
        "repeatable": False,
        "placeholder": "",
        "risk_level": risk_level,
        "approval_reason": "",
    }
    choices = {
        "sandbox": ["read-only", "workspace-write", "danger-full-access"],
        "approval_policy": ["untrusted", "on-request", "never"],
        "color": ["auto", "always", "never"],
        "platform": ["windows", "linux", "macos"],
        "shell": ["bash", "zsh", "fish", "power-shell", "powershell", "elvish"],
    }
    booleans = {"json", "bundled", "last", "all", "include_non_interactive", "web_search", "oss", "skip_git_repo_check", "ephemeral", "ignore_user_config", "ignore_rules", "include_managed_config", "log_denials", "bypass_approvals_and_sandbox"}
    arrays = {"images", "add_dirs", "enable", "disable", "sparse", "allow_unix_socket", "config", "env", "command"}
    required = {"branch", "task_id", "feature", "name", "source", "query", "user_message"}
    if name in choices:
        schema["type"] = "choice"
        schema["choices"] = choices[name]
    if name in booleans:
        schema["type"] = "boolean"
    if name in arrays:
        schema["type"] = "list"
        schema["repeatable"] = True
    if name in required:
        schema["required"] = True
    if name in {"images", "output_schema", "output_last_message", "path", "cd", "download_url", "ws_token_file", "ws_shared_secret_file"}:
        schema["type"] = "path" if name != "download_url" else "url"
    if name in {"danger-full-access", "bypass_approvals_and_sandbox"} or risk_level in {"high", "critical"}:
        schema["approval_reason"] = "This can change local Codex configuration, credentials, workspace files, or network-facing services."
    schema["placeholder"] = _placeholder_for(name)
    return schema


def _placeholder_for(name: str) -> str:
    return {
        "prompt": "Instruction for Codex",
        "session_id": "Codex session id",
        "branch": "feature/my-branch",
        "base": "main",
        "feature": "feature flag name",
        "name": "server or marketplace name",
        "source": "owner/repo or local path",
        "query": "Cloud task prompt",
        "env": "KEY=VALUE",
        "command": "command and args",
        "listen": "stdio:// or ws://127.0.0.1:PORT",
        "local_provider": "ollama",
    }.get(name, name.replace("_", " "))
