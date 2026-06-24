"""Test set loader -- reads TestCase records from JSONL or JSON files.

Supported formats:
  - JSONL: one TestCase object per line.
  - JSON:  a top-level array of TestCase objects.

Example file (JSONL):
  {"id":"e1","query":"年假还剩几天","expected_agent":"hr_agent","category":"hr"}
  {"id":"e2","query":"电脑蓝屏怎么报修","expected_agent":"it_agent","expected_tools":["create_ticket"],"category":"it"}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from src.evaluation.models import TestCase

logger = logging.getLogger(__name__)


class TestLoader:
    """Load and validate test cases from disk.

    Usage:
        loader = TestLoader("data/eval/test_set.jsonl")
        cases = loader.load()   # list[TestCase]
        print(f"Loaded {len(cases)} test cases")
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Test set not found: {self.path}")

    def load(self) -> list[TestCase]:
        """Load all test cases, skipping malformed lines with a warning.

        Returns:
            List of validated TestCase objects.
        """
        suffix = self.path.suffix.lower()
        if suffix == ".jsonl":
            return self._load_jsonl()
        if suffix == ".json":
            return self._load_json()
        raise ValueError(f"Unsupported test set format: {suffix} (use .jsonl or .json)")

    # ── Format-specific loaders ──────────────────────────────────

    def _load_jsonl(self) -> list[TestCase]:
        cases: list[TestCase] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                tc = self._parse_line(stripped, lineno)
                if tc:
                    cases.append(tc)
        logger.info("Loaded %d test cases from %s", len(cases), self.path)
        return cases

    def _load_json(self) -> list[TestCase]:
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError("JSON test set must be a top-level array")

        cases: list[TestCase] = []
        for i, item in enumerate(raw, start=1):
            tc = self._parse_item(item, i)
            if tc:
                cases.append(tc)
        logger.info("Loaded %d test cases from %s", len(cases), self.path)
        return cases

    # ── Parsing helpers ──────────────────────────────────────────

    def _parse_line(self, line: str, lineno: int) -> TestCase | None:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("Line %d: invalid JSON -- %s", lineno, e)
            return None
        return self._parse_item(raw, lineno)

    def _parse_item(self, raw: dict, index: int) -> TestCase | None:
        try:
            return TestCase(**raw)
        except ValidationError as e:
            logger.warning("Item %d: validation failed -- %s", index, e)
            return None
