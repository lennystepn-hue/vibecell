//! `hangar daemon uninstall` — remove the auto-start registration installed by
//! `hangar daemon install`. Platform-specific; no-ops cleanly when nothing is
//! registered.

use anyhow::Result;

pub async fn run() -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        uninstall_launchd()
    }
    #[cfg(target_os = "linux")]
    {
        uninstall_systemd()
    }
    #[cfg(target_os = "windows")]
    {
        uninstall_task_scheduler()
    }
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    {
        anyhow::bail!("`hangar daemon uninstall` is not supported on this platform")
    }
}

#[cfg(target_os = "macos")]
fn uninstall_launchd() -> Result<()> {
    use anyhow::Context;

    let home = dirs::home_dir().context("no home directory")?;
    let plist_path = home.join("Library/LaunchAgents/dev.hangar.agent.plist");

    if plist_path.exists() {
        let _ = std::process::Command::new("launchctl")
            .args(["unload", "-w", plist_path.to_str().unwrap_or("")])
            .status();
        std::fs::remove_file(&plist_path)
            .with_context(|| format!("removing {}", plist_path.display()))?;
        println!("ok removed launchd agent at {}", plist_path.display());
    } else {
        println!("i no launchd agent registered at {}", plist_path.display());
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn uninstall_systemd() -> Result<()> {
    use anyhow::Context;

    let home = dirs::home_dir().context("no home directory")?;
    let unit_path = home.join(".config/systemd/user/hangar.service");

    if unit_path.exists() {
        // Best-effort disable — silently ignore failures (user session may be
        // absent on a root VPS).
        let _ = std::process::Command::new("systemctl")
            .args(["--user", "disable", "--now", "hangar"])
            .status();
        std::fs::remove_file(&unit_path)
            .with_context(|| format!("removing {}", unit_path.display()))?;
        println!("ok removed systemd user unit at {}", unit_path.display());
    } else {
        println!("i no systemd --user unit at {}", unit_path.display());
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn uninstall_task_scheduler() -> Result<()> {
    use std::process::Command;

    let status = Command::new("schtasks")
        .args(["/Delete", "/F", "/TN", "Hangar Daemon"])
        .status();
    match status {
        Ok(s) if s.success() => {
            println!("ok removed Task Scheduler task 'Hangar Daemon'");
        }
        _ => {
            println!("i no Task Scheduler task 'Hangar Daemon' registered");
        }
    }
    Ok(())
}
