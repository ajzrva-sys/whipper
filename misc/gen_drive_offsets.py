#!/usr/bin/env python3
"""One-shot: generate whipper/common/drive_offsets.py from AccurateRip dump."""
import re
from collections import defaultdict
from pathlib import Path

path = Path("/Users/aji/.local/share/mimocode/tool-output/tool_g001a0b6401e72001psxIXexr5")
lines = [ln.rstrip() for ln in path.read_text(errors="replace").splitlines()]
votes = defaultdict(lambda: defaultdict(int))
i = 0
while i < len(lines) - 3:
    name = lines[i].strip()
    off = lines[i + 1].strip()
    cnt = lines[i + 2].strip()
    if re.fullmatch(r"[+-]?\d+", off) and re.fullmatch(r"\d+", cnt) and name:
        upper = name.upper()
        tokens = set()
        tokens.update(re.findall(r"PX-[A-Z0-9]+(?:[A-Z]+)?", upper))
        tokens.update(re.findall(r"PREMIUM2?", upper))
        tokens.update(
            re.findall(r"(?:CRW|DRW|GSA|GCE|ND|AD|AW|UJ|WH|GH|BH|BD|SH)-[A-Z0-9]+[A-Z0-9]*", upper)
        )
        tokens.update(re.findall(r"UJ[A-Z0-9]{3,}", upper))
        for tok in tokens:
            if len(tok) >= 5 and re.search(r"\d", tok):
                votes[tok][int(off)] += int(cnt)
        i += 4
    else:
        i += 1

forced = {
    "PX-750A": 102,
    "PX-751A": 102,
    "PX-716A": 30,
    "PX-716AL": 30,
    "PX-755A": 30,
    "PX-760A": 30,
    "PX-708A": 30,
    "PX-712A": 30,
    "PX-740A": 618,
    "PX-L890SA": 6,
    "PX-L890UE": 6,
    "PX-891SA": 6,
    "PX-W5224A": 30,
    "PREMIUM": 30,
    "PREMIUM2": 30,
    "PX-800A": 48,
}
by_tok = {}
for tok, offs in votes.items():
    ranked = sorted(offs.items(), key=lambda x: (-x[1], abs(x[0])))
    best_off, best_cnt = ranked[0]
    total = sum(offs.values())
    if total > 3 and best_cnt / total < 0.55:
        continue
    by_tok[tok] = best_off
by_tok.update(forced)
rows = sorted(by_tok.items())

header = '''# -*- Mode: Python; test-case-name: whipper.test.test_common_drive_offsets -*-
# vi:si:et:sw=4:sts=4:ts=4
"""AccurateRip-published drive read offsets and find-ordering helpers."""

import re

import logging
logger = logging.getLogger(__name__)

# Product-token -> AccurateRip correction offset (samples).
# Derived from http://www.accuraterip.com/driveoffsets.htm (majority
# submitted offset per model token). Matching is substring-based on the
# drive model string returned by pycdio/camcontrol.
_RAW = """
'''

footer = '''
"""

KNOWN_MODEL_OFFSETS = {}
for _line in _RAW.strip().splitlines():
    _tok, _off = _line.split()
    KNOWN_MODEL_OFFSETS[_tok] = int(_off)


def _normalize_model(value):
    """Collapse whitespace and uppercase a drive model string."""
    if not value:
        return ""
    return re.sub(r"\\s+", " ", str(value)).strip().upper()


def known_offsets_for(vendor=None, model=None):
    """
    Return published AccurateRip offsets for a drive, most specific first.

    Longest matching product token wins (e.g. PX-750A over PX-75).
    :rtype: list of int
    """
    haystack = _normalize_model(model)
    vendor_n = _normalize_model(vendor)
    if vendor_n:
        haystack = (vendor_n + " " + haystack).strip()
    if not haystack:
        return []
    hits = []
    for token, offset in KNOWN_MODEL_OFFSETS.items():
        if token and token in haystack:
            hits.append((len(token), -abs(offset), offset))
    hits.sort(reverse=True)
    ordered = []
    for _, _, offset in hits:
        if offset not in ordered:
            ordered.append(offset)
    return ordered


def parse_offset_list(text):
    """Parse a whipper --offsets string into a list of ints."""
    offsets = []
    for block in text.split(","):
        block = block.strip()
        if not block:
            continue
        if ":" in block:
            a, b = block.split(":", 1)
            offsets.extend(range(int(a), int(b) + 1))
        else:
            offsets.append(int(block))
    return offsets


def order_offsets(base_offsets, drive_info=None, configured=None,
                 prioritize_known=True):
    """
    Build the offset probe order for `whipper offset find`.

    When prioritize_known is true, prepend the configured read offset and
    AccurateRip-known offsets for the detected drive, even if they are
    missing from the user-supplied list.
    """
    base = list(base_offsets or [])
    if not prioritize_known:
        return base
    prefix = []
    if configured is not None:
        prefix.append(int(configured))
    if drive_info:
        vendor, model = drive_info[0], drive_info[1]
        for offset in known_offsets_for(vendor, model):
            prefix.append(offset)
    ordered = []
    seen = set()
    for offset in prefix + base:
        offset = int(offset)
        if offset not in seen:
            ordered.append(offset)
            seen.add(offset)
    return ordered
'''

body = header + "".join(f"{tok} {off}\n" for tok, off in rows) + footer
dest = Path("/Users/aji/project/whipper/whipper/common/drive_offsets.py")
dest.write_text(body)
print("wrote", dest, "tokens", len(rows), "bytes", dest.stat().st_size)
