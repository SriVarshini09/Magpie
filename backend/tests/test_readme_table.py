"""README parts parser (PLAN §13.1): leading spaces, missing quantities, anchors, and the real SO-ARM100 README."""

from __future__ import annotations

from app.config import FIXTURES_DIR
from app.pipeline import readme_table as rt

README = (FIXTURES_DIR / "sources" / "SO-ARM100_README.md").read_text(encoding="utf-8")


def test_real_readme_gives_the_six_follower_rows():
    tables = rt.parse_parts(README, "One SO-101 follower arm")
    assert len(tables) == 1 and "One Follower Arm" in tables[0].heading
    rows = tables[0].rows
    assert [(r.name, r.qty) for r in rows] == [
        ("STS3215 Servo 7.4V, 1/345 gear (C001)", 6), ("Motor Control Board", 1), ("USB-C Cable 2 pcs", 1),
        ("Power Supply", 1), ("Table Clamp 2pcs", 1), ("Screwdriver Set", 1)]
    for r in rows:  # every quote is the document's own text, at the span and line we report
        assert README[r.span[0]:r.span[1]] == r.quote and README.split("\n")[r.line - 1].count(r.quote) >= 1
    assert rows[0].line == 96  # the follower table, not the two-arm table above it that repeats the text
    assert rows[5].quote == "Screwdriver Set"  # the footnote markup is not part of the quote
    assert rows[0].links[0]["url"].startswith("https://www.alibaba.com/")  # kept as data, never an offer


def test_without_a_goal_the_smallest_complete_build_wins_and_totals_are_skipped():
    tables = rt.parse_parts(README)
    assert "One Follower Arm" in tables[0].heading
    assert all(r.name.lower() != "total" for t in rt.parse_tables(README) for r in t.rows)
    assert not any(r.name.lower().endswith(".stl") for t in rt.parse_tables(README) for r in t.rows)  # files to print, not parts to buy


def test_leading_spaces_before_the_pipe():
    md = "## Parts\n\n   | Part | Qty |\n   |---|---|\n   | ESP32 board | 1 |\n\t| BME280 sensor | 2 |\n"
    rows = rt.parse_parts(md)[0].rows
    assert [(r.name, r.qty, r.qty_stated) for r in rows] == [("ESP32 board", 1, True), ("BME280 sensor", 2, True)]
    assert md[rows[0].span[0]:rows[0].span[1]] == "ESP32 board"


def test_missing_quantity_column_means_one_and_is_never_invented():
    md = "## Components\n\n| Component | Link |\n|---|---|\n| LiPo battery 3.7V | [shop](https://example.com/b) |\n| 10 jumper wires | n/a |\n"
    t = rt.parse_parts(md)[0]
    assert not t.has_qty_column
    assert [(r.name, r.qty, r.qty_stated) for r in t.rows] == [("LiPo battery 3.7V", 1, False), ("10 jumper wires", 1, False)]


def test_unparseable_quantity_is_kept_as_a_note_not_a_number():
    md = "## BOM\n\n| Item | Amount |\n|---|---|\n| M3 screws | a handful |\n| Servo | 2x |\n"
    rows = rt.parse_parts(md)[0].rows
    assert (rows[0].qty, rows[0].qty_stated, rows[0].qty_text) == (1, False, "a handful")
    assert (rows[1].qty, rows[1].qty_stated) == (2, True)


def test_row_that_points_to_another_section_carries_both_quotes():
    md = ("## Parts\n\n| Part | Qty | Notes |\n|---|---|---|\n| Display panel | 1 | See Panel Support |\n| Cable | 1 | [details](#panel-support) |\n\n"
          "## Panel Support\n\n| Panel | Driver |\n|---|---|\n| 7.5 inch e-paper V2 | DESPI-C02 |\n")
    rows = rt.parse_parts(md)[0].rows
    for r in rows[:2]:
        assert len(r.more_quotes) == 1
        mq = r.more_quotes[0]
        assert mq["quote"] == "7.5 inch e-paper V2" and md[mq["span"][0]:mq["span"][1]] == mq["quote"] and mq["line_from"] == 12
    assert rt.find_anchor(md, "#panel-support")[0] == 8


def test_bullet_lists_under_a_parts_heading_when_there_is_no_table():
    md = "# Robot\n\n## What you need\n\n- 2x SG90 servo - any brand\n- Arduino Uno ([buy](https://example.com))\n* 4 pcs AA battery\n\n## Wiring\n\n- not a part\n"
    t = rt.parse_parts(md)[0]
    assert t.kind == "list" and [(r.name, r.qty, r.qty_stated) for r in t.rows] == [("SG90 servo", 2, True), ("Arduino Uno", 1, False), ("AA battery", 4, True)]


def test_tables_outside_parts_headings_and_code_fences_are_ignored():
    md = "## Results\n\n| Run | Score |\n|---|---|\n| A | 1 |\n\n```\n## Parts\n| Part | Qty |\n|---|---|\n| fake | 9 |\n```\n"
    assert rt.parse_parts(md) == []
