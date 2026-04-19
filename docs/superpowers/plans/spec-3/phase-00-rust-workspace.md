# Phase 0 — Rust Workspace + CI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Scaffold the `cli/` Rust project under the existing monorepo, produce a `hangar --version` binary, and wire cross-platform CI (macOS / Linux / Windows matrix). This is pure infrastructure — no Hangar-specific logic.

**Prerequisite:** Spec 1 complete (monorepo exists with backend/ + frontend/ + ops/).

---

## Success criteria

- `cd cli && cargo build --release` produces `cli/target/release/hangar` (or `.exe`) on the local dev machine
- `./target/release/hangar --version` prints `hangar 0.1.0`
- `cargo clippy -- -D warnings` + `cargo fmt --check` + `cargo test` pass
- GitHub Actions matrix runs the three platforms and passes on push to `main`
- No external system-level deps beyond what `cargo` pulls

---

## Files produced

```
cli/
├── Cargo.toml                 workspace member, edition = "2021"
├── Cargo.lock
├── .gitignore
├── README.md
├── rustfmt.toml
├── clippy.toml
└── src/
    └── main.rs                minimal: prints version
.github/workflows/cli.yml      CI matrix
```

---

## Task 0.1 — Create the `cli/` directory with Cargo skeleton

**Files:**
- Create: `cli/Cargo.toml`
- Create: `cli/src/main.rs`
- Create: `cli/.gitignore`
- Create: `cli/README.md`
- Create: `cli/rustfmt.toml`
- Create: `cli/clippy.toml`

### `cli/Cargo.toml`

```toml
[package]
name = "hangar-cli"
version = "0.1.0"
edition = "2021"
rust-version = "1.83"
description = "Hangar CLI + daemon + MCP server"
license = "MIT"
repository = "https://github.com/lenny/hangar"

[[bin]]
name = "hangar"
path = "src/main.rs"

[dependencies]
clap = { version = "4.5", features = ["derive"] }

[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1
strip = true
```

### `cli/src/main.rs`

```rust
use clap::Parser;

#[derive(Parser)]
#[command(name = "hangar")]
#[command(version, about = "Hangar CLI + daemon + MCP server", long_about = None)]
struct Cli {}

fn main() {
    let _cli = Cli::parse();
    println!(
        "hangar {} — CLI surface lands in phase 1",
        env!("CARGO_PKG_VERSION")
    );
}
```

### `cli/.gitignore`

```
/target
/Cargo.lock.bak
```

### `cli/README.md`

```markdown
# Hangar CLI

The `hangar` binary — CLI + daemon + MCP server for Claude Code integration.

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
```

### `cli/rustfmt.toml`

```toml
edition = "2021"
max_width = 100
```

### `cli/clippy.toml`

```toml
msrv = "1.83"
```

**Verify locally** (requires rustup/cargo — if not installed, use `curl -LsSf https://sh.rustup.rs | sh`):

```bash
cd cli
cargo build
./target/debug/hangar --version
# expected: "hangar 0.1.0 — CLI surface lands in phase 1"
```

**Commit:**

```bash
cd "C:/Users/ender/OneDrive/Desktop/Hangar"
git add cli/
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(cli): Rust cargo scaffold — hangar binary with --version

Spec 3 Phase 0: cli/ subdirectory, single bin target, clap 4 for
arg parsing. Release profile: lto=thin, codegen-units=1, strip=true
for ~5MB binary target.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 0.2 — CI matrix workflow

**File:** `.github/workflows/cli.yml`

```yaml
name: CLI

on:
  push:
    branches: [main]
    paths:
      - "cli/**"
      - ".github/workflows/cli.yml"
  pull_request:
    paths:
      - "cli/**"
      - ".github/workflows/cli.yml"

concurrency:
  group: cli-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    name: build (${{ matrix.os }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
            bin: hangar
          - os: macos-latest
            target: aarch64-apple-darwin
            bin: hangar
          - os: windows-latest
            target: x86_64-pc-windows-msvc
            bin: hangar.exe
    defaults:
      run:
        working-directory: cli
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}
          components: clippy, rustfmt
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: cli -> cli/target
      - name: rustfmt
        run: cargo fmt -- --check
      - name: clippy
        run: cargo clippy --target ${{ matrix.target }} -- -D warnings
      - name: test
        run: cargo test --target ${{ matrix.target }}
      - name: build release
        run: cargo build --release --target ${{ matrix.target }}
      - name: smoke test
        shell: bash
        run: ./target/${{ matrix.target }}/release/${{ matrix.bin }} --version
      - name: upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: hangar-${{ matrix.target }}
          path: cli/target/${{ matrix.target }}/release/${{ matrix.bin }}
          retention-days: 7
```

**Verify** (can't run GitHub Actions locally, so check syntax):

```bash
# yaml-syntax sanity
python -c "import yaml; yaml.safe_load(open('.github/workflows/cli.yml')); print('ok')"
```

**Commit:**

```bash
cd "C:/Users/ender/OneDrive/Desktop/Hangar"
git add .github/workflows/cli.yml
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
ci(cli): cross-platform build matrix (macOS / Linux / Windows)

rustfmt check + clippy -D warnings + cargo test + release build +
smoke test --version on all three platforms. Artifacts uploaded
per target for 7 days (inspection / preview).

Swatinem/rust-cache@v2 caches target/ per-workspace to keep CI fast.
concurrency group cancels superseded runs on same ref.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 0.3 — Local verification

Install rustup if not present:
```bash
# Windows via rustup-init.exe OR:
winget install Rustlang.Rustup
```

Then:
```bash
cd "C:/Users/ender/OneDrive/Desktop/Hangar/cli"
cargo fmt -- --check
cargo clippy -- -D warnings
cargo test
cargo build --release
./target/release/hangar.exe --version
```

Expected output:
```
hangar 0.1.0 — CLI surface lands in phase 1
```

If any step fails, fix and re-verify. Don't commit until all four commands pass locally.

---

## Phase 0 complete when

- [ ] `cli/Cargo.toml` + `cli/src/main.rs` exist
- [ ] `cd cli && cargo build --release` succeeds on local machine
- [ ] `./target/release/hangar --version` prints the expected line
- [ ] `.github/workflows/cli.yml` committed
- [ ] 2 commits on `main`: Cargo scaffold + CI workflow
- [ ] First CI run on `main` is green across all three platforms (verifiable after push)

Phase 1 (device-code pairing + backend /cli/pair endpoints + OS keychain storage) depends on this scaffold.
