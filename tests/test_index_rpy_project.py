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

    def run_cli_failure(self, *args: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertNotEqual(completed.returncode, 0)
        return completed

    def make_fixture_pilot(self, limit: int = 4) -> Path:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        output = self.temp_dir / "check-pilot.rpy"
        self.run_cli(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            str(limit),
            "--output",
            str(output),
        )
        return output

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
        color_samples, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--color",
            "#d8c8ff",
            "--source",
            "active",
            "--limit",
            "1",
            "--context",
            "0",
        )
        evidence_samples, evidence_raw = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--source",
            "evidence",
            "--limit",
            "100",
            "--context",
            "0",
        )

        self.assertIn("duke", summary["top_speakers"])
        self.assertIn("fonts/noble.ttf", summary["fonts"])
        self.assertNotIn("The hall fell silent", raw_summary)
        self.assertEqual(samples["returned"], 1)
        self.assertEqual(samples["samples"][0]["speaker"], "duke")
        self.assertTrue(samples["samples"][0]["source_comment"])
        self.assertLessEqual(len(samples["samples"][0]["context"]), 3)
        self.assertEqual(color_samples["returned"], 1)
        self.assertEqual(color_samples["samples"][0]["speaker"], "god")
        self.assertEqual(evidence_samples["matched"], 6)
        self.assertEqual(
            sum(
                bool(sample["source_comment"])
                for sample in evidence_samples["samples"]
            ),
            4,
        )
        self.assertEqual(
            sum(
                sample["kind"] == "old"
                for sample in evidence_samples["samples"]
            ),
            2,
        )
        self.assertNotIn('"kind": "new"', evidence_raw)

    def test_samples_bound_long_center_text(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        long_text = "A" * 200 + "SYNTHETIC_TAIL"
        with localization.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\ntranslate schinese long_strings:\n\n"
                f'    old "{long_text}"\n'
                '    new "target"\n'
            )
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        result, raw = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--source",
            "evidence",
            "--kind",
            "old",
            "--limit",
            "100",
            "--context",
            "0",
            "--max-chars",
            "40",
        )

        sample = next(
            item for item in result["samples"] if item["text_length"] > 40
        )
        self.assertEqual(len(sample["text"]), 40)
        self.assertTrue(sample["text"].endswith("…"))
        self.assertTrue(sample["text_truncated"])
        self.assertEqual(sample["text_length"], len(long_text))
        self.assertNotIn("SYNTHETIC_TAIL", raw)

    def test_profile_draft_is_evidence_only_and_requires_review(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        profile_path = self.temp_dir / "project-profile.json"

        result, raw = self.run_cli(
            "profile-draft",
            "--index",
            str(self.index),
            "--output",
            str(profile_path),
            "--speaker",
            "duke",
            "--speaker",
            "drifter",
            "--limit",
            "2",
            "--top",
            "2",
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "created")
        self.assertEqual(result["characters"], 2)
        self.assertEqual(result["approval_status"], "review")
        self.assertEqual(profile["defaults"]["status"], "review")
        self.assertEqual(set(profile["characters"]), {"duke", "drifter"})
        self.assertEqual(profile["characters"]["duke"]["status"], "review")
        self.assertIn(
            "fonts/noble.ttf",
            profile["characters"]["duke"]["markers"]["fonts"],
        )
        self.assertIn("font:fonts/mask.ttf", profile["channels"])
        self.assertNotIn("You are late", raw)
        self.assertNotIn("You are late", profile_path.read_text(encoding="utf-8"))

        check, check_raw = self.run_cli(
            "profile-check",
            str(profile_path),
            "--index",
            str(self.index),
        )
        self.assertEqual(check["status"], "review")
        self.assertTrue(check["source_evidence_matches_index"])
        self.assertGreater(check["review_item_count"], 0)
        self.assertNotIn("You are late", check_raw)

        duplicate = self.run_cli_failure(
            "profile-draft",
            "--index",
            str(self.index),
            "--output",
            str(profile_path),
        )
        self.assertIn("use --overwrite", duplicate.stderr)

    def test_profile_check_accepts_approval_and_rejects_empty_evidence(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        profile_path = self.temp_dir / "approved-profile.json"
        self.run_cli(
            "profile-draft",
            "--index",
            str(self.index),
            "--output",
            str(profile_path),
            "--speaker",
            "duke",
            "--top",
            "1",
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["channels"] = {}
        profile["defaults"].update(
            {
                "register": "natural-contemporary",
                "dialect_policy": "no-regional-dialect",
                "archaic_language": "restricted",
                "status": "approved",
            }
        )
        profile["characters"]["duke"].update(
            {
                "register": "formal-controlled",
                "rhythm": "complete-sentences",
                "status": "approved",
            }
        )
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False),
            encoding="utf-8",
        )

        result, raw = self.run_cli(
            "profile-check",
            str(profile_path),
            "--index",
            str(self.index),
            "--strict",
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["approval_statuses"], {"approved": 2})
        self.assertNotIn("You are late", raw)

        profile["characters"]["duke"]["register"] = None
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False),
            encoding="utf-8",
        )
        incomplete = self.run_cli_failure(
            "profile-check",
            str(profile_path),
            "--index",
            str(self.index),
        )
        incomplete_result = json.loads(incomplete.stdout)
        self.assertTrue(
            any(
                item["path"] == "characters.duke.register"
                for item in incomplete_result["hard_failures"]
            )
        )

        profile["characters"]["duke"]["register"] = "formal-controlled"
        profile["characters"]["duke"]["evidence"]["locations"] = []
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False),
            encoding="utf-8",
        )
        completed = self.run_cli_failure(
            "profile-check",
            str(profile_path),
            "--index",
            str(self.index),
        )
        failed = json.loads(completed.stdout)
        self.assertEqual(failed["status"], "fail")
        self.assertTrue(
            any(
                item["reason"] == "approved_evidence_required"
                for item in failed["hard_failures"]
            )
        )

        profile["characters"]["duke"]["markers"] = []
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False),
            encoding="utf-8",
        )
        malformed = self.run_cli_failure(
            "profile-check",
            str(profile_path),
        )
        malformed_result = json.loads(malformed.stdout)
        self.assertTrue(
            any(
                item["reason"] == "markers_must_be_an_object"
                for item in malformed_result["hard_failures"]
            )
        )

    def test_profile_check_reports_changed_source_evidence(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        profile_path = self.temp_dir / "stale-profile.json"
        self.run_cli(
            "profile-draft",
            "--index",
            str(self.index),
            "--output",
            str(profile_path),
            "--speaker",
            "duke",
            "--top",
            "1",
        )

        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        text = localization.read_text(encoding="utf-8")
        localization.write_text(
            text.replace("You are late", "You arrived late", 1),
            encoding="utf-8",
            newline="\n",
        )
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        result, raw = self.run_cli(
            "profile-check",
            str(profile_path),
            "--index",
            str(self.index),
        )
        self.assertEqual(result["status"], "review")
        self.assertFalse(result["source_evidence_matches_index"])
        self.assertTrue(
            any(
                item["reason"] == "index_changed"
                for item in result["review_items"]
            )
        )
        self.assertNotIn("You arrived late", raw)

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
                '    # duke "\\\"Interrupted.\\\"{w=0.5}{nw}"\n'
                '    duke "\\\"Target.\\\"{w=0.5}{nw}"\n'
                '    # duke "\\\"Cut off{w=0.5}{nw}"\n'
                '    duke "\\\"Target cut off{w=0.5}{nw}"\n'
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
        partial, _ = self.run_cli(
            "samples",
            "--index",
            str(self.index),
            "--speaker",
            "duke",
            "--source",
            "comments",
            "--outer-quotes",
            "partial",
            "--limit",
            "100",
            "--context",
            "0",
        )

        self.assertEqual(present["matched"], 2)
        self.assertEqual(absent["matched"], 3)
        self.assertEqual(partial["matched"], 1)
        self.assertEqual(partial["samples"][0]["text"], '\\"Cut off{w=0.5}{nw}')
        self.assertEqual(
            {sample["text"] for sample in present["samples"]},
            {'\\"Spoken aloud.\\"', '\\"Interrupted.\\"{w=0.5}{nw}'},
        )
        self.assertTrue(
            all(
                sample["text"] != '\\"Spoken aloud.\\"'
                for sample in absent["samples"]
            )
        )

    def test_pilot_extracts_source_comments_without_existing_targets(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        output = self.temp_dir / "pilot.rpy"

        result, raw = self.run_cli(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--start-line",
            "1",
            "--limit",
            "4",
            "--output",
            str(output),
        )
        pilot = output.read_text(encoding="utf-8")

        self.assertEqual(result["records"], 4)
        self.assertFalse(result["existing_targets_copied"])
        self.assertTrue(result["contains_source_text"])
        self.assertEqual(result["newline"], "lf")
        self.assertEqual(result["byte_order_mark"], "none")
        self.assertNotIn("You are late", raw)
        self.assertEqual(pilot.count("translate schinese start_a1b2c3d4:"), 1)
        self.assertIn('# duke "You are late, [player_name]."', pilot)
        self.assertIn('duke "You are late, [player_name]."', pilot)
        self.assertNotIn("你迟到了", pilot)
        self.assertFalse(output.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_pilot_refuses_overwrite_and_stale_index(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        output = self.temp_dir / "pilot.rpy"
        output.write_text("keep me", encoding="utf-8")

        existing = self.run_cli_failure(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            "1",
            "--output",
            str(output),
        )
        self.assertIn("already exists", existing.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        localization.write_text(
            localization.read_text(encoding="utf-8") + "\n# changed\n",
            encoding="utf-8",
        )
        stale = self.run_cli_failure(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            "1",
            "--output",
            str(output),
            "--overwrite",
        )
        self.assertIn("run scan again", stale.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep me")

    def test_pilot_preserves_utf8_bom_and_crlf(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        raw = localization.read_bytes().replace(b"\r\n", b"\n")
        localization.write_bytes(b"\xef\xbb\xbf" + raw.replace(b"\n", b"\r\n"))
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        output = self.temp_dir / "pilot.rpy"

        result, _ = self.run_cli(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            "1",
            "--output",
            str(output),
        )
        pilot_raw = output.read_bytes()

        self.assertEqual(result["newline"], "crlf")
        self.assertEqual(result["byte_order_mark"], "utf-8")
        self.assertTrue(pilot_raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", pilot_raw.replace(b"\r\n", b""))

    def test_pilot_rejects_mixed_newlines_and_indexed_output(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        raw = localization.read_bytes().replace(b"\r\n", b"\n")
        localization.write_bytes(raw.replace(b"\n", b"\r\n", 1))
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )

        mixed = self.run_cli_failure(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            "1",
            "--output",
            str(self.temp_dir / "pilot.rpy"),
        )
        self.assertIn("newline convention is 'mixed'", mixed.stderr)

        indexed = self.run_cli_failure(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--limit",
            "1",
            "--output",
            str(localization),
            "--overwrite",
        )
        self.assertIn("cannot overwrite an indexed source", indexed.stderr)

    def test_check_passes_a_translated_pilot_without_printing_text(self) -> None:
        pilot = self.make_fixture_pilot()
        lines = pilot.read_text(encoding="utf-8").splitlines()
        source_positions = [
            index for index, line in enumerate(lines) if line.startswith("    # ")
        ]
        translated_targets = [
            '    duke "你迟到了，[player_name]。"',
            '    drifter "路上太堵了。"',
            '    "大厅里安静下来。"',
            '    duke 2 stern "{font=fonts/mask.ttf}遮蔽"',
        ]
        for source_position, target in zip(
            source_positions, translated_targets, strict=True
        ):
            lines[source_position + 1] = target
        pilot.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        result, raw = self.run_cli(
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
            "--expected-targets",
            "4",
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["hard_failures"], [])
        self.assertEqual(result["review_flags"], [])
        self.assertTrue(result["source_evidence_matches_index"])
        self.assertTrue(result["indexed_file_sha256_matches"])
        self.assertEqual(result["source_evidence_integrity"]["unmatched"], 0)
        self.assertEqual(result["latin_residual_candidates"]["count"], 0)
        self.assertEqual(result["targets_without_han"]["count"], 0)
        self.assertNotIn("You are late", raw)
        self.assertNotIn("你迟到了", raw)

    def test_check_reports_review_and_strict_mode_fails(self) -> None:
        pilot = self.make_fixture_pilot()
        common_args = (
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
            "--expected-targets",
            "4",
        )

        result, raw = self.run_cli(*common_args)
        strict = self.run_cli_failure(*common_args, "--strict")
        strict_result = json.loads(strict.stdout)

        self.assertEqual(result["status"], "review")
        self.assertEqual(result["unchanged_targets"]["count"], 4)
        self.assertEqual(result["latin_residual_candidates"]["count"], 3)
        self.assertIn("unchanged_targets", result["review_flags"])
        self.assertIn("latin_residual_candidates", result["review_flags"])
        self.assertEqual(strict_result["status"], "review")
        self.assertNotIn("You are late", raw)

        missing_expected = self.run_cli_failure(
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
        )
        self.assertEqual(missing_expected.returncode, 2)
        self.assertIn("--expected-targets is required", missing_expected.stderr)

    def test_check_fails_on_source_empty_speaker_and_indentation_changes(self) -> None:
        pilot = self.make_fixture_pilot()
        lines = pilot.read_text(encoding="utf-8").splitlines()
        source_positions = [
            index for index, line in enumerate(lines) if line.startswith("    # ")
        ]
        lines[source_positions[0]] = '    # duke "Changed source."'
        lines[source_positions[0] + 1] = '    duke ""'
        lines[source_positions[1] + 1] = '    duke "已经翻译。"'
        lines[source_positions[2] + 1] = '        "大厅里安静下来。"'
        lines[source_positions[3] + 1] = (
            '    duke 2 stern "{font=fonts/mask.ttf}遮蔽"'
        )
        pilot.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        completed = self.run_cli_failure(
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
            "--expected-targets",
            "4",
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["status"], "fail")
        self.assertIn("source_evidence_integrity", result["hard_failures"])
        self.assertIn("empty_targets", result["hard_failures"])
        self.assertIn("speaker", result["hard_failures"])
        self.assertIn("indentation", result["hard_failures"])
        self.assertNotIn("Changed source", completed.stdout)

    def test_check_fails_on_format_drift(self) -> None:
        pilot = self.make_fixture_pilot(limit=1)
        raw = pilot.read_bytes().replace(b"\r\n", b"\n")
        pilot.write_bytes(raw.replace(b"\n", b"\r\n"))

        completed = self.run_cli_failure(
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
            "--expected-targets",
            "1",
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["status"], "fail")
        self.assertIn("file_format", result["hard_failures"])
        self.assertFalse(result["file_format"]["matches_source"])

    def test_check_detects_percent_format_token_loss(self) -> None:
        localization = self.project / "game" / "tl" / "schinese" / "story.rpy"
        with localization.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "\ntranslate schinese percent_formats_deadbeef:\n\n"
                '    # duke "Value: %s / %(name)s / %%"\n'
                '    duke "Old target"\n'
            )
        source_line = next(
            index
            for index, line in enumerate(
                localization.read_text(encoding="utf-8").splitlines(),
                start=1,
            )
            if line == '    # duke "Value: %s / %(name)s / %%"'
        )
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        pilot = self.temp_dir / "percent-pilot.rpy"
        self.run_cli(
            "pilot",
            "--index",
            str(self.index),
            "--file",
            "game/tl/schinese/story.rpy",
            "--start-line",
            str(source_line),
            "--limit",
            "1",
            "--output",
            str(pilot),
        )
        lines = pilot.read_text(encoding="utf-8").splitlines()
        target_line = next(
            index + 1
            for index, line in enumerate(lines)
            if line == '    # duke "Value: %s / %(name)s / %%"'
        )
        lines[target_line] = '    duke "数值：%(name)s。"'
        pilot.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        completed = self.run_cli_failure(
            "check",
            str(pilot),
            "--index",
            str(self.index),
            "--source-file",
            "game/tl/schinese/story.rpy",
            "--expected-targets",
            "1",
        )
        result = json.loads(completed.stdout)

        differences = result["structural_differences"]
        self.assertEqual(differences["percent_format_tokens"], 1)
        self.assertIn("percent_format_tokens", result["hard_failures"])
        self.assertNotIn("Value", completed.stdout)

    def test_check_accepts_target_edits_in_the_indexed_batch_file(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        data = json.loads(self.index.read_text(encoding="utf-8"))
        relative = "game/tl/schinese/story.rpy"
        localization = self.project / Path(relative)
        target_records = [
            record
            for record in data["files"][relative]["records"]
            if record.get("block") is not None
            and not record.get("source_comment")
            and record["kind"] not in {"character_definition", "old"}
        ]
        replacements = [
            '    duke "你迟到了，[player_name]。"',
            '    drifter "路上太堵了。"',
            '    "大厅里安静下来。"',
            '    duke 2 stern "{font=fonts/mask.ttf}遮蔽"',
            '    new "保存"',
            '    new "读取"',
        ]
        lines = localization.read_text(encoding="utf-8").splitlines()
        for record, replacement in zip(target_records, replacements, strict=True):
            lines[record["line"] - 1] = replacement
        localization.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        result, raw = self.run_cli(
            "check",
            str(localization),
            "--index",
            str(self.index),
            "--source-file",
            relative,
            "--strict",
        )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["expected_targets"], 6)
        self.assertEqual(result["source_comments"], 4)
        self.assertEqual(result["old_strings"], 2)
        self.assertEqual(result["active_targets"], 6)
        self.assertTrue(result["source_evidence_matches_index"])
        self.assertFalse(result["indexed_file_sha256_matches"])
        self.assertEqual(
            result["pairing"]["old_new"]["statement_pairs_compared"],
            2,
        )
        self.assertNotIn("你迟到了", raw)

    def test_check_rejects_source_header_changes_in_indexed_batch(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        relative = "game/tl/schinese/story.rpy"
        localization = self.project / Path(relative)
        text = localization.read_text(encoding="utf-8")
        localization.write_text(
            text.replace(
                "translate schinese start_a1b2c3d4:",
                "translate french start_a1b2c3d4:",
                1,
            ),
            encoding="utf-8",
            newline="\n",
        )

        completed = self.run_cli_failure(
            "check",
            str(localization),
            "--index",
            str(self.index),
            "--source-file",
            relative,
        )
        result = json.loads(completed.stdout)

        self.assertEqual(result["status"], "fail")
        self.assertFalse(result["source_evidence_matches_index"])
        self.assertFalse(result["indexed_file_sha256_matches"])
        self.assertIn("source_index_evidence", result["hard_failures"])
        self.assertIn("source_evidence_integrity", result["hard_failures"])
        self.assertNotIn("You are late", completed.stdout)

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

    def test_refreshes_entries_missing_source_evidence_metadata(self) -> None:
        self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        data = json.loads(self.index.read_text(encoding="utf-8"))
        for entry in data["files"].values():
            entry.pop("record_format_version")
            entry.pop("source_evidence_sha256")
            for record in entry["records"]:
                record.pop("language", None)
                record.pop("translate_header", None)
        self.index.write_text(json.dumps(data), encoding="utf-8")

        result, _ = self.run_cli(
            "scan",
            str(self.project),
            "--index",
            str(self.index),
        )
        refreshed = json.loads(self.index.read_text(encoding="utf-8"))

        self.assertEqual(result["changed_files"], 2)
        self.assertEqual(result["reused_files"], 0)
        for entry in refreshed["files"].values():
            self.assertEqual(entry["record_format_version"], 2)
            self.assertEqual(len(entry["source_evidence_sha256"]), 64)
            for record in entry["records"]:
                if record.get("block") is not None:
                    self.assertIsNotNone(record["language"])
                    self.assertIsNotNone(record["translate_header"])

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
