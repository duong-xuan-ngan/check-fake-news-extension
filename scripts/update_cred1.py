"""Download and validate the pinned CRED-1 compact domain dataset.

CRED-1 is a negative-signal dataset. A domain missing from the output is
unknown, not trustworthy. The application therefore uses this data only to
exclude domains with an explicit low credibility score.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


VERSION = "v2026-07-28"
SOURCE_URL = (
    "https://raw.githubusercontent.com/aloth/cred-1/"
    f"{VERSION}/data/cred1_compact.json"
)
SOURCE_SHA256 = "f47c9f471ad37397a55506a14e8361e09b6ee1f4d52c3df03743e232625fe7b2"
CATEGORY_CODES = {
    "c": "c",
    "conspiracy": "c",
    "f": "f",
    "fake": "f",
    "m": "m",
    "mixed": "m",
    "r": "r",
    "reliable": "r",
    "s": "s",
    "satire": "s",
    "u": "u",
    "unreliable": "u",
}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "cred1_compact.json"


def normalize_domain(value: str) -> str:
    """Normalize a CRED-1 key into a hostname without changing its suffix."""
    candidate = str(value or "").strip().lower()
    if not candidate:
        return ""

    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    hostname = (parsed.hostname or "").removeprefix("www.").rstrip(".")
    if not hostname:
        return ""

    try:
        ipaddress.ip_address(hostname)
        return hostname
    except ValueError:
        return hostname.encode("idna").decode("ascii")


def read_source(source_file: Path | None) -> bytes:
    if source_file:
        return source_file.read_bytes()
    with urlopen(SOURCE_URL, timeout=30) as response:
        return response.read()


def validate_and_normalize(raw: bytes) -> dict[str, dict[str, object]]:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(
            f"Unexpected CRED-1 checksum: {digest}; expected {SOURCE_SHA256}"
        )

    source = json.loads(raw)
    if not isinstance(source, dict):
        raise ValueError("CRED-1 compact data must be a JSON object")

    output: dict[str, dict[str, object]] = {}
    for raw_domain, raw_metadata in source.items():
        domain = normalize_domain(raw_domain)
        if not domain or not isinstance(raw_metadata, dict):
            continue

        category = CATEGORY_CODES.get(str(raw_metadata.get("c", "")).lower())
        score = raw_metadata.get("s")
        source_count = raw_metadata.get("n")
        if category is None:
            raise ValueError(
                f"Invalid category for {raw_domain}: {raw_metadata.get('c')!r}"
            )
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
            raise ValueError(f"Invalid score for {raw_domain}: {score!r}")
        if not isinstance(source_count, int) or source_count < 1:
            raise ValueError(f"Invalid source count for {raw_domain}: {source_count!r}")

        metadata = dict(raw_metadata)
        metadata["c"] = category
        metadata["s"] = round(float(score), 3)
        current = output.get(domain)
        # Prefer the more cautious score when upstream aliases normalize to
        # the same hostname (for example, a key containing a trailing slash).
        if current is None or float(metadata["s"]) < float(current["s"]):
            output[domain] = metadata

    if len(output) < 2_600:
        raise ValueError(f"CRED-1 validation produced only {len(output)} domains")
    return dict(sorted(output.items()))


def write_output(dataset: dict[str, dict[str, object]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dataset, ensure_ascii=True, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=OUTPUT_PATH.parent, delete=False
    ) as temp_file:
        temp_file.write(payload)
        temp_path = Path(temp_file.name)
    os.replace(temp_path, OUTPUT_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-file",
        type=Path,
        help="Use an already downloaded source file instead of the network.",
    )
    args = parser.parse_args()

    dataset = validate_and_normalize(read_source(args.source_file))
    write_output(dataset)
    print(f"Wrote {len(dataset)} CRED-1 domains to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
