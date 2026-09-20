"""Commande WebSocket `addon_mount_guard/subscribe`.

Elle existe pour une seule raison : **pousser la progression du rapatriement
sans attendre le cycle de polling.** L'attribut de
`sensor.mount_guard_remediations` porte déjà tout le contrat, mais il n'arrive
qu'au relevé suivant — jusqu'à une minute plus tard. Une barre de progression
qui bouge une fois par minute ne dit rien de plus qu'un texte figé.

La carte s'abonne d'abord ici et **retombe sur l'attribut du capteur** si la
souscription échoue : le WebSocket est un raccourci, jamais une dépendance. Une
installation où il serait indisponible verrait simplement la carte se mettre à
jour moins vite.

Ce module n'est **pas testable** sous les mocks de `tests/conftest.py` :
`@websocket_api.websocket_command` y est un MagicMock, qui *remplace* la
fonction décorée. Le module s'importe ; ce qu'il contient ne s'exécute jamais.
Il reste donc aussi mince que les plateformes d'entités — tout ce qui se calcule
vit dans `coordinator.publish` et `models.to_wire`.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import guard_entries
from .models import to_wire

_LOGGER = logging.getLogger(__name__)

TYPE_SUBSCRIBE = f"{DOMAIN}/subscribe"


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_subscribe)


@callback
@websocket_api.websocket_command({vol.Required("type"): TYPE_SUBSCRIBE})
def websocket_subscribe(
    hass: HomeAssistant, connection: Any, msg: dict[str, Any]
) -> None:
    """Pousse l'état de tous les montages, puis chaque changement."""
    entries = guard_entries(hass)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "Add-on Mount Guard n'est pas chargé")
        return

    source = entries[0][1].source

    @callback
    def forward(payload: dict[str, Any]) -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], {"remediation": payload})
        )

    # Désabonnement enregistré auprès de la connexion : sans lui, un onglet
    # fermé laisserait un abonné qui écrit dans une socket morte à chaque
    # publication, pour toute la durée de vie de Home Assistant.
    connection.subscriptions[msg["id"]] = source.subscribe(forward)
    connection.send_result(msg["id"])

    # L'instantané APRÈS `send_result` : la carte doit avoir accusé la
    # souscription avant de recevoir des événements, sinon elle les ignore.
    for remediation in source.snapshot():
        forward(to_wire(remediation))
