"""CI script: validate yaml_import profiles against installed HA core.

Imports real HA packages -- validates against the actual code that will run.
No AST parsing. If the import fails or the schema changes, that's exactly
what would happen at runtime.

Usage:
    python -m custom_components.yaml_import.check_versions

Exit codes:
    0 = all profiles match
    1 = errors (breaking issues found)
    2 = warnings only (may still work)
"""

from __future__ import annotations

import importlib
import sys


def check_all() -> int:
    """Check all profiles against installed HA packages.

    Returns 0=ok, 1=errors, 2=warnings only.
    """
    # Import here so the module can be loaded without HA installed
    # (for IDE autocompletion etc.)
    from homeassistant.config_entries import HANDLERS

    from .const import PROFILES

    errors = 0
    warnings = 0

    for domain, profile in PROFILES.items():
        print(f"Checking {domain}...")

        # --- Import config_flow (triggers HANDLERS registration) ---
        try:
            importlib.import_module(
                f"homeassistant.components.{domain}.config_flow"
            )
        except ImportError as exc:
            print(f"  ERROR: cannot import config_flow: {exc}")
            errors += 1
            continue

        handler = HANDLERS.get(domain)
        if handler is None:
            print(f"  ERROR: no ConfigFlow handler registered after import")
            errors += 1
            continue

        # --- Version check ---
        if profile["version"] != handler.VERSION:
            print(
                f"  ERROR: VERSION mismatch "
                f"(profile={profile['version']}, core={handler.VERSION})"
            )
            errors += 1
        elif profile["minor_version"] != handler.MINOR_VERSION:
            print(
                f"  WARN: MINOR_VERSION mismatch "
                f"(profile={profile['minor_version']}, "
                f"core={handler.MINOR_VERSION})"
            )
            warnings += 1
        else:
            print(
                f"  OK version={handler.VERSION}, "
                f"minor={handler.MINOR_VERSION}"
            )

        # --- Schema key check ---
        schema_extractor = profile.get("schema_extractor")
        if schema_extractor is not None:
            module = sys.modules.get(
                f"homeassistant.components.{domain}.config_flow"
            )
            if module is None:
                print(f"  WARN: config_flow module not in sys.modules")
                warnings += 1
            else:
                try:
                    actual_keys = schema_extractor(module)
                    known_keys = set(profile.get("known_data_keys", []))

                    added = actual_keys - known_keys
                    removed = known_keys - actual_keys
                    if added:
                        print(f"  WARN: core added new data keys: {added}")
                        warnings += 1
                    if removed:
                        print(
                            f"  WARN: core removed data keys: {removed}"
                        )
                        warnings += 1
                    if not added and not removed:
                        print(
                            f"  OK schema keys match "
                            f"({len(actual_keys)} keys)"
                        )
                except Exception as exc:
                    print(f"  WARN: schema extraction failed: {exc}")
                    warnings += 1

        # --- async_setup_entry check ---
        try:
            init_mod = importlib.import_module(
                f"homeassistant.components.{domain}"
            )
            if not hasattr(init_mod, "async_setup_entry"):
                print(f"  ERROR: no async_setup_entry in __init__.py")
                errors += 1
            else:
                print(f"  OK async_setup_entry exists")
        except ImportError as exc:
            print(f"  ERROR: cannot import __init__: {exc}")
            errors += 1

    # --- Summary ---
    print()
    total = len(PROFILES)
    print(f"Checked {total} profile(s): {errors} error(s), {warnings} warning(s)")

    if errors:
        return 1
    if warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(check_all())
