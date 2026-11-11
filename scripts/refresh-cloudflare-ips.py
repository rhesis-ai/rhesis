#!/usr/bin/env python3
"""Sync the Cloudflare edge IP ranges committed under kubernetes/ with Cloudflare's list.

Every block between `# cloudflare-ips:begin <format>` and `# cloudflare-ips:end` is
regenerated from https://api.cloudflare.com/client/v4/ips. Formats:

  csv      one `key: "cidr,cidr,..."` line with IPv4 and IPv6 (ingress-nginx config)
  list-v4  a YAML list of IPv4 CIDRs (Service loadBalancerSourceRanges; the VPC is IPv4-only)

Usage:
  scripts/refresh-cloudflare-ips.py          rewrite the blocks in place
  scripts/refresh-cloudflare-ips.py --check  exit 1 and print a diff if any block is stale
"""

import argparse
import difflib
import ipaddress
import json
import re
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.cloudflare.com/client/v4/ips"
REPO_ROOT = Path(__file__).resolve().parent.parent
SEARCH_ROOT = REPO_ROOT / "kubernetes"
BEGIN = re.compile(r"^(?P<indent>\s*)# cloudflare-ips:begin (?P<fmt>[a-z0-9-]+)\s*$")
END = re.compile(r"^\s*# cloudflare-ips:end\s*$")
CSV_LINE = re.compile(r'^(?P<prefix>\s*[A-Za-z0-9_.-]+:\s*)"[^"]*"\s*$')


def fetch_ranges() -> tuple[list[str], list[str]]:
    with urllib.request.urlopen(API_URL, timeout=30) as resp:
        body = json.load(resp)
    if not body.get("success"):
        raise SystemExit(f"Cloudflare API error: {body.get('errors')}")
    result = body["result"]
    v4 = sorted(result["ipv4_cidrs"], key=ipaddress.ip_network)
    v6 = sorted(result["ipv6_cidrs"], key=ipaddress.ip_network)
    # A short list means a broken response, and writing it would lock visitors out.
    if len(v4) < 10 or len(v6) < 5:
        raise SystemExit(f"Refusing suspiciously short list: {len(v4)} v4, {len(v6)} v6")
    return v4, v6


def render_block(fmt: str, indent: str, old: list[str], v4: list[str], v6: list[str]) -> list[str]:
    if fmt == "list-v4":
        return [f"{indent}- {cidr}\n" for cidr in v4]
    if fmt == "csv":
        if len(old) != 1 or not CSV_LINE.match(old[0]):
            raise SystemExit(f'csv block must hold exactly one `key: "..."` line, got {old!r}')
        prefix = CSV_LINE.match(old[0]).group("prefix")
        return [f'{prefix}"{",".join(v4 + v6)}"\n']
    raise SystemExit(f"Unknown cloudflare-ips block format: {fmt}")


def rewrite(lines: list[str], v4: list[str], v6: list[str], path: Path) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        begin = BEGIN.match(line)
        i += 1
        if not begin:
            continue
        start = i
        while i < len(lines) and not END.match(lines[i]):
            i += 1
        if i == len(lines):
            raise SystemExit(f"{path}: cloudflare-ips:begin without a matching end")
        out.extend(render_block(begin["fmt"], begin["indent"], lines[start:i], v4, v6))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = parser.parse_args()

    v4, v6 = fetch_ranges()
    stale = False
    for path in sorted(SEARCH_ROOT.rglob("*.yaml")):
        text = path.read_text()
        if "# cloudflare-ips:begin" not in text:
            continue
        old = text.splitlines(keepends=True)
        new = rewrite(old, v4, v6, path)
        if new == old:
            continue
        stale = True
        rel = path.relative_to(REPO_ROOT)
        if args.check:
            sys.stdout.writelines(difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}"))
        else:
            path.write_text("".join(new))
            print(f"updated {rel}")

    if args.check and stale:
        print("Cloudflare IP ranges are out of date; run scripts/refresh-cloudflare-ips.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
