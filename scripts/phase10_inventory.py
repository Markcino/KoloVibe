"""Generate the Phase 10 inventories (API, migrations, mobile screens, console) from the code and contracts of record.

Nothing here is hand-counted: re-run it and compare the output with the committed files to see what changed.
    python scripts/phase10_inventory.py            # writes docs/engineering/phase10/inventory/*.md
    python scripts/phase10_inventory.py --check    # exit 1 if the committed files are stale
Needs PyYAML (already a locked dependency).
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "engineering" / "phase10" / "inventory"
HTTP = ("get", "post", "put", "patch", "delete")
SERVICES = ("identity", "creators", "content", "engagement", "points", "moderation", "audit", "business", "gateway")


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def api():
    spec = yaml.safe_load((ROOT / "docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml").read_text())
    rows, groups = [], defaultdict(list)
    for path, item in spec["paths"].items():
        for method in HTTP:
            operation = item.get(method)
            if not operation:
                continue
            roles = ", ".join(operation.get("x-required-roles", [])) or ("anonymous" if operation.get("security") == [] else "")
            row = (method.upper(), path, operation.get("tags", [""])[0], "anonymous" if operation.get("security") == [] else "bearer",
                   roles, operation.get("x-implementation", ""), operation.get("operationId", ""))
            rows.append(row)
            groups[row[2]].append(row)
    implementation = Counter(row[5] or "unmarked" for row in rows)
    anonymous = sum(1 for row in rows if row[3] == "anonymous")
    text = ["# API inventory (generated)", "",
            f"Source: `docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml` (the contract of record; draft status). "
            f"**{len(rows)} operations**, {anonymous} anonymous, {len(rows) - anonymous} bearer-authenticated. "
            f"By `x-implementation` marker: " + ", ".join(f"{k} {v}" for k, v in sorted(implementation.items())) + ".", "",
            "Gateway route parity with this contract is enforced by `scripts/test_gateway_route_contract.py`; Business parity "
            "across Gateway, service, console and Dart by `scripts/test_business_contract_reconciliation.py`.", "",
            "## Operations by tag", "", table(("Tag", "Operations"), [(k, len(v)) for k, v in sorted(groups.items())]), ""]
    for tag, items in sorted(groups.items()):
        text += [f"## {tag}", "", table(("Method", "Path", "Tag", "Auth", "Roles", "Implementation", "operationId"), items), ""]
    return "\n".join(text)


def migrations():
    rows, total = [], 0
    for service in SERVICES + ("web (console)",):
        directory = ROOT / ("apps/web_django/web/migrations" if service.startswith("web") else f"services/{service}/service/migrations")
        names = sorted(p.stem for p in directory.glob("0*.py")) if directory.exists() else []
        total += len(names)
        rows.append((service, len(names), ", ".join(n.split("_", 1)[0] + " " + n.split("_", 1)[1] for n in names) or "none (no database)"))
    return "\n".join(["# Database migration inventory (generated)", "",
                      f"{total} migrations across the services and the console. Each service owns its schema and role; there are no "
                      "cross-service foreign keys. `makemigrations --check --dry-run` is clean for every service and the console "
                      "(CI step 'Service checks'); every migration is applied to a real TLS PostgreSQL by "
                      "`scripts/test_postgres_foundations.py` and `scripts/test_business_postgres.py`.", "",
                      table(("Service", "Count", "Migrations in order"), rows), ""])


def screens():
    coverage = (ROOT / "docs/mobile-design-coverage.md").read_text()
    designed = {}
    for line in coverage.splitlines():
        match = re.match(r"\|\s*M-(\d{3}) · ([^|]+?)\s*\|.*?\|\s*`([a-z_]+\.json)`\s*\|\s*([^|]*?)\s*\|", line)
        if match:
            designed[int(match.group(1))] = (match.group(2), match.group(3), match.group(4))
    binding, visual, header = {}, {}, ""
    for line in coverage.splitlines():
        if line.startswith("| Screen |"):
            header = line
            continue
        match = re.match(r"\|\s*M-(\d{3}) · [^|]+\|([^|]*)\|([^|]*)\|", line)
        if not match or "node" in line:
            continue
        number, first, second = int(match.group(1)), match.group(2).strip(), match.group(3).strip()
        if header.startswith("| Screen | Mode |"):
            binding[number] = (first, second)  # later tables are newer: they overwrite earlier rows
        elif header.startswith("| Screen | Class |"):
            visual[number] = first
    business = {}
    source = (ROOT / "apps/mobile/lib/features/business/business_screens.dart").read_text()
    for name, number in re.findall(r"static const (\w+) = (\d+);", source):
        if name not in ("first", "last") and 109 <= int(number) <= 144:
            business[int(number)] = re.sub(r"(?<!^)([A-Z])", r" \1", name).capitalize()
    rows = []
    for number in sorted(designed):
        name, group, prd = designed[number]
        mode, endpoint = binding.get(number, ("not in these tables (see FL-D and Phase 4 matrices)", ""))
        rows.append((f"M-{number:03d}", name, group.replace(".json", ""), prd, mode, endpoint, visual.get(number, "")))
    business_rows = [(f"M-{n:03d}", business[n]) for n in sorted(business)]
    tests = len(list((ROOT / "apps/mobile/test").glob("*_test.dart")))
    files = len(list((ROOT / "apps/mobile/lib").rglob("*.dart")))
    return "\n".join([
        "# Mobile screen inventory (generated)", "",
        f"Sources: `docs/mobile-design-coverage.md` (designed screens M-001 to M-108, with live-wiring status) and "
        f"`apps/mobile/lib/features/business/business_screens.dart` (Business screens M-109 to M-144). "
        f"**{len(designed)} designed + {len(business)} Business = {len(designed) + len(business)} screens**; "
        f"{files} Dart source files; {tests} test files. There are **no** screens for events, ticketing, advertising or "
        "financial accounts (no approved design and no backend).", "",
        "'Binding mode' and 'Endpoint' are copied from the coverage register's binding tables (latest wins); 'Visual class' "
        "from its 20 November review. They are a record, not a fresh assessment. A screen is accepted only through its tests "
        "and, later, device UAT; none has been run on a device.", "",
        "## Designed screens (M-001 to M-108)", "",
        table(("Route", "Screen", "Design group", "PRD", "Binding mode", "Endpoint / condition", "Visual class (20 Nov)"), rows), "",
        "## Business screens (M-109 to M-144, native, no Figma recipe)", "", table(("Route", "Screen"), business_rows), ""])


def console():
    urls = (ROOT / "apps/web_django/web/urls.py").read_text()
    rows = []
    for match in re.finditer(r'path\(\s*(f?)"([^"]*)",\s*([\w.]+(?:\.as_view\([^)]*\))?)[^\n]*?(?:name=(f?)"([^"]+)")?', urls):
        rows.append((("/" + match.group(2)).replace("//", "/"), match.group(5) or "", match.group(3)))
    templates = sorted(p.name for p in (ROOT / "apps/web_django/templates").glob("*.html"))
    return "\n".join([
        "# Administrator and moderator dashboard inventory (generated)", "",
        f"Source: `apps/web_django/web/urls.py`. {len(rows)} route declarations (some are generated in loops over a kind), "
        f"{len(templates)} templates. Per-route authentication, MFA, role and CSRF behaviour is proven by "
        "`apps/web_django/tests/test_route_security_matrix.py` (`docs/engineering/phase5/P5-01_route_security_matrix.md`). "
        "There are **no** ordinary-user routes, and **no** pages for events, ticketing, advertising or financial review.", "",
        table(("Path", "Route name", "View"), rows), "", "## Templates", "", ", ".join(templates), ""])


FILES = {"API_Inventory.md": api, "Migration_Inventory.md": migrations, "Mobile_Screen_Inventory.md": screens,
         "Console_Inventory.md": console}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    stale = []
    for name, build in FILES.items():
        text = build()
        path = OUT / name
        if arguments.check:
            if not path.exists() or path.read_text() != text:
                stale.append(name)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print("wrote", path.relative_to(ROOT))
    if stale:
        print("stale:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
