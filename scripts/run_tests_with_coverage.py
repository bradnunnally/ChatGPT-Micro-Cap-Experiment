#!/usr/bin/env python3
"""Run unit tests and enforce a minimum coverage percentage.

This script uses Python's built-in ``trace`` module to collect basic
coverage information while executing the project's pytest suite.  It
avoids external dependencies such as ``coverage`` or ``pytest-cov``
which may not be available in the execution environment.

The script prints a per-file summary of executed versus total lines and
exits with a non-zero status code if the overall coverage percentage is
below the required threshold (95% by default).
"""

from __future__ import annotations

import argparse
import os
import sys
import trace

import pytest

from infra.logging import get_logger, new_correlation_id

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run_tests() -> trace.CoverageResults:
    """Run pytest under ``trace`` and return coverage results."""
    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoremods=("pytest",),
        ignoredirs=[sys.prefix, sys.exec_prefix],
    )
    tracer.runfunc(lambda: pytest.main([]))
    return tracer.results()


def compute_coverage(results: trace.CoverageResults) -> tuple[dict[str, tuple[int, int]], float]:
    """Compute executed/total line counts for project files.

    Returns a mapping of filename -> (executed, total) and the overall coverage percentage.
    """
    files: dict[str, set[int]] = {}
    for (filename, lineno), _ in results.counts.items():
        if not filename.startswith(PROJECT_ROOT):
            continue
        if os.sep + "tests" + os.sep in filename:
            continue
        files.setdefault(filename, set()).add(lineno)

    totals: dict[str, tuple[int, int]] = {}
    covered = missed = 0
    for filename, executed_lines in files.items():
        try:
            with open(filename, "r", encoding="utf-8") as f:
                # Count only non-empty, non-comment lines as executable.
                lines = [line for line in f if line.strip() and not line.strip().startswith("#")]
        except OSError:
            continue
        total = len(lines)
        executed = len(executed_lines)
        totals[filename] = (executed, total)
        covered += executed
        missed += total - executed

    coverage_pct = 100.0 * covered / (covered + missed) if (covered + missed) else 0.0
    return totals, coverage_pct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min",
        type=float,
        default=95.0,
        help="minimum acceptable overall coverage percentage",
    )
    args = parser.parse_args()

    logger = get_logger(__name__)
    with new_correlation_id():
        results = run_tests()
        totals, coverage_pct = compute_coverage(results)

        for filename, (executed, total) in sorted(totals.items()):
            rel = os.path.relpath(filename, PROJECT_ROOT)
            logger.info(
                "file coverage",
                extra={
                    "event": "test_coverage_file",
                    "file": rel,
                    "executed": executed,
                    "total": total,
                },
            )
        logger.info(
            "total coverage",
            extra={
                "event": "test_coverage_total",
                "coverage_pct": round(coverage_pct, 2),
                "min_required": args.min,
            },
        )

        if coverage_pct < args.min:
            logger.error(
                "coverage below minimum",
                extra={
                    "event": "test_coverage_below_min",
                    "coverage_pct": round(coverage_pct, 2),
                    "min_required": args.min,
                },
            )
            return 1
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
