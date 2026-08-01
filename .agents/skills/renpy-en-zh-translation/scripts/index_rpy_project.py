#!/usr/bin/env python3
"""Build and query a compact local index of Ren'Py text.

The scanner reads the full project locally but prints only aggregate metadata.
Use the samples command to emit a bounded amount of source evidence.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


FORMAT_VERSION = 2
FILE_RECORD_VERSION = 2
PROFILE_FORMAT_VERSION = 1
PROFILE_STATUSES = {"approved", "provisional", "review"}
CHANNEL_CLASSIFICATIONS = {
    "voice-bearing",
    "layout-ui",
    "glyph-fallback",
    "redaction",
    "decorative",
    "mixed",
    "unknown",
}
STRING = r'(?P<quote>["\'])(?P<text>(?:\\.|(?!(?P=quote)).)*)(?P=quote)'
TRANSLATE_RE = re.compile(
    r"^(?P<indent>\s*)translate\s+(?P<language>\w+)\s+"
    r"(?P<block>[A-Za-z0-9_]+)\s*:"
)
CHARACTER_RE = re.compile(
    r"^\s*define\s+(?P<speaker>[A-Za-z_]\w*)\s*=\s*Character\s*\((?P<args>.*)\)\s*$"
)
OLD_NEW_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<kind>old|new)\s+{STRING}(?:\s+.*)?$"
)
MENU_RE = re.compile(
    rf"^(?P<indent>\s*){STRING}(?:\s+if\s+.+)?\s*:\s*$"
)
NARRATION_RE = re.compile(
    rf"^(?P<indent>\s*){STRING}(?:\s+[A-Za-z_]\w*)?\s*$"
)
UI_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<statement>text|textbutton)\s+{STRING}(?:\s+.*)?$"
)
DIALOGUE_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<speaker>[A-Za-z_]\w*)"
    rf"(?P<attributes>[^\"']*?)\s+{STRING}(?:\s+[A-Za-z_]\w*)?\s*$"
)
TAG_RE = re.compile(r"\{[^{}\r\n]+\}")
FONT_RE = re.compile(r"\{font=([^{}\r\n]+)\}")
COLOR_RE = re.compile(r"\{color=([^{}\r\n]+)\}")
INTERPOLATION_RE = re.compile(r"\[[^\[\]\r\n]+\]")
PERCENT_FORMAT_RE = re.compile(
    r"%(?:\([^)]+\))?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?"
    r"[diouxXeEfFgGcrsa%]"
)
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
QUOTED_RE = re.compile(r'(["\'])(.*?)(?<!\\)\1')
VISIBLE_OPENING_QUOTES = ('\\"', "“", "「", "『")
VISIBLE_CLOSING_QUOTES = ('\\"', "”", "」", "』")
PAIR_DIFFERENCE_FIELDS = (
    "statement_role",
    "speaker",
    "attributes",
    "indentation",
    "tag_tokens",
    "tag_order",
    "interpolation_tokens",
    "interpolation_order",
    "percent_format_tokens",
    "percent_format_order",
    "visible_quote_edges",
)

NON_SPEAKER_KEYWORDS = {
    "at",
    "call",
    "camera",
    "default",
    "define",
    "elif",
    "else",
    "hide",
    "if",
    "image",
    "init",
    "jump",
    "label",
    "menu",
    "new",
    "old",
    "pause",
    "play",
    "python",
    "queue",
    "return",
    "scene",
    "screen",
    "show",
    "stop",
    "style",
    "translate",
    "voice",
    "while",
    "with",
}


class IndexErrorMessage(RuntimeError):
    """A user-facing index error."""


def inspect_file(path: Path, encoding: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    try:
        text = raw.decode(encoding)
    except UnicodeError as exc:
        raise IndexErrorMessage(
            f"Cannot decode {path} with encoding {encoding}: {exc}"
        ) from exc

    without_crlf = text.replace("\r\n", "")
    newline_kinds = []
    if "\r\n" in text:
        newline_kinds.append("crlf")
    if "\n" in without_crlf:
        newline_kinds.append("lf")
    if "\r" in without_crlf:
        newline_kinds.append("cr")
    if not newline_kinds:
        newline = "none"
    elif len(newline_kinds) == 1:
        newline = newline_kinds[0]
    else:
        newline = "mixed"

    bom = "none"
    for name, marker in (
        ("utf-32-le", b"\xff\xfe\x00\x00"),
        ("utf-32-be", b"\x00\x00\xfe\xff"),
        ("utf-8", b"\xef\xbb\xbf"),
        ("utf-16-le", b"\xff\xfe"),
        ("utf-16-be", b"\xfe\xff"),
    ):
        if raw.startswith(marker):
            bom = name
            break

    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "newline": newline,
        "bom": bom,
    }, text


def extract_named_argument(args: str, names: Iterable[str]) -> list[str]:
    values: list[str] = []
    for name in names:
        pattern = re.compile(
            rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)(?<!\\)\1"
        )
        values.extend(match.group(2) for match in pattern.finditer(args))
    return values


def make_text_record(
    *,
    line_number: int,
    kind: str,
    speaker: str | None,
    text: str,
    indent: str,
    block: str | None,
    source_comment: bool,
    attributes: str | None = None,
) -> dict[str, Any]:
    tags = TAG_RE.findall(text)
    return {
        "line": line_number,
        "kind": kind,
        "speaker": speaker,
        "attributes": attributes,
        "text": text,
        "indent": indent,
        "block": block,
        "source_comment": source_comment,
        "tags": tags,
        "fonts": FONT_RE.findall(text),
        "colors": COLOR_RE.findall(text),
        "interpolations": INTERPOLATION_RE.findall(text),
    }


def parse_statement(
    content: str,
    *,
    line_number: int,
    block: str | None,
    source_comment: bool,
) -> dict[str, Any] | None:
    match = OLD_NEW_RE.match(content)
    if match:
        return make_text_record(
            line_number=line_number,
            kind=match.group("kind"),
            speaker=None,
            text=match.group("text"),
            indent=match.group("indent"),
            block=block,
            source_comment=source_comment,
        )

    match = MENU_RE.match(content)
    if match:
        return make_text_record(
            line_number=line_number,
            kind="menu",
            speaker=None,
            text=match.group("text"),
            indent=match.group("indent"),
            block=block,
            source_comment=source_comment,
        )

    match = NARRATION_RE.match(content)
    if match:
        return make_text_record(
            line_number=line_number,
            kind="narration",
            speaker=None,
            text=match.group("text"),
            indent=match.group("indent"),
            block=block,
            source_comment=source_comment,
        )

    match = UI_RE.match(content)
    if match:
        return make_text_record(
            line_number=line_number,
            kind="ui",
            speaker=None,
            text=match.group("text"),
            indent=match.group("indent"),
            block=block,
            source_comment=source_comment,
        )

    match = DIALOGUE_RE.match(content)
    if not match:
        return None

    speaker = match.group("speaker")
    attributes = match.group("attributes")
    if speaker in NON_SPEAKER_KEYWORDS or "=" in attributes:
        return None

    kind = "extend" if speaker == "extend" else "dialogue"
    return make_text_record(
        line_number=line_number,
        kind=kind,
        speaker=None if kind == "extend" else speaker,
        text=match.group("text"),
        indent=match.group("indent"),
        block=block,
        source_comment=source_comment,
        attributes=attributes.strip(),
    )


def parse_text(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    records: list[dict[str, Any]] = []
    current_block: str | None = None
    current_language: str | None = None
    current_header: str | None = None
    block_indent = -1

    for line_number, raw_line in enumerate(lines, start=1):
        translate_match = TRANSLATE_RE.match(raw_line)
        if translate_match:
            current_block = translate_match.group("block")
            current_language = translate_match.group("language")
            current_header = raw_line
            block_indent = len(translate_match.group("indent").expandtabs(4))
            continue

        stripped = raw_line.lstrip()
        indent_width = len(raw_line) - len(stripped)
        if (
            current_block is not None
            and stripped
            and not stripped.startswith("#")
            and indent_width <= block_indent
        ):
            current_block = None
            current_language = None
            current_header = None
            block_indent = -1

        character_match = CHARACTER_RE.match(raw_line)
        if character_match:
            args = character_match.group("args")
            first_quoted = QUOTED_RE.search(args)
            records.append(
                {
                    "line": line_number,
                    "kind": "character_definition",
                    "speaker": character_match.group("speaker"),
                    "display_name": first_quoted.group(2) if first_quoted else None,
                    "fonts": extract_named_argument(
                        args, ("what_font", "who_font")
                    ),
                    "colors": extract_named_argument(
                        args, ("what_color", "who_color", "color")
                    ),
                }
            )
            continue

        source_comment = False
        content = raw_line
        if stripped.startswith("#"):
            if current_block is None:
                continue
            source_comment = True
            comment_offset = len(raw_line) - len(stripped)
            content = raw_line[:comment_offset] + stripped[1:].lstrip()

        record = parse_statement(
            content,
            line_number=line_number,
            block=current_block,
            source_comment=source_comment,
        )
        if record is not None:
            record["language"] = current_language
            record["translate_header"] = current_header
            records.append(record)

    return records


def is_source_evidence_record(record: dict[str, Any]) -> bool:
    return (
        record.get("source_comment")
        and record["kind"] not in {"old", "new"}
    ) or (
        not record.get("source_comment") and record["kind"] == "old"
    )


def source_record_fingerprint(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("language"),
        record.get("translate_header"),
        record.get("block"),
        record.get("kind"),
        record.get("speaker"),
        record.get("attributes"),
        record.get("indent"),
        record.get("text"),
    )


def source_evidence_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [record for record in records if is_source_evidence_record(record)]


def source_evidence_sha256(records: Iterable[dict[str, Any]]) -> str:
    fingerprints = [
        source_record_fingerprint(record)
        for record in source_evidence_records(records)
    ]
    serialized = json.dumps(
        fingerprints,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def discover_rpy_files(root: Path, exclude_patterns: list[str]) -> list[Path]:
    if root.is_file():
        if root.suffix.lower() != ".rpy":
            raise IndexErrorMessage(f"Expected an .rpy file: {root}")
        return [root]
    if not root.is_dir():
        raise IndexErrorMessage(f"Project path does not exist: {root}")
    files = []
    for path in root.rglob("*.rpy"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(
            fnmatch.fnmatchcase(relative, pattern)
            for pattern in exclude_patterns
        ):
            continue
        files.append(path)
    return sorted(files)


def load_index(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IndexErrorMessage(f"Index does not exist: {path}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IndexErrorMessage(f"Invalid index {path}: {exc}") from exc

    if data.get("format_version") != FORMAT_VERSION:
        raise IndexErrorMessage(
            f"Unsupported index format in {path}: "
            f"{data.get('format_version')!r}"
        )
    return data


def write_index_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_profile_atomic(
    path: Path, data: dict[str, Any], overwrite: bool
) -> None:
    if path.exists() and not overwrite:
        raise IndexErrorMessage(
            f"Profile output already exists; use --overwrite: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path, text: str, encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        newline="",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def scan_project(args: argparse.Namespace) -> int:
    root = Path(args.project).resolve()
    index_path = Path(args.index).resolve()
    files = discover_rpy_files(root, args.exclude)
    root_for_paths = root if root.is_dir() else root.parent

    old_data: dict[str, Any] | None = None
    if index_path.exists():
        candidate = load_index(index_path)
        if Path(candidate.get("project_root", "")).resolve() == root_for_paths:
            old_data = candidate

    old_files = old_data.get("files", {}) if old_data else {}
    indexed_files: dict[str, Any] = {}
    changed_files = 0
    reused_files = 0

    for path in files:
        relative = path.relative_to(root_for_paths).as_posix()
        file_metadata, text = inspect_file(path, args.encoding)
        digest = file_metadata["sha256"]
        old_entry = old_files.get(relative)
        if (
            old_entry
            and old_entry.get("sha256") == digest
            and old_entry.get("encoding") == args.encoding
            and old_entry.get("record_format_version") == FILE_RECORD_VERSION
            and old_entry.get("source_evidence_sha256")
        ):
            indexed_files[relative] = {**old_entry, **file_metadata}
            reused_files += 1
            continue

        records = parse_text(text)
        indexed_files[relative] = {
            **file_metadata,
            "encoding": args.encoding,
            "record_format_version": FILE_RECORD_VERSION,
            "source_evidence_sha256": source_evidence_sha256(records),
            "records": records,
        }
        changed_files += 1

    removed_files = len(set(old_files) - set(indexed_files))
    data = {
        "format_version": FORMAT_VERSION,
        "project_root": str(root_for_paths),
        "files": indexed_files,
    }
    write_index_atomic(index_path, data)
    result = compact_summary(data)
    result.update(
        {
            "index": str(index_path),
            "changed_files": changed_files,
            "reused_files": reused_files,
            "removed_files": removed_files,
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def iter_records(data: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for relative, entry in sorted(data["files"].items()):
        for record in entry["records"]:
            yield {"file": relative, **record}


def count_speakers(records: Iterable[dict[str, Any]]) -> Counter[str]:
    return Counter(
        record["speaker"]
        for record in records
        if record.get("speaker") is not None
    )


def count_markers(
    records: Iterable[dict[str, Any]], field: str
) -> Counter[str]:
    return Counter(
        marker
        for record in records
        for marker in dict.fromkeys(record.get(field, []))
    )


def select_profile_evidence(
    text_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    active_records = [
        record for record in text_records if not record["source_comment"]
    ]
    source_records = [
        record for record in text_records if record["source_comment"]
    ]
    old_records = [
        record for record in active_records if record["kind"] == "old"
    ]
    new_records = [
        record for record in active_records if record["kind"] == "new"
    ]
    if source_records:
        source_evidence = source_records + old_records
        target_records = [
            record for record in active_records if record["kind"] != "old"
        ]
        source_mode = (
            "source_comments_and_old"
            if old_records
            else "source_comments"
        )
    elif old_records:
        source_evidence = [
            record for record in active_records if record["kind"] != "new"
        ]
        target_records = new_records
        source_mode = "active_statements_and_old"
    else:
        source_evidence = active_records
        target_records = []
        source_mode = "active_statements"
    return source_evidence, target_records, source_mode


def visible_quote_edges(text: str) -> tuple[bool, bool]:
    """Return source-relative opening and closing visible-quote roles."""
    return (
        text.startswith(VISIBLE_OPENING_QUOTES),
        text.endswith(VISIBLE_CLOSING_QUOTES),
    )


def compare_record_pair(
    source: dict[str, Any], target: dict[str, Any]
) -> dict[str, int]:
    differences = Counter()
    source_kind = "string" if source["kind"] == "old" else source["kind"]
    target_kind = "string" if target["kind"] == "new" else target["kind"]
    if source_kind != target_kind:
        differences["statement_role"] += 1
    if source.get("speaker") != target.get("speaker"):
        differences["speaker"] += 1
    if source.get("attributes") != target.get("attributes"):
        differences["attributes"] += 1
    if source.get("indent") != target.get("indent"):
        differences["indentation"] += 1
    source_tags = source.get("tags", [])
    target_tags = target.get("tags", [])
    if Counter(source_tags) != Counter(target_tags):
        differences["tag_tokens"] += 1
    elif source_tags != target_tags:
        differences["tag_order"] += 1
    source_interpolations = source.get("interpolations", [])
    target_interpolations = target.get("interpolations", [])
    if Counter(source_interpolations) != Counter(target_interpolations):
        differences["interpolation_tokens"] += 1
    elif source_interpolations != target_interpolations:
        differences["interpolation_order"] += 1
    source_percent_formats = PERCENT_FORMAT_RE.findall(source["text"])
    target_percent_formats = PERCENT_FORMAT_RE.findall(target["text"])
    if Counter(source_percent_formats) != Counter(target_percent_formats):
        differences["percent_format_tokens"] += 1
    elif source_percent_formats != target_percent_formats:
        differences["percent_format_order"] += 1
    if visible_quote_edges(source["text"]) != visible_quote_edges(target["text"]):
        differences["visible_quote_edges"] += 1
    return {
        name: differences[name]
        for name in PAIR_DIFFERENCE_FIELDS
    }


def summarize_pairs(
    records: list[dict[str, Any]],
    *,
    source_kind: str,
    top: int,
) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        block = record.get("block")
        if block is None:
            continue
        if source_kind == "comments":
            if record["kind"] in {"old", "new"}:
                continue
            side = "source" if record["source_comment"] else "target"
        else:
            if record["kind"] not in {"old", "new"}:
                continue
            side = "source" if record["kind"] == "old" else "target"
        group = groups.setdefault(
            (record["file"], block), {"source": [], "target": []}
        )
        group[side].append(record)

    counts = Counter()
    differences = Counter()
    examples = []
    first_example_by_field: dict[str, dict[str, Any]] = {}
    for group in groups.values():
        sources = group["source"]
        targets = group["target"]
        if sources and targets and len(sources) == len(targets):
            counts["balanced_blocks"] += 1
        elif sources and targets:
            counts["count_mismatch_blocks"] += 1
        elif sources:
            counts["source_only_blocks"] += 1
        else:
            counts["target_only_blocks"] += 1
        counts["source_statements"] += len(sources)
        counts["target_statements"] += len(targets)
        counts["statement_pairs_compared"] += min(len(sources), len(targets))
        for source, target in zip(sources, targets):
            pair_differences = compare_record_pair(source, target)
            differences.update(pair_differences)
            fields = [
                name for name, count in pair_differences.items() if count
            ]
            if fields:
                example = {
                    "file": source["file"],
                    "block": source["block"],
                    "source_line": source["line"],
                    "target_line": target["line"],
                    "fields": fields,
                }
                if len(examples) < top:
                    examples.append(example)
                for field in fields:
                    first_example_by_field.setdefault(field, example)

    representative_examples = []
    seen_locations = set()
    candidate_examples = [
        first_example_by_field[field]
        for field in PAIR_DIFFERENCE_FIELDS
        if field in first_example_by_field
    ]
    candidate_examples.extend(examples)
    for example in candidate_examples:
        location = (
            example["file"],
            example["block"],
            example["source_line"],
            example["target_line"],
        )
        if location in seen_locations:
            continue
        seen_locations.add(location)
        representative_examples.append(example)
        if len(representative_examples) == top:
            break

    return {
        "blocks": len(groups),
        "balanced_blocks": counts["balanced_blocks"],
        "count_mismatch_blocks": counts["count_mismatch_blocks"],
        "source_only_blocks": counts["source_only_blocks"],
        "target_only_blocks": counts["target_only_blocks"],
        "source_statements": counts["source_statements"],
        "target_statements": counts["target_statements"],
        "statement_pairs_compared": counts["statement_pairs_compared"],
        "structural_differences": {
            name: differences[name]
            for name in PAIR_DIFFERENCE_FIELDS
        },
        "difference_locations": representative_examples,
    }


def compact_summary(data: dict[str, Any], top: int = 20) -> dict[str, Any]:
    records = list(iter_records(data))
    character_records = [
        record for record in records if record["kind"] == "character_definition"
    ]
    text_records = [
        record for record in records if record["kind"] != "character_definition"
    ]
    active_records = [
        record for record in text_records if not record["source_comment"]
    ]
    source_records = [
        record for record in text_records if record["source_comment"]
    ]
    source_evidence, target_records, profile_source = select_profile_evidence(
        text_records
    )
    profile_records = source_evidence
    speakers = count_speakers(profile_records)
    source_speakers = count_speakers(source_evidence)
    target_speakers = count_speakers(target_records)
    kinds = Counter(record["kind"] for record in text_records)
    source_fonts = count_markers(source_evidence, "fonts")
    target_fonts = count_markers(target_records, "fonts")
    source_colors = count_markers(source_evidence, "colors")
    target_colors = count_markers(target_records, "colors")
    fonts = count_markers(profile_records + character_records, "fonts")
    colors = count_markers(profile_records + character_records, "colors")
    encodings = Counter(
        entry.get("encoding", "unknown") for entry in data["files"].values()
    )
    newlines = Counter(
        entry.get("newline", "unknown") for entry in data["files"].values()
    )
    byte_order_marks = Counter(
        entry.get("bom", "unknown") for entry in data["files"].values()
    )
    return {
        "files": len(data["files"]),
        "file_formats": {
            "encodings": dict(encodings.most_common()),
            "newlines": dict(newlines.most_common()),
            "byte_order_marks": dict(byte_order_marks.most_common()),
        },
        "file_format_locations": {
            "mixed_newlines": [
                relative
                for relative, entry in sorted(data["files"].items())
                if entry.get("newline") == "mixed"
            ][:top],
            "byte_order_marks": [
                {"file": relative, "bom": entry["bom"]}
                for relative, entry in sorted(data["files"].items())
                if entry.get("bom") not in (None, "none")
            ][:top],
        },
        "text_statements": len(text_records),
        "active_statements": len(active_records),
        "source_comment_statements": len(source_records),
        "profile_evidence_source": profile_source,
        "character_definitions": len(character_records),
        "character_markers": [
            {
                "speaker": record["speaker"],
                "display_name": record["display_name"],
                "fonts": record["fonts"],
                "colors": record["colors"],
                "file": record["file"],
                "line": record["line"],
            }
            for record in character_records[:top]
        ],
        "kinds": dict(kinds.most_common()),
        "top_speakers": dict(speakers.most_common(top)),
        "top_speakers_source": dict(source_speakers.most_common(top)),
        "top_speakers_target": dict(target_speakers.most_common(top)),
        "fonts": dict(fonts.most_common(top)),
        "fonts_source": dict(source_fonts.most_common(top)),
        "fonts_target": dict(target_fonts.most_common(top)),
        "colors": dict(colors.most_common(top)),
        "colors_source": dict(source_colors.most_common(top)),
        "colors_target": dict(target_colors.most_common(top)),
        "pairing": {
            "commented_source_targets": summarize_pairs(
                text_records, source_kind="comments", top=top
            ),
            "old_new": summarize_pairs(
                text_records, source_kind="old", top=top
            ),
        },
    }


def summarize_index(args: argparse.Namespace) -> int:
    data = load_index(Path(args.index).resolve())
    print(
        json.dumps(
            compact_summary(data, top=args.top),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def evenly_spaced(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(records) <= limit:
        return records
    if limit == 1:
        return [records[len(records) // 2]]
    indices = {
        round(position * (len(records) - 1) / (limit - 1))
        for position in range(limit)
    }
    return [records[index] for index in sorted(indices)]


def profile_evidence_components(
    data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    records = list(iter_records(data))
    character_records = [
        record for record in records if record["kind"] == "character_definition"
    ]
    text_records = [
        record for record in records if record["kind"] != "character_definition"
    ]
    source_evidence, _, source_mode = select_profile_evidence(text_records)
    source_evidence.sort(key=lambda item: (item["file"], item["line"]))
    return character_records, source_evidence, source_mode


def profile_evidence_sha256(
    character_records: Iterable[dict[str, Any]],
    source_evidence: Iterable[dict[str, Any]],
) -> str:
    fingerprints = []
    for record in character_records:
        fingerprints.append(
            (
                "character",
                record["file"],
                record["line"],
                record.get("speaker"),
                record.get("display_name"),
                record.get("fonts", []),
                record.get("colors", []),
            )
        )
    for record in source_evidence:
        fingerprints.append(
            (
                "text",
                record["file"],
                record["line"],
                *source_record_fingerprint(record),
            )
        )
    serialized = json.dumps(
        fingerprints,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def profile_location(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": record["file"],
        "line": record["line"],
        "kind": record["kind"],
    }


def ordered_marker_counts(
    records: Iterable[dict[str, Any]], field: str
) -> list[tuple[str, int]]:
    counts = count_markers(records, field)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def draft_profile(args: argparse.Namespace) -> int:
    index_path = Path(args.index).resolve()
    output_path = Path(args.output).resolve()
    if output_path == index_path:
        raise IndexErrorMessage("Profile output must not replace the index")

    data = load_index(index_path)
    character_records, source_evidence, source_mode = (
        profile_evidence_components(data)
    )
    speaker_counts = count_speakers(source_evidence)
    if args.speaker:
        selected_speakers = list(dict.fromkeys(args.speaker))
        missing = [
            speaker for speaker in selected_speakers if speaker not in speaker_counts
        ]
        if missing:
            raise IndexErrorMessage(
                "Speakers lack source evidence: " + ", ".join(missing)
            )
    else:
        selected_speakers = [
            speaker
            for speaker, _ in sorted(
                speaker_counts.items(), key=lambda item: (-item[1], item[0])
            )[: args.top]
        ]

    characters: dict[str, Any] = {}
    for speaker in selected_speakers:
        definitions = [
            record
            for record in character_records
            if record.get("speaker") == speaker
        ]
        statements = [
            record
            for record in source_evidence
            if record.get("speaker") == speaker
        ]
        display_names = list(
            dict.fromkeys(
                record["display_name"]
                for record in definitions
                if record.get("display_name") is not None
            )
        )
        marker_records = definitions + statements
        sample_records = evenly_spaced(statements, args.limit)
        characters[speaker] = {
            "display_name": display_names[0] if len(display_names) == 1 else None,
            "display_name_candidates": display_names,
            "markers": {
                "speakers": [speaker],
                "fonts": sorted(
                    count_markers(marker_records, "fonts").keys()
                ),
                "colors": sorted(
                    count_markers(marker_records, "colors").keys()
                ),
            },
            "register": None,
            "rhythm": None,
            "address_terms": {},
            "preferred_features": [],
            "avoid": [],
            "relationship_variants": {},
            "evidence": {
                "statement_count": len(statements),
                "locations": [
                    profile_location(record) for record in sample_records
                ],
                "definition_locations": [
                    profile_location(record) for record in definitions
                ],
            },
            "status": "review",
        }

    channels: dict[str, Any] = {}
    marker_source = character_records + source_evidence
    for field, marker_type in (("fonts", "font"), ("colors", "color")):
        for marker, _ in ordered_marker_counts(marker_source, field)[
            : args.top
        ]:
            matching = [
                record
                for record in marker_source
                if marker in record.get(field, [])
            ]
            text_matching = [
                record
                for record in matching
                if record["kind"] != "character_definition"
            ]
            samples = evenly_spaced(matching, min(5, args.limit))
            channels[f"{marker_type}:{marker}"] = {
                "marker_type": marker_type,
                "marker": marker,
                "markers": {
                    "speakers": sorted(
                        {
                            record["speaker"]
                            for record in matching
                            if record.get("speaker") is not None
                        }
                    ),
                    "fonts": [marker] if marker_type == "font" else [],
                    "colors": [marker] if marker_type == "color" else [],
                },
                "classification": "unknown",
                "register": None,
                "preferred_features": [],
                "avoid": [],
                "evidence": {
                    "statement_count": len(text_matching),
                    "locations": [
                        profile_location(record) for record in samples
                    ],
                },
                "status": "review",
            }

    profile = {
        "profile_format_version": PROFILE_FORMAT_VERSION,
        "language": {"source": "en", "target": "zh-Hans"},
        "source": {
            "index_format_version": data["format_version"],
            "evidence_sha256": profile_evidence_sha256(
                character_records, source_evidence
            ),
            "files": len(data["files"]),
            "evidence_mode": source_mode,
        },
        "defaults": {
            "register": None,
            "dialect_policy": None,
            "archaic_language": None,
            "font_tag_policy": "preserve-source",
            "status": "review",
        },
        "typography_exceptions": [],
        "characters": characters,
        "channels": channels,
    }
    write_profile_atomic(output_path, profile, args.overwrite)
    result = {
        "status": "created",
        "profile": str(output_path),
        "evidence_mode": source_mode,
        "characters": len(characters),
        "channels": len(channels),
        "speaker_sample_locations": sum(
            len(entry["evidence"]["locations"]) for entry in characters.values()
        ),
        "channel_sample_locations": sum(
            len(entry["evidence"]["locations"]) for entry in channels.values()
        ),
        "approval_status": "review",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def load_profile(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IndexErrorMessage(f"Profile does not exist: {path}") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise IndexErrorMessage(f"Invalid profile {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise IndexErrorMessage(f"Profile root must be an object: {path}")
    return data


def check_profile(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile).resolve()
    profile = load_profile(profile_path)
    hard_failures: list[dict[str, str]] = []
    review_items: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()

    def hard(path: str, reason: str) -> None:
        hard_failures.append({"path": path, "reason": reason})

    def check_status(path: str, value: Any) -> str | None:
        if value not in PROFILE_STATUSES:
            hard(f"{path}.status", "invalid_status")
            return None
        status_counts[value] += 1
        if value != "approved":
            review_items.append(
                {"path": path, "reason": f"status_{value}"}
            )
        return value

    def check_locations(path: str, value: Any) -> int:
        if not isinstance(value, list):
            hard(path, "locations_must_be_a_list")
            return 0
        valid = 0
        for index, location in enumerate(value):
            item_path = f"{path}[{index}]"
            if not isinstance(location, dict):
                hard(item_path, "location_must_be_an_object")
                continue
            if not isinstance(location.get("file"), str) or not location["file"]:
                hard(f"{item_path}.file", "invalid_file")
            elif not isinstance(location.get("line"), int) or location["line"] < 1:
                hard(f"{item_path}.line", "invalid_line")
            else:
                valid += 1
        return valid

    def check_markers(path: str, value: Any) -> None:
        if not isinstance(value, dict):
            hard(path, "markers_must_be_an_object")
            return
        for field in ("speakers", "fonts", "colors"):
            markers = value.get(field)
            if not isinstance(markers, list) or not all(
                isinstance(marker, str) for marker in markers
            ):
                hard(f"{path}.{field}", "markers_must_be_strings")

    if profile.get("profile_format_version") != PROFILE_FORMAT_VERSION:
        hard("profile_format_version", "unsupported_version")
    language = profile.get("language")
    if not isinstance(language, dict):
        hard("language", "language_must_be_an_object")
    elif language.get("source") != "en" or language.get("target") != "zh-Hans":
        hard("language", "expected_en_to_zh_hans")

    source = profile.get("source")
    stored_evidence_digest = None
    if not isinstance(source, dict):
        hard("source", "source_must_be_an_object")
    else:
        stored_evidence_digest = source.get("evidence_sha256")
        if not isinstance(stored_evidence_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", stored_evidence_digest
        ):
            hard("source.evidence_sha256", "invalid_sha256")

    defaults = profile.get("defaults")
    if not isinstance(defaults, dict):
        hard("defaults", "defaults_must_be_an_object")
    else:
        defaults_status = check_status("defaults", defaults.get("status"))
        if defaults_status == "approved":
            for field in (
                "register",
                "dialect_policy",
                "archaic_language",
                "font_tag_policy",
            ):
                if not isinstance(defaults.get(field), str) or not defaults[field]:
                    hard(f"defaults.{field}", "approved_value_required")

    for collection_name in ("characters", "channels"):
        collection = profile.get(collection_name)
        if not isinstance(collection, dict):
            hard(collection_name, "collection_must_be_an_object")
            continue
        for key, entry in collection.items():
            path = f"{collection_name}.{key}"
            if not isinstance(key, str) or not key:
                hard(collection_name, "entry_key_must_be_a_string")
                continue
            if not isinstance(entry, dict):
                hard(path, "entry_must_be_an_object")
                continue
            entry_status = check_status(path, entry.get("status"))
            markers = entry.get("markers")
            check_markers(f"{path}.markers", markers)
            evidence = entry.get("evidence")
            valid_locations = 0
            if not isinstance(evidence, dict):
                hard(f"{path}.evidence", "evidence_must_be_an_object")
            else:
                valid_locations = check_locations(
                    f"{path}.evidence.locations", evidence.get("locations")
                )
            if entry_status == "approved" and valid_locations == 0:
                hard(f"{path}.evidence", "approved_evidence_required")
            if collection_name == "characters":
                speakers = (
                    markers.get("speakers", [])
                    if isinstance(markers, dict)
                    else []
                )
                if isinstance(markers, dict) and key not in speakers:
                    hard(f"{path}.markers.speakers", "character_key_missing")
                if entry_status == "approved":
                    for field in ("register", "rhythm"):
                        if (
                            not isinstance(entry.get(field), str)
                            or not entry[field]
                        ):
                            hard(f"{path}.{field}", "approved_value_required")
            else:
                classification = entry.get("classification")
                if classification not in CHANNEL_CLASSIFICATIONS:
                    hard(f"{path}.classification", "invalid_classification")
                elif entry_status == "approved" and classification == "unknown":
                    hard(f"{path}.classification", "approved_value_required")

    exceptions = profile.get("typography_exceptions")
    if not isinstance(exceptions, list):
        hard("typography_exceptions", "exceptions_must_be_a_list")
    else:
        for index, exception in enumerate(exceptions):
            path = f"typography_exceptions[{index}]"
            if not isinstance(exception, dict):
                hard(path, "exception_must_be_an_object")
                continue
            exception_status = check_status(path, exception.get("status"))
            if exception_status == "approved":
                for field in ("marker", "target_action", "reason", "scope"):
                    if not isinstance(exception.get(field), str) or not exception[field]:
                        hard(f"{path}.{field}", "approved_value_required")

    source_evidence_matches_index: bool | None = None
    if args.index is not None:
        index_data = load_index(Path(args.index).resolve())
        characters, evidence, _ = profile_evidence_components(index_data)
        current_digest = profile_evidence_sha256(characters, evidence)
        source_evidence_matches_index = current_digest == stored_evidence_digest
        if source_evidence_matches_index is False:
            review_items.append(
                {"path": "source.evidence_sha256", "reason": "index_changed"}
            )

    status = (
        "fail"
        if hard_failures
        else "review"
        if review_items
        else "pass"
    )
    result = {
        "status": status,
        "profile": str(profile_path),
        "characters": len(profile.get("characters", {}))
        if isinstance(profile.get("characters"), dict)
        else 0,
        "channels": len(profile.get("channels", {}))
        if isinstance(profile.get("channels"), dict)
        else 0,
        "approval_statuses": dict(status_counts),
        "source_evidence_matches_index": source_evidence_matches_index,
        "hard_failure_count": len(hard_failures),
        "hard_failures": hard_failures[: args.top],
        "review_item_count": len(review_items),
        "review_items": review_items[: args.top],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if status == "fail" or (args.strict and status == "review"):
        return 1
    return 0


def truncate_line(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def context_for_record(
    data: dict[str, Any],
    record: dict[str, Any],
    context: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    root = Path(data["project_root"])
    entry = data["files"][record["file"]]
    path = root / record["file"]
    try:
        lines = path.read_text(encoding=entry["encoding"]).splitlines()
    except (OSError, UnicodeError) as exc:
        return [{"error": str(exc)}]

    center = record["line"] - 1
    start = max(0, center - context)
    end = min(len(lines), center + context + 1)
    return [
        {
            "line": index + 1,
            "text": truncate_line(lines[index], max_chars),
        }
        for index in range(start, end)
    ]


def has_escaped_outer_quotes(text: str) -> bool:
    return len(text) >= 4 and text.startswith('\\"') and text.endswith('\\"')


def sample_index(args: argparse.Namespace) -> int:
    data = load_index(Path(args.index).resolve())
    candidates = [
        record
        for record in iter_records(data)
        if record["kind"] != "character_definition"
    ]

    if args.speaker is not None:
        candidates = [
            record for record in candidates if record.get("speaker") == args.speaker
        ]
    if args.font is not None:
        candidates = [
            record for record in candidates if args.font in record.get("fonts", [])
        ]
    if args.kind is not None:
        candidates = [
            record for record in candidates if record["kind"] == args.kind
        ]
    if args.file:
        candidates = [
            record
            for record in candidates
            if any(
                fnmatch.fnmatchcase(record["file"], pattern)
                for pattern in args.file
            )
        ]
    if args.outer_quotes is not None:
        expected = args.outer_quotes == "present"
        candidates = [
            record
            for record in candidates
            if has_escaped_outer_quotes(record["text"]) == expected
        ]
    if args.source == "comments":
        candidates = [
            record for record in candidates if record["source_comment"]
        ]
    elif args.source == "active":
        candidates = [
            record for record in candidates if not record["source_comment"]
        ]

    candidates.sort(key=lambda item: (item["file"], item["line"]))
    selected = evenly_spaced(candidates, args.limit)
    output = []
    for record in selected:
        item = dict(record)
        item["context"] = context_for_record(
            data, record, args.context, args.max_chars
        )
        output.append(item)

    result = {
        "matched": len(candidates),
        "returned": len(output),
        "samples": output,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def find_translate_header(
    lines: list[str], record: dict[str, Any]
) -> tuple[int, str]:
    for index in range(record["line"] - 2, -1, -1):
        match = TRANSLATE_RE.match(lines[index])
        if match is None:
            continue
        if match.group("block") != record["block"]:
            raise IndexErrorMessage(
                f"Indexed block {record['block']!r} no longer matches "
                f"the header above line {record['line']}"
            )
        return index + 1, lines[index]
    raise IndexErrorMessage(
        f"Cannot find translate header for indexed line {record['line']}"
    )


def uncomment_source_statement(line: str, line_number: int) -> str:
    stripped = line.lstrip(" \t")
    indent = line[: len(line) - len(stripped)]
    if not stripped.startswith("#"):
        raise IndexErrorMessage(
            f"Indexed source-comment line {line_number} is no longer a comment"
        )
    statement = stripped[1:]
    if statement.startswith((" ", "\t")):
        statement = statement[1:]
    return indent + statement


def pilot_output_encoding(indexed_encoding: str, bom: str) -> str:
    normalized = indexed_encoding.lower().replace("_", "-")
    if normalized == "utf-8-sig" and bom == "none":
        return "utf-8"
    return indexed_encoding


def extract_pilot(args: argparse.Namespace) -> int:
    index_path = Path(args.index).resolve()
    data = load_index(index_path)
    relative = args.file.replace("\\", "/")
    entry = data["files"].get(relative)
    if entry is None:
        raise IndexErrorMessage(f"File is not present in the index: {relative}")

    root = Path(data["project_root"])
    source_path = (root / relative).resolve()
    output_path = Path(args.output).resolve()
    if not source_path.is_file():
        raise IndexErrorMessage(f"Indexed source does not exist: {relative}")
    if output_path.suffix.lower() != ".rpy":
        raise IndexErrorMessage("Pilot output must use the .rpy extension")
    indexed_paths = {
        (root / indexed_relative).resolve()
        for indexed_relative in data["files"]
    }
    if output_path in indexed_paths:
        raise IndexErrorMessage("Pilot output cannot overwrite an indexed source file")
    if output_path.exists() and not args.overwrite:
        raise IndexErrorMessage(
            f"Pilot output already exists; pass --overwrite to replace it: "
            f"{args.output}"
        )

    metadata, source_text = inspect_file(source_path, entry["encoding"])
    if metadata["sha256"] != entry["sha256"]:
        raise IndexErrorMessage(
            f"Indexed source has changed; run scan again before extracting: {relative}"
        )
    newline_kind = metadata["newline"]
    if newline_kind not in {"lf", "crlf", "cr"}:
        raise IndexErrorMessage(
            f"Source newline convention is {newline_kind!r}; choose a policy "
            "before creating a pilot"
        )

    source_lines = source_text.splitlines()
    records = sorted(
        (
            record
            for record in entry["records"]
            if record.get("source_comment")
            and record.get("block")
            and record["kind"] not in {"old", "new"}
            and record["line"] >= args.start_line
        ),
        key=lambda record: record["line"],
    )[: args.limit]
    if len(records) != args.limit:
        raise IndexErrorMessage(
            f"Requested {args.limit} source statements but found {len(records)}"
        )

    output_lines = [
        "# Local calibration pilot generated from indexed source comments.",
        "# Active targets initially duplicate the English source.",
        "# Existing target translations were not copied.",
    ]
    current_header_line = None
    for record in records:
        header_line, header = find_translate_header(source_lines, record)
        if header_line != current_header_line:
            output_lines.extend(("", header, ""))
            current_header_line = header_line
        source_line = source_lines[record["line"] - 1]
        active_line = uncomment_source_statement(source_line, record["line"])
        output_lines.extend((source_line, active_line, ""))

    newline = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}[newline_kind]
    encoding = pilot_output_encoding(entry["encoding"], metadata["bom"])
    write_text_atomic(
        output_path,
        newline.join(output_lines) + newline,
        encoding,
    )
    result = {
        "output": args.output,
        "source_file": relative,
        "records": len(records),
        "first_source_line": records[0]["line"],
        "last_source_line": records[-1]["line"],
        "encoding": encoding,
        "newline": newline_kind,
        "byte_order_mark": metadata["bom"],
        "contains_source_text": True,
        "existing_targets_copied": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def translation_target_records(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("block") is not None
        and not record.get("source_comment")
        and record["kind"] not in {"character_definition", "old"}
    ]


def paired_records(
    records: Iterable[dict[str, Any]], source_kind: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for record in records:
        block = record.get("block")
        if block is None:
            continue
        if source_kind == "comments":
            if record["kind"] in {"old", "new"}:
                continue
            side = "source" if record["source_comment"] else "target"
        else:
            if record["kind"] not in {"old", "new"}:
                continue
            side = "source" if record["kind"] == "old" else "target"
        groups.setdefault(block, {"source": [], "target": []})[side].append(
            record
        )
    return [
        pair
        for group in groups.values()
        for pair in zip(group["source"], group["target"])
    ]


def bounded_locations(
    records: Iterable[dict[str, Any]], top: int
) -> list[int]:
    return [record["line"] for record in records][:top]


def check_translation(args: argparse.Namespace) -> int:
    data = load_index(Path(args.index).resolve())
    relative = args.source_file.replace("\\", "/")
    source_entry = data["files"].get(relative)
    if source_entry is None:
        raise IndexErrorMessage(f"File is not present in the index: {relative}")
    if source_entry.get("record_format_version") != FILE_RECORD_VERSION:
        raise IndexErrorMessage(
            "Index lacks current source-evidence metadata; run scan again"
        )

    pilot_path = Path(args.pilot).resolve()
    if not pilot_path.is_file():
        raise IndexErrorMessage(f"Pilot file does not exist: {args.pilot}")
    pilot_metadata, pilot_text = inspect_file(
        pilot_path, source_entry["encoding"]
    )
    pilot_records = parse_text(pilot_text)
    named_pilot_records = [
        {"file": pilot_path.name, **record}
        for record in pilot_records
    ]
    pairing = {
        "commented_source_targets": summarize_pairs(
            named_pilot_records,
            source_kind="comments",
            top=args.top,
        ),
        "old_new": summarize_pairs(
            named_pilot_records,
            source_kind="old",
            top=args.top,
        ),
    }
    sources = source_evidence_records(pilot_records)
    targets = translation_target_records(pilot_records)
    pairs = paired_records(pilot_records, "comments")
    pairs.extend(paired_records(pilot_records, "old"))

    indexed_source_counts = Counter(
        source_record_fingerprint(record)
        for record in source_evidence_records(source_entry["records"])
    )
    unmatched_sources = []
    for record in sources:
        fingerprint = source_record_fingerprint(record)
        if indexed_source_counts[fingerprint]:
            indexed_source_counts[fingerprint] -= 1
        else:
            unmatched_sources.append(record)

    project_root = Path(data["project_root"])
    indexed_source_path = (project_root / relative).resolve()
    same_as_indexed_file = pilot_path == indexed_source_path
    expected_targets = args.expected_targets
    if expected_targets is None:
        if not same_as_indexed_file:
            raise IndexErrorMessage(
                "--expected-targets is required for a partial or separate file"
            )
        expected_targets = len(source_evidence_records(source_entry["records"]))

    source_evidence_matches_index = False
    indexed_file_sha256_matches = False
    if indexed_source_path.is_file():
        if same_as_indexed_file:
            current_metadata = pilot_metadata
            current_records = pilot_records
        else:
            current_metadata, current_text = inspect_file(
                indexed_source_path, source_entry["encoding"]
            )
            current_records = parse_text(current_text)
        indexed_file_sha256_matches = (
            current_metadata["sha256"] == source_entry["sha256"]
        )
        source_evidence_matches_index = (
            source_evidence_sha256(current_records)
            == source_entry["source_evidence_sha256"]
        )

    expected_format_available = all(
        key in source_entry for key in ("newline", "bom")
    )
    format_matches_source = None
    if expected_format_available:
        format_matches_source = (
            pilot_metadata["newline"] == source_entry["newline"]
            and pilot_metadata["bom"] == source_entry["bom"]
        )

    empty_targets = [
        record for record in targets if not str(record["text"]).strip()
    ]
    unchanged_targets = [
        target
        for source, target in pairs
        if source["text"] == target["text"]
    ]
    allowed_latin = {word.casefold() for word in args.allowed_latin}
    latin_residuals = []
    targets_without_han = []
    for record in targets:
        text = str(record["text"])
        searchable = TAG_RE.sub("", text)
        searchable = INTERPOLATION_RE.sub("", searchable)
        searchable = PERCENT_FORMAT_RE.sub("", searchable)
        residual_words = [
            word
            for word in LATIN_WORD_RE.findall(searchable)
            if word.casefold() not in allowed_latin
        ]
        if residual_words:
            latin_residuals.append(
                {"line": record["line"], "word_count": len(residual_words)}
            )
        if not HAN_RE.search(text):
            targets_without_han.append(record)

    outside_statements = [
        record
        for record in pilot_records
        if record["kind"] != "character_definition"
        and record.get("block") is None
    ]
    differences = Counter()
    for source, target in pairs:
        differences.update(compare_record_pair(source, target))
    review_order_fields = (
        "tag_order",
        "interpolation_order",
        "percent_format_order",
    )
    hard_structural_fields = tuple(
        field
        for field in PAIR_DIFFERENCE_FIELDS
        if field not in review_order_fields
    )

    hard_failures = []
    if len(sources) != expected_targets:
        hard_failures.append("source_evidence_count")
    if len(targets) != expected_targets:
        hard_failures.append("active_target_count")
    if any(
        summary["count_mismatch_blocks"]
        or summary["source_only_blocks"]
        or summary["target_only_blocks"]
        for summary in pairing.values()
    ):
        hard_failures.append("pairing_coverage")
    if unmatched_sources:
        hard_failures.append("source_evidence_integrity")
    if not source_evidence_matches_index:
        hard_failures.append("source_index_evidence")
    if format_matches_source is False:
        hard_failures.append("file_format")
    if empty_targets:
        hard_failures.append("empty_targets")
    if outside_statements:
        hard_failures.append("outside_translate_statements")
    hard_failures.extend(
        field for field in hard_structural_fields if differences[field]
    )

    review_flags = []
    if unchanged_targets:
        review_flags.append("unchanged_targets")
    if latin_residuals:
        review_flags.append("latin_residual_candidates")
    review_flags.extend(
        field for field in review_order_fields if differences[field]
    )
    status = "fail" if hard_failures else "review" if review_flags else "pass"
    result = {
        "status": status,
        "file": args.pilot,
        "source_file": relative,
        "expected_targets": expected_targets,
        "source_evidence": len(sources),
        "source_comments": sum(
            bool(record.get("source_comment")) for record in sources
        ),
        "old_strings": sum(record["kind"] == "old" for record in sources),
        "active_targets": len(targets),
        "pairing": pairing,
        "structural_differences": {
            field: differences[field] for field in PAIR_DIFFERENCE_FIELDS
        },
        "source_evidence_integrity": {
            "unmatched": len(unmatched_sources),
            "locations": bounded_locations(unmatched_sources, args.top),
        },
        "empty_targets": {
            "count": len(empty_targets),
            "locations": bounded_locations(empty_targets, args.top),
        },
        "unchanged_targets": {
            "count": len(unchanged_targets),
            "locations": bounded_locations(unchanged_targets, args.top),
        },
        "latin_residual_candidates": {
            "count": len(latin_residuals),
            "locations": latin_residuals[: args.top],
        },
        "targets_without_han": {
            "count": len(targets_without_han),
            "locations": bounded_locations(targets_without_han, args.top),
        },
        "outside_translate_statements": {
            "count": len(outside_statements),
            "locations": bounded_locations(outside_statements, args.top),
        },
        "file_format": {
            "encoding": source_entry["encoding"],
            "newline": pilot_metadata["newline"],
            "byte_order_mark": pilot_metadata["bom"],
            "matches_source": format_matches_source,
        },
        "source_evidence_matches_index": source_evidence_matches_index,
        "indexed_file_sha256_matches": indexed_file_sha256_matches,
        "hard_failures": list(dict.fromkeys(hard_failures)),
        "review_flags": list(dict.fromkeys(review_flags)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if hard_failures or (args.strict and review_flags):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and query a bounded-output Ren'Py text index."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser(
        "scan",
        help="Scan all .rpy files locally and update an index.",
    )
    scan.add_argument("project", help="Project directory or one .rpy file.")
    scan.add_argument("--index", required=True, help="Index JSON path.")
    scan.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Source encoding (default: utf-8-sig).",
    )
    scan.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Exclude a project-relative POSIX-style glob; repeat as needed "
            "(example: **/tl/**)."
        ),
    )
    scan.set_defaults(func=scan_project)

    summary = subparsers.add_parser(
        "summary",
        help="Print aggregate metadata without dialogue text.",
    )
    summary.add_argument("--index", required=True, help="Index JSON path.")
    summary.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum speakers, markers, and difference locations to return.",
    )
    summary.set_defaults(func=summarize_index)

    samples = subparsers.add_parser(
        "samples",
        help="Print bounded representative samples from the index.",
    )
    samples.add_argument("--index", required=True, help="Index JSON path.")
    samples.add_argument("--speaker", help="Exact speaker identifier.")
    samples.add_argument("--font", help="Exact font tag value.")
    samples.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "Include a project-relative POSIX-style file glob; repeat to "
            "match multiple groups (example: routes/anders*.rpy)."
        ),
    )
    samples.add_argument(
        "--kind",
        choices=("dialogue", "narration", "extend", "menu", "ui", "old", "new"),
    )
    samples.add_argument(
        "--outer-quotes",
        choices=("present", "absent"),
        help=(
            "Filter text by escaped visible quotes wrapping the whole value; "
            "this is a syntactic signal, not an automatic voice label."
        ),
    )
    samples.add_argument(
        "--source",
        choices=("all", "active", "comments"),
        default="all",
        help="Choose active statements, source comments, or both.",
    )
    samples.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum records to return (1-100).",
    )
    samples.add_argument(
        "--context",
        type=int,
        default=2,
        help="Neighboring source lines per sample (0-10).",
    )
    samples.add_argument(
        "--max-chars",
        type=int,
        default=500,
        help="Maximum characters per context line (40-2000).",
    )
    samples.set_defaults(func=sample_index)

    profile_draft = subparsers.add_parser(
        "profile-draft",
        help="Create an evidence-only project profile draft without dialogue.",
    )
    profile_draft.add_argument(
        "--index", required=True, help="Index JSON path."
    )
    profile_draft.add_argument(
        "--output", required=True, help="Local project profile JSON path."
    )
    profile_draft.add_argument(
        "--speaker",
        action="append",
        default=[],
        help=(
            "Include one exact source-evidence speaker; repeat as needed. "
            "Without this option, use the most frequent speakers."
        ),
    )
    profile_draft.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum automatic speakers and markers per type (1-100).",
    )
    profile_draft.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum evidence locations per speaker (1-20).",
    )
    profile_draft.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing profile draft.",
    )
    profile_draft.set_defaults(func=draft_profile)

    profile_check = subparsers.add_parser(
        "profile-check",
        help="Validate profile structure, approvals, and optional index freshness.",
    )
    profile_check.add_argument("profile", help="Project profile JSON path.")
    profile_check.add_argument(
        "--index",
        help="Optional current index for source-evidence freshness review.",
    )
    profile_check.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum hard failures and review items to return.",
    )
    profile_check.add_argument(
        "--strict",
        action="store_true",
        help="Return failure for unresolved review items.",
    )
    profile_check.set_defaults(func=check_profile)

    pilot = subparsers.add_parser(
        "pilot",
        help="Create a bounded source-only calibration .rpy file.",
    )
    pilot.add_argument("--index", required=True, help="Index JSON path.")
    pilot.add_argument(
        "--file",
        required=True,
        help="One indexed project-relative .rpy file.",
    )
    pilot.add_argument(
        "--start-line",
        type=int,
        default=1,
        help="First source-comment line eligible for extraction.",
    )
    pilot.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Exact number of source statements to copy (1-100).",
    )
    pilot.add_argument("--output", required=True, help="Local pilot .rpy path.")
    pilot.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing non-source output file.",
    )
    pilot.set_defaults(func=extract_pilot)

    check = subparsers.add_parser(
        "check",
        help="Validate a translated pilot or indexed batch without text output.",
    )
    check.add_argument("pilot", help="Translated pilot or batch .rpy file.")
    check.add_argument("--index", required=True, help="Source index JSON path.")
    check.add_argument(
        "--source-file",
        required=True,
        help="Indexed project-relative source .rpy file.",
    )
    check.add_argument(
        "--expected-targets",
        type=int,
        help=(
            "Expected source/target count; required for partial or separate "
            "files and inferred for the indexed source file."
        ),
    )
    check.add_argument(
        "--allowed-latin",
        action="append",
        default=[],
        metavar="WORD",
        help="Ignore one exact Latin word in residual review; repeat as needed.",
    )
    check.add_argument(
        "--top",
        type=int,
        default=20,
        help="Maximum locations to return per issue type.",
    )
    check.add_argument(
        "--strict",
        action="store_true",
        help="Return failure for review candidates as well as hard failures.",
    )
    check.set_defaults(func=check_translation)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if hasattr(args, "top") and args.top < 1:
        raise IndexErrorMessage("--top must be at least 1")
    if hasattr(args, "limit") and not 1 <= args.limit <= 100:
        raise IndexErrorMessage("--limit must be between 1 and 100")
    if hasattr(args, "context") and not 0 <= args.context <= 10:
        raise IndexErrorMessage("--context must be between 0 and 10")
    if hasattr(args, "start_line") and args.start_line < 1:
        raise IndexErrorMessage("--start-line must be at least 1")
    if (
        hasattr(args, "expected_targets")
        and args.expected_targets is not None
        and args.expected_targets < 1
    ):
        raise IndexErrorMessage("--expected-targets must be at least 1")
    if hasattr(args, "max_chars") and not 40 <= args.max_chars <= 2000:
        raise IndexErrorMessage("--max-chars must be between 40 and 2000")
    if args.command == "profile-draft" and args.top > 100:
        raise IndexErrorMessage("--top must be between 1 and 100")
    if args.command == "profile-draft" and args.limit > 20:
        raise IndexErrorMessage("--limit must be between 1 and 20")


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def main() -> int:
    configure_utf8_output()
    parser = build_parser()
    args = parser.parse_args()
    try:
        validate_args(args)
        return args.func(args)
    except IndexErrorMessage as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
