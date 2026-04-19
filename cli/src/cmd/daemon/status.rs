//! `hangar daemon status` — best-effort health check.
//!
//! Strategy: open a short-timeout TCP connection to 127.0.0.1:7421. If it
//! succeeds, the daemon is listening. PID detection is best-effort per
//! platform (pgrep on unix, tasklist on Windows).

use anyhow::Result;
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

const MCP_ADDR: &str = "127.0.0.1:7421";

pub async fn run() -> Result<()> {
    let running = probe_tcp();
    let pid = detect_pid();

    if running {
        match pid {
            Some(pid) => println!("ok daemon running (PID {pid}) — MCP on http://{}", MCP_ADDR),
            None => println!("ok daemon running — MCP on http://{}", MCP_ADDR),
        }
    } else {
        println!("i daemon stopped (nothing listening on {})", MCP_ADDR);
        println!("  start with: hangar daemon start");
    }
    Ok(())
}

fn probe_tcp() -> bool {
    let addr: SocketAddr = match MCP_ADDR.parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

#[cfg(unix)]
fn detect_pid() -> Option<u32> {
    // `pgrep -f "hangar daemon start"` — return first PID line.
    let out = std::process::Command::new("pgrep")
        .args(["-f", "hangar daemon start"])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&out.stdout);
    stdout.lines().next()?.trim().parse::<u32>().ok()
}

#[cfg(windows)]
fn detect_pid() -> Option<u32> {
    // `tasklist /FI "IMAGENAME eq hangar.exe" /FO CSV /NH` — parse first PID column.
    let out = std::process::Command::new("tasklist")
        .args(["/FI", "IMAGENAME eq hangar.exe", "/FO", "CSV", "/NH"])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&out.stdout);
    for line in stdout.lines() {
        // CSV: "hangar.exe","12345","Console","1","8,456 K"
        let cols: Vec<&str> = line.split(',').collect();
        if cols.len() >= 2 {
            let pid = cols[1].trim_matches('"').trim();
            if let Ok(n) = pid.parse::<u32>() {
                return Some(n);
            }
        }
    }
    None
}

#[cfg(not(any(unix, windows)))]
fn detect_pid() -> Option<u32> {
    None
}
