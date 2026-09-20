"""Le test de joignabilité du NAS.

C'est lui qui déclenche toute la séquence. Un faux positif arrête les add-ons
pour rien et enchaîne les échecs ; un faux négatif laisse l'add-on écrire en
local des heures après le retour du NAS. Aucun des deux ne se voit sur un
tableau de bord.
"""
from __future__ import annotations

import asyncio

from custom_components.addon_mount_guard.reachability import async_is_reachable, probe_port


class FakeWriter:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TestProbePort:
    def test_each_protocol_has_its_port(self):
        assert probe_port("cifs") == 445
        assert probe_port("nfs") == 2049

    def test_the_case_does_not_matter(self):
        assert probe_port("CIFS") == 445

    def test_an_unknown_type_falls_back_instead_of_raising(self):
        """Le Supervisor peut gagner un type de partage sans nous prévenir.
        Refuser de tester laisserait le montage dégradé pour toujours ; se
        tromper de port fait au pire attendre un peu plus longtemps."""
        assert probe_port("sshfs") == 445
        assert probe_port(None) == 445


class TestIsReachable:
    async def test_a_nas_that_answers_is_reachable(self):
        writer = FakeWriter()

        async def opener(host, port):
            assert (host, port) == ("10.0.0.12", 445)
            return object(), writer

        assert await async_is_reachable("10.0.0.12", port=445, opener=opener) is True

    async def test_a_refused_connection_is_not_reachable(self):
        async def opener(host, port):
            raise ConnectionRefusedError(111, "refusé")

        assert await async_is_reachable("10.0.0.12", port=445, opener=opener) is False

    async def test_an_unknown_host_is_not_reachable(self):
        """Nom introuvable : OSError, pas une exception à part. La laisser
        remonter ferait échouer le cycle entier du coordinator pour un seul
        montage mal orthographié."""
        async def opener(host, port):
            raise OSError("nom introuvable")

        assert await async_is_reachable("nas.invalide", port=445, opener=opener) is False

    async def test_a_nas_that_takes_too_long_is_not_reachable(self):
        """Le cas qui compte le plus : un NAS qui répond au bout de huit
        secondes n'est pas joignable au sens de cette intégration. Monter les
        add-ons dessus dans cet état fait échouer la réparation à l'étape 3."""
        async def opener(host, port):
            await asyncio.sleep(10)
            return object(), FakeWriter()

        assert await async_is_reachable("lent", port=445, timeout=0.01, opener=opener) is False

    async def test_the_connection_is_always_closed(self):
        """Un writer laissé ouvert à chaque cycle finit par épuiser les
        descripteurs de fichiers du conteneur, et la panne qui en résulte ne
        ressemble en rien à sa cause."""
        writer = FakeWriter()

        async def opener(host, port):
            return object(), writer

        await async_is_reachable("10.0.0.12", port=445, opener=opener)
        assert writer.closed is True

    async def test_it_never_blocks_the_loop(self):
        """La garantie qui justifie asyncio.open_connection plutôt que
        socket.connect : pendant le test, le reste de la boucle tourne. Avec un
        appel bloquant, `ticks` resterait à zéro et Home Assistant serait figé
        pendant tout le délai, par montage et par cycle."""
        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0)
                ticks += 1

        async def opener(host, port):
            await asyncio.sleep(0.05)
            return object(), FakeWriter()

        probe = asyncio.create_task(
            async_is_reachable("lent", port=445, timeout=1.0, opener=opener)
        )
        await ticker()
        assert ticks == 5
        assert await probe is True
