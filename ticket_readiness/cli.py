"""ticket-readiness review <file...> [--json] [--fail-under N]"""
from __future__ import annotations

import argparse
import json
import sys

from .llm import ProviderError, provider_from_env
from .report import build_report, render_text
from .ticket import TicketError, load_ticket

EXIT_OK, EXIT_USAGE, EXIT_DATA, EXIT_PROVIDER, EXIT_THRESHOLD = 0, 2, 3, 4, 5


def main(argv: list[str] | None = None, out=None) -> int:
    out = out or sys.stdout
    p = argparse.ArgumentParser(prog="ticket-readiness", description="Advisory readiness review for engineering tickets.")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("review", help="review one or more ticket files")
    r.add_argument("files", nargs="+")
    r.add_argument("--json", action="store_true", help="machine-readable output")
    r.add_argument("--fail-under", type=int, default=None,
                   help="exit 5 if any ticket scores below N (for CI gates; still advisory - a human can override)")
    args = p.parse_args(argv)

    try:
        provider = provider_from_env()
    except ProviderError as exc:
        print(f"error: {exc}", file=out)
        return EXIT_PROVIDER

    reports, errors = [], []
    for path in args.files:
        try:
            ticket = load_ticket(path)
        except TicketError as exc:
            errors.append(str(exc))
            continue
        report = build_report(ticket)
        try:
            report.rewrite = provider.rewrite(ticket, report.findings)
            report.rewrite_provider = provider.name
        except ProviderError as exc:
            report.rewrite = None
            report.rewrite_provider = f"unavailable ({exc})"
        reports.append(report)

    if args.json:
        print(json.dumps({"reports": [r.to_dict() for r in reports], "errors": errors}, indent=2), file=out)
    else:
        for r in reports:
            print(render_text(r), file=out)
            print(file=out)
        for e in errors:
            print(f"error: {e}", file=out)
        if reports:
            print("Summary: " + ", ".join(f"{r.ticket_id}={r.score}" for r in reports), file=out)

    if errors and not reports:
        return EXIT_DATA
    if args.fail_under is not None and any(r.score < args.fail_under for r in reports):
        return EXIT_THRESHOLD
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
