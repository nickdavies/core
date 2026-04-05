"""Constants and integration profiles for yaml_import."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

DOMAIN = "yaml_import"

# --- Schema extractor helpers ---


def _vol_schema_keys(schema: vol.Schema) -> set[str]:
    """Extract field name strings from a voluptuous Schema."""
    keys: set[str] = set()
    for key in schema.schema:
        if isinstance(key, (vol.Optional, vol.Required)):
            keys.add(str(key.schema))
        elif isinstance(key, str):
            keys.add(key)
    return keys


# --- NUT profile ---

NUT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("port", default=3493): int,
        vol.Optional("username"): str,
        vol.Optional("password"): str,
        vol.Optional("alias"): str,
    }
)


def nut_schema_extractor(config_flow_module: Any) -> set[str]:
    """Extract expected data keys from NUT's real config flow."""
    schema = config_flow_module._base_schema({})
    keys = _vol_schema_keys(schema)
    # alias comes from a separate _ups_schema() step
    keys.add("alias")
    return keys


# --- MQTT profile ---

MQTT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("broker"): str,
        vol.Required("port", default=1883): int,
        vol.Optional("username"): str,
        vol.Optional("password"): str,
        vol.Optional("client_id"): str,
        vol.Optional("keepalive"): int,
        vol.Optional("protocol"): str,
        vol.Optional("transport"): str,
        vol.Optional("ws_path"): str,
        vol.Optional("ws_headers"): dict,
        vol.Optional("tls_insecure"): bool,
        vol.Optional("certificate"): str,
        vol.Optional("client_cert"): str,
        vol.Optional("client_key"): str,
    }
)

MQTT_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("discovery", default=True): bool,
        vol.Optional("discovery_prefix", default="homeassistant"): str,
        vol.Optional("birth_message"): dict,
        vol.Optional("will_message"): dict,
    }
)


def mqtt_schema_extractor(config_flow_module: Any) -> set[str]:
    """Extract expected broker data keys from MQTT's real config flow.

    MQTT builds its schema dynamically via async_get_broker_settings().
    We extract the known broker field set from the module's constants.
    """
    # The broker fields are the ones passed through validated_user_input
    # in async_get_broker_settings. We can verify by checking imports.
    from homeassistant.components.mqtt.const import (
        CONF_BROKER,
        CONF_CERTIFICATE,
        CONF_CLIENT_CERT,
        CONF_CLIENT_KEY,
        CONF_KEEPALIVE,
        CONF_TLS_INSECURE,
        CONF_TRANSPORT,
        CONF_WS_HEADERS,
        CONF_WS_PATH,
    )
    from homeassistant.const import (
        CONF_CLIENT_ID,
        CONF_PASSWORD,
        CONF_PORT,
        CONF_PROTOCOL,
        CONF_USERNAME,
    )

    return {
        CONF_BROKER,
        CONF_PORT,
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_CLIENT_ID,
        CONF_KEEPALIVE,
        CONF_PROTOCOL,
        CONF_TRANSPORT,
        CONF_WS_PATH,
        CONF_WS_HEADERS,
        CONF_TLS_INSECURE,
        CONF_CERTIFICATE,
        CONF_CLIENT_CERT,
        CONF_CLIENT_KEY,
    }


# --- Profile registry ---

PROFILES: dict[str, dict[str, Any]] = {
    "nut": {
        "version": 1,
        "minor_version": 1,
        "data_schema": NUT_DATA_SCHEMA,
        "options_schema": None,
        "required_keys": {"host", "port"},
        "known_data_keys": {"host", "port", "username", "password", "alias"},
        "schema_extractor": nut_schema_extractor,
    },
    "mqtt": {
        "version": 2,
        "minor_version": 1,
        "data_schema": MQTT_DATA_SCHEMA,
        "options_schema": MQTT_OPTIONS_SCHEMA,
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
        "schema_extractor": mqtt_schema_extractor,
    },
}
