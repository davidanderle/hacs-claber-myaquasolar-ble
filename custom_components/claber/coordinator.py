"""Data coordinator for Claber BLE advertisements."""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .protocol import ClaberBroadcastData, parse_broadcast

_LOGGER = logging.getLogger(__name__)


class ClaberDataUpdateCoordinator(DataUpdateCoordinator[ClaberBroadcastData | None]):
    """Track the latest advertisement payload from a specific Claber device."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize coordinator."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_{address}", update_interval=None)
        self.address = address.upper()
        self._unsub_bluetooth: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start listening to passive Bluetooth advertisements."""
        if self._unsub_bluetooth is not None:
            return

        self._unsub_bluetooth = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            {"address": self.address},
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

        if service_info := bluetooth.async_last_service_info(
            self.hass,
            self.address,
            connectable=False,
        ):
            self._async_handle_bluetooth_event(
                service_info,
                bluetooth.BluetoothChange.ADVERTISEMENT,
            )

    async def async_stop(self) -> None:
        """Stop Bluetooth callback registration."""
        if self._unsub_bluetooth is None:
            return

        self._unsub_bluetooth()
        self._unsub_bluetooth = None

    async def _async_update_data(self) -> ClaberBroadcastData | None:
        """No polling is needed because this integration is push-only."""
        return self.data

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle each incoming advertisement event."""
        decoded = parse_broadcast(service_info.manufacturer_data, service_info.rssi)
        if decoded is None:
            return

        self.async_set_updated_data(decoded)
