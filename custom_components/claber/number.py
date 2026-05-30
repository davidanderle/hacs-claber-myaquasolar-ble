"""Number entities for Claber valve durations."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_DURATION_MINUTES, DOMAIN, MAX_IRRIGATION_MINUTES
from .entity import ClaberControlEntity, ClaberRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Claber number entities for one config entry."""
    runtime: ClaberRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ClaberValveDurationNumber(runtime, 1),
            ClaberValveDurationNumber(runtime, 2),
        ]
    )


class ClaberValveDurationNumber(ClaberControlEntity, NumberEntity, RestoreEntity):
    """Duration control for one valve line."""

    _attr_native_min_value = 1
    _attr_native_max_value = MAX_IRRIGATION_MINUTES
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"

    def __init__(self, runtime: ClaberRuntimeData, line: int) -> None:
        """Initialize entity."""
        super().__init__(runtime, f"valve_{line}_duration")
        self._line = line
        self._attr_translation_key = f"valve_{line}_duration"
        self.runtime.durations.setdefault(self._line, DEFAULT_DURATION_MINUTES)

    @property
    def available(self) -> bool:
        """This helper entity is always locally available."""
        return True

    @property
    def native_value(self) -> float:
        """Return stored duration for this line."""
        return float(self.runtime.durations[self._line])

    async def async_set_native_value(self, value: float) -> None:
        """Persist the selected duration in runtime state."""
        int_value = int(round(value))
        if int_value < 1:
            int_value = 1
        if int_value > MAX_IRRIGATION_MINUTES:
            int_value = MAX_IRRIGATION_MINUTES

        self.runtime.durations[self._line] = int_value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore previous state when available."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                return
            try:
                restored_value = int(float(last_state.state))
            except ValueError:
                return

            if 1 <= restored_value <= MAX_IRRIGATION_MINUTES:
                self.runtime.durations[self._line] = restored_value
                self.async_write_ha_state()
