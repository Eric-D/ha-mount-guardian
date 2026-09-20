"""Capteurs. Enveloppe mince autour de `entities.py`.

Ce module n'est **pas importable** sous les mocks de `tests/conftest.py` :
`class _GuardSensor(CoordinatorEntity, SensorEntity)` lève
`TypeError: metaclass conflict` quand les deux bases sont des MagicMock. Tout
ce qui vit ici est donc hors de portée de la suite, et la CI resterait verte
quoi qu'on y casse.

**Ne pas y mettre de calcul.** Les dérivations vivent dans `entities.py`, qui
est importable et testé.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import MountGuardConfigEntry
from .const import CONF_MOUNTS, CONF_SLUG, DOMAIN, SUBENTRY_TYPE_ADDON
from .coordinator import build_unique_id
from .entities import (
    active_remediations,
    addon_identifier,
    addon_state,
    last_incident,
    mount_identifier,
    pending_files,
)
from .models import to_wire


class _Base(CoordinatorEntity, SensorEntity):
    """Socle commun. `_attr_has_entity_name` partout : Home Assistant compose
    alors « Frigate État » à partir du nom de l'appareil, et renommer l'appareil
    renomme toutes ses entités."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, unique_id: str, device: DeviceInfo, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device
        self._attr_translation_key = key

    @property
    def _states(self) -> dict:
        return self.coordinator.data or {}


class RemediationsSensor(_Base):
    """Le capteur global, et le seul contrat public avec la carte."""

    _attr_icon = "mdi:folder-sync"

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(
            coordinator,
            build_unique_id(entry_id, "remediations"),
            DeviceInfo(
                identifiers={(DOMAIN, entry_id)},
                name="Add-on Mount Guard",
                manufacturer="Eric-D",
                entry_type="service",
            ),
            "remediations",
        )

    @property
    def native_value(self) -> int:
        return active_remediations(self._states)

    @property
    def extra_state_attributes(self) -> dict:
        """La liste complète, sérialisée par le même `to_wire` que le WebSocket
        et que l'événement. Un seul chemin : les trois canaux ne peuvent pas
        diverger, et un champ ajouté au contrat arrive partout sans rien
        toucher ici."""
        return {"remediations": [to_wire(rem) for rem in self._states.values()]}


class AddonStateSensor(_Base):
    def __init__(self, coordinator, entry_id, slug, device, mounts) -> None:
        super().__init__(
            coordinator, build_unique_id(entry_id, "addon", slug, "state"), device, "addon_state"
        )
        self._slug = slug
        self._mounts = mounts

    @property
    def native_value(self) -> str:
        return addon_state(self._states, self._slug, self._mounts)


class PendingFilesSensor(_Base):
    _attr_icon = "mdi:file-clock"
    _attr_native_unit_of_measurement = "fichiers"

    def __init__(self, coordinator, unique_id, device, mounts) -> None:
        super().__init__(coordinator, unique_id, device, "pending_files")
        self._mounts = mounts

    @property
    def native_value(self) -> int:
        return pending_files(self._states, self._mounts)


class LastIncidentSensor(_Base):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, unique_id, device, mounts) -> None:
        super().__init__(coordinator, unique_id, device, "last_incident")
        self._mounts = mounts

    @property
    def native_value(self):
        stamp = last_incident(self._states, self._mounts)
        # `dt_util.parse_datetime` et non `datetime.fromisoformat` : une chaîne
        # illisible rend None au lieu de lever, et un capteur d'horodatage qui
        # lève retire toutes ses entités sœurs de la plateforme.
        return dt_util.parse_datetime(stamp) if stamp else None


@callback
def async_setup_entry(
    hass: HomeAssistant,
    entry: MountGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Un appareil par add-on, un par montage, plus le capteur global."""
    coordinator = entry.runtime_data.coordinator
    table = entry.runtime_data.source.table

    async_add_entities([RemediationsSensor(coordinator, entry.entry_id)])

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ADDON:
            continue
        slug = subentry.data[CONF_SLUG]
        mounts = tuple(subentry.data.get(CONF_MOUNTS, ()))
        device = DeviceInfo(
            identifiers={addon_identifier(entry.entry_id, slug)},
            name=subentry.title or slug,
            manufacturer="Home Assistant",
            model="Add-on",
        )
        async_add_entities(
            [
                AddonStateSensor(coordinator, entry.entry_id, slug, device, mounts),
                PendingFilesSensor(
                    coordinator,
                    build_unique_id(entry.entry_id, "addon", slug, "pending"),
                    device,
                    mounts,
                ),
                LastIncidentSensor(
                    coordinator,
                    build_unique_id(entry.entry_id, "addon", slug, "incident"),
                    device,
                    mounts,
                ),
            ],
            config_subentry_id=subentry_id,
        )

    for mount in table.mounts:
        device = DeviceInfo(
            identifiers={mount_identifier(entry.entry_id, mount)},
            name=mount,
            manufacturer="Home Assistant",
            model="Stockage réseau",
        )
        async_add_entities(
            [
                PendingFilesSensor(
                    coordinator,
                    build_unique_id(entry.entry_id, "mount", mount, "pending"),
                    device,
                    (mount,),
                ),
                LastIncidentSensor(
                    coordinator,
                    build_unique_id(entry.entry_id, "mount", mount, "incident"),
                    device,
                    (mount,),
                ),
            ]
        )
