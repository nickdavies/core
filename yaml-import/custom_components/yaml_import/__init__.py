"""YAML Import - restore YAML configuration for config-entry-only integrations.

Creates config entries directly from YAML configuration, bypassing the
interactive config flow UI. Uses ConfigEntries.async_add() to inject entries
for integrations that have removed their YAML support.
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import HANDLERS, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN, PROFILES

_LOGGER = logging.getLogger(__name__)

ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("integration"): vol.In(PROFILES),
        vol.Optional("title"): str,
        vol.Optional("unique_id"): str,
        vol.Optional("data", default=dict): dict,
        vol.Optional("options", default=dict): dict,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [ENTRY_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def _async_validate_version(
    hass: HomeAssistant, domain: str, profile: dict[str, Any]
) -> bool:
    """Validate config entry version against the target integration's ConfigFlow.

    Returns True if versions are compatible, False if major version mismatch.
    """
    try:
        integration = await async_get_integration(hass, domain)
        await integration.async_get_platform("config_flow")
    except Exception:
        _LOGGER.error(
            "yaml_import: cannot load config flow for '%s' -- skipping", domain
        )
        return False

    handler = HANDLERS.get(domain)
    if handler is None:
        _LOGGER.error(
            "yaml_import: '%s' has no ConfigFlow handler registered -- skipping",
            domain,
        )
        return False

    if profile["version"] != handler.VERSION:
        _LOGGER.error(
            "yaml_import: '%s' VERSION mismatch (profile=%d, core=%d) -- "
            "entry will fail to load, skipping. Update the profile in const.py",
            domain,
            profile["version"],
            handler.VERSION,
        )
        return False

    if profile["minor_version"] != handler.MINOR_VERSION:
        _LOGGER.warning(
            "yaml_import: '%s' MINOR_VERSION mismatch (profile=%d, core=%d) -- "
            "proceeding, but consider updating the profile",
            domain,
            profile["minor_version"],
            handler.MINOR_VERSION,
        )

    return True


async def _async_validate_schema(
    hass: HomeAssistant,
    domain: str,
    profile: dict[str, Any],
    entry_data: dict[str, Any],
    entry_options: dict[str, Any],
) -> bool:
    """Validate data/options dicts against the profile schema and live integration.

    Returns True if validation passes, False on errors.
    """
    # Validate against our voluptuous schemas
    try:
        if profile["data_schema"] is not None:
            entry_data = profile["data_schema"](entry_data)
    except vol.Invalid as exc:
        _LOGGER.error(
            "yaml_import: '%s' data validation failed: %s", domain, exc
        )
        return False

    try:
        if profile.get("options_schema") is not None and entry_options:
            entry_options = profile["options_schema"](entry_options)
    except vol.Invalid as exc:
        _LOGGER.error(
            "yaml_import: '%s' options validation failed: %s", domain, exc
        )
        return False

    # Cross-check keys against the live integration's schema
    if "schema_extractor" in profile:
        try:
            integration = await async_get_integration(hass, domain)
            config_flow_module = await integration.async_get_platform("config_flow")
            expected_keys = profile["schema_extractor"](config_flow_module)
            provided_keys = set(entry_data.keys())

            unknown = provided_keys - expected_keys
            if unknown:
                _LOGGER.warning(
                    "yaml_import: '%s' has data keys not recognized by the "
                    "integration's config flow: %s -- they may be ignored",
                    domain,
                    unknown,
                )
        except Exception:
            _LOGGER.debug(
                "yaml_import: '%s' schema extraction failed, skipping live check",
                domain,
            )

    return True


def _entry_already_exists(
    hass: HomeAssistant, domain: str, unique_id: str | None
) -> bool:
    """Check if a matching config entry already exists."""
    existing = hass.config_entries.async_entries(domain)
    if unique_id:
        return any(e.unique_id == unique_id for e in existing)
    return len(existing) > 0


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up yaml_import from configuration.yaml."""
    if DOMAIN not in config:
        return True

    for entry_config in config[DOMAIN]:
        domain = entry_config["integration"]
        profile = PROFILES[domain]
        unique_id = entry_config.get("unique_id")
        entry_data = entry_config.get("data", {})
        entry_options = entry_config.get("options", {})
        title = entry_config.get("title", domain)

        # 1. Deduplication
        if _entry_already_exists(hass, domain, unique_id):
            _LOGGER.debug(
                "yaml_import: config entry for '%s' already exists, skipping",
                domain,
            )
            continue

        # 2. Version compatibility
        if not await _async_validate_version(hass, domain, profile):
            continue

        # 3. Schema validation (our schema + live integration check)
        if not await _async_validate_schema(
            hass, domain, profile, entry_data, entry_options
        ):
            continue

        # 4. Create and inject the config entry
        entry = ConfigEntry(
            domain=domain,
            title=title,
            data=entry_data,
            options=entry_options,
            source="yaml_import",
            version=profile["version"],
            minor_version=profile["minor_version"],
            unique_id=unique_id,
            discovery_keys=MappingProxyType({}),
            subentries_data=None,
        )

        _LOGGER.info(
            "yaml_import: creating config entry for '%s' (title=%s, unique_id=%s)",
            domain,
            title,
            unique_id,
        )
        await hass.config_entries.async_add(entry)

    return True
