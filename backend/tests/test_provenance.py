"""Provenance checks (PLAN §3.18): five types, one check each; a failing line is dropped and logged; assumptions block Approve."""

from __future__ import annotations

from app.audit.chain import sha256_hex
from app.models import (
    AssumptionProvenance, BOMLine, PhotoRegionProvenance, ReadmeQuoteProvenance, ReferenceProjectProvenance, TemplateRowProvenance,
)
from app.pipeline import provenance as pv

TEXT = "# Build\n\n| Part | Qty |\n|---|---|\n| Brushless motor 1404 | 4 |\n| Brushless motor 1404 | 4 |\n"
SHA = sha256_hex(TEXT)
TPL_SHA = "t" * 64
CTX = {"docs": {SHA: TEXT}, "template_rows": {"kb://tpl_quadcopter#motor": {"row_id": "motor"}}, "template_sha256": TPL_SHA,
       "image_sha256": ["i" * 64], "images": {"img1": (1024, 768)}, "labels": ["servo", "breadboard"]}


def line(prov, name="Brushless motor", **kw):
    return BOMLine(bom_line_id="b0", raw_name=name, qty=4, provenance=prov, line_kind="part", status="extracted", **kw)


def quote(q="Brushless motor 1404", span=None, **kw):
    span = span or pv.find_span(TEXT, q) or (0, 1)
    return ReadmeQuoteProvenance(type="readme_quote", url="https://github.com/a/b", path="README.md", commit_sha="c" * 40, via="http", quote=q, span=span,
                                 line_from=5, line_to=5, doc_sha256=kw.pop("doc", SHA), **kw)


def tpl(kb="kb://tpl_quadcopter#motor", sha=TPL_SHA, basis="rule_of_thumb"):
    return TemplateRowProvenance(type="template_row", kb_ref=kb, template_id="tpl_quadcopter", row_id=kb.split("#")[-1], template_sha256=sha, basis=basis)


def photo(box=(10, 10, 200, 200), sha="i" * 64, label="servo"):
    return PhotoRegionProvenance(type="photo_region", image_id="img1", image_sha256=sha, box_xyxy_px=box, label=label, score=0.7, detector="claude_vision")


def test_readme_quote_must_be_an_exact_substring_of_the_fetched_text():
    assert pv.check_line(line(quote()), CTX)
    assert pv.why_failed(line(quote("Brushless Motor 1404", span=(0, 20))), CTX) == "quote is not an exact substring of the fetched document"
    assert "span" in pv.why_failed(line(quote(span=(0, 20))), CTX)
    assert "not fetched" in pv.why_failed(line(quote(doc="f" * 64)), CTX)  # a document we never fetched proves nothing


def test_span_is_the_occurrence_on_the_given_line():
    first, second = pv.find_span(TEXT, "Brushless motor 1404"), pv.find_span(TEXT, "Brushless motor 1404", line_from=6)
    assert first != second and TEXT[second[0]:second[1]] == "Brushless motor 1404" and TEXT.count("\n", 0, second[0]) + 1 == 6


def test_reference_project_needs_an_allowed_host_and_a_quote_from_the_hashed_page():
    def ref(url="https://docs.px4.io/x", q="Brushless motor 1404"):
        return ReferenceProjectProvenance(type="reference_project", url=url, title="X500", quote=q, span=pv.find_span(TEXT, q) or (0, 1), doc_sha256=SHA,
                                          fetched_at="2026-11-20T13:00:00-08:00", found_via="keenable", fetched_via="http")
    assert pv.check_line(line(ref()), CTX)
    assert "never-request" in pv.why_failed(line(ref(url="https://www.amazon.com/dp/B0")), CTX)
    assert pv.why_failed(line(ref(q="a search snippet that is not in the page")), CTX)


def test_template_row_must_resolve_and_match_the_loaded_template_hash():
    assert pv.check_line(line(tpl()), CTX)
    assert "does not resolve" in pv.why_failed(line(tpl(kb="kb://tpl_quadcopter#warp_drive")), CTX)
    assert "hash" in pv.why_failed(line(tpl(sha="z" * 64)), CTX)
    assert pv.check_line(line(tpl(kb="kb://tpl_quadcopter#esc")), {**CTX, "kb_resolver": lambda ref: ref.endswith("#esc")})


def test_photo_region_needs_the_image_in_scope_a_box_inside_it_and_a_named_label():
    assert pv.check_line(line(photo()), CTX)
    assert "mandate scope" in pv.why_failed(line(photo(sha="x" * 64)), CTX)
    assert "outside" in pv.why_failed(line(photo(box=(900, 700, 1100, 800))), CTX)
    assert "empty" in pv.why_failed(line(photo(box=(50, 50, 50, 90))), CTX)
    assert "label" in pv.why_failed(line(photo(label="flux capacitor")), CTX)


def test_assumption_needs_a_statement_and_blocks_until_confirmed():
    ok = line(AssumptionProvenance(type="assumption", statement="Assumed 3-inch props", basis="chip defaulted"))
    assert pv.check_line(ok, CTX) and pv.open_assumptions([ok]) == ["b0"]
    assert pv.why_failed(line(AssumptionProvenance(type="assumption", statement="  ", basis="x")), CTX) == "assumption without a statement"
    ok.provenance.confirmed_by_user = True
    assert pv.open_assumptions([ok]) == []
    removed = line(AssumptionProvenance(type="assumption", statement="x", basis="y"))
    removed.status = "removed"
    assert pv.open_assumptions([removed]) == []


def test_failing_lines_are_dropped_and_logged_with_a_reason():
    kept, rejected = pv.check_lines([line(quote()), line(quote("invented part", span=(0, 5)), name="Invented"), line(tpl(kb="kb://nope#x"), name="Ghost")], CTX)
    assert [ln.raw_name for ln in kept] == ["Brushless motor"]
    assert [(r["raw_name"], r["provenance_type"]) for r in rejected] == [("Invented", "readme_quote"), ("Ghost", "template_row")] and all(r["reason"] for r in rejected)


def test_a_failing_support_is_removed_but_the_line_stays():
    ln = line(quote(supports=[photo(sha="x" * 64), tpl()]))
    assert pv.check_line(ln, CTX) and [s.type for s in ln.provenance.supports] == ["template_row"]


def test_merge_keeps_the_strongest_provenance_and_moves_the_rest_to_supports():
    a = line(tpl(), name="Brushless motor", category="motor")
    b = line(quote(), name="Brushless motor")
    c = line(photo(), name="Servo")
    merged = pv.merge_lines([[a], [b], [c]])
    assert [ln.bom_line_id for ln in merged] == ["b1", "b2"]
    assert merged[0].provenance.type == "readme_quote" and [s.type for s in merged[0].provenance.supports] == ["template_row"]
    assert merged[0].category == "motor"  # the weaker line still contributes what the stronger one lacks
    assert pv.STRENGTH == {"readme_quote": 1, "reference_project": 2, "template_row": 3, "photo_region": 4, "assumption": 5}
