"""Explainable search over the catalog. Keep behavior aligned with task_search.js."""

import json
from pathlib import Path
import re
import unicodedata


MODES = ("related", "all", "exact")
STOP_WORDS = set(
    "a an and are as at be by can could do does for from how i in into is it its "
    "me of on onto or our robot should task that the their then them there these they "
    "this to use using was what when where which will with would you your".split()
)
FIELDS = (
    ("Task", 8, ("title", "name", "description", "instruction")),
    ("Setup", 5, ("setup_summary", "setup", "objects")),
    ("Grading", 4, ("grading_summary", "goal", "predicates")),
    ("Robot input", 2, ("observation",)),
    ("Grader evidence", 2, ("grading_evidence",)),
    ("Catalog metadata", 2, ("id", "benchmark", "family", "suite", "activity", "setting", "split", "aliases", "record_kind")),
)


def text_value(value):
    """Flatten structured catalog fields identically in Python and JavaScript."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {text_value(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(text_value(item) for item in value)
    return str(value)


def normalize(value):
    """Separate registry identifiers while preserving word and phrase boundaries."""
    value = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", text_value(value))
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def includes(haystack, phrase):
    return bool(phrase) and f" {phrase} " in haystack


class SearchIndex:
    def __init__(self, tasks, concepts=None):
        if concepts is None:
            concepts = json.loads(Path(__file__).with_name("task_concepts.json").read_text())
        self.tasks = tasks
        self.aliases = {}
        self.max_alias_length = 1
        for concept in concepts:
            aliases = tuple(dict.fromkeys(normalize(alias) for alias in concept["aliases"]))
            for alias in aliases:
                self.aliases.setdefault(alias, (concept["term"], concept["kind"], aliases))
                self.max_alias_length = max(self.max_alias_length, len(alias.split()))
        self.fields = [
            tuple(
                (label, weight, tuple(f" {normalize(task.get(key))} " for key in keys if task.get(key)))
                for label, weight, keys in FIELDS
            )
            for task in tasks
        ]

    def _terms(self, query, mode):
        if mode == "exact":
            phrase = normalize(query)
            return [(phrase, "Keyword", (phrase,), phrase)] if phrase else []
        terms = []
        seen = set()
        for fragment in re.finditer(r'"([^"]*)"|([^"]+)', query):
            phrase = normalize(fragment.group(1) if fragment.group(1) is not None else fragment.group(2))
            if not phrase:
                continue
            if fragment.group(1) is not None:
                if (phrase, "Keyword") not in seen:
                    terms.append((phrase, "Keyword", (phrase,), phrase))
                    seen.add((phrase, "Keyword"))
                continue
            words = phrase.split()
            offset = 0
            while offset < len(words):
                for size in range(min(self.max_alias_length, len(words) - offset), 0, -1):
                    alias = " ".join(words[offset:offset + size])
                    concept = self.aliases.get(alias)
                    if concept:
                        break
                else:
                    size = 1
                    alias = words[offset]
                offset += size
                if not concept and alias in STOP_WORDS:
                    continue
                term, kind, aliases = concept or (alias, "Keyword", (alias,))
                if (term, kind) not in seen:
                    terms.append((term, kind, aliases, alias))
                    seen.add((term, kind))
        # A query composed entirely of stop words can still be searched literally.
        phrase = normalize(query)
        return terms or ([(phrase, "Keyword", (phrase,), phrase)] if phrase else [])

    def describe_query(self, query="", mode="related"):
        if mode not in MODES:
            raise ValueError(f"Unknown search mode: {mode}")
        return [
            {"term": term, "kind": kind, "original": original}
            for term, kind, _, original in self._terms(query, mode)
        ]

    def search(self, query="", *, mode="related", family="", benchmark="", suite="", setting=""):
        if mode not in MODES:
            raise ValueError(f"Unknown search mode: {mode}")
        terms = self._terms(query, mode)
        phrase = normalize(query)
        results = []
        for task, fields in zip(self.tasks, self.fields):
            if family and task.get("family", "").lower() != family.lower():
                continue
            if benchmark and task.get("benchmark", "").lower() != benchmark.lower():
                continue
            if setting and task.get("setting", "").lower() != setting.lower():
                continue
            if suite:
                key, expected = ("split", suite[6:]) if suite.startswith("split:") else ("suite", suite)
                if task.get(key, "").lower() != expected.lower():
                    continue
            matches = []
            score = 0
            for term, kind, aliases, original in terms:
                for label, weight, values in fields:
                    matched = next(
                        (alias for alias in dict.fromkeys((original, *aliases))
                         if any(includes(value, alias) for value in values)),
                        None,
                    )
                    if matched:
                        matches.append({"term": term, "kind": kind, "field": label, "matched": matched})
                        direct = matched in (original, original + "s") or original == matched + "s"
                        specificity = 4 if kind in ("Object", "Outcome") else 0
                        score += 20 + weight + specificity + (3 if direct else 0)
                        break
            if terms and (not matches or (mode == "all" and len(matches) != len(terms))):
                continue
            if len(terms) > 1 and any(includes(value, phrase) for value in fields[0][2]):
                score += 6
            results.append({"task": task, "score": score, "matches": matches})
        return sorted(results, key=lambda result: -result["score"])
