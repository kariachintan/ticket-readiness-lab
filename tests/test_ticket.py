import pytest

from ticket_readiness.ticket import TicketError, load_ticket, parse_ticket


def test_parse_front_matter_and_sections():
    t = parse_ticket("---\nid: X-1\ntitle: Hello\ndepends_on: [A-1, B-2]\n---\n## Summary\nhi\n## Acceptance criteria\n- one\n")
    assert t.id == "X-1" and t.title == "Hello"
    assert t.meta["depends_on"] == ["A-1", "B-2"]
    assert t.section("summary") == "hi"
    assert t.section("ACCEPTANCE CRITERIA", "ac") == "- one"
    assert t.section("nope") is None


def test_no_front_matter_uses_filename(tmp_path):
    f = tmp_path / "my-ticket.md"
    f.write_text("---\ntitle: T\n---\nbody")
    assert load_ticket(f).id == "my-ticket"


def test_empty_list_and_empty_body():
    t = parse_ticket("---\nid: X\ntitle: T\ndepends_on: []\n---\n")
    assert t.meta["depends_on"] == [] and t.is_empty


@pytest.mark.parametrize("text, msg", [
    ("", "empty"),
    ("---\nid: X\n", "unterminated"),
    ("---\nid X\n---\nbody", "bad front matter"),
    ("---\nid: X\n---\nbody", "no title"),
])
def test_errors(text, msg):
    with pytest.raises(TicketError, match=msg):
        parse_ticket(text)


def test_missing_file(tmp_path):
    with pytest.raises(TicketError, match="not found"):
        load_ticket(tmp_path / "x.md")


def test_non_utf8(tmp_path):
    f = tmp_path / "b.md"
    f.write_bytes(b"\xff\xfe---\ntitle: x\n---")
    with pytest.raises(TicketError, match="UTF-8"):
        load_ticket(f)
