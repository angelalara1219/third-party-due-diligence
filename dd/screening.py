"""Screen names against the sanctions lists collected by sanctions-list-tracker.

The lists come from the snapshots that repo refreshes every weekday:
US OFAC SDN, UK Sanctions List, Australia DFAT, and the UN Consolidated List.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests
from rapidfuzz import fuzz, process

SNAPSHOT_BASE = ("https://raw.githubusercontent.com/angelalara1219/"
                 "sanctions-list-tracker/main/data/snapshots/")
LISTS = {
    "us_ofac": "US OFAC SDN",
    "uk_fcdo": "UK Sanctions List",
    "au_dfat": "Australia DFAT",
    "un_sc": "UN Consolidated List",
}

# Words that say what kind of company it is, not who it is.
LEGAL_SUFFIXES = {
    "llc", "ltd", "limited", "inc", "incorporated", "co", "company", "corp",
    "corporation", "plc", "gmbh", "ag", "sa", "sas", "srl", "bv", "nv", "pte",
    "pty", "kk", "ltda", "fze", "fzco", "fzc", "fzllc", "sdn", "bhd", "jsc",
    "ojsc", "pjsc", "ooo", "the",
}

REVIEW_THRESHOLD = 90  # scores at or above this go to a person for review


@dataclass
class ListedName:
    source: str
    entry_id: str
    name: str
    entry_type: str
    programs: str
    key: str
    compact: str


@dataclass
class Hit:
    screened_name: str
    source: str
    entry_id: str
    listed_name: str
    programs: str
    score: int


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    text = re.sub(r"\b([a-z]) (?=[a-z]\b)", r"\1", text)  # "l l c" -> "llc"
    words = [w for w in text.split() if w not in LEGAL_SUFFIXES]
    return " ".join(words)


def load_lists(local_dir: Path | None = None) -> list[ListedName]:
    names: list[ListedName] = []
    for key, label in LISTS.items():
        if local_dir:
            path = local_dir / f"{key}.csv"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
        else:
            resp = requests.get(SNAPSHOT_BASE + f"{key}.csv", timeout=120)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            text = resp.text
        for row in csv.DictReader(io.StringIO(text)):
            key_name = normalize(row["name"])
            if not key_name:
                continue
            names.append(ListedName(label, row["entry_id"], row["name"], row["entry_type"],
                                    row["programs"], key_name, key_name.replace(" ", "")))
    return names


class Screener:
    def __init__(self, listed: list[ListedName]):
        self.listed = listed
        self.keys = [n.key for n in listed]
        self.compacts = [n.compact for n in listed]

    def screen(self, name: str, limit: int = 3) -> list[Hit]:
        key = normalize(name)
        if not key:
            return []
        best: dict[int, int] = {}
        # Word order and spacing vary between lists ("Green Leaf" vs "Greenleaf"),
        # so score both the word-sorted form and the no-spaces form.
        for choices, query, scorer in ((self.keys, key, fuzz.token_sort_ratio),
                                       (self.compacts, key.replace(" ", ""), fuzz.ratio)):
            for _, score, idx in process.extract(query, choices, scorer=scorer,
                                                 score_cutoff=REVIEW_THRESHOLD, limit=limit):
                best[idx] = max(best.get(idx, 0), round(score))
        hits = [Hit(name, self.listed[i].source, self.listed[i].entry_id, self.listed[i].name,
                    self.listed[i].programs, s) for i, s in best.items()]
        return sorted(hits, key=lambda h: -h.score)[:limit]
