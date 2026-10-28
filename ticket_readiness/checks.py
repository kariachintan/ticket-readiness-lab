"""Readiness checks.

Each check inspects a Ticket and yields Findings. A Finding is always one of:

* kind="fact"       - directly observable in the ticket text (e.g. "no
                      acceptance-criteria section"), with the evidence quoted.
* kind="assumption" - the reviewer's inference about what *might* be missing
                      (e.g. "exports of large datasets may need pagination").
                      These are suggestions for a human to confirm or reject.

Nothing here blocks a ticket. The verdict is advisory and says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .ticket import Ticket

Severity = str  # "high" | "medium" | "low"


@dataclass
class Finding:
    check: str
    severity: Severity
    kind: str  # "fact" | "assumption"
    message: str
    evidence: str = ""
    suggestion: str = ""


Check = Callable[[Ticket], Iterable[Finding]]
CHECKS: list[tuple[str, Check]] = []


def check(name: str):
    def deco(fn: Check) -> Check:
        CHECKS.append((name, fn))
        return fn
    return deco


AMBIGUOUS_TERMS = {
    "fast": "state a measurable target (e.g. p95 under 2s for 10k rows)",
    "quick": "state a measurable target",
    "everything": "enumerate exactly what is included",
    "etc": "list the remaining items or mark them out of scope",
    "tbd": "resolve before scheduling, or split the undecided part into a spike",
    "maybe": "decide, or record the open question explicitly",
    "probably": "confirm, or record as an assumption",
    "or so": "give a concrete value",
    "as needed": "define the trigger",
    "appropriate": "define what appropriate means here",
    "should": "prefer 'must' / 'must not' so testers know what is required",
    "like the": "name the exact behaviours to copy; 'like X' hides decisions",
    "similar to": "name the exact behaviours to copy",
    "user-friendly": "describe the concrete interaction",
    "robust": "state the failure modes it must survive",
}

GWT_RE = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.IGNORECASE | re.DOTALL)
MEASURABLE_RE = re.compile(r"\d|\bmust\b|\breturns?\b|\bshows?\b|\bwithin\b|\bat least\b|\bat most\b", re.IGNORECASE)
TICKET_REF_RE = re.compile(r"\b([A-Z]{2,6}-\d{2,6})\b")
TEAM_RE = re.compile(r"\b(coordinate|sync|align|depends? on|blocked by|waiting on|the \w+ team)\b", re.IGNORECASE)


def _bullets(section: str) -> list[str]:
    return [l.lstrip("-*0123456789. ").strip() for l in section.splitlines() if l.strip().startswith(("-", "*")) or re.match(r"^\s*\d+\.", l)]


@check("empty-ticket")
def empty_ticket(t: Ticket):
    if t.is_empty:
        yield Finding("empty-ticket", "high", "fact", "Ticket has a title but no body.",
                      evidence=t.title, suggestion="Add a summary, acceptance criteria, and scope before anyone estimates it.")


@check("user-and-outcome")
def user_and_outcome(t: Ticket):
    if t.is_empty:
        return
    summary = t.section("summary", "description") or t.body
    if not re.search(r"\bas an?\b.*\bi want\b|\bso that\b", summary, re.IGNORECASE | re.DOTALL):
        yield Finding("user-and-outcome", "medium", "fact",
                      "No actor or outcome is stated (no 'As a ... I want ... so that ...').",
                      evidence=summary.splitlines()[0][:120] if summary else "",
                      suggestion="Name who this is for and what they can do afterwards; it anchors every later decision.")


@check("acceptance-criteria")
def acceptance_criteria(t: Ticket):
    if t.is_empty:
        return
    ac = t.section("acceptance criteria", "acceptance", "ac", "done when")
    if ac is None:
        yield Finding("acceptance-criteria", "high", "fact", "No acceptance-criteria section.",
                      suggestion="Add 'Acceptance criteria' with testable Given/When/Then bullets.")
        return
    bullets = _bullets(ac)
    if not bullets:
        yield Finding("acceptance-criteria", "high", "fact", "Acceptance-criteria section is empty.", evidence=ac[:80])
        return
    for b in bullets:
        if not GWT_RE.search(b) and not MEASURABLE_RE.search(b):
            yield Finding("acceptance-criteria", "medium", "fact", "Criterion is not obviously testable.",
                          evidence=b[:120], suggestion="Rewrite as Given/When/Then or add a measurable condition.")
    if len(bullets) < 2:
        yield Finding("acceptance-criteria", "low", "assumption",
                      "Only one criterion; most features have at least a success and a failure path.",
                      suggestion="Consider adding the failure / invalid-input case.")


@check("ambiguity")
def ambiguity(t: Ticket):
    low = t.text.lower()
    for term, fix in AMBIGUOUS_TERMS.items():
        for m in re.finditer(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", low):
            start = max(0, m.start() - 40)
            snippet = t.text[start:m.end() + 40].replace("\n", " ").strip()
            yield Finding("ambiguity", "medium" if term not in {"should"} else "low", "fact",
                          f"Ambiguous term '{term}'.", evidence=f"...{snippet}...", suggestion=fix)
            break  # one finding per term keeps the report readable


@check("scope")
def scope(t: Ticket):
    if t.is_empty:
        return
    if t.section("out of scope", "non-goals", "not in scope") is None:
        yield Finding("scope", "low", "assumption", "No out-of-scope section; scope creep risk.",
                      suggestion="List the adjacent things this ticket deliberately does not do.")


EDGE_CASE_HINTS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\bexport|download|report\b", re.I), [
        "very large result sets (timeouts, memory, pagination or async job?)",
        "zero rows to export (empty-state UX)",
        "permissions: can a user export data they can only partially see?",
        "file format and character encoding",
    ]),
    (re.compile(r"\bimport|upload\b", re.I), ["malformed or oversized files", "partial failure mid-way: rollback or resume?"]),
    (re.compile(r"\bpassword|login|reset|auth|token\b", re.I), [
        "expired or already-used tokens", "concurrent reset requests for one account", "account enumeration via response differences",
    ]),
    (re.compile(r"\brate limit|throttl|429\b", re.I), [
        "clients that retry immediately after 429 (Retry-After header?)",
        "limit keyed per user vs per IP vs per API key; shared NAT addresses",
        "behaviour when the limiter backend (e.g. Redis) is unavailable: fail open or closed?",
    ]),
    (re.compile(r"\bapi|endpoint\b", re.I), ["backwards compatibility for existing clients", "error response shape and status codes"]),
    (re.compile(r"\bdark mode|theme|color|colour\b", re.I), ["user-uploaded images and embedded content that assume a light background", "print stylesheet"]),
]


@check("edge-cases")
def edge_cases(t: Ticket):
    if t.is_empty:
        return
    existing = (t.section("edge cases", "edge-cases", "error cases") or "").lower()
    seen: set[str] = set()
    for pattern, hints in EDGE_CASE_HINTS:
        if pattern.search(t.text):
            for hint in hints:
                key_words = [w for w in re.findall(r"[a-z]{5,}", hint.lower())][:2]
                already = key_words and all(w in existing or w in t.text.lower() for w in key_words)
                if hint in seen or already:
                    continue
                seen.add(hint)
                yield Finding("edge-cases", "medium", "assumption", f"Possible unhandled edge case: {hint}",
                              suggestion="Confirm whether it applies; if so, add it to acceptance criteria or out-of-scope.")


@check("dependencies")
def dependencies(t: Ticket):
    if t.is_empty:
        return
    declared = set(t.meta.get("depends_on", []) or [])
    referenced = {r for r in TICKET_REF_RE.findall(t.body) if r != t.id}
    for ref in sorted(referenced - declared):
        yield Finding("dependencies", "medium", "fact", f"Ticket {ref} is mentioned but not declared in depends_on.",
                      evidence=ref, suggestion="Declare it in front matter so planning tools can see the ordering.")
    m = TEAM_RE.search(t.body)
    if m and not declared and not referenced:
        yield Finding("dependencies", "medium", "fact", "Cross-team coordination is mentioned but no dependency is declared.",
                      evidence=t.body[max(0, m.start() - 30):m.end() + 50].replace("\n", " "),
                      suggestion="Name the owning team or ticket and whether it blocks start or release.")


@check("recorded-assumptions")
def recorded_assumptions(t: Ticket):
    for m in re.finditer(r"\(assumption[^)]*\)|\bassum(e|ption)s?\b[^.\n]*", t.body, re.IGNORECASE):
        yield Finding("recorded-assumptions", "low", "fact", "Ticket records an explicit assumption; make sure someone owns confirming it.",
                      evidence=m.group(0)[:120])
        break


def run_checks(t: Ticket) -> list[Finding]:
    findings: list[Finding] = []
    for _, fn in CHECKS:
        findings.extend(fn(t))
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.check))
    return findings
