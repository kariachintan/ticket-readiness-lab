from pathlib import Path

from ticket_readiness.checks import run_checks
from ticket_readiness.report import build_report, score_findings
from ticket_readiness.ticket import load_ticket, parse_ticket

DATA = Path(__file__).resolve().parent.parent / "data" / "tickets"


def checks_named(findings, name):
    return [f for f in findings if f.check == name]


def test_empty_ticket_is_high_and_capped():
    r = build_report(load_ticket(DATA / "empty.md"))
    assert r.verdict == "not ready" and r.score <= 40
    assert checks_named(r.findings, "empty-ticket")[0].kind == "fact"


def test_vague_export_findings():
    f = run_checks(load_ticket(DATA / "vague-export.md"))
    assert checks_named(f, "acceptance-criteria")[0].severity == "high"
    terms = {x.message for x in checks_named(f, "ambiguity")}
    assert any("'fast'" in m for m in terms) and any("'everything'" in m for m in terms)
    assert all(x.kind == "assumption" for x in checks_named(f, "edge-cases"))
    assert any("large result sets" in x.message for x in checks_named(f, "edge-cases"))


def test_well_formed_ticket_looks_ready():
    r = build_report(load_ticket(DATA / "dark-mode.md"))
    assert r.verdict == "looks ready" and r.score >= 80
    assert not r.facts  # every finding is an assumption to confirm


def test_edge_case_dedup_against_existing_text():
    # dark-mode.md already covers forced-colors; the generic theme hints must not repeat covered items
    f = run_checks(load_ticket(DATA / "dark-mode.md"))
    msgs = [x.message for x in checks_named(f, "edge-cases")]
    assert not any("high-contrast" in m for m in msgs)


def test_undeclared_dependency_reference():
    t = parse_ticket("---\nid: A-1\ntitle: T\n---\n## Summary\nAs a user I want X so that Y. Needs SYN-07 first.\n## Acceptance criteria\n- Given x, when y, then z\n- Given q, when r, then s\n")
    f = checks_named(run_checks(t), "dependencies")
    assert f and "SYN-07" in f[0].message and f[0].kind == "fact"


def test_declared_dependency_is_quiet():
    r = build_report(load_ticket(DATA / "password-reset.md"))
    assert not checks_named(r.findings, "dependencies")
    assert checks_named(r.findings, "recorded-assumptions")


def test_cross_team_mention_without_dependency():
    f = run_checks(load_ticket(DATA / "rate-limit-api.md"))
    dep = checks_named(f, "dependencies")
    assert dep and "coordination" in dep[0].message


def test_untestable_criterion_flagged():
    t = parse_ticket("---\nid: A\ntitle: T\n---\n## Acceptance criteria\n- It works nicely\n- Given a, when b, then c\n")
    ac = checks_named(run_checks(t), "acceptance-criteria")
    assert len(ac) == 1 and "works nicely" in ac[0].evidence


def test_single_criterion_assumption():
    t = parse_ticket("---\nid: A\ntitle: T\n---\n## Acceptance criteria\n- Given a, when b, then c\n")
    ac = checks_named(run_checks(t), "acceptance-criteria")
    assert ac[0].kind == "assumption"


def test_ambiguity_one_finding_per_term():
    t = parse_ticket("---\nid: A\ntitle: T\n---\nshould should should maybe maybe")
    amb = checks_named(run_checks(t), "ambiguity")
    assert sorted(a.message for a in amb) == ["Ambiguous term 'maybe'.", "Ambiguous term 'should'."]


def test_ambiguity_does_not_match_inside_words():
    t = parse_ticket("---\nid: A\ntitle: T\n---\nThe breakfast etcetera menu")  # 'fast' inside breakfast, 'etc' inside etcetera
    assert not checks_named(run_checks(t), "ambiguity")


def test_score_scale():
    assert score_findings([]) == (100, "looks ready")
    s, v = score_findings(run_checks(load_ticket(DATA / "vague-export.md")))
    assert v == "not ready" and s < 50
