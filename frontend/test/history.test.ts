/** Le journal repliable. */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { renderHistory } from '../src/renders/history.ts';
import { all, mount, transition } from './helpers.ts';

describe('renderHistory', () => {
  test('vide, rien n’est rendu', () => {
    assert.equal(mount(renderHistory([])).querySelector('details'), null);
  });

  test('une ligne par transition, dans l’ordre reçu', () => {
    // Le backend envoie la plus récente en tête. Réordonner ici ferait lire le
    // journal à l'envers.
    const rows = all(
      mount(
        renderHistory([
          transition({ at: '2026-09-20T18:44:00+00:00', from: 'degraded', to: 'repairing' }),
          transition({ at: '2026-09-20T18:39:00+00:00', from: 'ok', to: 'degraded' }),
        ])
      ),
      'tr'
    );
    assert.equal(rows.length, 2);
    assert.match(rows[0].textContent ?? '', /dégradé → réparation/);
  });

  test('les états sont traduits, pas affichés bruts', () => {
    const host = mount(renderHistory([transition({ from: 'ok', to: 'pending' })]));
    assert.match(host.textContent ?? '', /réparation due/);
    assert.doesNotMatch(host.textContent ?? '', /pending/);
  });

  test('un état inconnu s’affiche tel quel plutôt que de disparaître', () => {
    // Un état ajouté côté Python doit rester lisible, même sans libellé.
    const host = mount(renderHistory([transition({ to: 'futur' as never })]));
    assert.match(host.textContent ?? '', /futur/);
  });

  test('l’erreur est rendue comme du texte', () => {
    const host = mount(renderHistory([transition({ error: '<i>boum</i>' })]));
    assert.equal(host.querySelector('i'), null);
    assert.match(host.textContent ?? '', /<i>boum<\/i>/);
  });

  test('sans erreur, la cellule reste vide plutôt que « null »', () => {
    const host = mount(renderHistory([transition({ error: null })]));
    assert.doesNotMatch(host.textContent ?? '', /null/);
  });

  test('le compte annoncé est celui des entrées', () => {
    const host = mount(renderHistory([transition(), transition(), transition()]));
    assert.match(host.querySelector('summary')?.textContent ?? '', /Historique \(3\)/);
  });
});
