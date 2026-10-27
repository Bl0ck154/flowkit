#!/usr/bin/env python3
"""Package Flow Kit's Chrome extension and optionally publish an update feed.

The script is intentionally deterministic about version and extension identity:
- source manifest version is the single source of truth;
- the manifest public key must derive to the expected extension id;
- the packed CRX manifest must match the source version;
- published CRXs are versioned, while updates.xml is a stable pointer.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def extension_id_from_manifest_key(key_b64: str) -> str:
    der = base64.b64decode(key_b64)
    digest = hashlib.sha256(der).digest()[:16]
    return "".join(chr(ord("a") + nibble) for byte in digest for nibble in (byte >> 4, byte & 0x0F))


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def read_manifest_from_crx(path: Path) -> dict:
    # CRX files have a binary prefix before the ZIP payload. Python's zipfile
    # handles prepended bytes by locating the central directory from the end.
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json").decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension-dir", type=Path, default=Path("extension"))
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--expected-id")
    parser.add_argument("--feed-dir", type=Path)
    parser.add_argument("--feed-base-url", default="http://127.0.0.1:8110")
    args = parser.parse_args()

    extension_dir = args.extension_dir.resolve()
    manifest_path = extension_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest["version"])
    key_b64 = manifest.get("key")
    if not key_b64:
        raise SystemExit("manifest.json must contain the extension public key")

    extension_id = extension_id_from_manifest_key(key_b64)
    if args.expected_id and extension_id != args.expected_id:
        raise SystemExit(f"extension id mismatch: manifest={extension_id} expected={args.expected_id}")

    packed_path = extension_dir.with_suffix(".crx")
    packed_path.unlink(missing_ok=True)
    subprocess.run(
        [
            str(args.chrome),
            f"--pack-extension={extension_dir}",
            f"--pack-extension-key={args.key.resolve()}",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not packed_path.exists():
        raise SystemExit(f"Chrome did not produce {packed_path}")

    packed_manifest = read_manifest_from_crx(packed_path)
    packed_version = str(packed_manifest.get("version"))
    if packed_version != version:
        raise SystemExit(f"packed CRX version mismatch: source={version} packed={packed_version}")

    sha256 = hashlib.sha256(packed_path.read_bytes()).hexdigest()
    result = {
        "version": version,
        "extension_id": extension_id,
        "crx": str(packed_path),
        "sha256": sha256,
    }

    if args.feed_dir:
        feed_dir = args.feed_dir.resolve()
        feed_dir.mkdir(parents=True, exist_ok=True)
        crx_name = f"flowkit-{version}.crx"
        published_crx = feed_dir / crx_name
        temp_crx = feed_dir / f".{crx_name}.tmp"
        shutil.copy2(packed_path, temp_crx)
        os.replace(temp_crx, published_crx)

        base_url = args.feed_base_url.rstrip("/")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">\n'
            f'  <app appid="{escape(extension_id)}">\n'
            f'    <updatecheck codebase="{escape(base_url)}/{escape(crx_name)}" version="{escape(version)}" />\n'
            '  </app>\n'
            '</gupdate>\n'
        )
        atomic_write(feed_dir / "updates.xml", xml)
        atomic_write(feed_dir / f"updates-{version}.xml", xml)
        atomic_write(
            feed_dir / "release.json",
            json.dumps({**result, "crx": crx_name}, indent=2) + "\n",
        )
        result["published_crx"] = str(published_crx)
        result["updates_xml"] = str(feed_dir / "updates.xml")


    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
