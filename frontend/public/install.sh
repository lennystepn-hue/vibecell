#!/usr/bin/env sh
#
# Vibecell CLI installer (macOS / Linux).
#
# Usage:
#   curl -LsSf https://vibecell.dev/install.sh | sh
#
# Environment overrides:
#   HANGAR_BASE_URL      — base URL to fetch from (default: https://vibecell.dev)
#   HANGAR_INSTALL_DIR   — directory to install into (default: $HOME/.local/bin)
#
# Verifying the download:
#   A .sha256 sidecar is published next to each tarball. To verify:
#     curl -LO "$BASE/releases/hangar-$TARGET.tar.gz.sha256"
#     sha256sum -c "hangar-$TARGET.tar.gz.sha256"

set -eu

BASE_URL="${HANGAR_BASE_URL:-https://vibecell.dev}"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$OS/$ARCH" in
    darwin/arm64)               TARGET="aarch64-apple-darwin" ;;
    darwin/x86_64)              TARGET="x86_64-apple-darwin" ;;
    linux/x86_64)               TARGET="x86_64-unknown-linux-gnu" ;;
    linux/aarch64|linux/arm64)  TARGET="aarch64-unknown-linux-gnu" ;;
    *)
        echo "hangar install: unsupported platform: $OS/$ARCH" >&2
        exit 1
        ;;
esac

INSTALL_DIR="${HANGAR_INSTALL_DIR:-$HOME/.local/bin}"
mkdir -p "$INSTALL_DIR"

URL="${BASE_URL%/}/releases/hangar-${TARGET}.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> downloading ${URL}"
curl -LsSf -o "$TMP/hangar.tar.gz" "$URL"

echo "==> extracting to $INSTALL_DIR"
tar -xzf "$TMP/hangar.tar.gz" -C "$TMP"
install -m 755 "$TMP/hangar" "$INSTALL_DIR/hangar"

echo
echo "ok installed to $INSTALL_DIR/hangar"
case ":$PATH:" in
    *":$INSTALL_DIR:"*)
        echo "   $INSTALL_DIR is already in PATH — you're done."
        ;;
    *)
        echo "   add $INSTALL_DIR to your PATH to run \`hangar\` from anywhere:"
        echo "     export PATH=\"$INSTALL_DIR:\$PATH\""
        ;;
esac
echo

# One-line setup path: /i/{code} exports HANGAR_SETUP_CODE before piping us
# here. `hangar setup` pairs this device and wires up every MCP client it
# finds, so the user never sees a settings page.
#
# The `||` fallback matters during rollout: `setup` arrives in a later CLI
# release than this script, so anyone on an older binary would otherwise get
# a bare "unknown subcommand" and no idea what to do next.
if [ -n "${HANGAR_SETUP_CODE:-}" ]; then
    echo "==> pairing this device and configuring your MCP clients"
    if "$INSTALL_DIR/hangar" setup --code "$HANGAR_SETUP_CODE"; then
        exit 0
    fi
    echo
    echo "   automatic setup unavailable in this build — falling back" >&2
fi

case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *) echo "   (run it via $INSTALL_DIR/hangar until PATH is updated)" ;;
esac
echo "next: run \`hangar pair\` to connect this device."
