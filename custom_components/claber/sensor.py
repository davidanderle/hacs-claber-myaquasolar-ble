"""Sensor platform for Claber myAquaSolar."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RSSI_LEVEL_OPTIONS, SOLAR_LEVEL_OPTIONS
from .entity import ClaberCoordinatorEntity, ClaberRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Claber sensor entities for one config entry."""
    runtime: ClaberRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ClaberBatterySensor(runtime),
            ClaberSolarIrradianceSensor(runtime),
            ClaberSolarIrradianceLevelSensor(runtime),
            ClaberRssiQualitySensor(runtime),
        ]
    )


class ClaberBatterySensor(ClaberCoordinatorEntity, SensorEntity):
    """Battery sensor mapped from 5-bit energy level."""

    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "battery")

    @property
    def native_value(self) -> int | None:
        """Return the battery percentage."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.battery_percent

    @property
    def extra_state_attributes(self) -> dict[str, str | int] | None:
        """Expose decoded battery details."""
        if self.coordinator.data is None:
            return None
        return {
            "raw_level": self.coordinator.data.energy_level,
            "label": self.coordinator.data.battery_label,
        }


class ClaberSolarIrradianceSensor(ClaberCoordinatorEntity, SensorEntity):
    """Raw solar irradiance from advertisement company id high byte."""

    _attr_translation_key = "solar_irradiance"
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "solar_irradiance")

    @property
    def native_value(self) -> int | None:
        """Return raw irradiance level (0-255)."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.solar_irradiance

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose decoded irradiance level label."""
        if self.coordinator.data is None:
            return None
        return {"level": self.coordinator.data.solar_label}


class ClaberSolarIrradianceLevelSensor(ClaberCoordinatorEntity, SensorEntity):
    """Solar irradiance level as enum label."""

    _attr_translation_key = "solar_irradiance_level"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SOLAR_LEVEL_OPTIONS
    _attr_icon = "mdi:white-balance-sunny"

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "solar_irradiance_level")

    @property
    def native_value(self) -> str | None:
        """Return irradiance quality label."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.solar_label


class ClaberRssiQualitySensor(ClaberCoordinatorEntity, SensorEntity):
    """Signal quality sensor derived from RSSI."""

    _attr_translation_key = "rssi"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = RSSI_LEVEL_OPTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: ClaberRuntimeData) -> None:
        """Initialize entity."""
        super().__init__(runtime, "rssi")

    @property
    def native_value(self) -> str | None:
        """Return RSSI quality label."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.rssi_label

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Expose raw RSSI value."""
        if self.coordinator.data is None or self.coordinator.data.rssi is None:
            return None
        return {"rssi_dbm": self.coordinator.data.rssi}
