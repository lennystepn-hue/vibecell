from app.mcp.tools import TOOLS, TOOLS_BY_NAME


def test_exactly_22_tools_registered() -> None:
    assert len(TOOLS) == 22


def test_vibecell_run_is_absent() -> None:
    assert "vibecell.run" not in TOOLS_BY_NAME
    names = [t.name for t in TOOLS]
    assert "vibecell.run" not in names


def test_all_expected_tools_present() -> None:
    expected = {
        "vibecell.ping", "vibecell.active", "vibecell.list", "vibecell.get",
        "vibecell.brief", "vibecell.search", "vibecell.recent_projects", "vibecell.switch",
        "vibecell.log_session", "vibecell.update_context", "vibecell.decision",
        "vibecell.idea", "vibecell.note_append", "vibecell.ship", "vibecell.status",
        "vibecell.claude_md", "vibecell.handover", "vibecell.activity",
        "vibecell.secret_set", "vibecell.secret_list", "vibecell.secret_rm",
        "vibecell.secret_get_value",
    }
    actual = {t.name for t in TOOLS}
    assert actual == expected
