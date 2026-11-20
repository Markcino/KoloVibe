"""Compose per-screen mobile design evidence.

Each output picture has three panels, left to right: the approved Figma export
from ``docs/designed/`` (402 x 874), the Flutter render at 390 x 844 and the
Flutter render at 375 x 667. Renders come from the widget-test audit
(``apps/mobile/test/design_audit_test.dart``) written to ``<raw>/<name>.png``.

    AUDIT_DIR=/tmp/audit flutter test test/design_audit_test.dart
    python3 scripts/compose_mobile_evidence.py /tmp/audit/raw docs/evidence/<dir>

Entries with several captured states use ``M-NNN-<state>`` names and are placed
beside the same export. Panels without a render are drawn as a labelled blank so
a missing capture is visible rather than silently omitted.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GAP = 12
BACKGROUND = (136, 136, 136)


REVISED_DIR = ROOT / "docs/designed/R1 adaptations (pending owner review)"

# Screens whose approved export was revised for R1 (docs/mobile-design-r1-adaptations.md). The key is the
# capture tag; the revised frame replaces the approved export for that tag only, and is labelled as such.
REVISED = {
    "M-019": "M-019 R1 latest original.png",
    "M-033": "M-033 R1 playback error.png",
    "M-034": "M-034 R1 slow connection.png",
    "M-096": "M-096 R1 slow connection page.png",
    "M-078-eligible": "M-078 R1 eligible entry.png",
    "M-078-eligible-validation": "M-078 R1 eligible validation.png",
    "M-078-eligible-sending": "M-078 R1 eligible sending.png",
    "M-078-eligible-failure": "M-078 R1 eligible failure.png",
    "M-078-eligible-receipt": "M-078 R1 eligible receipt.png",
}


def exports():
    found = {}
    for path in (ROOT / "docs/designed").rglob("*.png"):
        if REVISED_DIR in path.parents:
            continue
        match = re.search(r"M-(\d{3})", str(path.relative_to(ROOT / "docs/designed")))
        if match:
            found[int(match.group(1))] = path
    return found


def label(image, text):
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, 16), fill=(30, 30, 30))
    draw.text((4, 2), text, fill=(255, 255, 255), font=ImageFont.load_default())


def panel(path, text, size):
    if path is not None and path.exists():
        image = Image.open(path).convert("RGB")
    else:
        image = Image.new("RGB", size, (200, 200, 200))
        ImageDraw.Draw(image).text((8, 30), "not captured", fill=(60, 60, 60))
    image = image.copy()
    label(image, text)
    return image


def main(raw, out):
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    refs = exports()
    states = {}
    for number in range(1, 109):
        states.setdefault(number, set()).add("")
    for path in raw.glob("M-*_390x844.png"):
        match = re.fullmatch(r"M-(\d{3})(-[A-Za-z0-9-]+)?_390x844\.png", path.name)
        if match:
            states.setdefault(int(match.group(1)), set()).add(match.group(2) or "")
    written = 0
    for number, variants in sorted(states.items()):
        for variant in sorted(variants):
            tag = f"M-{number:03d}{variant}"
            revised = REVISED_DIR / REVISED[tag] if tag in REVISED else None
            if revised is not None and revised.exists():
                reference = panel(revised, f"Figma R1 revision {tag} (owner review pending)", (402, 874))
            else:
                reference = panel(refs[number], f"Figma export M-{number:03d}", (402, 874))
            panels = [
                reference,
                panel(raw / f"{tag}_390x844.png", "Flutter 390x844", (390, 844)),
                panel(raw / f"{tag}_375x667.png", "Flutter 375x667", (375, 667)),
            ]
            width = sum(p.width for p in panels) + GAP * 2
            height = max(p.height for p in panels)
            sheet = Image.new("RGB", (width, height), BACKGROUND)
            x = 0
            for p in panels:
                sheet.paste(p, (x, 0))
                x += p.width + GAP
            sheet = sheet.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
            sheet.save(out / f"{tag}.png", optimize=True)
            written += 1
    print(f"wrote {written} pictures to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
