"""Config flow for Claber myAquaSolar."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ADDRESS, CONF_PIN, DOMAIN
from .protocol import CMD_STATUS, authenticate_and_send, validate_pin

_LOGGER = logging.getLogger(__name__)


def _normalize_address(address: str) -> str:
    """Normalize a BLE MAC address for storage and matching."""
    return address.strip().upper()


def _normalize_pin(pin: str) -> str:
    """Normalize a user-provided PIN."""
    return pin.strip().upper()


def _entry_title(address: str) -> str:
    """Build a stable config entry title."""
    suffix = address.replace(":", "")[-6:]
    return f"Claber Sun-{suffix}"


class ClaberConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Claber devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow handler."""
        self._address: str | None = None

    async def async_step_bluetooth(
        self,
        discovery_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> FlowResult:
        """Handle Bluetooth discovery."""
        address = _normalize_address(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._address = address
        self.context["title_placeholders"] = {"address": address}
        return await self.async_step_pin()

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = _normalize_address(user_input[CONF_ADDRESS])
            pin = _normalize_pin(user_input[CONF_PIN])

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_credentials(address, pin)
            if not errors:
                return self.async_create_entry(
                    title=_entry_title(address),
                    data={CONF_ADDRESS: address, CONF_PIN: pin},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS, default=self._address or ""): str,
                vol.Required(CONF_PIN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_pin(self, user_input: dict | None = None) -> FlowResult:
        """Handle PIN entry after Bluetooth discovery."""
        if self._address is None:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        if user_input is not None:
            pin = _normalize_pin(user_input[CONF_PIN])
            errors = await self._async_validate_credentials(self._address, pin)
            if not errors:
                return self.async_create_entry(
                    title=_entry_title(self._address),
                    data={CONF_ADDRESS: self._address, CONF_PIN: pin},
                )

        data_schema = vol.Schema({vol.Required(CONF_PIN): str})
        return self.async_show_form(step_id="pin", data_schema=data_schema, errors=errors)

    async def _async_validate_credentials(self, address: str, pin: str) -> dict[str, str]:
        """Validate PIN format and perform a live auth test against the device."""
        if not validate_pin(pin):
            return {"base": "invalid_pin"}

        try:
            result = await authenticate_and_send(
                self.hass,
                address,
                pin,
                CMD_STATUS,
            )
        except Exception:
            _LOGGER.exception("Failed to connect/authenticate during config flow")
            return {"base": "cannot_connect"}

        if not result.ok:
            return {"base": "auth_failed"}

        return {}
