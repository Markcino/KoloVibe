"""Select successful main checks for one exact commit before GHCR publication."""

import json
from http.client import HTTPSConnection
import os
from pathlib import Path
import re

WORKFLOWS = {
    "API quality": (
        "api-quality.yml",
        {"Django services and reproducibility", "Flutter static and widget tests",
         "Security scans and SBOM"},
    ),
    "Container quality": (
        "container-quality.yml",
        {f"Image build and security / {service}" for service in
         ("gateway", "identity", "creators", "content", "engagement", "points",
          "moderation", "audit")},
    ),
    "Dependency vulnerability review": (
        "dependency-security.yml",
        {"Python and Flutter dependency advisories / osv-scan"},
    ),
}


class GitHubAPI:
    def __init__(self, repository, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub repository")
        if not token:
            raise ValueError("Missing GitHub Actions token")
        self.base = f"/repos/{repository}"
        self.token = token

    def get(self, path):
        if not path.startswith("/actions/"):
            raise ValueError("Only repository Actions API paths are permitted")
        connection = HTTPSConnection("api.github.com", timeout=30)
        try:
            connection.request("GET", self.base + path, headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "KoloVibe-GHCR-Gate",
            })
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"GitHub Actions API failed (HTTP {response.status})")
            body = response.read(10_000_001)
            if len(body) > 10_000_000:
                raise RuntimeError("GitHub Actions API response exceeds the size limit")
            return json.loads(body)
        finally:
            connection.close()

    def items(self, path, key):
        separator = "&" if "?" in path else "?"
        for page in range(1, 101):
            items = self.get(f"{path}{separator}per_page=100&page={page}")[key]
            yield from items
            if len(items) < 100:
                return
        raise RuntimeError("GitHub pagination limit exceeded")


def select_runs(api, sha, event_run):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid commit SHA")
    if event_run.get("name") not in WORKFLOWS:
        raise ValueError("Unexpected triggering workflow")
    if (event_run.get("head_sha") != sha or event_run.get("head_branch") != "main"
            or event_run.get("event") != "push"):
        return None, "Publication withheld: trigger is not a main push for this commit"
    selected = {}
    for name, (filename, expected_jobs) in WORKFLOWS.items():
        runs = list(api.items(
            f"/actions/workflows/{filename}/runs?head_sha={sha}&branch=main&event=push",
            "workflow_runs",
        ))
        runs = [run for run in runs if run.get("head_sha") == sha
                and run.get("head_branch") == "main" and run.get("event") == "push"]
        if not runs:
            return None, f"Publication withheld: missing {name} for this commit"
        run = max(runs, key=lambda item: (item["run_number"], item.get("run_attempt", 1)))
        if (run.get("status") != "completed" or run.get("conclusion") != "success"):
            return None, f"Publication withheld: {name} is not completed successfully"
        if name == event_run["name"] and (
            run["id"] != event_run["id"]
            or run.get("run_attempt", 1) != event_run.get("run_attempt", 1)
        ):
            return None, "Publication withheld: stale triggering workflow run"
        jobs = list(api.items(
            f"/actions/runs/{run['id']}/attempts/{run.get('run_attempt', 1)}/jobs", "jobs"))
        successful = {job["name"] for job in jobs if job.get("status") == "completed"
                      and job.get("conclusion") == "success"}
        if not expected_jobs <= successful or any(
            job.get("status") != "completed" or job.get("conclusion") != "success"
            for job in jobs
        ):
            return None, f"Publication withheld: missing or unsuccessful jobs in {name}"
        selected[name] = run["id"]
    return selected, "All required exact-commit quality checks passed"


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    run = event["workflow_run"]
    repository = os.environ["GITHUB_REPOSITORY"]
    if run.get("head_repository", {}).get("full_name") != repository:
        raise ValueError("Publication from another repository is prohibited")
    api = GitHubAPI(repository, os.environ["GH_TOKEN"])
    selected, message = select_runs(api, run["head_sha"], run)
    print(message)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(message + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"eligible={'true' if selected else 'false'}\n")
        if selected:
            output.write(f"sha={run['head_sha']}\n")
            output.write(f"container_run={selected['Container quality']}\n")


if __name__ == "__main__":
    main()
