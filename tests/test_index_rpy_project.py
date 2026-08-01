from __future__ import annotations

import json
import os
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
        self.assertEqual(result["file_formats"]["newlines"], {"lf": 2})
        self.assertEqual(
            result["file_formats"]["byte_order_marks"], {"none": 2}
        )
        self.assertEqual(result["changed_files"], 2)
        self.assertEqual(result["reused_files"], 0)
        self.assertNotIn("You are late", raw)
        self.assertNotIn("executable string", raw)
        self.assertGreater(result["text_statements"], 10)
        self.assertEqual(result["character_definitions"], 3)
        self.assertEqual(result["kinds"]["ui"], 2)
        self.assertNotIn("extend", result["top_speakers"])
        self.assertEqual(
            result["profile_evidence_source"], "source_comments_and_old"
        )
        self.assertEqual(result["top_speakers"]["duke"], 2)
        self.assertGreater(result["top_speakers_target"]["duke"], 2)
        pairing = result["pairing"]["commented_source_targets"]
        self.assertEqual(pairing["balanced_blocks"], 1)
        self.assertEqual(pairing["structural_differences"]["tag_tokens"], 0)
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

    def test_samples_filter_by_project_relative_file_glob(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        samples, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--file",
            "game/tl/**",
            "--source",
            "comments",
            "--limit",
            "100",
            "--context",
            "0",
        )
        union_samples, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--file",
            "game/story.rpy",
            "--file",
            "game/tl/**",
            "--limit",
            "100",
            "--context",
            "0",
        )

        self.assertEqual(samples["matched"], 2)
        self.assertTrue(
            all(
                sample["file"] == "game/tl/schinese/story.rpy"
                for sample in samples["samples"]
            )
        )
        self.assertEqual(union_samples["matched"], union_samples["returned"])
        self.assertEqual(
            {sample["file"] for sample in union_samples["samples"]},
            {"game/story.rpy", "game/tl/schinese/story.rpy"},
        )

    def test_samples_filter_by_escaped_outer_quotes(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        with localization.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\ntranslate schinese voice_modes_deadbeef:\n\n"
                '    # duke "\\\"Spoken aloud.\\\""\n'
                '    duke "\\\"Target spoken.\\\""\n'
                '    # duke "An internal observation."\n'
                '    duke "Target thought."\n'
            )
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        present, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--source",
            "comments",
            "--outer-quotes",
            "present",
            "--limit",
            "100",
            "--context",
            "0",
        )
        absent, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--source",
            "comments",
            "--outer-quotes",
            "absent",
            "--limit",
            "100",
            "--context",
            "0",
        )

        self.assertEqual(present["matched"], 1)
        self.assertEqual(absent["matched"], 3)
        self.assertEqual(present["samples"][0]["text"], '\\"Spoken aloud.\\"')
        self.assertTrue(
            all(
                sample["text"] != '\\"Spoken aloud.\\"'
                for sample in absent["samples"]
            )
        )

    def test_records_dialogue_attributes_and_source_relative_tags(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        data = json.loads(self.index.read_text(encoding="utf-8"))
        records = [
            record
            for entry in data["files"].values()
            for record in entry["records"]
            if record.get("speaker") == "duke"
            and record.get("attributes") == "2 stern"
        ]

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["tags"], ["{font=fonts/mask.ttf}"])
        self.assertEqual(records[1]["tags"], ["{font=fonts/mask.ttf}"])

    def test_reports_structural_differences_without_printing_text(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        with localization.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                '\ntranslate schinese mismatch_deadbeef:\n\n'
                '    # duke 1 stern "{i}Stop, [player_name].{/i}"\n'
                '    duke 2 smile "停下，[player_name]。"\n'
                '\ntranslate schinese reorder_cafefeed:\n\n'
                '    # duke "First [alpha], then [beta]."\n'
                '    duke "先[beta]，再[alpha]。"\n'
            )

        result, raw = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        differences = result["pairing"]["commented_source_targets"][
            "structural_differences"
        ]

        self.assertEqual(differences["attributes"], 1)
        self.assertEqual(differences["tag_tokens"], 1)
        self.assertEqual(differences["interpolation_tokens"], 0)
        self.assertEqual(differences["interpolation_order"], 1)
        locations = result["pairing"]["commented_source_targets"][
            "difference_locations"
        ]
        self.assertEqual(locations[0]["file"], "game/tl/schinese/story.rpy")
        self.assertNotIn("text", locations[0])
        self.assertNotIn("Stop", raw)
        self.assertNotIn("停下", raw)

    def test_compares_visible_quote_edges_across_extend_fragments(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        with localization.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\ntranslate schinese quoted_span_deadbeef:\n\n"
                '    # duke "\\\"Say this, "\n'
                '    duke "“先说这句，"\n'
                '    # extend "then finish it.\\\""\n'
                '    extend "再把话说完。”"\n'
                "\ntranslate schinese missing_close_cafefeed:\n\n"
                '    # duke "\\\"One more, "\n'
                '    duke "“还有一句，"\n'
                '    # extend "then stop.\\\""\n'
                '    extend "然后停下。"\n'
            )

        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        paired = result["pairing"]["commented_source_targets"]

        self.assertEqual(
            paired["structural_differences"]["visible_quote_edges"],
            1,
        )
        mismatch = next(
            location
            for location in paired["difference_locations"]
            if location["block"] == "missing_close_cafefeed"
        )
        self.assertEqual(mismatch["fields"], ["visible_quote_edges"])

    def test_cli_forces_utf8_output_on_legacy_windows_encoding(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1252"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "samples",
                "--index",
                str(self.index),
                "--speaker",
                "duke",
                "--source",
                "active",
                "--limit",
                "100",
                "--context",
                "0",
            ],
            check=True,
            capture_output=True,
            env=environment,
        )
        output = completed.stdout.decode("utf-8")

        self.assertIn("你迟到了", output)

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

    def test_reused_legacy_entries_gain_file_format_metadata(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        data = json.loads(self.index.read_text(encoding="utf-8"))
        for entry in data["files"].values():
            entry.pop("newline")
            entry.pop("bom")
        self.index.write_text(json.dumps(data), encoding="utf-8")

        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        self.assertEqual(result["changed_files"], 0)
        self.assertEqual(result["reused_files"], 2)
        self.assertEqual(result["file_formats"]["newlines"], {"lf": 2})
        self.assertEqual(
            result["file_formats"]["byte_order_marks"], {"none": 2}
        )

    def test_reports_mixed_newlines(self) -> None:
        story = self.project / "game" / "story.rpy"
        raw = story.read_bytes()
        story.write_bytes(b"\xef\xbb\xbf" + raw.replace(b"\n", b"\r\n", 1))

        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        self.assertEqual(
            result["file_formats"]["newlines"],
            {"mixed": 1, "lf": 1},
        )
        self.assertEqual(
            result["file_format_locations"]["mixed_newlines"],
            ["game/story.rpy"],
        )
        self.assertEqual(
            result["file_formats"]["byte_order_marks"],
            {"utf-8": 1, "none": 1},
        )
        self.assertEqual(
            result["file_format_locations"]["byte_order_marks"],
            [{"file": "game/story.rpy", "bom": "utf-8"}],
        )

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
        self.assertIn("duke", result["top_speakers"])
        self.assertEqual(result["top_speakers_target"], {})

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
