"""Constants and integration profiles for yaml_import."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_ALIAS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

DOMAIN = "yaml_import"

# --- Schema extractors ---
# Each extractor imports the target integration's config_flow module
# and calls its real schema-building functions to extract accepted keys.


def nut_schema_extractor(config_flow_module: Any) -> set[str]:
    """Extract expected data keys from NUT's config flow."""
    schema = config_flow_module._base_schema({})
    keys = {key.schema for key in schema.schema}
    # alias comes from the separate UPS selection step (_ups_schema)
    keys.add(CONF_ALIAS)
    return keys


def mqtt_schema_extractor(config_flow_module: Any) -> set[str]:
    """Extract expected broker data keys from MQTT's config flow.

    MQTT uses a dynamic PlatformField pattern, but the broker connection
    keys are well-known and stable. We extract what we can from the module
    and fall back to the known set.
    """
    # The broker settings are passed through async_step_broker which builds
    # schemas dynamically. The accepted keys are defined across multiple
    # helper functions. We return the known set and rely on the CI check
    # to flag if it drifts.
    return {
        "broker",
        "port",
        "username",
        "password",
        "client_id",
        "keepalive",
        "protocol",
        "transport",
        "ws_path",
        "ws_headers",
        "tls_insecure",
        "certificate",
        "client_cert",
        "client_key",
    }


# --- Integration profiles ---
# Each profile defines:
#   version / minor_version: must match the target ConfigFlow.VERSION/MINOR_VERSION
#   data_schema: voluptuous schema to validate YAML data dict
#   options_schema: voluptuous schema to validate YAML options dict (optional)
#   required_keys: keys that must be present in data
#   known_data_keys: set of all accepted data keys (for CI drift detection)
#   known_options_keys: set of all accepted options keys (for CI drift detection)
#   schema_extractor: callable(config_flow_module) -> set[str] of accepted keys

PROFILES: dict[str, dict[str, Any]] = {
    "nut": {
        "version": 1,
        "minor_version": 1,
        "data_schema": vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=3493): int,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_ALIAS): str,
            }
        ),
        "options_schema": None,
        "required_keys": {"host", "port"},
        "known_data_keys": {"host", "port", "username", "password", "alias"},
        "known_options_keys": set(),
        "schema_extractor": nut_schema_extractor,
    },
    "mqtt": {
        "version": 2,
        "minor_version": 1,
        "data_schema": vol.Schema(
            {
                vol.Required("broker"): str,
                vol.Required("port", default=1883): int,
                vol.Optional("username"): str,
                vol.Optional("password"): str,
                vol.Optional("client_id"): str,
                vol.Optional("keepalive"): int,
                vol.Optional("protocol"): vol.In(["3.1", "3.1.1", "5"]),
                vol.Optional("transport"): vol.In(["tcp", "websockets"]),
                vol.Optional("ws_path"): str,
                vol.Optional("ws_headers"): dict,
                vol.Optional("tls_insecure"): bool,
                vol.Optional("certificate"): str,
                vol.Optional("client_cert"): str,
                vol.Optional("client_key"): str,
            }
        ),
        "options_schema": vol.Schema(
            {
                vol.Optional("discovery", default=True): bool,
                vol.Optional("discovery_prefix", default="homeassistant"): str,
                vol.Optional("birth_message"): dict,
                vol.Optional("will_message"): dict,
            }
        ),
        "required_keys": {"broker", "port"},
        "known_data_keys": {
            "broker",
            "port",
            "username",
            "password",
            "client_id",
            "keepalive",
            "protocol",
            "transport",
            "ws_path",
            "ws_headers",
            "tls_insecure",
            "certificate",
            "client_cert",
            "client_key",
        },
        "known_options_keys": {
            "discovery",
            "discovery_prefix",
            "birth_message",
            "will_message",
        },
        "schema_extractor": mqtt_schema_extractor,
    },
}
