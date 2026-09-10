#!/usr/bin/env python3
"""Install a Chrome managed-policy pointer to Flow Kit's stable update feed."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

EXTENSION_ID_RE = re.compile(r"^[a-p]{32}$")


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        # Managed Chrome policy is consumed by the unprivileged browser user.
        # mkstemp defaults to 0600, which would make a root-installed policy
        # unreadable and silently disable the force-install/update policy.
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-json", type=Path, required=True)
    parser.add_argument("--policy-file", type=Path, required=True)
    parser.add_argument("--update-url", required=True)
    parser.add_argument("--daemon-reload", action="store_true")
    args = parser.parse_args()

    release = json.loads(args.release_json.read_text(encoding="utf-8"))
    extension_id = str(release.get("extension_id") or "")
    version = str(release.get("version") or "")
    if not EXTENSION_ID_RE.fullmatch(extension_id):
        raise SystemExit(f"invalid extension id in release metadata: {extension_id!r}")
    if not version:
        raise SystemExit("release metadata has no version")

    policy = {
        "ExtensionInstallForcelist": [
            f"{extension_id};{args.update_url}"
        ]
    }
    atomic_write(args.policy_file.resolve(), json.dumps(policy, indent=2) + "\n")
    if args.daemon_reload:
        # Managed deployments can opt in when unit files were changed alongside
        # the policy. Keep the standalone helper side-effect free by default.
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    print(json.dumps({
        "extension_id": extension_id,
        "version": version,
        "policy_file": str(args.policy_file.resolve()),
        "update_url": args.update_url,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
