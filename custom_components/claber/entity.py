"""Entity helpers for the Claber integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import ClaberDataUpdateCoordinator


@dataclass(slots=True)
class ClaberRuntimeData:
    """Runtime data shared between entities."""

    coordinator: ClaberDataUpdateCoordinator
    address: str
    pin: str
    durations: dict[int, int]
    command_lock: asyncio.Lock


def make_device_info(address: str) -> DeviceInfo:
    """Build the shared device metadata for this integration."""
    normalized = address.upper()
    suffix = normalized.replace(":", "")[-6:]
    return DeviceInfo(
        identifiers={(DOMAIN, normalized)},
        connections={(dr.CONNECTION_BLUETOOTH, normalized)},
        manufacturer="Claber",
        model="myAquaSolar",
        name=f"Claber Sun-{suffix}",
    )


class ClaberCoordinatorEntity(CoordinatorEntity[ClaberDataUpdateCoordinator]):
    """Base class for coordinator-backed Claber entities."""

    _attr_has_entity_name = True

    def __init__(self, runtime: ClaberRuntimeData, unique_key: str) -> None:
        """Initialize the coordinator entity."""
        super().__init__(runtime.coordinator)
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.address.lower()}_{unique_key}"
        self._attr_device_info = make_device_info(runtime.address)


class ClaberControlEntity(Entity):
    """Base class for Claber entities not driven by coordinator updates."""

    _attr_has_entity_name = True

    def __init__(self, runtime: ClaberRuntimeData, unique_key: str) -> None:
        """Initialize the control entity."""
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.address.lower()}_{unique_key}"
        self._attr_device_info = make_device_info(runtime.address)
