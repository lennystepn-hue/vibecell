# Vibecell CLI

CLI + daemon + MCP server for Claude Code integration. Ships as **two
identically-behaving binaries**: `vibecell` (the user-facing brand) and
`hangar` (the internal codename). Use whichever you prefer — both run
the same code, both read/write the same `~/.hangar/config.toml`.

```bash
vibecell pair          # OAuth-pair against vibecell.dev
vibecell skill update  # refresh the SKILL.md
vibecell status        # show pairing + active workspace
```

`hangar pair`, `hangar skill update`, etc. continue to work unchanged.

(Internal identifiers — env vars `HANGAR_*`, config dir `~/.hangar/`,
keychain service name, Cargo package name — intentionally stay `hangar`
so existing self-hosters and shell history aren't churned.)

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
