param(
    [ValidateSet("install", "upgrade", "uninstall")]
    [string]$Action = "install",
    [string]$Version = $env:AGENS_VERSION,
    [switch]$Yes,
    [switch]$NonInteractive,
    [ValidateSet("auto", "pipx", "pip")]
    [string]$Method = $(if ($env:AGENS_INSTALL_METHOD) { $env:AGENS_INSTALL_METHOD } else { "auto" }),
    [string]$Python = $env:PYTHON,
    [string]$Package = $(if ($env:AGENS_PACKAGE) { $env:AGENS_PACKAGE } else { "agens" })
)

$ErrorActionPreference = "Stop"
$AppName = "agens"
$script:PythonBaseArgs = @()

function Write-Step([string]$Message) {
    Write-Host "==> $Message"
}

function Write-Warn([string]$Message) {
    Write-Warning $Message
}

function Fail([string]$Message) {
    Write-Error $Message
    exit 1
}

function HasCommand([string]$Name) {
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PlatformArch {
    switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture) {
        "X64" { "x86_64"; break }
        "Arm64" { "arm64"; break }
        default { $_.ToString().ToLowerInvariant() }
    }
}

function Find-Python {
    if ($Python) {
        if (-not (HasCommand $Python)) { Fail "Python executable not found: $Python" }
        $script:PythonBaseArgs = @()
        return $Python
    }
    if (HasCommand "py") {
        & py -3.13 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            $script:PythonBaseArgs = @("-3.13")
            return "py"
        }
        & py -3 -c "import sys" *> $null
        if ($LASTEXITCODE -eq 0) {
            $script:PythonBaseArgs = @("-3")
            return "py"
        }
    }
    foreach ($candidate in @("python3.13", "python3", "python")) {
        if (HasCommand $candidate) { return $candidate }
    }
    Fail "Python 3.13+ is required. Install Python, then rerun this installer."
}

function Invoke-Python {
    param([string]$Py, [string[]]$Args)
    if ($Py -eq "py") {
        & py @script:PythonBaseArgs @Args
    } else {
        & $Py @Args
    }
}

function Test-PythonVersion {
    param([string]$Py)
    Invoke-Python $Py @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)")
    if ($LASTEXITCODE -ne 0) {
        Fail "Agens requires Python 3.13 or newer."
    }
}

function Package-Spec {
    if ($Version) { return "$Package==$Version" }
    return $Package
}

function Pip-Install {
    param([string]$Py, [string[]]$PipArgs)
    Invoke-Python $Py @("-m", "pip", "--version")
    if ($LASTEXITCODE -ne 0) { Fail "pip is not available for $Py." }

    Invoke-Python $Py @("-c", "import sys; raise SystemExit(0 if hasattr(sys, 'real_prefix') or sys.prefix != sys.base_prefix else 1)")
    $inVenv = $LASTEXITCODE -eq 0
    if ($inVenv) {
        Invoke-Python $Py (@("-m", "pip") + $PipArgs)
    } else {
        Invoke-Python $Py (@("-m", "pip") + $PipArgs + @("--user"))
    }
}

function Install-WithPipx {
    $spec = Package-Spec
    switch ($Action) {
        "install" {
            Write-Step "Installing $spec with pipx."
            & pipx install $spec
        }
        "upgrade" {
            if ($Version) {
                Write-Step "Installing pinned $spec with pipx."
                & pipx install $spec --force
            } else {
                Write-Step "Upgrading $AppName with pipx."
                & pipx upgrade $AppName
            }
        }
        "uninstall" {
            Write-Step "Uninstalling $AppName with pipx."
            & pipx uninstall $AppName
        }
    }
}

function Install-WithPip {
    param([string]$Py)
    $spec = Package-Spec
    switch ($Action) {
        "install" {
            Write-Step "Installing $spec with pip."
            Pip-Install $Py @("install", $spec)
        }
        "upgrade" {
            Write-Step "Upgrading $spec with pip."
            Pip-Install $Py @("install", "--upgrade", $spec)
        }
        "uninstall" {
            Write-Step "Uninstalling $AppName with pip."
            Invoke-Python $Py @("-m", "pip", "uninstall", $AppName, "-y")
        }
    }
}

if ($env:AGENS_YES -eq "1") { $Yes = $true }
if ($env:AGENS_NON_INTERACTIVE -eq "1") { $NonInteractive = $true; $Yes = $true }

$os = if ($IsWindows -or $PSVersionTable.PSEdition -eq "Desktop") { "windows" } elseif ($IsMacOS) { "macos" } elseif ($IsLinux) { "linux" } else { "unknown" }
$arch = Get-PlatformArch
Write-Step "Detected platform: $os/$arch"
if ($os -eq "unknown") { Fail "Unsupported operating system. Use pipx install agens or pip install agens manually." }

$py = Find-Python
Test-PythonVersion $py
Write-Step "Using Python: $py"

if ($Action -eq "uninstall" -and -not $Yes -and -not $NonInteractive) {
    $answer = Read-Host "Uninstall Agens? [y/N]"
    if ($answer -notin @("y", "Y", "yes", "YES")) {
        Write-Step "Cancelled."
        exit 0
    }
}

if ($Method -eq "pipx" -or ($Method -eq "auto" -and (HasCommand "pipx"))) {
    Install-WithPipx
    if ($LASTEXITCODE -ne 0) {
        if ($Method -eq "pipx") { Fail "pipx $Action failed." }
        Write-Warn "pipx $Action failed; falling back to pip."
        Install-WithPip $py
    }
} else {
    if ($Method -eq "auto") { Write-Warn "pipx was not found; falling back to pip user installation." }
    Install-WithPip $py
}

if ($Action -ne "uninstall") {
    if (HasCommand "agens") {
        $installedVersion = & agens --version
        Write-Step "Installed: $installedVersion"
    } else {
        Write-Warn "Agens installed, but the 'agens' command is not on PATH yet. Restart PowerShell or add the Python Scripts directory to PATH."
    }
}

Write-Step "Done."
