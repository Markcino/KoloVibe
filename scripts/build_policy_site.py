"""Render the static KoloVibe policies page from the exact legal texts Identity serves (Decision B).

Usage: python scripts/build_policy_site.py OUTPUT_DIR

Only the small Markdown subset the texts use is supported (`#`, `##`, `-` lists, `**bold**`, paragraphs). Everything
is HTML-escaped. The output has no script, form, cookie or external resource. See apps/policies/README.md.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "identity"))

PAGES = {"terms": "terms", "privacy": "privacy"}  # document kind -> path
# Owner ruling, 26 November 2026: the account-deletion request page that Google Play requires outside the app.
# It is a draft like the legal texts, and it has no form: requests are made in the app, or by email.
DELETION = ROOT / "apps" / "policies" / "delete-account.md"
DELETION_PATH = "delete-account"
CSP = "default-src 'none'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
CSS = """body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.55;color:#14213d;
background:#fff;margin:0}main{max-width:44rem;margin:0 auto;padding:1.5rem 1rem 3rem}h1{font-size:1.75rem}
h2{font-size:1.2rem;margin-top:1.75rem}.notice{border:2px solid #b45309;background:#fff7ed;padding:.75rem 1rem;
border-radius:.5rem}.meta{color:#475569}nav a{margin-right:1rem}a{color:#1d4ed8}
"""


DRAFT = ('<p class="notice"><strong>Draft pending legal review.</strong> This text has not been approved by '
         "a lawyer. It describes how KoloVibe works today and may change.</p>")


def _inline(text):
    parts = html.escape(text, quote=True).split("**")
    return "".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(parts))


def render_markdown(text):
    out, items = [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            items.append(_inline(line[2:]))
            continue
        flush()
        if not line:
            continue
        if line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        else:
            out.append(f"<p>{_inline(line)}</p>")
    flush()
    return "\n".join(out)


def page(title, body, depth):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex">
<title>{html.escape(title)} · KoloVibe</title>
<link rel="stylesheet" href="{up}policies.css">
</head>
<body>
<main>
<nav><a href="{up}">KoloVibe policies</a><a href="{up}terms/">Terms of Service</a><a href="{up}privacy/">Privacy Notice</a><a href="{up}{DELETION_PATH}/">Delete your account</a></nav>
{body}
</main>
</body>
</html>
"""


def build(output):
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "service.settings")
    os.environ.setdefault("KOLOVIBE_ENV", "local")
    os.environ.setdefault("DJANGO_SECRET_KEY", "policy-site-build-only-not-a-secret-0123456789")
    django.setup()
    from service import legal

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "policies.css").write_text(CSS)
    links = []
    for kind, path in PAGES.items():
        document = legal.DOCUMENTS[kind]
        notice = DRAFT if document.status == legal.PENDING else ""
        meta = (f'<p class="meta">Version {html.escape(document.version)}, effective '
                f'{html.escape(document.effective_at)}.</p>')
        (output / path).mkdir(exist_ok=True)
        (output / path / "index.html").write_text(
            page(document.title, notice + meta + render_markdown(document.text), 1))
        links.append(f'<li><a href="{path}/">{html.escape(document.title)}</a> (version '
                     f'{html.escape(document.version)})</li>')
    (output / DELETION_PATH).mkdir(exist_ok=True)
    (output / DELETION_PATH / "index.html").write_text(
        page("Delete your account", DRAFT + render_markdown(DELETION.read_text()), 1))
    links.append(f'<li><a href="{DELETION_PATH}/">Delete your KoloVibe account</a></li>')
    index = ("<h1>KoloVibe policies</h1><p>The current terms and privacy notice for the KoloVibe app, and how to "
             "delete your account. Accounts, videos and businesses are in the app only.</p><ul>" + "".join(links)
             + "</ul>")
    (output / "index.html").write_text(page("Policies", index, 0))
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: build_policy_site.py OUTPUT_DIR")
    print(build(sys.argv[1]))
