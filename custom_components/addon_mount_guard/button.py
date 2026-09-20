"""Le bouton « Réparer maintenant », sur l'appareil de chaque montage.

Enveloppe mince : voir la docstring de `sensor.py` pour la raison.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MountGuardConfigEntry
from .const import CONF_MOUNTS, CONF_SLUG, SUBENTRY_TYPE_ADDON
from .coordinator import build_unique_id
from .entities import addon_identifier, mount_identifier, repair_available


class RepairButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "repair"
    _attr_icon = "mdi:folder-sync"

    def __init__(self, coordinator, unique_id: str, device: DeviceInfo, mount: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device
        self._attr_translation_placeholders = {"mount": mount}
        self._mount = mount

    @property
    def available(self) -> bool:
        """Indisponible quand il n'y a rien à réparer.

        Un bouton actif sur un montage sain arrêterait les add-ons pour rien —
        la séquence ne casserait rien (`repair.py` refuse de mettre de côté un
        montage actif) mais Frigate s'arrêterait quand même.
        """
        return super().available and repair_available(
            (self.coordinator.data or {}).get(self._mount)
        )

    async def async_press(self) -> None:
        source = self.coordinator.config_entry.runtime_data.source
        await source.async_repair_now(self._mount)


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
                RepairButton(
                    coordinator,
                    build_unique_id(entry.entry_id, "addon", slug, mount, "repair"),
                    device,
                    mount,
                )
                for mount in subentry.data.get(CONF_MOUNTS, ())
            ],
            config_subentry_id=subentry_id,
        )

    async_add_entities(
        [
            RepairButton(
                coordinator,
                build_unique_id(entry.entry_id, "mount", mount, "repair"),
                DeviceInfo(identifiers={mount_identifier(entry.entry_id, mount)}),
                mount,
            )
            for mount in table.mounts
        ]
    )
