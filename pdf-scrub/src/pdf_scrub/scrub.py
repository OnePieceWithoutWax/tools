"""pikepdf operations: strip mailto link annotations and watermarks from a PDF."""

from __future__ import annotations

import contextlib
from pathlib import Path

import pikepdf


def _strip_mailto_links(pdf: pikepdf.Pdf) -> int:
    """Remove all /Link annotations whose action URI starts with 'mailto:'.

    Args:
        pdf: Open pikepdf document (modified in place).

    Returns:
        Number of mailto annotations removed.
    """
    removed = 0
    for page in pdf.pages:
        annots = page.get("/Annots")
        if annots is None:
            continue
        keep = []
        for annot in annots:
            if str(annot.get("/Subtype", "")) == "/Link":
                action = annot.get("/A")
                if action is not None and str(action.get("/S", "")) == "/URI":
                    uri = str(action.get("/URI", ""))
                    if uri.lower().startswith("mailto:"):
                        removed += 1
                        continue
            keep.append(annot)
        if keep:
            page["/Annots"] = pikepdf.Array(keep)
        elif "/Annots" in page:
            del page["/Annots"]
    return removed


def _strip_watermark_annots(pdf: pikepdf.Pdf) -> int:
    """Remove annotations with /Subtype /Watermark.

    Args:
        pdf: Open pikepdf document (modified in place).

    Returns:
        Number of watermark annotations removed.
    """
    removed = 0
    for page in pdf.pages:
        annots = page.get("/Annots")
        if annots is None:
            continue
        keep = []
        for annot in annots:
            if str(annot.get("/Subtype", "")) == "/Watermark":
                removed += 1
                continue
            keep.append(annot)
        if keep:
            page["/Annots"] = pikepdf.Array(keep)
        elif "/Annots" in page:
            del page["/Annots"]
    return removed


def _strip_watermark_layers(pdf: pikepdf.Pdf) -> int:
    """Remove Optional Content Groups (layers) whose /Name contains 'watermark'.

    Removes the OCG entries from /OCProperties and cleans up the default
    viewer configuration (/D). Content streams that reference the removed
    OCGs remain intact but the content will no longer render.

    Args:
        pdf: Open pikepdf document (modified in place).

    Returns:
        Number of OCG layers removed.
    """
    root = pdf.Root
    oc_props = root.get("/OCProperties")
    if oc_props is None:
        return 0
    ocgs_arr = oc_props.get("/OCGs")
    if ocgs_arr is None:
        return 0

    wm_objgens: set[tuple[int, int]] = set()
    keep: list[pikepdf.Object] = []

    for ocg in ocgs_arr:
        name = str(ocg.get("/Name", ""))
        if "watermark" in name.lower():
            with contextlib.suppress(Exception):
                wm_objgens.add(ocg.objgen)
        else:
            keep.append(ocg)

    if not wm_objgens:
        return 0

    oc_props["/OCGs"] = pikepdf.Array(keep)

    d_conf = oc_props.get("/D")
    if d_conf is not None:
        for key in ("/ON", "/OFF", "/Order", "/Locked"):
            lst = d_conf.get(key)
            if lst is None:
                continue
            filtered = []
            for item in lst:
                try:
                    if item.objgen not in wm_objgens:
                        filtered.append(item)
                except Exception:
                    filtered.append(item)
            d_conf[key] = pikepdf.Array(filtered)

    return len(wm_objgens)


def scrub(
    input_path: Path,
    output_path: Path | None = None,
    *,
    mailto: bool = True,
    watermarks: bool = True,
) -> dict[str, int]:
    """Scrub a PDF of mailto links and/or watermarks.

    Args:
        input_path: Source PDF path.
        output_path: Destination path; defaults to overwriting the input file.
        mailto: Remove mailto link annotations.
        watermarks: Remove watermark annotations and OCG layers.

    Returns:
        Counts of removed elements keyed by type:
        ``mailto``, ``watermark_annots``, ``watermark_layers``.

    Note:
        Watermarks that are burned directly into page content streams
        (i.e. not annotation-based or layer-based) cannot be detected or
        removed by this function.
    """
    out = output_path or input_path
    overwrite = out.resolve() == input_path.resolve()
    stats: dict[str, int] = {}

    with pikepdf.open(input_path, allow_overwriting_input=overwrite) as pdf:
        if mailto:
            stats["mailto"] = _strip_mailto_links(pdf)
        if watermarks:
            stats["watermark_annots"] = _strip_watermark_annots(pdf)
            stats["watermark_layers"] = _strip_watermark_layers(pdf)
        pdf.save(out)

    return stats
