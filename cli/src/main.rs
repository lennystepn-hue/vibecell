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
