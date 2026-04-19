# Vibecell CLI

The `hangar` binary — CLI + daemon + MCP server for Claude Code integration.
(Binary name stays `hangar` as an internal codename — renaming would
break every user's existing shell history, keychain entry, and config dir.)

## Dev

```bash
cd cli
cargo build
./target/debug/hangar --version
```

## Release

```bash
cargo build --release
./target/release/hangar --version
```

## Cross-compile

CI (see `.github/workflows/cli.yml`) builds on macOS / Linux / Windows matrix.
Local cross-compile via `cross`:

```bash
cargo install cross
cross build --release --target aarch64-apple-darwin
cross build --release --target x86_64-pc-windows-msvc
```
