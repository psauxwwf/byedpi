#!/usr/bin/env python3

import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STRATEGY_FILE = ROOT / "STRATEGY.txt"
OUTPUT_FILE = ROOT / ".env.example"
CONTAINER_NAME = "byedpi"
PROXY_URL = "socks5h://127.0.0.1:3080"
TEST_URLS = [
    "https://www.youtube.com/generate_204",
    "https://youtu.be/dQw4w9WgXcQ?list=RDdQw4w9WgXcQ",
    # "https://t.me/telegram/449",
]
REMOTE_STRATEGY_URL = "https://raw.githubusercontent.com/romanvht/ByeByeDPI/refs/heads/master/app/src/main/assets/proxytest_strategies.list"
DEFAULT_SNI = '"fe2.update.microsoft.com"'


def run(command, *, env=None, capture_output=False, timeout=None):
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=capture_output,
        timeout=timeout,
        check=False,
    )


def normalize_strategy(parts):
    return re.sub(r"\s+", " ", " ".join(part.strip() for part in parts)).strip()


def parse_strategies(text):
    strategies = []
    current = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("-") and current:
            strategies.append(normalize_strategy(current))
            current = [line]
            continue

        if line.startswith("-"):
            current = [line]
            continue

        if current:
            current.append(line)

    if current:
        strategies.append(normalize_strategy(current))

    seen = set()
    unique = []
    for strategy in strategies:
        if strategy in seen:
            continue
        seen.add(strategy)
        unique.append(strategy)
    return unique


def load_local_strategies():
    text = STRATEGY_FILE.read_text(encoding="utf-8")
    return parse_strategies(text)


def load_remote_strategies():
    with urllib.request.urlopen(REMOTE_STRATEGY_URL, timeout=10) as response:
        text = response.read().decode("utf-8")
    text = text.replace("{sni}", DEFAULT_SNI)
    return parse_strategies(text)


def load_strategies():
    strategies = []
    strategies.extend(load_local_strategies())

    try:
        strategies.extend(load_remote_strategies())
    except OSError as exc:
        print(f"warning: failed to load remote strategies: {exc}", file=sys.stderr)

    seen = set()
    unique = []
    for strategy in strategies:
        if strategy in seen:
            continue
        seen.add(strategy)
        unique.append(strategy)
    return unique


def wait_until_running():
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        result = run(
            ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER_NAME],
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "true":
            return True
        time.sleep(0.1)
    return False


def stop_container():
    run(["docker", "compose", "down", "--remove-orphans"])


def build_image():
    result = run(["docker", "compose", "build"])
    return result.returncode == 0


def check_strategy(strategy):
    env = os.environ.copy()
    env["BYEDPI_IP"] = "127.0.0.1"
    env["BYEDPI_PORT"] = "3080"
    env["BYEDPI_OPTIONS"] = strategy

    up = run(
        ["docker", "compose", "up", "-d", "--force-recreate", "--no-build"], env=env
    )
    if up.returncode != 0:
        return False

    if not wait_until_running():
        return False

    for test_url in TEST_URLS:
        curl = run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--output",
                "/dev/null",
                "--max-time",
                "2",
                "--connect-timeout",
                "2",
                "-x",
                PROXY_URL,
                test_url,
            ],
            timeout=4,
        )
        if curl.returncode != 0:
            return False
    return True


def write_successes(strategies):
    lines = [f"# BYEDPI_OPTIONS={strategy}" for strategy in strategies]
    OUTPUT_FILE.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main():
    strategies = load_strategies()
    if not strategies:
        print("No strategies found in available sources", file=sys.stderr)
        return 1

    stop_container()

    if not build_image():
        print("docker compose build failed", file=sys.stderr)
        return 1

    successes = []
    try:
        for index, strategy in enumerate(strategies, start=1):
            print(f"[{index}/{len(strategies)}] checking strategy")
            ok = False
            try:
                ok = check_strategy(strategy)
            except subprocess.TimeoutExpired:
                ok = False
            finally:
                stop_container()

            if ok:
                print("  success")
                successes.append(strategy)
            else:
                print("  skipped")
    finally:
        stop_container()

    write_successes(successes)
    print(f"Saved {len(successes)} successful strategies to {OUTPUT_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
