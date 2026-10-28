import io
import json
from pathlib import Path

from ticket_readiness.cli import EXIT_DATA, EXIT_OK, EXIT_PROVIDER, EXIT_THRESHOLD, main
from ticket_readiness.llm import AnthropicProvider, ProviderError, RulesOnlyProvider
from ticket_readiness.report import build_report, render_text
from ticket_readiness.ticket import load_ticket

DATA = Path(__file__).resolve().parent.parent / "data" / "tickets"


def run(*argv):
    out = io.StringIO()
    return main(list(argv), out=out), out.getvalue()


def test_review_text(monkeypatch):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "rules")
    code, text = run("review", str(DATA / "vague-export.md"))
    assert code == EXIT_OK and "not ready (advisory)" in text and "To confirm (assumptions)" in text


def test_review_json(monkeypatch):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "rules")
    code, text = run("review", str(DATA / "dark-mode.md"), "--json")
    data = json.loads(text)
    assert code == EXIT_OK and data["reports"][0]["verdict"] == "looks ready" and "disclaimer" in data["reports"][0]


def test_missing_file_only(monkeypatch, tmp_path):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "rules")
    code, text = run("review", str(tmp_path / "nope.md"))
    assert code == EXIT_DATA and "not found" in text


def test_mixed_good_and_bad_files(monkeypatch, tmp_path):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "rules")
    code, text = run("review", str(DATA / "dark-mode.md"), str(tmp_path / "nope.md"))
    assert code == EXIT_OK and "error:" in text and "SYN-105" in text


def test_fail_under(monkeypatch):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "rules")
    code, _ = run("review", str(DATA / "vague-export.md"), "--fail-under", "50")
    assert code == EXIT_THRESHOLD


def test_bad_provider(monkeypatch):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "crystal-ball")
    code, text = run("review", str(DATA / "dark-mode.md"))
    assert code == EXIT_PROVIDER


class FakeClient:
    def __init__(self, text=None, fail=False):
        self.text, self.fail = text, fail
        self.calls = []
        outer = self

        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                outer.calls.append(kw)
                if outer.fail:
                    raise RuntimeError("timeout")

                class B:
                    text = outer.text

                class R:
                    content = [B()]

                return R()

        self.messages = messages


def test_rules_provider_returns_none():
    t = load_ticket(DATA / "vague-export.md")
    assert RulesOnlyProvider().rewrite(t, []) is None


def test_anthropic_provider_rewrite_labelled():
    t = load_ticket(DATA / "vague-export.md")
    client = FakeClient(text="## Summary\nOPEN QUESTION: which data?")
    prov = AnthropicProvider(client=client, model="fake")
    r = build_report(t)
    r.rewrite, r.rewrite_provider = prov.rewrite(t, r.findings), prov.name
    rendered = render_text(r)
    assert "model-generated, review before use" in rendered and "OPEN QUESTION" in rendered
    assert "FINDINGS:" in client.calls[0]["messages"][0]["content"]


def test_anthropic_provider_failure_surfaces(monkeypatch):
    monkeypatch.setenv("TICKET_READINESS_PROVIDER", "anthropic")
    import ticket_readiness.cli as cli

    monkeypatch.setattr(cli, "provider_from_env", lambda: AnthropicProvider(client=FakeClient(fail=True), model="fake"))
    code, text = run("review", str(DATA / "dark-mode.md"))
    assert code == EXIT_OK and "unavailable (model call failed: timeout)" not in text  # rewrite omitted silently in text...
    code, text = run("review", str(DATA / "dark-mode.md"), "--json")
    assert "unavailable (model call failed: timeout)" in json.loads(text)["reports"][0]["rewrite_provider"]


def test_anthropic_requires_config(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import pytest

    with pytest.raises(ProviderError):
        AnthropicProvider()
