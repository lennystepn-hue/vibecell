//! Smoke test for `hangar skill print` — runs the built binary against a
//! mockito server that pretends to be the Hangar backend. Validates that the
//! HTTP client picks up `HANGAR_BASE_URL` and streams the SKILL.md body.

use std::process::Command;

#[test]
fn skill_print_fetches_from_base_url() {
    let mut server = mockito::Server::new();
    let body = "# Hangar skill (mock)\n\nClaude should read this.\n";
    let _m = server
        .mock("GET", "/skill/SKILL.md")
        .with_status(200)
        .with_header("content-type", "text/markdown; charset=utf-8")
        .with_body(body)
        .create();

    // `CARGO_BIN_EXE_hangar` is set by cargo for integration tests of `[[bin]]`
    // named "hangar".
    let exe = env!("CARGO_BIN_EXE_hangar");
    let output = Command::new(exe)
        .args(["skill", "print"])
        .env("HANGAR_BASE_URL", server.url())
        .env("HOME", tempfile::tempdir().unwrap().path()) // isolate ~/.hangar/config.toml
        .env("USERPROFILE", tempfile::tempdir().unwrap().path()) // Windows HOME
        .output()
        .expect("run hangar skill print");

    assert!(
        output.status.success(),
        "hangar skill print exited with {:?}\nstderr: {}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("Hangar skill (mock)"),
        "stdout did not contain mocked body; got: {stdout}"
    );
}
