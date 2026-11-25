"""Run Phase 11 black-box groups against one disposable stack and record every outcome as JSON (nothing is hidden).

    python runner.py OUTPUT.json [module ...]       modules default to all test_g*.py in this directory
Each test id is the T<group>_<n> token in its name; outcomes are PASS, FAIL (assertion), ERROR (the test itself broke) or SKIP.
"""
import importlib
import json
import re
import sys
import time
import traceback
import unittest
from pathlib import Path

import lib

HERE = Path(__file__).resolve().parent


class Recorder(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows, self.started = [], {}

    def startTest(self, test):
        super().startTest(test)
        self.started[test.id()] = time.monotonic()

    def _add(self, test, status, detail=""):
        match = re.search(r"T\d+_\d+", test.id())
        self.rows.append({"id": match.group(0) if match else "SETUP:" + test.id(), "test": test.id().split(".", 1)[-1], "status": status,
                          "seconds": round(time.monotonic() - self.started.get(test.id(), time.monotonic()), 2),
                          "doc": ((getattr(test, "_testMethodDoc", None) or "").strip().splitlines() or [""])[0],
                          "detail": detail[-900:]})

    def addSuccess(self, test):
        self._add(test, "PASS")

    def addFailure(self, test, err):
        self._add(test, "FAIL", "".join(traceback.format_exception_only(err[0], err[1])))

    def addError(self, test, err):
        self._add(test, "ERROR", "".join(traceback.format_exception(*err))[-900:])

    def addSkip(self, test, reason):
        self._add(test, "SKIP", reason)


def main(argv):
    output, modules = argv[1], argv[2:] or sorted(p.stem for p in HERE.glob("test_g*.py"))
    attach = None
    if modules and modules[0].startswith("--attach="):
        attach, modules = modules[0].split("=", 1)[1], modules[1:]
    import contextlib

    with (contextlib.nullcontext(lib.Stack.attach(attach)) if attach else lib.stack(broker=not __import__('os').environ.get('P11_NO_BROKER'))) as stack:
        lib.CURRENT = stack
        recorder = Recorder()
        for name in modules:
            module = importlib.import_module(name)
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            suite.run(recorder)
            print(f"{name}: {len(recorder.rows)} results so far", flush=True)
        # stack logs are kept for secret-hygiene scanning
        (Path(output).with_suffix(".stacklogs")).mkdir(exist_ok=True)
        for log in ([] if attach else stack.base.glob("*.log")):
            (Path(output).with_suffix(".stacklogs") / log.name).write_bytes(log.read_bytes())
    Path(output).write_text(json.dumps({"results": recorder.rows}, indent=1))
    counts = {}
    for row in recorder.rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(counts)


if __name__ == "__main__":
    main(sys.argv)
