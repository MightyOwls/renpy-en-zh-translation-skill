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
STRING = r'(?P<quote>["\'])(?P<text>(?:\\.|(?!(?P=quote)).)*)(?P=quote)'
TRANSLATE_RE = re.compile(
    r"^(?P<indent>\s*)translate\s+\w+\s+(?P<block>[A-Za-z0-9_]+)\s*:"
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
QUOTED_RE = re.compile(r'(["\'])(.*?)(?<!\\)\1')

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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def parse_file(path: Path, encoding: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding=encoding).splitlines()
    except UnicodeError as exc:
        raise IndexErrorMessage(
            f"Cannot decode {path} with encoding {encoding}: {exc}"
        ) from exc

    records: list[dict[str, Any]] = []
    current_block: str | None = None
    block_indent = -1

    for line_number, raw_line in enumerate(lines, start=1):
        translate_match = TRANSLATE_RE.match(raw_line)
        if translate_match:
            current_block = translate_match.group("block")
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
            records.append(record)

    return records


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
        digest = file_sha256(path)
        old_entry = old_files.get(relative)
        if (
            old_entry
            and old_entry.get("sha256") == digest
            and old_entry.get("encoding") == args.encoding
        ):
            indexed_files[relative] = old_entry
            reused_files += 1
            continue

        indexed_files[relative] = {
            "sha256": digest,
            "encoding": args.encoding,
            "records": parse_file(path, args.encoding),
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
    return {
        name: differences[name]
        for name in (
            "statement_role",
            "speaker",
            "attributes",
            "tag_tokens",
            "tag_order",
            "interpolation_tokens",
            "interpolation_order",
        )
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
            if fields and len(examples) < top:
                examples.append(
                    {
                        "file": source["file"],
                        "block": source["block"],
                        "source_line": source["line"],
                        "target_line": target["line"],
                        "fields": fields,
                    }
                )

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
            for name in (
                "statement_role",
                "speaker",
                "attributes",
                "tag_tokens",
                "tag_order",
                "interpolation_tokens",
                "interpolation_order",
            )
        },
        "difference_locations": examples,
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
        profile_source = (
            "source_comments_and_old"
            if old_records
            else "source_comments"
        )
    elif old_records:
        source_evidence = [
            record for record in active_records if record["kind"] != "new"
        ]
        target_records = new_records
        profile_source = "active_statements_and_old"
    else:
        source_evidence = active_records
        target_records = []
        profile_source = "active_statements"
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
    return {
        "files": len(data["files"]),
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
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if hasattr(args, "top") and args.top < 1:
        raise IndexErrorMessage("--top must be at least 1")
    if hasattr(args, "limit") and not 1 <= args.limit <= 100:
        raise IndexErrorMessage("--limit must be between 1 and 100")
    if hasattr(args, "context") and not 0 <= args.context <= 10:
        raise IndexErrorMessage("--context must be between 0 and 10")
    if hasattr(args, "max_chars") and not 40 <= args.max_chars <= 2000:
        raise IndexErrorMessage("--max-chars must be between 40 and 2000")


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
