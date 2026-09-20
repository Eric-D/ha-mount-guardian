/** Tri et filtrage des lignes.
 *
 * Une erreur ici retire silencieusement un montage en panne de la carte — le
 * défaut exact que l'intégration existe pour empêcher côté backend.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { emptyReason, severity, visibleMounts } from '../src/helpers/sort.ts';
import { remediation } from './helpers.ts';

const ok = remediation({ mount: 'zeta' });
const degraded = remediation({ mount: 'beta', state: 'degraded' });
const pending = remediation({ mount: 'gamma', state: 'pending' });
const repairing = remediation({ mount: 'alpha', state: 'repairing' });

describe('severity', () => {
  test('ce qui se passe maintenant passe avant ce qui va se passer', () => {
    assert.ok(severity(repairing) > severity(pending));
  });

  test('dégradé passe après, parce qu’il appelle une action humaine', () => {
    // Rallumer le NAS. Les deux premiers n'appellent rien.
    assert.ok(severity(pending) > severity(degraded));
    assert.ok(severity(degraded) > severity(ok));
  });
});

describe('visibleMounts', () => {
  test('les plus graves en tête', () => {
    const rows = visibleMounts([ok, degraded, pending, repairing], {});
    assert.deepEqual(rows.map((r) => r.mount), ['alpha', 'gamma', 'beta', 'zeta']);
  });

  test('à gravité égale, le tri est stable sur le nom', () => {
    // Sans second critère, deux montages sains changeraient de place à chaque
    // rendu selon l'ordre de l'objet reçu, et la carte clignoterait.
    const a = remediation({ mount: 'b' });
    const b = remediation({ mount: 'a' });
    assert.deepEqual(
      visibleMounts([a, b], {}).map((r) => r.mount),
      ['a', 'b']
    );
    assert.deepEqual(
      visibleMounts([b, a], {}).map((r) => r.mount),
      ['a', 'b']
    );
  });

  test('le filtre par nom ne garde que ce qu’on lui demande', () => {
    const rows = visibleMounts([ok, degraded], { mounts: ['beta'] });
    assert.deepEqual(rows.map((r) => r.mount), ['beta']);
  });

  test('un filtre vide n’est pas un filtre', () => {
    // `mounts: []` arrive quand l'éditeur vide la liste ; le traiter comme un
    // filtre donnerait une carte définitivement vide.
    assert.equal(visibleMounts([ok, degraded], { mounts: [] }).length, 2);
  });

  test('show_ok masque les montages sains, et eux seuls', () => {
    const rows = visibleMounts([ok, degraded, repairing], { show_ok: false });
    assert.deepEqual(rows.map((r) => r.mount), ['alpha', 'beta']);
  });

  test('show_ok vaut vrai par défaut', () => {
    // Masquer ce qui va bien donne une carte vide en temps normal, et une
    // carte vide ressemble à une carte cassée.
    assert.equal(visibleMounts([ok], {}).length, 1);
  });

  test('l’entrée n’est pas mutée', () => {
    // `sort` trie en place : sans la copie, la carte réordonnerait l'attribut
    // du capteur, que d'autres cartes lisent aussi.
    const input = [ok, repairing];
    visibleMounts(input, {});
    assert.deepEqual(input.map((r) => r.mount), ['zeta', 'alpha']);
  });
});

describe('emptyReason', () => {
  test('aucun montage configuré et « tout va bien » sont deux messages', () => {
    // Les deux donnent une liste vide et appellent deux explications
    // différentes : l'une demande d'ajouter un add-on, l'autre non.
    assert.equal(emptyReason([], {}), 'none-configured');
    assert.equal(emptyReason([ok], { show_ok: false }), 'all-healthy');
  });

  test('avec quelque chose à montrer, aucune raison', () => {
    assert.equal(emptyReason([degraded], {}), null);
  });
});
