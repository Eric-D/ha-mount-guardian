/** Mise en forme.
 *
 * Une erreur dans `renders/` se voit à l'œil au premier chargement ; une erreur
 * ici ne se voit pas. « 1,2 Go » au lieu de « 1,2 Mo » est parfaitement
 * lisible.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import {
  formatBytes,
  formatCountdown,
  formatDuration,
  secondsSince,
  secondsUntil,
  truncatePath,
} from '../src/helpers/format.ts';

describe('formatBytes', () => {
  test('les unités sont décimales, comme celles du Superviseur', () => {
    // Compter en 1024 donnerait un nombre différent de celui que
    // l'utilisateur lit juste à côté, et le ferait douter du bon.
    assert.equal(formatBytes(1000), '1.0 ko');
    assert.equal(formatBytes(1_000_000), '1.0 Mo');
    assert.equal(formatBytes(9_150_000_000), '9.2 Go');
  });

  test('une décimale en dessous de dix, aucune au-dessus', () => {
    // « 941,3 Go » n'apporte rien et fait sauter la colonne à chaque
    // rafraîchissement.
    assert.equal(formatBytes(9_400_000_000), '9.4 Go');
    assert.equal(formatBytes(941_300_000_000), '941 Go');
  });

  test('les petites tailles restent en octets', () => {
    assert.equal(formatBytes(0), '0 o');
    assert.equal(formatBytes(999), '999 o');
  });

  test('une valeur absurde ne produit pas « NaN o »', () => {
    for (const value of [Number.NaN, Number.POSITIVE_INFINITY, -1]) {
      assert.equal(formatBytes(value), '—');
    }
  });
});

describe('formatDuration', () => {
  test('les trois échelles', () => {
    assert.equal(formatDuration(42), '42 s');
    assert.equal(formatDuration(128), '2 min 08 s');
    assert.equal(formatDuration(3720), '1 h 02');
  });

  test('les secondes et les minutes sont remplies à deux chiffres', () => {
    // Sans le padding, « 2 min 8 s » et « 2 min 48 s » n'ont pas la même
    // largeur et la ligne bouge à chaque seconde.
    assert.equal(formatDuration(122), '2 min 02 s');
    assert.equal(formatDuration(3660), '1 h 01');
  });

  test('rien de négatif ni de non fini', () => {
    assert.equal(formatDuration(-5), '—');
    assert.equal(formatDuration(Number.NaN), '—');
  });
});

describe('formatCountdown', () => {
  test('mm:ss', () => {
    assert.equal(formatCountdown(107), '01:47');
    assert.equal(formatCountdown(5), '00:05');
  });

  test('borné à zéro', () => {
    // L'horloge du navigateur et celle de Home Assistant ne sont jamais
    // exactement d'accord : un « -00:03 » au moment où le réessai part
    // donnerait l'impression que la carte est cassée.
    assert.equal(formatCountdown(-3), '00:00');
  });
});

describe('secondsSince / secondsUntil', () => {
  const now = Date.parse('2026-09-20T18:05:00Z');

  test('le temps écoulé est positif, le rebours négatif à l’envers', () => {
    assert.equal(secondsSince('2026-09-20T18:00:00+00:00', now), 300);
    assert.equal(secondsUntil('2026-09-20T18:10:00+00:00', now), 300);
  });

  test('un horodatage illisible rend null, pas NaN', () => {
    // NaN traverserait `formatDuration` et s'afficherait « NaN s ».
    assert.equal(secondsSince('pas une date', now), null);
    assert.equal(secondsSince(null, now), null);
  });

  test('le fuseau du navigateur ne change rien', () => {
    // Le backend n'envoie que des INSTANTS en UTC, jamais des dates civiles :
    // c'est ce qui permet de les soustraire sans se soucier du fuseau
    // configuré dans Home Assistant.
    assert.equal(secondsSince('2026-09-20T20:00:00+02:00', now), 300);
  });
});

describe('truncatePath', () => {
  test('tronque par la GAUCHE et garde le nom du fichier', () => {
    // Deux enregistrements voisins partagent quarante caractères de préfixe et
    // ne diffèrent que par les derniers. Une troncature à droite les rendrait
    // identiques à l'écran.
    const path = 'clips/front_door/2026-09-20/2026-09-20-14-02-17.mp4';
    const out = truncatePath(path, 24);
    assert.equal(out.startsWith('…'), true);
    assert.equal(out.endsWith('14-02-17.mp4'), true);
    assert.equal(out.length, 24);
  });

  test('un chemin court n’est pas touché', () => {
    assert.equal(truncatePath('a.mp4', 24), 'a.mp4');
  });

  test('null rend une chaîne vide, pas « null »', () => {
    assert.equal(truncatePath(null), '');
  });
});
