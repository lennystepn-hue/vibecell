from app.mcp.tools import TOOLS, TOOLS_BY_NAME, resolve_tool


def test_exactly_32_tools_registered() -> None:
    assert len(TOOLS) == 32


def test_vibecell_run_is_absent() -> None:
    assert "vibecell_run" not in TOOLS_BY_NAME
    assert "vibecell.run" not in TOOLS_BY_NAME
    names = [t.name for t in TOOLS]
    assert "vibecell_run" not in names
    assert "vibecell.run" not in names


def test_all_expected_tools_present() -> None:
    expected = {
        "vibecell_ping", "vibecell_active", "vibecell_list", "vibecell_get",
        "vibecell_brief", "vibecell_search", "vibecell_recent_projects", "vibecell_switch",
        "vibecell_log_session", "vibecell_update_context", "vibecell_decision",
        "vibecell_idea", "vibecell_note_append", "vibecell_ship", "vibecell_status",
        "vibecell_claude_md", "vibecell_handover", "vibecell_activity",
        "vibecell_secret_set", "vibecell_secret_list", "vibecell_secret_rm",
        "vibecell_secret_get_value",
        "vibecell_todo_list", "vibecell_todo_add", "vibecell_todo_batch_add",
        "vibecell_todo_start", "vibecell_todo_complete", "vibecell_todo_match",
        "vibecell_ai_plan_todos", "vibecell_ai_launch_copy",
        "vibecell_ai_retro", "vibecell_ai_resume_brief",
    }
    actual = {t.name for t in TOOLS}
    assert actual == expected


def test_names_pass_claude_desktop_validation() -> None:
    """Tool names must match ^[a-zA-Z0-9_-]{1,64}$ (Claude Desktop validator)."""
    import re
    pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    for t in TOOLS:
        assert pattern.match(t.name), f"tool name fails Claude Desktop validation: {t.name!r}"


def test_legacy_dotted_names_still_resolve() -> None:
    """Old Claude Code sessions cached the dotted names (vibecell.ping).
    The dispatcher must still accept those via resolve_tool()."""
    assert resolve_tool("vibecell_ping") is not None
    assert resolve_tool("vibecell.ping") is not None
    # Unknown names still return None.
    assert resolve_tool("vibecell.nope") is None
    assert resolve_tool("totally_unrelated") is None
