"""Switch platform for Claber valve control."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ClaberCoordinatorEntity, ClaberRuntimeData
from .protocol import CMD_STOP_ALL, authenticate_and_send, turn_on_line


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Claber switch entities for one config entry."""
    runtime: ClaberRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ClaberValveSwitch(runtime, 1), ClaberValveSwitch(runtime, 2)])


class ClaberValveSwitch(ClaberCoordinatorEntity, SwitchEntity):
    """Valve control switch for one line."""

    def __init__(self, runtime: ClaberRuntimeData, line: int) -> None:
        """Initialize entity."""
        super().__init__(runtime, f"valve_{line}")
        self._line = line
        self._attr_translation_key = f"valve_{line}"

    @property
    def available(self) -> bool:
        """Keep switches available even before first advertisement arrives."""
        return True

    @property
    def is_on(self) -> bool:
        """Return current valve state from latest broadcast."""
        if self.coordinator.data is None:
            return False
        if self._line == 1:
            return self.coordinator.data.line1_active
        return self.coordinator.data.line2_active

    @property
    def icon(self) -> str:
        """Dynamic icon reflecting open/closed state."""
        return "mdi:valve-open" if self.is_on else "mdi:valve-closed"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on this valve line for the configured duration."""
        minutes = self.runtime.durations[self._line]
        await self._async_send_command(turn_on_line(self._line, minutes))
        self._async_apply_optimistic_on_state(minutes)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off this valve line (protocol stop-all command)."""
        await self._async_send_command(CMD_STOP_ALL)
        self._async_apply_optimistic_off_state()

    async def _async_send_command(self, command: bytes) -> None:
        """Send one command in an atomic auth + command session."""
        async with self.runtime.command_lock:
            result = await authenticate_and_send(
                self.hass,
                self.runtime.address,
                self.runtime.pin,
                command,
            )

        if not result.ok:
            raise HomeAssistantError(
                "Command rejected by valve "
                f"(auth_status={result.auth_status}, cmd_status={result.command_status})"
            )

    def _async_apply_optimistic_on_state(self, minutes: int) -> None:
        """Optimistically mirror expected XOR state until next broadcast arrives."""
        if self.coordinator.data is None:
            return

        if self._line == 1:
            new_data = replace(
                self.coordinator.data,
                line1_active=True,
                line1_remaining=minutes,
                line2_active=False,
                line2_remaining=0,
                is_watering=True,
            )
        else:
            new_data = replace(
                self.coordinator.data,
                line1_active=False,
                line1_remaining=0,
                line2_active=True,
                line2_remaining=minutes,
                is_watering=True,
            )

        self.coordinator.async_set_updated_data(new_data)

    def _async_apply_optimistic_off_state(self) -> None:
        """Optimistically mirror stop-all state until next broadcast arrives."""
        if self.coordinator.data is None:
            return

        self.coordinator.async_set_updated_data(
            replace(
                self.coordinator.data,
                line1_active=False,
                line1_remaining=0,
                line2_active=False,
                line2_remaining=0,
                is_watering=False,
            )
        )
