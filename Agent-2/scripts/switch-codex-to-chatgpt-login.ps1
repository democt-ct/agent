[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$ProviderName = "picklyone",
  [string]$CodexDir = (Join-Path $HOME ".codex"),
  [switch]$SkipLogin
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host "[codex-switch] $Message"
}

function Backup-File {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$BackupDir
  )

  if (-not (Test-Path -LiteralPath $Path)) {
    Write-Step "Skip backup, file not found: $Path"
    return $null
  }

  $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $fileName = Split-Path -Path $Path -Leaf
  $backupPath = Join-Path $BackupDir "$fileName.$timestamp.bak"

  if ($PSCmdlet.ShouldProcess($Path, "Backup to $backupPath")) {
    Copy-Item -LiteralPath $Path -Destination $backupPath -Force
  }

  Write-Step "Backed up $fileName to $backupPath"
  return $backupPath
}

function Remove-ProviderBlock {
  param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [Parameter(Mandatory = $true)]
    [string]$ProviderName
  )

  if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Step "config.toml not found, skip provider cleanup: $ConfigPath"
    return $false
  }

  $content = Get-Content -LiteralPath $ConfigPath -Raw
  $escapedProvider = [regex]::Escape($ProviderName)

  $patterns = @(
    "(?ms)^[ \t]*\[providers\.$escapedProvider\][\r\n]+.*?(?=^[ \t]*\[[^\r\n]+\]|`z)",
    "(?ms)^[ \t]*\[provider\.$escapedProvider\][\r\n]+.*?(?=^[ \t]*\[[^\r\n]+\]|`z)",
    "(?ms)^[ \t]*\[$escapedProvider\][\r\n]+.*?(?=^[ \t]*\[[^\r\n]+\]|`z)"
  )

  $updated = $content
  foreach ($pattern in $patterns) {
    $updated = [regex]::Replace($updated, $pattern, "", 1)
  }

  $updated = [regex]::Replace(
    $updated,
    "(?m)^([ \t]*(default_model_provider|model_provider|provider)[ \t]*=[ \t]*[""'])$escapedProvider(([""'].*))$",
    '${1}${4}'
  )
  $updated = [regex]::Replace(
    $updated,
    "(?m)^[ \t]*(default_model_provider|model_provider|provider)[ \t]*=[ \t]*[""']$escapedProvider[""'][ \t]*\r?\n?",
    ""
  )
  $updated = [regex]::Replace($updated, "(\r?\n){3,}", "`r`n`r`n").TrimEnd() + "`r`n"

  if ($updated -eq $content) {
    Write-Step "No config entries matched provider '$ProviderName'"
    return $false
  }

  if ($PSCmdlet.ShouldProcess($ConfigPath, "Remove provider '$ProviderName' from config.toml")) {
    Set-Content -LiteralPath $ConfigPath -Value $updated -Encoding UTF8
  }

  Write-Step "Removed provider references for '$ProviderName' from config.toml"
  return $true
}

$codexDirResolved = [System.IO.Path]::GetFullPath($CodexDir)
$configPath = Join-Path $codexDirResolved "config.toml"
$authPath = Join-Path $codexDirResolved "auth.json"
$backupDir = Join-Path $codexDirResolved "backups"

if (-not (Test-Path -LiteralPath $codexDirResolved)) {
  throw "Codex directory not found: $codexDirResolved"
}

if ($PSCmdlet.ShouldProcess($backupDir, "Ensure backup directory exists")) {
  New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

Write-Step "Using Codex directory: $codexDirResolved"
Backup-File -Path $authPath -BackupDir $backupDir | Out-Null
Backup-File -Path $configPath -BackupDir $backupDir | Out-Null
$removed = Remove-ProviderBlock -ConfigPath $configPath -ProviderName $ProviderName

if ($SkipLogin) {
  Write-Step "SkipLogin enabled, no login command executed"
  exit 0
}

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codexCommand) {
  Write-Step "Provider cleanup finished, but 'codex' command was not found in PATH"
  Write-Step "Run 'codex login' manually after confirming config.toml is clean"
  exit 0
}

Write-Step "Starting 'codex login' to switch to ChatGPT account login"
if ($PSCmdlet.ShouldProcess("codex login", "Launch interactive login")) {
  & $codexCommand.Source login
}

if ($LASTEXITCODE -ne 0) {
  throw "codex login exited with code $LASTEXITCODE"
}

if ($removed) {
  Write-Step "Switch completed: custom provider removed and login finished"
} else {
  Write-Step "Login finished; no matching provider block was removed"
}
