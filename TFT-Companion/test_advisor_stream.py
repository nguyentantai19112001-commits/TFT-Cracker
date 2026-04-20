"""Unit tests for the streaming advisor's progressive JSON field extractor.

No network. Pure parser logic.
Run: py test_advisor_stream.py
"""

from __future__ import annotations

import sys

from advisor import _extract_complete_string_field as extract


FAILS: list[str] = []


def case(label: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILS.append(label)


def main() -> int:
    print("=== advisor stream parser ===")

    # empty buffer
    case("empty buffer returns None", extract("", "one_liner") is None)

    # key not yet in buffer
    case("missing key returns None",
         extract('{"other": "foo"', "one_liner") is None)

    # key present, string not yet closed
    case("open string returns None (no closing quote)",
         extract('{"one_liner": "roll', "one_liner") is None)

    # clean closed string
    case("closed string returns value",
         extract('{"one_liner": "Roll down", "confidence"', "one_liner")
         == "Roll down")

    # escaped quote inside the value
    case("escaped quote inside value",
         extract(r'{"one_liner": "say \"hi\"", "x": 1', "one_liner")
         == 'say "hi"')

    # newline escape handled
    case("escaped newline",
         extract(r'{"reasoning": "line1\nline2", "x"', "reasoning")
         == "line1\nline2")

    # different key ordering
    case("second field extracted",
         extract('{"a": "x", "one_liner": "Hold gold", "b": 1',
                 "one_liner") == "Hold gold")

    # streaming-in-progress simulation (only one_liner closed, reasoning open)
    buf = '{"one_liner": "Level 8 now", "confidence": "HIGH", "reasoning": "you are'
    case("partial stream: one_liner closed",
         extract(buf, "one_liner") == "Level 8 now")
    case("partial stream: reasoning still open",
         extract(buf, "reasoning") is None)

    # unicode passes through
    case("unicode value",
         extract('{"one_liner": "roll → win"}', "one_liner") == "roll → win")

    # should NOT match a substring key (key needs exact match)
    case("prefix-ambiguous key is not matched",
         extract('{"line": "bad", "one_liner": "good"', "one_liner") == "good")

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
