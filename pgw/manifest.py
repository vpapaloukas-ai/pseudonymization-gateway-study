"""Freeze check and run manifest. The scored run refuses code whose hashes differ from the pre-registered
ones; a change after the freeze is an amendment, not an edit (spec §6, §8)."""
import hashlib
import json
import platform
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("presidio-analyzer", "presidio-anonymizer", "spacy", "en-core-web-lg", "anthropic",
            "tldextract", "phonenumbers", "regex")

HEX64 = re.compile(r"[0-9a-f]{64}")
RESERVED = ("written_at", "versions", "script_hashes")


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def script_hashes(root: Path = ROOT) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_lf(p) for p in sorted((root / "pgw").glob("*.py"))}


def freeze_record(root: Path = ROOT) -> dict:
    """What the pre-registration pins: every script's hash and every recorded package version."""
    return {"scripts": script_hashes(root), "versions": versions()}


def check_frozen(frozen_file: Path, root: Path = ROOT) -> list[str]:
    frozen = json.loads(Path(frozen_file).read_text(encoding="utf-8"))
    scripts = frozen.get("scripts") if isinstance(frozen, dict) else None
    pinned = frozen.get("versions") if isinstance(frozen, dict) else None
    if (not isinstance(scripts, dict) or not scripts or not isinstance(pinned, dict) or not pinned
            or not all(isinstance(v, str) and HEX64.fullmatch(v) for v in scripts.values())
            or not all(isinstance(v, str) for v in pinned.values())):
        raise ValueError(f"{frozen_file}: not a freeze record (needs non-empty 'scripts' of sha256 hex and 'versions')")
    current = script_hashes(root)
    bad = sorted(k for k in scripts.keys() | current.keys()
                 if k not in scripts or k not in current or scripts[k] != current[k])
    installed = versions()
    bad += sorted(f"version:{k}" for k, v in pinned.items() if installed.get(k) != v)
    return bad


def versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not installed"
    return out


def write_manifest(path: Path, **fields) -> dict:
    clash = sorted(set(fields) & set(RESERVED))
    if clash:
        raise ValueError(f"manifest fields would overwrite recorded provenance: {clash}")
    data = {**fields, "written_at": datetime.now(timezone.utc).isoformat(), "versions": versions(),
            "script_hashes": script_hashes()}
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return data
