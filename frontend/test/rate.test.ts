/** Débit et temps restant.
 *
 * Sur un rapatriement de deux heures, c'est la seule information qui dise à
 * l'utilisateur s'il doit attendre ou aller se coucher.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { RateTracker } from '../src/helpers/rate.ts';
import { remediation } from './helpers.ts';

const T0 = Date.parse('2026-09-20T18:00:00Z');

function running(bytes: number, total = 1000) {
  return remediation({
    state: 'repairing',
    started_at: '2026-09-20T17:59:00+00:00',
    bytes_done: bytes,
    bytes_total: total,
  });
}

describe('RateTracker', () => {
  test('le premier échantillon ne conclut rien', () => {
    // Un débit calculé sur un seul point n'existe pas.
    assert.equal(new RateTracker().measure(running(0), T0), null);
  });

  test('le débit se mesure entre deux échantillons', () => {
    const tracker = new RateTracker();
    tracker.measure(running(100), T0);
    const rate = tracker.measure(running(300), T0 + 2000);
    assert.equal(rate?.bytesPerSecond, 100);
  });

  test('le temps restant suit le débit mesuré', () => {
    const tracker = new RateTracker();
    tracker.measure(running(100, 1100), T0);
    const rate = tracker.measure(running(300, 1100), T0 + 2000);
    assert.equal(rate?.etaSeconds, 8);
  });

  test('la mesure ne part PAS de started_at', () => {
    // `started_at` couvre aussi l'arrêt des add-ons, la mise de côté et le
    // rechargement, qui ne transfèrent aucun octet. Les inclure annoncerait
    // le double du temps réel dès les premières minutes.
    const tracker = new RateTracker();
    tracker.measure(running(0), T0);
    const rate = tracker.measure(running(1000, 1000), T0 + 1000);
    assert.equal(rate?.bytesPerSecond, 1000);
  });

  test('un intervalle trop court ne conclut rien', () => {
    // Le bruit d'échantillonnage y fait sauter l'estimation d'un facteur dix,
    // et un temps restant qui saute est pire que pas de temps restant.
    const tracker = new RateTracker();
    tracker.measure(running(100), T0);
    assert.equal(tracker.measure(running(300), T0 + 200), null);
  });

  test('une nouvelle tentative repart de zéro', () => {
    // Sinon on moyennerait deux rapatriements différents, séparés par une
    // attente de deux minutes.
    const tracker = new RateTracker();
    tracker.measure(running(500), T0);
    const next = remediation({
      state: 'repairing',
      started_at: '2026-09-20T18:10:00+00:00',
      bytes_done: 0,
      bytes_total: 1000,
    });
    assert.equal(tracker.measure(next, T0 + 5000), null);
  });

  test('aucun octet transféré ne produit pas une division par zéro', () => {
    // Pendant l'arrêt des add-ons, rien n'avance : un `Infinity` s'afficherait
    // « ∞ restantes ».
    const tracker = new RateTracker();
    tracker.measure(running(100), T0);
    assert.equal(tracker.measure(running(100), T0 + 5000), null);
  });

  test('terminé, il n’y a plus de temps restant', () => {
    const tracker = new RateTracker();
    tracker.measure(running(0, 1000), T0);
    const rate = tracker.measure(running(1000, 1000), T0 + 1000);
    assert.equal(rate?.etaSeconds, null);
    assert.ok((rate?.bytesPerSecond ?? 0) > 0);
  });

  test('un montage oublié repart à zéro', () => {
    const tracker = new RateTracker();
    tracker.measure(running(100), T0);
    tracker.forget('nas_media');
    assert.equal(tracker.measure(running(300), T0 + 2000), null);
  });
});
