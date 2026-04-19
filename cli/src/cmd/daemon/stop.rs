//! `hangar daemon stop` — graceful termination of the running daemon.

use anyhow::Result;

pub async fn run() -> Result<()> {
    #[cfg(unix)]
    {
        stop_unix()
    }
    #[cfg(windows)]
    {
        stop_windows()
    }
    #[cfg(not(any(unix, windows)))]
    {
        anyhow::bail!("`hangar daemon stop` is not supported on this platform")
    }
}

#[cfg(unix)]
fn stop_unix() -> Result<()> {
    let status = std::process::Command::new("pkill")
        .args(["-TERM", "-f", "hangar daemon start"])
        .status();
    match status {
        Ok(s) if s.success() => {
            println!("ok sent SIGTERM to running daemon");
        }
        _ => {
            println!("i no running daemon process matched `hangar daemon start`");
        }
    }
    Ok(())
}

#[cfg(windows)]
fn stop_windows() -> Result<()> {
    let status = std::process::Command::new("taskkill")
        .args(["/IM", "hangar.exe", "/F"])
        .status();
    match status {
        Ok(s) if s.success() => {
            println!("ok taskkill'd hangar.exe");
        }
        _ => {
            println!("i no running hangar.exe to stop");
        }
    }
    Ok(())
}
