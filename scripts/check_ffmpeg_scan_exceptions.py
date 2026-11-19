#!/usr/bin/env python3
"""Prove that every FFmpeg scanner exception still holds for the built media-worker binary.

`infra/docker/ffmpeg/scan-exceptions.json` lists CVEs whose vulnerable component is not part of the minimal FFmpeg build.
This script reads what the *built* ffmpeg reports about itself and fails if any listed component is present:

    check_ffmpeg_scan_exceptions.py EXCEPTIONS.json VERSION.txt DECODERS.txt ENCODERS.txt HWACCELS.txt BSFS.txt

where the text files are the outputs of `ffmpeg -hide_banner -version | -decoders | -encoders | -hwaccels | -bsfs`.
Nothing here trusts the build recipe: it asks the binary. If a component is ever enabled, the exception that relied on its
absence must be removed and the finding fixed or re-approved, so CI fails instead of keeping a stale exception.
"""
import json
import sys
from pathlib import Path

KINDS = ("decoders", "encoders", "hwaccels", "bsfs")


def configuration(version_text):
    """The configure options the binary was built with, as exact tokens (from the `configuration:` line)."""
    for line in version_text.splitlines():
        if line.strip().startswith("configuration:"):
            return set(line.split(":", 1)[1].split())
    raise ValueError("no 'configuration:' line in the ffmpeg -version output")


def listed_names(kind, text):
    """Names an `ffmpeg -decoders|-encoders|-hwaccels|-bsfs` listing reports (no header or legend lines)."""
    lines = text.splitlines()
    if kind in ("decoders", "encoders"):
        # Rows follow a ` ------` separator and look like ` V....D h264   H.264 / AVC ...`: the name is token 2.
        start = next((i for i, line in enumerate(lines) if line.strip().startswith("---")), None)
        if start is None:
            raise ValueError("unrecognised ffmpeg -" + kind + " listing")
        return {tokens[1] for tokens in (line.split() for line in lines[start + 1:]) if len(tokens) >= 2}
    # -hwaccels and -bsfs print a heading line and then one name per line.
    return {line.strip() for line in lines[1:] if line.strip()}


def check(document, version_text, listings):
    """Return a list of problems; empty means every exception premise holds for this binary."""
    problems = []
    config = configuration(version_text)
    for option in document["build_must_have"]:
        if option not in config:
            problems.append("the build lacks " + option)
    for flag in config:  # a blanket enable would invalidate every 'component is absent' argument
        if flag in ("--enable-decoders", "--enable-encoders", "--enable-hwaccels", "--enable-bsfs", "--enable-filters",
                    "--enable-parsers", "--enable-demuxers", "--enable-muxers", "--enable-protocols", "--enable-network",
                    "--enable-autodetect"):
            problems.append("the build uses the blanket option " + flag)
    names = {kind: listed_names(kind, listings[kind]) for kind in KINDS}
    for row in document["rows"]:
        cve = row["cve"]
        if not row["absent"] and not row["configure_lacks"]:
            problems.append(cve + ": no check recorded")
        for kind, wanted_absent in row["absent"].items():
            if kind not in names:
                problems.append(cve + ": unknown listing " + kind)
                continue
            for name in wanted_absent:
                if name in names[kind]:
                    problems.append(cve + ": " + name + " is present in ffmpeg -" + kind)
        for option in row["configure_lacks"]:
            if option in config:
                problems.append(cve + ": the build uses " + option)
    return problems


def main(argv):
    if len(argv) != 7:
        print(__doc__, file=sys.stderr)
        return 2
    document = json.loads(Path(argv[1]).read_text())
    version_text = Path(argv[2]).read_text()
    listings = dict(zip(KINDS, (Path(p).read_text() for p in argv[3:7])))
    problems = check(document, version_text, listings)
    for problem in problems:
        print("::error::" + problem)
    if problems:
        print("FFmpeg scan exceptions no longer hold: remove the exception or fix the finding", file=sys.stderr)
        return 1
    print("All " + str(len(document["rows"])) + " FFmpeg scan exceptions hold for the built binary")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
