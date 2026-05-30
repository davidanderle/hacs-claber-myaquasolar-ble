"""The Claber myAquaSolar integration."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_PIN, DEFAULT_DURATION_MINUTES, DOMAIN, PLATFORMS
from .coordinator import ClaberDataUpdateCoordinator
from .entity import ClaberRuntimeData


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration from YAML (not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Claber from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address = str(entry.data[CONF_ADDRESS]).upper()
    pin = str(entry.data[CONF_PIN]).upper()

    coordinator = ClaberDataUpdateCoordinator(hass, address)
    await coordinator.async_start()

    runtime = ClaberRuntimeData(
        coordinator=coordinator,
        address=address,
        pin=pin,
        durations={1: DEFAULT_DURATION_MINUTES, 2: DEFAULT_DURATION_MINUTES},
        command_lock=asyncio.Lock(),
    )
    hass.data[DOMAIN][entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not unload_ok:
        return False

    runtime: ClaberRuntimeData | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    if runtime is not None:
        await runtime.coordinator.async_stop()

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
