#!/usr/bin/env sh
set -eu

APP_NAME="agens"
PACKAGE_NAME="${AGENS_PACKAGE:-agens}"
ACTION="install"
VERSION_PIN="${AGENS_VERSION:-}"
ASSUME_YES="${AGENS_YES:-0}"
NON_INTERACTIVE="${AGENS_NON_INTERACTIVE:-0}"
METHOD="${AGENS_INSTALL_METHOD:-auto}"
PYTHON_BIN="${PYTHON:-}"

usage() {
  cat <<'EOF'
Agens installer

Usage:
  install.sh [install|upgrade|uninstall] [options]

Options:
  --version VERSION       Install a specific Agens version.
  --yes, -y              Do not prompt for confirmation.
  --non-interactive      Fail instead of prompting. Suitable for CI.
  --method auto|pipx|pip Choose installer backend. Default: auto.
  --python PATH          Python executable to use for pip fallback.
  --help, -h             Show this help.

Environment:
  AGENS_VERSION, AGENS_YES=1, AGENS_NON_INTERACTIVE=1,
  AGENS_INSTALL_METHOD=auto|pipx|pip, AGENS_PACKAGE=agens
EOF
}

log() { printf '%s\n' "==> $*"; }
warn() { printf '%s\n' "Warning: $*" >&2; }
fail() { printf '%s\n' "Error: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

confirm() {
  [ "$ASSUME_YES" = "1" ] && return 0
  [ "$NON_INTERACTIVE" = "1" ] && return 0
  printf '%s [y/N] ' "$1"
  read ans || return 1
  case "$ans" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

detect_os() {
  case "$(uname -s 2>/dev/null || printf unknown)" in
    Linux*) printf linux ;;
    Darwin*) printf macos ;;
    MINGW*|MSYS*|CYGWIN*) printf windows ;;
    *) printf unknown ;;
  esac
}

detect_arch() {
  arch="$(uname -m 2>/dev/null || printf unknown)"
  case "$arch" in
    x86_64|amd64) printf x86_64 ;;
    arm64|aarch64) printf arm64 ;;
    *) printf '%s' "$arch" ;;
  esac
}

find_python() {
  if [ -n "$PYTHON_BIN" ]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON_BIN"
    printf '%s' "$PYTHON_BIN"
    return
  fi
  for candidate in python3.13 python3 python py; do
    if have "$candidate"; then
      printf '%s' "$candidate"
      return
    fi
  done
  fail "Python 3.13+ is required. Install Python, then rerun this installer."
}

python_check() {
  py="$1"
  "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else 1)' \
    || fail "Agens requires Python 3.13 or newer. Found: $("$py" -c 'import sys; print(sys.version.split()[0])')"
}

package_spec() {
  if [ -n "$VERSION_PIN" ]; then
    printf '%s==%s' "$PACKAGE_NAME" "$VERSION_PIN"
  else
    printf '%s' "$PACKAGE_NAME"
  fi
}

pip_cmd() {
  py="$1"
  shift
  "$py" -m pip --version >/dev/null 2>&1 || fail "pip is not available for $py."
  if "$py" -c 'import sys; raise SystemExit(0 if hasattr(sys, "real_prefix") or sys.prefix != sys.base_prefix else 1)' >/dev/null 2>&1; then
    "$py" -m pip "$@"
  else
    "$py" -m pip "$@" --user
  fi
}

install_with_pipx() {
  spec="$(package_spec)"
  case "$ACTION" in
    install)
      log "Installing $spec with pipx."
      pipx install "$spec"
      ;;
    upgrade)
      if [ -n "$VERSION_PIN" ]; then
        log "Installing pinned $spec with pipx."
        pipx install "$spec" --force
      else
        log "Upgrading $APP_NAME with pipx."
        pipx upgrade "$APP_NAME"
      fi
      ;;
    uninstall)
      log "Uninstalling $APP_NAME with pipx."
      pipx uninstall "$APP_NAME"
      ;;
  esac
}

install_with_pip() {
  py="$1"
  spec="$(package_spec)"
  case "$ACTION" in
    install)
      log "Installing $spec with pip."
      pip_cmd "$py" install "$spec"
      ;;
    upgrade)
      log "Upgrading $spec with pip."
      pip_cmd "$py" install --upgrade "$spec"
      ;;
    uninstall)
      log "Uninstalling $APP_NAME with pip."
      "$py" -m pip uninstall "$APP_NAME" -y
      ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    install|upgrade|uninstall) ACTION="$1" ;;
    --version) shift; [ "$#" -gt 0 ] || fail "--version requires a value."; VERSION_PIN="$1" ;;
    --yes|-y) ASSUME_YES=1 ;;
    --non-interactive|--ci) NON_INTERACTIVE=1; ASSUME_YES=1 ;;
    --method) shift; [ "$#" -gt 0 ] || fail "--method requires auto, pipx, or pip."; METHOD="$1" ;;
    --python) shift; [ "$#" -gt 0 ] || fail "--python requires a path."; PYTHON_BIN="$1" ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
  shift
done

case "$METHOD" in auto|pipx|pip) ;; *) fail "--method must be auto, pipx, or pip." ;; esac

OS="$(detect_os)"
ARCH="$(detect_arch)"
log "Detected platform: $OS/$ARCH"
[ "$OS" != "unknown" ] || fail "Unsupported operating system. Use pipx install agens or pip install agens manually."

PY="$(find_python)"
python_check "$PY"
log "Using Python: $("$PY" -c 'import sys; print(sys.executable)')"

if [ "$ACTION" = "uninstall" ] && ! confirm "Uninstall Agens?"; then
  log "Cancelled."
  exit 0
fi

if [ "$METHOD" = "pipx" ] || { [ "$METHOD" = "auto" ] && have pipx; }; then
  install_with_pipx || {
    [ "$METHOD" = "pipx" ] && fail "pipx $ACTION failed."
    warn "pipx $ACTION failed; falling back to pip."
    install_with_pip "$PY"
  }
else
  [ "$METHOD" != "auto" ] || warn "pipx was not found; falling back to pip user installation."
  install_with_pip "$PY"
fi

if [ "$ACTION" != "uninstall" ]; then
  if command -v agens >/dev/null 2>&1; then
    log "Installed: $(agens --version)"
  else
    warn "Agens installed, but the 'agens' command is not on PATH yet. Restart your shell or add your Python user scripts directory to PATH."
  fi
fi

log "Done."
