from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "renpy-en-zh-translation"
    / "scripts"
    / "index_rpy_project.py"
)
FIXTURE = ROOT / "tests" / "skill_fixtures" / "index_project"


class IndexRpyProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="renpy-index-test-"))
        self.project = self.temp_dir / "project"
        shutil.copytree(FIXTURE, self.project)
        self.index = self.temp_dir / "index.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def run_cli(self, *args: str) -> tuple[dict, str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return json.loads(completed.stdout), completed.stdout

    def test_scan_outputs_only_compact_metadata(self) -> None:
        result, raw = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        self.assertEqual(result["files"], 2)
        self.assertEqual(result["changed_files"], 2)
        self.assertEqual(result["reused_files"], 0)
        self.assertNotIn("You are late", raw)
        self.assertNotIn("executable string", raw)
        self.assertGreater(result["text_statements"], 10)
        self.assertEqual(result["character_definitions"], 3)
        self.assertEqual(result["kinds"]["ui"], 2)
        self.assertNotIn("extend", result["top_speakers"])
        duke_marker = next(
            marker
            for marker in result["character_markers"]
            if marker["speaker"] == "duke"
        )
        self.assertEqual(duke_marker["fonts"], ["fonts/noble.ttf"])

    def test_summary_and_bounded_speaker_samples(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        summary, raw_summary = self.run_cli(
            "summary",
            "--index",
            str(self.index),
            "--top",
            "5",
        )
        samples, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--source",
            "comments",
            "--limit",
            "1",
            "--context",
            "1",
        )

        self.assertIn("duke", summary["top_speakers"])
        self.assertIn("fonts/noble.ttf", summary["fonts"])
        self.assertNotIn("The hall fell silent", raw_summary)
        self.assertEqual(samples["returned"], 1)
        self.assertEqual(samples["samples"][0]["speaker"], "duke")
        self.assertTrue(samples["samples"][0]["source_comment"])
        self.assertLessEqual(len(samples["samples"][0]["context"]), 3)

    def test_reuses_unchanged_files_and_refreshes_changed_file(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        story = self.project / "game" / "story.rpy"
        story.write_text(
            story.read_text(encoding="utf-8") + '\nduke "One more thing."\n',
            encoding="utf-8",
        )

        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        self.assertEqual(result["changed_files"], 1)
        self.assertEqual(result["reused_files"], 1)
        self.assertEqual(result["removed_files"], 0)

    def test_exclude_glob_avoids_localization_duplicates(self) -> None:
        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
            "--exclude",
            "**/tl/**",
        )

        self.assertEqual(result["files"], 1)
        self.assertEqual(result["source_comment_statements"], 0)

    def test_python_assignment_is_not_indexed(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        data = json.loads(self.index.read_text(encoding="utf-8"))
        texts = [
            record.get("text", "")
            for entry in data["files"].values()
            for record in entry["records"]
        ]

        self.assertNotIn(
            "This executable string must not be indexed.",
            texts,
        )
        self.assertNotIn(
            "This commented-out line is not localization source evidence.",
            texts,
        )
        self.assertIn(
            'He said, \\"Wait.\\"  Then he left.',
            texts,
        )
        self.assertIn(
            "Don\\'t push it.",
            texts,
        )


if __name__ == "__main__":
    unittest.main()
