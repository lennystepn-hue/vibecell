//! `hangar daemon install` — register the daemon as an auto-starting service.
//!
//! - macOS:   LaunchAgent plist in ~/Library/LaunchAgents/dev.hangar.agent.plist
//! - Linux:   systemd --user unit at ~/.config/systemd/user/hangar.service
//! - Windows: Task Scheduler task named "Hangar Daemon" triggered at logon

use anyhow::Result;

pub async fn run() -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        install_launchd()
    }
    #[cfg(target_os = "linux")]
    {
        install_systemd()
    }
    #[cfg(target_os = "windows")]
    {
        install_task_scheduler()
    }
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    {
        anyhow::bail!("`hangar daemon install` is not supported on this platform")
    }
}

#[cfg(target_os = "macos")]
fn install_launchd() -> Result<()> {
    use anyhow::Context;

    let home = dirs::home_dir().context("no home directory")?;
    let agent_dir = home.join("Library/LaunchAgents");
    std::fs::create_dir_all(&agent_dir)
        .with_context(|| format!("creating {}", agent_dir.display()))?;
    let plist_path = agent_dir.join("dev.hangar.agent.plist");

    let exe = std::env::current_exe().context("locating current executable")?;
    let log_dir = home.join(".hangar");
    std::fs::create_dir_all(&log_dir).ok();

    let plist = format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>dev.hangar.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
        <string>daemon</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{log}/hangar.log</string>
    <key>StandardErrorPath</key><string>{log}/hangar.log</string>
</dict>
</plist>
"#,
        exe = exe.display(),
        log = log_dir.display(),
    );
    std::fs::write(&plist_path, plist)
        .with_context(|| format!("writing {}", plist_path.display()))?;

    // Best-effort load now. `-w` enables on next boot as well.
    let _ = std::process::Command::new("launchctl")
        .args([
            "load",
            "-w",
            plist_path.to_str().unwrap_or("dev.hangar.agent.plist"),
        ])
        .status();

    println!("ok installed launchd agent at {}", plist_path.display());
    println!("  daemon will auto-start on login. Run `hangar daemon status` to verify.");
    Ok(())
}

#[cfg(target_os = "linux")]
fn install_systemd() -> Result<()> {
    use anyhow::Context;

    let home = dirs::home_dir().context("no home directory")?;
    let unit_dir = home.join(".config/systemd/user");
    std::fs::create_dir_all(&unit_dir)
        .with_context(|| format!("creating {}", unit_dir.display()))?;
    let unit_path = unit_dir.join("hangar.service");

    let exe = std::env::current_exe().context("locating current executable")?;
    let log_dir = home.join(".hangar");
    std::fs::create_dir_all(&log_dir).ok();

    let unit = format!(
        r#"[Unit]
Description=Hangar daemon (MCP server for Claude Code)
After=network.target

[Service]
ExecStart={exe} daemon start
Restart=on-failure
RestartSec=5
StandardOutput=append:{log}/hangar.log
StandardError=append:{log}/hangar.log

[Install]
WantedBy=default.target
"#,
        exe = exe.display(),
        log = log_dir.display(),
    );
    std::fs::write(&unit_path, unit).with_context(|| format!("writing {}", unit_path.display()))?;

    println!(
        "ok installed systemd --user unit at {}",
        unit_path.display()
    );
    println!("  enable + start with:");
    println!("    systemctl --user daemon-reload");
    println!("    systemctl --user enable --now hangar");
    Ok(())
}

#[cfg(target_os = "windows")]
fn install_task_scheduler() -> Result<()> {
    use anyhow::Context;
    use std::process::Command;

    let exe = std::env::current_exe().context("locating current executable")?;
    let exe_str = exe.to_string_lossy().to_string();

    let status = Command::new("schtasks")
        .args([
            "/Create",
            "/F",
            "/TN",
            "Hangar Daemon",
            "/TR",
            &format!("\"{}\" daemon start", exe_str),
            "/SC",
            "ONLOGON",
            "/RL",
            "LIMITED",
        ])
        .status()
        .context("invoking schtasks")?;
    if !status.success() {
        anyhow::bail!("schtasks failed with {}", status);
    }

    println!("ok registered Task Scheduler task 'Hangar Daemon'");
    println!("  runs on every logon. `schtasks /Run /TN \"Hangar Daemon\"` to start immediately.");
    Ok(())
}
