"""CI script: validate yaml_import profiles against the installed HA core.

Imports real HA packages -- validates against the actual code that will run.
No AST parsing; if the import fails or the schema changes, that's exactly
what would happen at runtime.

Usage:
    python -m custom_components.yaml_import.check_versions

Exit codes:
    0 - all profiles match
    1 - errors (major version mismatch, missing async_setup_entry, import failure)
    2 - warnings only (minor version mismatch, schema key drift)
"""

from __future__ import annotations

import importlib
import sys

from .const import PROFILES


def _check_version(
    domain: str, profile: dict, handler: type
) -> tuple[int, int]:
    """Check VERSION and MINOR_VERSION. Returns (errors, warnings)."""
    errors = 0
    warnings = 0

    if profile["version"] != handler.VERSION:
        print(
            f"  ERROR: VERSION mismatch "
            f"(profile={profile['version']}, core={handler.VERSION})"
        )
        errors += 1
    elif profile["minor_version"] != handler.MINOR_VERSION:
        print(
            f"  WARN: MINOR_VERSION mismatch "
            f"(profile={profile['minor_version']}, core={handler.MINOR_VERSION})"
        )
        warnings += 1
    else:
        print(f"  OK version={handler.VERSION}, minor={handler.MINOR_VERSION}")

    return errors, warnings


def _check_schema_keys(
    domain: str, profile: dict, config_flow_module: object
) -> tuple[int, int]:
    """Check schema keys haven't drifted. Returns (errors, warnings)."""
    warnings = 0

    if "schema_extractor" not in profile:
        print("  SKIP schema check (no schema_extractor defined)")
        return 0, 0

    try:
        actual_keys = profile["schema_extractor"](config_flow_module)
        known_keys = set(profile.get("known_data_keys", []))

        added = actual_keys - known_keys
        removed = known_keys - actual_keys

        if added:
            print(f"  WARN: core added new data keys: {added}")
            warnings += 1
        if removed:
            print(f"  WARN: core removed data keys: {removed}")
            warnings += 1
        if not added and not removed:
            print(f"  OK schema keys match ({len(actual_keys)} keys)")
    except Exception as exc:
        print(f"  WARN: schema extraction failed: {exc}")
        warnings += 1

    return 0, warnings


def _check_async_setup_entry(domain: str) -> int:
    """Check that the target integration still has async_setup_entry."""
    try:
        init_mod = importlib.import_module(f"homeassistant.components.{domain}")
        if not hasattr(init_mod, "async_setup_entry"):
            print(f"  ERROR: no async_setup_entry in {domain}/__init__.py")
            return 1
        print("  OK async_setup_entry exists")
    except ImportError as exc:
        print(f"  ERROR: cannot import {domain}.__init__: {exc}")
        return 1
    return 0


def check_all() -> int:
    """Check all profiles against installed HA packages.

    Returns:
        0 if all checks pass
        1 if any errors found
        2 if only warnings found
    """
    # Import HANDLERS lazily -- it's populated when config_flow modules are imported
    from homeassistant.config_entries import HANDLERS

    total_errors = 0
    total_warnings = 0

    for domain, profile in PROFILES.items():
        print(f"\nChecking {domain}...")

        # Import config_flow module (triggers __init_subclass__ -> HANDLERS registration)
        try:
            importlib.import_module(
                f"homeassistant.components.{domain}.config_flow"
            )
        except ImportError as exc:
            print(f"  ERROR: cannot import config_flow: {exc}")
            total_errors += 1
            continue

        handler = HANDLERS.get(domain)
        if handler is None:
            print("  ERROR: no ConfigFlow handler registered after import")
            total_errors += 1
            continue

        # Version check
        errs, warns = _check_version(domain, profile, handler)
        total_errors += errs
        total_warnings += warns

        # Schema key check
        config_flow_module = sys.modules[
            f"homeassistant.components.{domain}.config_flow"
        ]
        errs, warns = _check_schema_keys(domain, profile, config_flow_module)
        total_errors += errs
        total_warnings += warns

        # async_setup_entry check
        total_errors += _check_async_setup_entry(domain)

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Profiles checked: {len(PROFILES)}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")

    if total_errors:
        return 1
    if total_warnings:
        return 2
    return 0


def main() -> None:
    """Entry point."""
    sys.exit(check_all())


if __name__ == "__main__":
    main()
