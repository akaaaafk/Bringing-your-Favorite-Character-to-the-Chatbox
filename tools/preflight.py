"""Validate local artifacts and configuration before running or deploying."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PERSONAS_PATH = ROOT / "config" / "personas.json"
MANIFEST_PATH = ROOT / "models" / "manifest.json"
REQUIRED_PERSONA_FIELDS = {
    "character_id",
    "character_name",
    "movie_title",
    "line_count",
    "persona_tag",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=("local", "docker", "modal", "vercel"),
        default="local",
    )
    parser.add_argument(
        "--api-base",
        help="Modal HTTPS base URL compiled into the Vercel frontend",
    )
    return parser.parse_args()


def check_file(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"{label} missing: {path.relative_to(ROOT)}")


def check_personas(errors: list[str]) -> None:
    check_file(PERSONAS_PATH, "Persona manifest", errors)
    if errors:
        return
    try:
        personas = json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Persona manifest is unreadable: {exc}")
        return
    if not isinstance(personas, list) or not personas:
        errors.append("Persona manifest must be a non-empty JSON array")
        return
    tags: list[str] = []
    for index, persona in enumerate(personas):
        if not isinstance(persona, dict):
            errors.append(f"Persona #{index + 1} must be an object")
            continue
        missing = REQUIRED_PERSONA_FIELDS - persona.keys()
        if missing:
            errors.append(
                f"Persona #{index + 1} missing fields: {sorted(missing)}"
            )
        tag = persona.get("persona_tag")
        if isinstance(tag, str):
            tags.append(tag)
    if len(tags) != len(set(tags)):
        errors.append("persona_tag values must be unique")


def check_model_artifacts(errors: list[str]) -> None:
    check_file(MANIFEST_PATH, "Model artifact manifest", errors)
    if not MANIFEST_PATH.is_file():
        return
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        artifacts = manifest["artifacts"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"Model artifact manifest is invalid: {exc}")
        return
    for artifact in artifacts:
        relative = artifact.get("path", "")
        if not isinstance(relative, str) or not relative:
            errors.append("Model artifact manifest contains an invalid path")
            continue
        check_file(ROOT / relative, "Model artifact", errors)


def check_api_base(api_base: str | None, errors: list[str]) -> None:
    value = (api_base or "").strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(
            "Vercel requires --api-base with the deployed Modal HTTPS URL"
        )
    elif value.endswith("/"):
        errors.append("--api-base must not have a trailing slash")


def main() -> int:
    args = parse_args()
    errors: list[str] = []

    check_personas(errors)
    check_file(ROOT / "README.md", "Project README", errors)
    check_file(ROOT / "pyproject.toml", "Python project metadata", errors)

    if args.target in {"local", "docker", "modal"}:
        check_model_artifacts(errors)
        runtime = ROOT / "src" / "movie_persona"
        for name in ("api.py", "pipeline.py", "speech.py", "paths.py"):
            check_file(runtime / name, "Runtime module", errors)

    if args.target == "docker":
        check_file(
            ROOT / "deploy" / "docker" / "Dockerfile",
            "Dockerfile",
            errors,
        )
        check_file(ROOT / "web" / "package-lock.json", "Frontend lockfile", errors)

    if args.target == "modal":
        check_file(ROOT / "deploy" / "modal.py", "Modal entrypoint", errors)

    if args.target == "vercel":
        check_file(ROOT / "web" / "vercel.json", "Vercel config", errors)
        check_file(ROOT / "web" / "package-lock.json", "Frontend lockfile", errors)
        check_api_base(args.api_base, errors)

    if errors:
        print(f"Preflight failed for {args.target}:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Preflight passed for {args.target}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
