"""Turn findings into a readiness report. Advisory only."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .checks import Finding, run_checks
from .ticket import Ticket

PENALTY = {"high": 25, "medium": 6, "low": 2}
HIGH_CAP = 40  # any high-severity fact caps the score: one missing fundamental outweighs many small wins


@dataclass
class Report:
    ticket_id: str
    title: str
    score: int                      # 0-100, higher = fewer concerns
    verdict: str                    # "looks ready" | "needs clarification" | "not ready"
    findings: list[Finding] = field(default_factory=list)
    rewrite: str | None = None      # optional, model-generated, clearly labelled
    rewrite_provider: str = "none"

    @property
    def facts(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "fact"]

    @property
    def assumptions(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "assumption"]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["disclaimer"] = DISCLAIMER
        return d


DISCLAIMER = (
    "Advisory output. Facts are observed in the ticket text; assumptions are the reviewer's guesses "
    "to confirm or reject. A human decides whether the ticket is ready."
)


def score_findings(findings: list[Finding]) -> tuple[int, str]:
    # Assumptions cost less than facts: they are prompts, not defects.
    total = 0
    for f in findings:
        total += PENALTY[f.severity] * (0.5 if f.kind == "assumption" else 1.0)
    score = max(0, int(round(100 - total)))
    has_high = any(f.severity == "high" for f in findings)
    if has_high:
        score = min(score, HIGH_CAP)
    verdict = "not ready" if has_high or score < 50 else "needs clarification" if score < 80 else "looks ready"
    return score, verdict


def build_report(ticket: Ticket) -> Report:
    findings = run_checks(ticket)
    score, verdict = score_findings(findings)
    return Report(ticket_id=ticket.id, title=ticket.title, score=score, verdict=verdict, findings=findings)


def render_text(r: Report) -> str:
    lines = [f"== {r.ticket_id}: {r.title}", f"   readiness {r.score}/100 - {r.verdict} (advisory)"]
    if not r.findings:
        lines.append("   no findings")
    if r.facts:
        lines.append("   Observed (facts):")
        for f in r.facts:
            lines.append(f"     [{f.severity}] {f.check}: {f.message}")
            if f.evidence:
                lines.append(f"            evidence: {f.evidence}")
            if f.suggestion:
                lines.append(f"            suggest:  {f.suggestion}")
    if r.assumptions:
        lines.append("   To confirm (assumptions):")
        for f in r.assumptions:
            lines.append(f"     [{f.severity}] {f.check}: {f.message}")
            if f.suggestion:
                lines.append(f"            suggest:  {f.suggestion}")
    if r.rewrite:
        lines.append(f"   Suggested rewrite ({r.rewrite_provider}; model-generated, review before use):")
        lines.extend("     " + l for l in r.rewrite.splitlines())
    lines.append(f"   {DISCLAIMER}")
    return "\n".join(lines)
