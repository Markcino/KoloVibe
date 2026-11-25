"""Build the Phase 11 test matrix from the recorded results plus an explicit registry of what could not be run.

    python matrix.py RESULTS_DIR OUTPUT.md
Every status is PASS, FAIL, BLOCKED or NOT RUN. A recorded ERROR (a test that broke) is reported as FAIL with its detail, never hidden.
"""
import json
import re
import sys
from pathlib import Path

GROUPS = {
    "T1": "1 Accounts and security", "T2": "2 Creator and content", "T3": "3 Engagement and points", "T4": "4 Business",
    "T5": "5 Events", "T6": "6 Advertising", "T7": "7 Financial workflows", "T8": "8 Mobile devices", "T9": "9 Administration dashboard",
    "T10": "10 Infrastructure and security", "B": "Baseline suites (existing automated tests, re-run at the test commit)",
}

NOT_RUN = []
# Phase 12 unblock (25 November 2026): T3_92, T9_90, T9_91, T10_92, T10_93, T10_96 and T10_97 now have recorded results in
# docs/engineering/phase12/results/unblock.json (evidence in docs/engineering/phase12/unblock/), so they are no longer registered here.
PHASE12_NOTE = ("**Phase 12 regression.** Every applicable Phase 11 test was run again on the fixed build; no earlier PASS is reused. "
                "A FAIL is either an open defect (listed in the [Phase 12 defect register](Phase12_Defect_Register.md)) or a static finding. "
                "Every BLOCKED and NOT RUN row has a disposition and an owner in the last two columns. ")


def add(group, ident, name, status, reason):
    NOT_RUN.append({"group": group, "id": ident, "name": name, "status": status, "reason": reason})


NO_EVENTS = "No code exists: Events and ticketing are a Phase 7A design only (unapproved); nothing to test"
NO_ADS = "No code exists: Advertising is a Phase 8A design only (unapproved); nothing to test"
NO_FIN = "No code exists: Revenue and payouts are a Phase 9A design only (unapproved); nothing to test"
NO_DEVICE = "No physical iPhone or Android device and no attached machine; cannot be run from this environment"
for i, name in enumerate(["Organizer onboarding", "Event creation", "Event publication", "Ticket inventory", "Booking", "Sandbox checkout", "Ticket issuance",
                          "QR validation", "Duplicate check-in", "Event cancellation", "Refund workflow", "Organizer reports", "Concurrent ticket reservations",
                          "Replay resistance"], 1):
    add("T5", f"T5_{i:02d}", name, "NOT RUN", NO_EVENTS)
for i, name in enumerate(["Advertiser onboarding", "Campaign management", "Creative review", "Ad placement", "Impression tracking", "Invalid traffic protection",
                          "Campaign reporting", "Budget enforcement"], 1):
    add("T6", f"T6_{i:02d}", name, "NOT RUN", NO_ADS)
for i, name in enumerate(["Revenue records", "Allocation correctness", "Reconciliation", "Eligibility", "Holds and adjustments", "Sandbox payout", "Repeated requests",
                          "Failed provider events", "Financial authorization", "Audit integrity"], 1):
    add("T7", f"T7_{i:02d}", name, "NOT RUN", NO_FIN)
for i, name in enumerate(["Installation", "App launch", "Authentication", "Session persistence", "Navigation", "All approved user journeys", "Video playback", "Uploads",
                          "Offline handling", "Slow connectivity", "Error recovery", "Screen layout", "Accessibility", "Notifications (none implemented)",
                          "Permission prompts", "Security-sensitive storage behaviour (Keychain / Keystore)"], 1):
    add("T8", f"T8_{i:02d}", name + " (iOS)", "BLOCKED", NO_DEVICE)
    add("T8", f"T8_{i:02d}A", name + " (Android)", "BLOCKED", NO_DEVICE)
