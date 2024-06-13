#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = ["ghrepo ~= 0.7", "ghreq ~= 0.5", "ghtoken ~= 0.1"]
# ///

"""
This script updates an `auto`-using GitHub repository so that the `auto` label
names (other than "release") will begin with a given prefix ("semver-" by
default).  It must either be run inside a local clone of such a repository or
else passed one or more paths to local clones of such repositories.

This script assumes that the repository contains an `.autorc` file that is
valid JSON (i.e., it does not contain any comments) and that does not already
define a "labels" field.
"""

from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
import subprocess
from ghrepo import GHRepo, get_local_repo
from ghreq import Client
from ghtoken import get_ghtoken

# (name, release type)
LABELS = [
    ("major", "major"),
    ("minor", "minor"),
    ("patch", "patch"),
    ("dependencies", "none"),
    ("documentation", "none"),
    ("internal", "none"),
    ("performance", "none"),
    ("tests", "none"),
]

PR_BRANCH = "auto-prefix-labels"

log = logging.getLogger("reautolabel")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-P", "--prefix", default="semver-")
    parser.add_argument("dirpath", type=Path, nargs="*")
    args = parser.parse_args()
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )
    dirs = args.dirpath or [Path.cwd()]
    prefix = args.prefix
    title = f"Prefix auto labels with {prefix!r}"
    body = (
        "This PR modifies the `auto` configuration so that the label names"
        f' (other than "release") will be prefixed with {prefix!r}.  This is'
        " necessary to keep Dependabot from applying `auto` labels to its PRs,"
        " causing undesirable version bumps."
        "\n\n"
        "See <https://github.com/datalad/datalad-installer/issues/175> for more"
        " information."
    )
    with Client(token=get_ghtoken()) as client:
        for d in dirs:
            log.info("Operating on %s ...", d)
            repo = get_local_repo(d)
            log.info("'origin' remote points to GitHub repository %s", repo)
            repo_data = client.get(f"/repo/{repo}")
            defbranch = repo_data["default_branch"]
            head_owner: str | None
            if (parent := repo_data.get("parent")) is not None:
                head_owner = repo_data["owner"]["login"]
                repo = GHRepo.parse(parent["full_name"])
                log.info("GitHub repository is a fork; operating on parent %s", repo)
            else:
                head_owner = None
            log.info("Renaming labels")
            for label, _ in LABELS:
                new_label = prefix + label
                log.info("%r -> %r", label, new_label)
                client.patch(
                    f"/repos/{repo}/labels/{label}", json={"new_name": new_label}
                )
            log.info("Creating PR to update .autorc")
            subprocess.run(
                ["git", "checkout", "-b", PR_BRANCH, defbranch],
                check=True,
                cwd=d,
            )
            autorc = d / ".autorc"
            config = json.loads(autorc.read_text(encoding="utf-8"))
            config["labels"] = [
                {"name": name, "releaseType": rt} for (name, rt) in LABELS
            ]
            autorc.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-m", title, ".autorc"], check=True, cwd=d)
            subprocess.run(
                ["git", "push", "--set-upstream", "origin", PR_BRANCH],
                check=True,
                cwd=d,
            )
            pr = client.post(
                f"/repos/{repo}/pulls",
                json={
                    "title": title,
                    "head": (
                        f"{head_owner}:{PR_BRANCH}"
                        if head_owner is not None
                        else PR_BRANCH
                    ),
                    "base": defbranch,
                    "body": body,
                    "maintainer_can_modify": True,
                },
            )
            log.info("PR created: %s", pr["url"])


if __name__ == "__main__":
    main()
