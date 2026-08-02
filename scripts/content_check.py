"""Validate every question in the content banks and generators.

    pixi run content-check
"""

from __future__ import annotations

import sys

from tutor.content import content_summary, validate_content


def main() -> int:
    summary = content_summary()
    print("Content summary")
    print("---------------")
    for key, value in summary.items():
        print(f"  {key.replace('_', ' '):<18} {value}")
    print()

    problems = validate_content()
    if problems:
        print(f"Found {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("All skills produce valid, self-consistent questions. ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
