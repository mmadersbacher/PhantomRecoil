import argparse
import hashlib
import json
import os
from datetime import datetime, timezone


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def normalize_tag(version_text):
    version = str(version_text or "").strip()
    if not version:
        raise ValueError("Version must not be empty.")
    if version.startswith("v"):
        return version
    return f"v{version}"


def build_asset(path, download_base):
    name = os.path.basename(path)
    return {
        "name": name,
        "url": f"{download_base}/{name}",
        "sha256": sha256_file(path),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate latest.json manifest for Phantom Recoil releases.")
    parser.add_argument("--version", required=True, help="Release version, e.g. v1.0.22 or 1.0.22")
    parser.add_argument("--repo", default="mmadersbacher/PhantomRecoil", help="GitHub repo in owner/name form")
    parser.add_argument("--portable", required=True, help="Path to portable executable")
    parser.add_argument("--installer", default="", help="Optional path to installer executable")
    parser.add_argument("--checksums", default="", help="Optional path to SHA256SUMS.txt")
    parser.add_argument("--output", default="latest.json", help="Output path for manifest")
    args = parser.parse_args()

    tag = normalize_tag(args.version)
    repo = str(args.repo).strip()
    release_url = f"https://github.com/{repo}/releases/tag/{tag}"
    download_base = f"https://github.com/{repo}/releases/download/{tag}"

    if not os.path.exists(args.portable):
        raise FileNotFoundError(f"Portable executable not found: {args.portable}")

    manifest = {
        "version": tag,
        "release_url": release_url,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "assets": {
            "portable": build_asset(args.portable, download_base),
            "installer": None,
            "checksums": None,
        },
    }

    if args.installer and os.path.exists(args.installer):
        manifest["assets"]["installer"] = build_asset(args.installer, download_base)

    if args.checksums and os.path.exists(args.checksums):
        checksum_name = os.path.basename(args.checksums)
        manifest["assets"]["checksums"] = {
            "name": checksum_name,
            "url": f"{download_base}/{checksum_name}",
            "sha256": sha256_file(args.checksums),
        }

    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=True, indent=2)
        handle.write("\n")

    print(f"Wrote manifest: {args.output}")
    print(f"Version: {tag}")
    print(f"Repo: {repo}")


if __name__ == "__main__":
    main()
