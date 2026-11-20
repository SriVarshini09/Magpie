"""Deterministic parser for parts tables and bullet lists in a README (PLAN §13.1). Owner: A.

Rules:
- A table row may have leading spaces before the first `|` (a `^\\|` regex misses real READMEs).
- A missing quantity column means quantity 1. A quantity is never invented.
- A cell that points to another section ("See Panel Support") is followed through its anchor, and the
  row it points to becomes a second quote on the same line.
- Every row keeps the exact text of its name cell and where it sits in the document, so the quote
  check (`pipeline/provenance.py`) can prove the line was not invented.
- Links in the source are kept as data. They are never offers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = ["parse_tables", "parse_bullets", "parse_parts", "select_tables", "TableRow", "PartsTable", "slugify", "find_anchor"]

FILE_NAME = re.compile(r"(?i)\.(stl|step|stp|3mf|obj|pdf|zip|md|py|ino|urdf|dxf|svg|png|jpe?g)$")  # a file to download, not a part to buy
PARTS_HEADING = re.compile(r"(?i)\b(parts?|components?|bom|bill of materials|items? needed|what you(?:'ll| will)? need|materials|hardware|shopping list|sourcing)\b")
NAME_COL = re.compile(r"(?i)^(part|parts|item|items|component|components|name|description|product|what|material)s?\b")
QTY_COL = re.compile(r"(?i)^(amount|qty|quantity|count|pcs|pieces|number|#|no\.?|units?)\b")
SKIP_NAME = re.compile(r"(?i)^(total|subtotal|sum|shipping|tax|---+|-+|n/?a)?$")
# Tables that list software, fonts, icons or people, not parts to buy: a licence column, or a credits-type heading
NOT_PARTS_COL = re.compile(r"(?i)^(licen[cs]es?|copyright|author|contributors?)$")
NOT_PARTS_HEADING = re.compile(r"(?i)\b(licen[cs](e|es|ing)|credits?|acknowledg(e?ments?)?|attributions?|contributors?|changelog|release notes)\b")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_ROW = re.compile(r"^\s*\|.*\|\s*$|^\s*[^|\s][^|]*\|.*$")
_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_SEE = re.compile(r"(?i)\bsee\s+(?:the\s+)?(?:section\s+)?[\"'“]?(?P<label>[A-Z0-9][\w .&/+-]{1,60}?)[\"'”]?(?:\s+(?:section|table|below|above))?\s*$")
_BULLET = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
_QTY_PREFIX = re.compile(r"^\s*(\d{1,4})\s*(?:x|×|pcs?\.?|pieces?)?\s+(?=\S)", re.I)
_QTY_X = re.compile(r"^\s*(\d{1,4})\s*[x×]\s*", re.I)


@dataclass
class TableRow:
    name: str  # cleaned name (markup stripped)
    quote: str  # exact substring of the document (the name cell, or its clean prefix)
    span: tuple[int, int]  # character offsets of `quote` in the document, on `line`
    line: int  # 1-based line number
    qty: int = 1
    qty_stated: bool = False  # False: the source gives no quantity (we use 1 and say so)
    qty_text: str | None = None
    cells: dict[str, str] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)  # [{text, url}] data only, never offers
    more_quotes: list[dict[str, Any]] = field(default_factory=list)  # [{quote, span, line_from, line_to}]


@dataclass
class PartsTable:
    heading: str
    heading_line: int
    parents: list[str]
    columns: list[str]
    rows: list[TableRow]
    kind: str = "table"  # table | list
    has_qty_column: bool = False


def slugify(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    s = _LINK.sub(r"\1", heading).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def _line_offsets(text: str) -> list[int]:
    offs, pos = [], 0
    for line in text.split("\n"):
        offs.append(pos)
        pos += len(line) + 1
    return offs


def _split_cells(line: str) -> list[tuple[str, int]]:
    """[(cell text, start offset in the line)] for a markdown table row. Escaped pipes stay in the cell."""
    cells: list[tuple[str, int]] = []
    start, i, depth = 0, 0, 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            i += 2
            continue
        if ch == "`":
            depth ^= 1
        if ch == "|" and not depth:
            cells.append((line[start:i], start))
            start = i + 1
        i += 1
    cells.append((line[start:], start))
    if cells and not cells[0][0].strip():
        cells = cells[1:]  # leading "|" (possibly after spaces)
    if cells and not cells[-1][0].strip():
        cells = cells[:-1]
    return cells


def _clean_name(cell: str) -> tuple[str, str]:
    """(clean name, exact quote). The quote is the longest clean prefix that is also raw text of the cell."""
    raw = cell.strip()
    cut = len(raw)
    for marker in ("<sup", "<sub", "<a ", "<br", "**<", " **<", "[^"):
        i = raw.find(marker)
        if i > 0:
            cut = min(cut, i)
    quote = raw[:cut].rstrip(" *_")
    name = _LINK.sub(r"\1", quote)
    name = re.sub(r"<[^>]+>", "", name)
    name = re.sub(r"`|[*]+|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])", "", name).strip()
    name = re.sub(r"\s+", " ", name)
    if not quote or _LINK.search(quote) or "<" in quote:
        m = _LINK.search(raw)
        if m and m.group(1).strip():  # a linked name: quote the link text
            quote, name = m.group(1), re.sub(r"\s+", " ", m.group(1)).strip()
    return name, quote


def _parse_qty(cell: str) -> tuple[int | None, str | None]:
    s = re.sub(r"[*_`]", "", cell).strip()
    if not s:
        return None, None
    m = re.match(r"^(?:x\s*)?(\d{1,5})(?:\s*(?:x|pcs?\.?|pieces?|units?|sets?))?$", s, re.I)
    if m:
        return int(m.group(1)), None
    m = re.match(r"^(\d{1,5})\b", s)
    if m:
        return int(m.group(1)), s
    return None, s  # "a few", "1 set": stated but not a number


def find_anchor(text: str, label_or_anchor: str) -> tuple[int, str] | None:
    """Find the heading (or `<a name=…>`) a row points to. Returns (1-based line, heading text)."""
    want = slugify(label_or_anchor.lstrip("#"))
    if not want:
        return None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and slugify(m.group(2)) == want:
            return i + 1, m.group(2)
        if re.search(rf"<a\s+(?:name|id)=[\"']?{re.escape(label_or_anchor.lstrip('#'))}[\"']?\s*>", line, re.I):
            return i + 1, line.strip()
    for i, line in enumerate(lines):  # a looser match: the label is contained in the heading
        m = _HEADING.match(line)
        if m and want in slugify(m.group(2)):
            return i + 1, m.group(2)
    return None


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    out, fence = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if fence:
            continue
        m = _HEADING.match(line)
        if m:
            out.append((i, len(m.group(1)), _LINK.sub(r"\1", m.group(2)).strip(" :*_")))
    return out


def _context(heads: list[tuple[int, int, str]], line_idx: int) -> tuple[str, int, list[str]]:
    """(nearest heading, its 1-based line, parent headings) for a line."""
    stack: list[tuple[int, int, str]] = []
    for h in heads:
        if h[0] > line_idx:
            break
        while stack and stack[-1][1] >= h[1]:
            stack.pop()
        stack.append(h)
    if not stack:
        return "", 0, []
    return stack[-1][2], stack[-1][0] + 1, [s[2] for s in stack[:-1]]


def _follow(text: str, row: TableRow, cell: str, offs: list[int]) -> None:
    """Follow "See X" or a `(#anchor)` link in a non-name cell; add the first row of that section as a quote."""
    targets = [u for _, u in _LINK.findall(cell) if u.startswith("#")]
    m = _SEE.search(_LINK.sub(r"\1", cell).strip())
    if m:
        targets.append(m.group("label").strip())
    lines = text.split("\n")
    for t in targets:
        hit = find_anchor(text, t)
        if not hit:
            continue
        start = hit[0]  # 0-based index of the line after the heading
        for j in range(start, min(start + 40, len(lines))):
            if _HEADING.match(lines[j]) and j > start:
                break
            if _ROW.match(lines[j]) and not _SEP.match(lines[j]):
                cells = _split_cells(lines[j])
                if j + 1 < len(lines) and _SEP.match(lines[j + 1]):
                    continue  # the header row of the target table
                if cells and cells[0][0].strip():
                    q = cells[0][0].strip()
                    pos = offs[j] + lines[j].find(q)
                    row.more_quotes.append({"quote": q, "span": (pos, pos + len(q)), "line_from": j + 1, "line_to": j + 1})
                    return
            elif lines[j].strip() and not lines[j].lstrip().startswith(("<", "|", ">")):
                q = lines[j].strip()
                pos = offs[j] + lines[j].find(q)
                row.more_quotes.append({"quote": q, "span": (pos, pos + len(q)), "line_from": j + 1, "line_to": j + 1})
                return


def parse_tables(text: str) -> list[PartsTable]:
    """Every markdown table in the document, with its heading. Tables without a name column are skipped."""
    lines = text.split("\n")
    offs = _line_offsets(text)
    heads = _headings(lines)
    out: list[PartsTable] = []
    i, fence = 0, False
    while i < len(lines):
        if lines[i].lstrip().startswith(("```", "~~~")):
            fence = not fence
        if fence or i + 1 >= len(lines) or "|" not in lines[i] or not _SEP.match(lines[i + 1]) or "|" not in lines[i + 1]:
            i += 1
            continue
        header = [c.strip() for c, _ in _split_cells(lines[i])]
        clean = [re.sub(r"[*_`]", "", h).strip() for h in header]
        name_idx = next((k for k, h in enumerate(clean) if NAME_COL.match(h)), None)
        qty_idx = next((k for k, h in enumerate(clean) if QTY_COL.match(h)), None)
        heading, hline, parents = _context(heads, i)
        relevant = bool(PARTS_HEADING.search(" ".join([heading, *parents])))
        if any(NOT_PARTS_COL.match(h) for h in clean) or (NOT_PARTS_HEADING.search(heading) and not PARTS_HEADING.search(heading)):
            i += 2  # e.g. "Name | License | Description" under "Licensing": fonts and libraries, not parts
            continue
        if name_idx is None and relevant and qty_idx is not None and clean:
            name_idx = 0 if qty_idx != 0 else (1 if len(clean) > 1 else None)  # a quantity column but an unusual name header
        j = i + 2
        rows: list[TableRow] = []
        while j < len(lines) and "|" in lines[j] and lines[j].strip():
            cells = _split_cells(lines[j])
            if name_idx is not None and name_idx < len(cells):
                cell, cstart = cells[name_idx]
                name, quote = _clean_name(cell)
                if name and not SKIP_NAME.match(name) and not FILE_NAME.search(name):
                    pos = offs[j] + cstart + cell.find(quote) if quote in cell else offs[j] + lines[j].find(quote)
                    row = TableRow(name=name, quote=quote, span=(pos, pos + len(quote)), line=j + 1,
                                   cells={(clean[k] if k < len(clean) else f"col{k}"): c.strip() for k, (c, _) in enumerate(cells)})
                    if qty_idx is not None and qty_idx < len(cells):
                        q, note = _parse_qty(cells[qty_idx][0])
                        if q is not None:
                            row.qty, row.qty_stated = q, True
                        row.qty_text = note
                    for k, (c, _) in enumerate(cells):
                        row.links += [{"text": t, "url": u} for t, u in _LINK.findall(c) if not u.startswith("#")]
                        if k != name_idx:
                            _follow(text, row, c, offs)
                    if not row.more_quotes and _SEE.search(_LINK.sub(r"\1", cell).strip()):
                        _follow(text, row, cell, offs)
                    rows.append(row)
            j += 1
        if rows and (relevant or (name_idx is not None and NAME_COL.match(clean[name_idx]))):
            out.append(PartsTable(heading=heading, heading_line=hline, parents=parents, columns=clean, rows=rows, has_qty_column=qty_idx is not None))
        i = j
    return out


def parse_bullets(text: str) -> list[PartsTable]:
    """Bullet lists directly under a parts heading. Quantity comes only from an explicit "2x" or "2 pcs" prefix."""
    lines = text.split("\n")
    offs = _line_offsets(text)
    heads = _headings(lines)
    out: list[PartsTable] = []
    for idx, (hl, level, title) in enumerate(heads):
        if not PARTS_HEADING.search(title):
            continue
        end = next((h[0] for h in heads[idx + 1:] if h[1] <= level), len(lines))
        nxt = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        rows: list[TableRow] = []
        for j in range(hl + 1, min(end, nxt)):
            m = _BULLET.match(lines[j])
            if not m or len(m.group(1)) > 3:
                continue
            body = m.group(2)
            qty, stated = 1, False
            mq = _QTY_X.match(body) or _QTY_PREFIX.match(body)
            if mq and (mq.re is _QTY_X or re.match(r"^\s*\d+\s*(?:x|×|pcs?\.?|pieces?)\s", body, re.I)):
                qty, stated, body = int(mq.group(1)), True, body[mq.end():]
            name_part = re.split(r"\s+[-–—:]\s+|\s*\(\s*(?:https?://|\[)", body, maxsplit=1)[0]
            name, quote = _clean_name(name_part)
            if not name or len(name) > 120 or SKIP_NAME.match(name) or name.lower().startswith(("from ", "see ", "note")):
                continue
            pos = offs[j] + lines[j].find(quote)
            rows.append(TableRow(name=name, quote=quote, span=(pos, pos + len(quote)), line=j + 1, qty=qty, qty_stated=stated,
                                 links=[{"text": t, "url": u} for t, u in _LINK.findall(m.group(2)) if not u.startswith("#")]))
        if rows:
            _, _, parents = _context(heads, hl)
            out.append(PartsTable(heading=title, heading_line=hl + 1, parents=parents, columns=["Part"], rows=rows, kind="list"))
    return out


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def select_tables(tables: list[PartsTable], goal: str | None = None) -> list[PartsTable]:
    """Pick the table(s) that describe ONE build.

    A README often lists the same parts several times (a two-arm kit, then one arm). Tables with
    the same columns are alternatives: keep the one whose heading shares the most words with the
    goal, then the one with the smallest total quantity (the smallest complete build).
    Tables with different columns are different parts lists and are all kept.
    """
    groups: dict[tuple[str, ...], list[PartsTable]] = {}
    for t in tables:
        groups.setdefault(tuple(c.lower() for c in t.columns), []).append(t)
    goal_words = _words(goal or "")
    out: list[PartsTable] = []
    for group in groups.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        def score(t: PartsTable) -> tuple[int, int, int]:
            return (-len(goal_words & _words(t.heading)), sum(r.qty for r in t.rows), t.heading_line)
        out.append(min(group, key=score))
    return sorted(out, key=lambda t: t.heading_line)


def parse_parts(text: str, goal: str | None = None) -> list[PartsTable]:
    """Tables first; bullet lists only when the document has no parts table."""
    tables = parse_tables(text)
    if tables:
        return select_tables(tables, goal)
    return select_tables(parse_bullets(text), goal)