add("T2", "T2_90", "Real Cloudflare R2 upload and playback object access", "BLOCKED", "No R2 credentials and no authorization to contact Cloudflare; the signing code is exercised offline only (T2_27)")
add("T2", "T2_91", "Upload to playback lifecycle with fixture storage (draft, intent, encode, screen, moderate, publish, playback, unpublish)", "NOT RUN",
    "Covered by the existing upload-to-playback journey test in the baseline (B_CONTENT); not re-implemented as a black-box test")
add("T3", "T3_91", "Approved points reversals", "NOT RUN", "No execution path exists (excluded by the R1 SRS); ledger constraints only are tested by the existing suite")
add("T9", "T9_92", "Screen reader (NVDA, VoiceOver, TalkBack) on the console", "NOT RUN", "No screen reader available; only structural accessibility was tested (T9_30 to T9_33)")
add("T9", "T9_93", "Event review, advertising review and financial oversight pages", "NOT RUN", "These console pages do not exist")
add("T9", "T9_94", "Creator verification, business verification, moderation decisions and appeals through the browser (full reviewer workflows)", "NOT RUN",
    "Reviewer workflows are covered by the existing real-HTTP console journeys (baseline B_JOURNEYS); only sign-in, authorization, sessions and rendering were re-tested in a browser here")
add("T10", "T10_90X", "HTTPS termination and proxy security on the deployed edge (Cloudflare, host Nginx)", "BLOCKED", "No access to AWS or the deployed edge; repository configuration reviewed statically only")
add("T10", "T10_94", "Database grants and role ownership on the staging database", "BLOCKED", "No access to AWS; the repository's own schema script was tested on a disposable database (T10_01 to T10_04)")
add("T10", "T10_95", "Deployed RabbitMQ accounts, permissions and queue policy", "BLOCKED", "No broker access; accounts from the generator's table were proven on a disposable broker (Phase 10, T3_*)")
add("T10", "T10_96L", "Logging and alerting pipelines on the deployed Swarm", "NOT RUN", "No monitoring stack here; runtime limits passed on a local Swarm (T10_96)")
add("T10", "T10_98", "Penetration test by an independent tester", "NOT RUN", "Not authorized or available; this phase is internal testing only")
add("T10", "T10_99", "Mobile application security review on a device (binary, storage, pinning)", "BLOCKED", NO_DEVICE)


def disposition(row):
    """(disposition, owner) for a BLOCKED or NOT RUN row. Phase 12: nothing may stay open without both."""
    i, g = row["id"], row["group"]
    if g in ("T5", "T6", "T7"):
        return "Out of R1 scope: the module is a design package only. Test group stays NOT RUN until the module is approved and built", "Product owner"
    if g == "T8":
        return "Required before release: run the iPhone and Android checklists on physical devices against a staging build", "Product owner (devices) with QA"
    return {
        "T2_90": ("Required before release: real R2 upload and playback once credentials are provisioned", "Product owner (R2) and Media engineering"),
        "T2_91": ("Accepted: covered by the baseline upload-to-playback journey (B_JOURNEYS, B_BROKER_PIPELINE)", "Engineering"),
        "T3_91": ("Accepted for R1: reversals are excluded by the SRS; no execution path exists", "Product owner"),
        "T9_92": ("Required before general release: screen-reader pass on the console", "QA / accessibility reviewer"),
        "T9_93": ("Out of R1 scope: the pages do not exist", "Product owner"),
        "T9_94": ("Accepted: covered by the baseline real-HTTP console journeys (B_JOURNEYS)", "Engineering"),
        "T10_90X": ("Required before release: edge verification on staging", "Infrastructure owner"),
        "T10_94": ("Required before release: read back grants on staging and run the R-01 conversion (runbook), then repeat T10_03, T10_04", "Infrastructure owner, DBA"),
        "T10_95": ("Required before release: read back broker permissions, adopt a dead-letter policy", "Infrastructure owner"),
        "T10_96L": ("Required before release: verify logging and alerting on staging", "Infrastructure owner"),
        "T10_98": ("Required before general release: independent penetration test", "Product owner"),
        "T10_99": ("Required before release: device security review", "Product owner with QA"),
    }.get(i, ("UNASSIGNED: needs a disposition", "UNASSIGNED"))


