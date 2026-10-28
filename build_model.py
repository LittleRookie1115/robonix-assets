#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Build one robot model through its repository-local release definition."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import re

from asset_builder import write_deployment_manifest


REPOSITORY_ROOT = Path(__file__).resolve().parent
MODEL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def available_models() -> tuple[str, ...]:
    """Discover importable model definitions without a hard-coded registry."""
    models_dir = REPOSITORY_ROOT / "models"
    return tuple(
        sorted(
            path.name
            for path in models_dir.iterdir()
            if path.is_dir()
            and MODEL_NAME.fullmatch(path.name)
            and (path / "build.py").is_file()
        )
    )


def parse_args() -> argparse.Namespace:
    """Parse a model name and reproducibility-oriented source options."""
    models = available_models()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=models)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Build only from source files already verified in .cache/sources.",
    )
    parser.add_argument(
        "--source-base-url",
        help="Use an exact-content source mirror without changing the source lock.",
    )
    parser.add_argument(
        "--artifact-url",
        help="Also generate a fetcher manifest pinned to this immutable HTTPS URL.",
    )
    return parser.parse_args()


def main() -> int:
    """Load the selected model definition and execute its build function."""
    args = parse_args()
    module = importlib.import_module(f"models.{args.model}.build")
    build_manifest = module.build(
        offline=args.offline, source_base_url=args.source_base_url
    )
    if args.artifact_url:
        output = REPOSITORY_ROOT / "dist" / f"{args.model}.model-assets.json"
        write_deployment_manifest(build_manifest, args.artifact_url, output)
        print(f"[build] wrote deployment manifest {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
