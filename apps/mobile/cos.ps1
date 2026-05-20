$Root = "C:\Users\Adam\Desktop\Programing\ProOpr\projekt\devlink"
$Out = Join-Path $Root "codex-hub-sidebar-dump.md"
$Fence = "```"

$Files = @(
  "apps/mobile/src/screens/WorkspaceChatScreen.tsx",
  "apps/mobile/src/components/AppSettingsModal.tsx",
  "apps/mobile/src/components/PairingPanel.tsx",
  "apps/mobile/src/preferences/PreferencesContext.tsx",
  "apps/mobile/src/navigation/AppNavigator.tsx",
  "apps/mobile/src/api/client.ts",
  "apps/backend/agents/command_catalog.py",
  "apps/backend/agents/views.py",
  "apps/backend/agents/models.py",
  "apps/backend/devices/views.py",
  "apps/backend/devices/services.py",
  "apps/backend/tasks/services.py",
  "apps/cli/devlink_cli/daemon.py",
  "apps/cli/devlink_cli/codex_process.py"
)

Remove-Item -LiteralPath $Out -ErrorAction SilentlyContinue

foreach ($Rel in $Files) {
  $Path = Join-Path $Root $Rel
  if (-not (Test-Path -LiteralPath $Path)) { continue }

  Add-Content -LiteralPath $Out -Encoding UTF8 -Value ""
  Add-Content -LiteralPath $Out -Encoding UTF8 -Value "## $Rel"
  Add-Content -LiteralPath $Out -Encoding UTF8 -Value ""
  Add-Content -LiteralPath $Out -Encoding UTF8 -Value "$Fence$([IO.Path]::GetExtension($Path).TrimStart('.'))"
  Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | Add-Content -LiteralPath $Out -Encoding UTF8
  Add-Content -LiteralPath $Out -Encoding UTF8 -Value $Fence
}

Write-Host "Dump zapisany do: $Out"