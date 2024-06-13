#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = ["ghreq ~= 0.1", "ghtoken ~= 0.1"]
# ///

"""
List repositories that use both auto and Dependabot and thus are susceptible to
<https://github.com/datalad/datalad-installer/issues/175>
"""

from __future__ import annotations
from collections.abc import Iterator
import ghreq
from ghtoken import get_ghtoken

OWNERS = ["con", "dandi", "datalad", "duecredit", "ReproNim"]


class Client(ghreq.Client):
    def get_repos_for_owner(self, owner: str) -> Iterator[dict]:
        return self.paginate(f"/users/{owner}/repos")

    def has_file(self, repo_url: str, path: str) -> bool:
        try:
            self.request("HEAD", f"{repo_url}/contents/{path}", raw=True)
        except ghreq.PrettyHTTPError as e:
            if e.response.status_code == 404:
                return False
            else:
                raise e
        else:
            return True


with Client(token=get_ghtoken()) as client:
    for owner in OWNERS:
        for r in client.get_repos_for_owner(owner):
            if r["archived"] or r["fork"]:
                continue
            if client.has_file(r["url"], ".autorc") and client.has_file(
                r["url"], ".github/dependabot.yml"
            ):
                print(r["full_name"])
