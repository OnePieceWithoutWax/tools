"""Scrub tests against real PDFs built with pikepdf."""

from __future__ import annotations

from pathlib import Path

import pikepdf
from pdf_scrub.scrub import scrub


def _link_annot(pdf: pikepdf.Pdf, uri: str) -> pikepdf.Object:
    return pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Link,
            Rect=pikepdf.Array([0, 0, 100, 20]),
            A=pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String(uri)),
        )
    )


def _watermark_annot(pdf: pikepdf.Pdf) -> pikepdf.Object:
    return pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Watermark,
            Rect=pikepdf.Array([0, 0, 200, 200]),
        )
    )


def make_pdf(
    path: Path,
    *,
    mailto: bool = False,
    web_link: bool = False,
    watermark_annot: bool = False,
    watermark_layer: bool = False,
) -> None:
    """Build a one-page PDF containing the requested elements."""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    page = pdf.pages[0]

    annots = []
    if mailto:
        annots.append(_link_annot(pdf, "mailto:someone@example.com"))
    if web_link:
        annots.append(_link_annot(pdf, "https://example.com"))
    if watermark_annot:
        annots.append(_watermark_annot(pdf))
    if annots:
        page["/Annots"] = pdf.make_indirect(pikepdf.Array(annots))

    if watermark_layer:
        ocg = pdf.make_indirect(
            pikepdf.Dictionary(Type=pikepdf.Name.OCG, Name=pikepdf.String("Watermark Layer"))
        )
        pdf.Root.OCProperties = pikepdf.Dictionary(
            OCGs=pikepdf.Array([ocg]),
            D=pikepdf.Dictionary(ON=pikepdf.Array([ocg]), Order=pikepdf.Array([ocg])),
        )

    pdf.save(path)


def page_annots(path: Path) -> list[dict[str, str]]:
    """Return page-1 annotations as [{subtype, uri}] for easy assertions."""
    with pikepdf.open(path) as pdf:
        annots = pdf.pages[0].get("/Annots")
        if annots is None:
            return []
        out = []
        for annot in annots:
            action = annot.get("/A")
            uri = str(action.get("/URI", "")) if action is not None else ""
            out.append({"subtype": str(annot.get("/Subtype", "")), "uri": uri})
        return out


def test_removes_mailto_keeps_web_link(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    make_pdf(src, mailto=True, web_link=True)

    stats = scrub(src, dst)

    assert stats["mailto"] == 1
    remaining = page_annots(dst)
    assert remaining == [{"subtype": "/Link", "uri": "https://example.com"}]


def test_removes_watermark_annotation(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    make_pdf(src, watermark_annot=True)

    stats = scrub(src, dst)

    assert stats["watermark_annots"] == 1
    assert page_annots(dst) == []


def test_removes_watermark_layer(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    make_pdf(src, watermark_layer=True)

    stats = scrub(src, dst)

    assert stats["watermark_layers"] == 1
    with pikepdf.open(dst) as pdf:
        oc_props = pdf.Root["/OCProperties"]
        assert len(oc_props["/OCGs"]) == 0
        assert len(oc_props["/D"]["/ON"]) == 0
        assert len(oc_props["/D"]["/Order"]) == 0


def test_clean_pdf_passes_through_unchanged(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    make_pdf(src, web_link=True)

    stats = scrub(src, dst)

    assert stats == {"mailto": 0, "watermark_annots": 0, "watermark_layers": 0}
    assert page_annots(dst) == [{"subtype": "/Link", "uri": "https://example.com"}]
    with pikepdf.open(dst) as pdf:
        assert len(pdf.pages) == 1


def test_overwrites_input_when_no_output_given(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    make_pdf(src, mailto=True)

    stats = scrub(src)

    assert stats["mailto"] == 1
    assert page_annots(src) == []


def test_flags_can_skip_each_scrub(tmp_path: Path) -> None:
    src = tmp_path / "in.pdf"
    dst = tmp_path / "out.pdf"
    make_pdf(src, mailto=True, watermark_annot=True)

    stats = scrub(src, dst, mailto=False)

    assert "mailto" not in stats
    assert stats["watermark_annots"] == 1
    assert page_annots(dst) == [{"subtype": "/Link", "uri": "mailto:someone@example.com"}]
