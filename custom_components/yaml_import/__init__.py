"""YAML Import: restore YAML configuration for config-entry-only integrations.

Creates config entries directly from YAML configuration, bypassing config flows.
This allows integrations that have dropped YAML support (e.g., NUT, MQTT broker)
to be configured via configuration.yaml again.
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import HANDLERS, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, loader
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PROFILES

_LOGGER = logging.getLogger(__name__)

ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("integration"): str,
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
    """Validate config entry version against the target integration.

    Returns True if version is compatible, False if major version mismatch.
    """
    try:
        integration = await loader.async_get_integration(hass, domain)
        await integration.async_get_platform("config_flow")
    except Exception:
        _LOGGER.warning(
            "yaml_import: could not load config_flow for %s, "
            "skipping version check",
            domain,
        )
        return True

    handler = HANDLERS.get(domain)
    if handler is None:
        _LOGGER.warning(
            "yaml_import: %s has no registered ConfigFlow handler, "
            "skipping version check",
            domain,
        )
        return True

    if profile["version"] != handler.VERSION:
        _LOGGER.error(
            "yaml_import: %s config entry VERSION mismatch! "
            "Profile=%d, Core=%d. Skipping entry creation. "
            "Update the profile in yaml_import/const.py",
            domain,
            profile["version"],
            handler.VERSION,
        )
        return False

    if profile["minor_version"] != handler.MINOR_VERSION:
        _LOGGER.warning(
            "yaml_import: %s MINOR_VERSION mismatch. "
            "Profile=%d, Core=%d. Proceeding anyway",
            domain,
            profile["minor_version"],
            handler.MINOR_VERSION,
        )

    return True


async def _async_validate_schema_keys(
    hass: HomeAssistant, domain: str, profile: dict[str, Any], data: dict[str, Any]
) -> None:
    """Validate provided data keys against the integration's real schema."""
    schema_extractor = profile.get("schema_extractor")
    if schema_extractor is None:
        return

    try:
        integration = await loader.async_get_integration(hass, domain)
        config_flow_module = await integration.async_get_platform("config_flow")
        expected_keys = schema_extractor(config_flow_module)
    except Exception:
        _LOGGER.warning(
            "yaml_import: could not extract schema keys for %s, "
            "skipping key validation",
            domain,
        )
        return

    provided_keys = set(data.keys())
    unknown = provided_keys - expected_keys
    if unknown:
        _LOGGER.warning(
            "yaml_import: %s has unknown data keys: %s. "
            "These may be ignored by the integration",
            domain,
            unknown,
        )

    required = profile.get("required_keys", set())
    missing = required - provided_keys
    if missing:
        _LOGGER.error(
            "yaml_import: %s is missing required data keys: %s",
            domain,
            missing,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up yaml_import from configuration.yaml."""
    if DOMAIN not in config:
        return True

    for entry_config in config[DOMAIN]:
        domain = entry_config["integration"]
        title = entry_config.get("title", domain)
        unique_id = entry_config.get("unique_id")
        data = entry_config.get("data", {})
        options = entry_config.get("options", {})

        # Check profile exists
        profile = PROFILES.get(domain)
        if profile is None:
            _LOGGER.error(
                "yaml_import: no profile defined for integration '%s'. "
                "Add one to custom_components/yaml_import/const.py",
                domain,
            )
            continue

        # Validate data against profile schema
        data_schema = profile.get("data_schema")
        if data_schema is not None:
            try:
                data = data_schema(data)
            except vol.Invalid as exc:
                _LOGGER.error(
                    "yaml_import: %s data validation failed: %s",
                    domain,
                    exc,
                )
                continue

        # Validate options against profile schema
        options_schema = profile.get("options_schema")
        if options_schema is not None and options:
            try:
                options = options_schema(options)
            except vol.Invalid as exc:
                _LOGGER.error(
                    "yaml_import: %s options validation failed: %s",
                    domain,
                    exc,
                )
                continue

        # Check config entry version compatibility
        if not await _async_validate_version(hass, domain, profile):
            continue

        # Validate data keys against real integration schema
        await _async_validate_schema_keys(hass, domain, profile, data)

        # Deduplication: skip if entry already exists
        existing = hass.config_entries.async_entries(domain)
        if unique_id:
            if any(e.unique_id == unique_id for e in existing):
                _LOGGER.debug(
                    "yaml_import: %s entry with unique_id=%s already exists, skipping",
                    domain,
                    unique_id,
                )
                continue
        elif existing:
            _LOGGER.debug(
                "yaml_import: %s already has a config entry, skipping",
                domain,
            )
            continue

        # Create the config entry directly
        entry = ConfigEntry(
            domain=domain,
            title=title,
            data=data,
            options=options,
            source="yaml_import",
            version=profile["version"],
            minor_version=profile["minor_version"],
            unique_id=unique_id,
            discovery_keys=MappingProxyType({}),
            subentries_data=None,
        )

        _LOGGER.info(
            "yaml_import: creating config entry for %s (title=%s)",
            domain,
            title,
        )
        await hass.config_entries.async_add(entry)

    return True
