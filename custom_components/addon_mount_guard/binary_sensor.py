"""Un capteur binaire par montage, sur l'appareil du montage et sur celui de
chaque add-on qui l'utilise.

Enveloppe mince : voir la docstring de `sensor.py` pour la raison.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MountGuardConfigEntry
from .const import CONF_MOUNTS, CONF_SLUG, SUBENTRY_TYPE_ADDON
from .coordinator import build_unique_id
from .entities import addon_identifier, has_problem, mount_identifier
from .models import to_wire


class MountProblemSensor(CoordinatorEntity, BinarySensorEntity):
    """`problem` et non `connectivity` : ce qui intéresse l'utilisateur est
    qu'il y a quelque chose à faire, pas l'état d'un lien réseau."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "mount_problem"

    def __init__(self, coordinator, unique_id: str, device: DeviceInfo, mount: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device
        self._attr_translation_placeholders = {"mount": mount}
        self._mount = mount

    @property
    def _remediation(self):
        return (self.coordinator.data or {}).get(self._mount)

    @property
    def is_on(self) -> bool:
        return has_problem(self._remediation)

    @property
    def extra_state_attributes(self) -> dict:
        """La remédiation complète de CE montage, dans le même format que
        partout ailleurs. C'est ce qui permet à une automatisation de lire
        l'étape en cours sans passer par le capteur global."""
        remediation = self._remediation
        return to_wire(remediation) if remediation else {}


@callback
def async_setup_entry(
    hass: HomeAssistant,
    entry: MountGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    table = entry.runtime_data.source.table

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ADDON:
            continue
        slug = subentry.data[CONF_SLUG]
        device = DeviceInfo(identifiers={addon_identifier(entry.entry_id, slug)})
        async_add_entities(
            [
                MountProblemSensor(
                    coordinator,
                    build_unique_id(entry.entry_id, "addon", slug, mount, "problem"),
                    device,
                    mount,
                )
                for mount in subentry.data.get(CONF_MOUNTS, ())
            ],
            config_subentry_id=subentry_id,
        )

    async_add_entities(
        [
            MountProblemSensor(
                coordinator,
                build_unique_id(entry.entry_id, "mount", mount, "problem"),
                DeviceInfo(identifiers={mount_identifier(entry.entry_id, mount)}),
                mount,
            )
            for mount in table.mounts
        ]
    )
