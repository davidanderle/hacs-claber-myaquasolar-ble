"""Binary sensor platform for Claber myAquaSolar."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ClaberCoordinatorEntity, ClaberRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Claber binary sensors for one config entry."""
    runtime: ClaberRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ClaberRainSensor(runtime), ClaberIsWateringSensor(runtime)])


class ClaberRainSensor(ClaberCoordinatorEntity, BinarySensorEntity):
    """Rain sensor from advertisement flag byte."""

    _attr_translation_key = "rain"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_entity_registry_enabled_default = False

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "rain")

    @property
    def is_on(self) -> bool | None:
        """Return True when rain is detected."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.rain_detected


class ClaberIsWateringSensor(ClaberCoordinatorEntity, BinarySensorEntity):
    """Indicates if either valve is currently watering."""

    _attr_translation_key = "is_watering"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "is_watering")

    @property
    def is_on(self) -> bool | None:
        """Return true if any line is active."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.is_watering