def main(results_dir, out, phase="11"):
    rows = []
    for path in sorted(Path(results_dir).glob("*.json")):
        for r in json.loads(path.read_text())["results"]:
            status = "FAIL" if r["status"] in ("FAIL", "ERROR") else ("NOT RUN" if r["status"] == "SKIP" else r["status"])
            ident = r["id"]
            group = re.match(r"(T\d+|B)", ident.replace("SETUP:", "")).group(1) if re.match(r"(T\d+|B)", ident.replace("SETUP:", "")) else "?"
            rows.append({"group": group, "id": ident, "name": r["test"].split("test_" + ident + "_")[-1].replace("_", " ") if "test_" + ident in r["test"] else r["test"],
                         "status": status, "reason": (r["detail"].strip().splitlines()[-1][:220] if r["detail"] else ""), "seconds": r["seconds"], "raw": r["status"]})
    rows += [dict(r, seconds="") for r in NOT_RUN]

    def key(r):
        m = re.match(r"([A-Z]+)(\d*)_?(\d*)", r["id"].replace("SETUP:", ""))
        return (list(GROUPS).index(r["group"]) if r["group"] in GROUPS else 99, r["id"].rjust(8, "0") if False else (int(re.sub(r"\D", "", r["id"].split("_")[-1]) or 0), r["id"]))
    rows.sort(key=key)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    p12 = phase == "12"
    phase11_note = ("**Reading the FAIL rows.** Eight are product defects (T1_03, T1_31, T1_94, T3_35, T4_23, T9_32, T10_03, T10_04 = D11-001 to D11-006). "
                    "T10_81 is a static-review finding (no rate limiting in the repository's Nginx configuration; related to D11-004). Two rows, `B_WEB_try1` and "
                    "`B_PG_try1`, are **errors in my own runner script** on a first attempt (a missing environment variable and a missing PATH entry); they are kept "
                    "visible, and the re-runs that replaced them pass. They are not defects in the product.")
    register = "Phase12_Defect_Register.md" if p12 else "Phase11_Defect_Register.md"
    lines = [f"# Phase {phase} complete application test matrix", "",
             f"Generated by `scripts/phase11/matrix.py` from the recorded result files. **{len(rows)} tests: "
             + ", ".join(f"{counts.get(s, 0)} {s}" for s in ("PASS", "FAIL", "BLOCKED", "NOT RUN")) + ".** "
             "Every row is PASS, FAIL, BLOCKED or NOT RUN; nothing was removed or edited after it ran. A FAIL links to a defect in the "
             f"[defect register]({register}).", "",
             PHASE12_NOTE if p12 else phase11_note, ""]
    for group, title in GROUPS.items():
        subset = [r for r in rows if r["group"] == group]
        if not subset:
            continue
        gc = {}
        for r in subset:
            gc[r["status"]] = gc.get(r["status"], 0) + 1
        lines += [f"## Group {title}", "", " ".join(f"**{s}** {gc.get(s, 0)}" for s in ("PASS", "FAIL", "BLOCKED", "NOT RUN")), "",
                  "| ID | Test | Status | Evidence or reason |" + (" Disposition | Owner |" if p12 else ""),
                  "| --- | --- | --- | --- |" + (" --- | --- |" if p12 else "")]
        for r in subset:
            extra = ""
            if p12:
                d = disposition(r) if r["status"] in ("BLOCKED", "NOT RUN") else ("", "")
                extra = f" {d[0]} | {d[1]} |"
            lines.append(f"| {r['id'].replace('SETUP:', 'SETUP ')} | {r['name'][:110]} | **{r['status']}** | {str(r['reason']).replace('|', '/')[:230]} |" + extra)
        lines.append("")
    Path(out).write_text("\n".join(lines))
    print(counts, len(rows))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "11")
