#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


OPTION_RE = re.compile(r"(?:^|\s)-{1,2}[A-Za-z]")


def iter_fragments(text):
    if isinstance(text, str):
        yield text
        return

    if not isinstance(text, list):
        return

    for item in text:
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            value = item.get("text")
            if isinstance(value, str):
                yield value


def join_fragments(text):
    return "".join(iter_fragments(text))


def normalize_strategy(text):
    line = text.strip()
    if not line.startswith("-"):
        return None
    if len(OPTION_RE.findall(line)) < 2:
        return None
    return line


def update_quote_state(text, quote):
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
    return quote


def collect_strategy(lines, start):
    quote = None
    collected = []

    for index in range(start, len(lines)):
        raw_line = lines[index].rstrip()
        stripped = raw_line.strip()

        if index == start:
            if not normalize_strategy(stripped):
                return None
            collected.append(stripped)
            quote = update_quote_state(raw_line, quote)
            continue

        if not stripped:
            break
        if quote is None and not stripped.startswith("-"):
            break

        collected.append(raw_line)
        quote = update_quote_state(raw_line, quote)

    return "\n".join(collected).strip()


def extract_from_fragment(fragment):
    fragment = fragment.strip()
    if not fragment:
        return None

    for chunk in re.split(r"\n\s*\n", fragment):
        lines = chunk.splitlines()
        for index, line in enumerate(lines):
            candidate = collect_strategy(lines, index)
            if candidate:
                return candidate
    return None


def extract_strategy(message):
    full_text = join_fragments(message.get("text"))
    candidate = extract_from_fragment(full_text)
    if candidate:
        return candidate

    for fragment in iter_fragments(message.get("text")):
        candidate = extract_from_fragment(fragment)
        if candidate:
            return candidate
    return None


def load_export(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_results(path):
    data = load_export(path)

    for message in data.get("messages", []):
        strategy = extract_strategy(message)
        if not strategy:
            continue

        yield {
            "source": str(path),
            "id": message.get("id"),
            "date": message.get("date"),
            "from": message.get("from") or "",
            "strategy": strategy,
        }


def resolve_paths(items):
    for item in items:
        path = Path(item)
        if path.is_dir():
            path = path / "result.json"
        yield path


def print_plain(results, unique):
    seen = set()
    for result in results:
        strategy = result["strategy"]
        if unique and strategy in seen:
            continue
        seen.add(strategy)
        print(strategy)


def print_tsv(results, unique):
    seen = set()
    print("source\tid\tdate\tfrom\tstrategy")
    for result in results:
        strategy = result["strategy"]
        if unique and strategy in seen:
            continue
        seen.add(strategy)
        row = [
            result["source"],
            str(result["id"]),
            result["date"] or "",
            result["from"].replace("\t", " "),
            strategy.replace("\t", " "),
        ]
        print("\t".join(row))


def print_jsonl(results, unique):
    seen = set()
    for result in results:
        strategy = result["strategy"]
        if unique and strategy in seen:
            continue
        seen.add(strategy)
        print(json.dumps(result, ensure_ascii=False))


def main(argv):
    parser = argparse.ArgumentParser(
        description="Extract ByeDPI strategies from Telegram ChatExport result.json files.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Path to result.json or to a ChatExport directory.",
    )
    parser.add_argument(
        "--format",
        choices=("plain", "tsv", "jsonl"),
        default="plain",
        help="Output format.",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Print only unique strategies.",
    )
    args = parser.parse_args(argv)

    results = []
    for path in resolve_paths(args.paths):
        if not path.exists():
            print(f"error: file not found: {path}", file=sys.stderr)
            return 1
        results.extend(iter_results(path))

    if args.format == "plain":
        print_plain(results, args.unique)
    elif args.format == "tsv":
        print_tsv(results, args.unique)
    else:
        print_jsonl(results, args.unique)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
