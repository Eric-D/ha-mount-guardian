/** La ligne de montage, montée dans un vrai DOM.
 *
 * On rend réellement plutôt que d'inspecter le TemplateResult : c'est le seul
 * moyen de voir ce que ni `tsc` ni oxlint ne voient — deux paramètres de même
 * type inversés, et surtout un `@click` branché sur le mauvais bouton.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { renderMountRow } from '../src/renders/mount-row.ts';
import { addon, all, click, mount, remediation, text } from './helpers.ts';

const NOW = Date.parse('2026-09-20T18:05:00Z');

function row(overrides = {}, options: Record<string, unknown> = {}) {
  return mount(
    renderMountRow({
      remediation: remediation(overrides),
      now: NOW,
      showHistory: false,
      compact: false,
      onRepair: () => {},
      onCancel: () => {},
      ...options,
    })
  );
}

describe('identification du montage', () => {
  test('le nom et le chemin sont affichés, et pas intervertis', () => {
    // Deux chaînes adjacentes dans une signature positionnelle s'inversent
    // sans que rien ne le dise, et le rendu reste parfaitement lisible.
    const host = row({ mount: 'nas_media', path: '/media/frigate' });
    assert.equal(text(host, '.name'), 'nas_media');
    assert.equal(text(host, '.path'), '/media/frigate');
  });

  test('la pastille porte un jeton de thème, jamais une couleur figée', () => {
    // Une couleur figée est illisible dans la moitié des thèmes installés, et
    // le défaut ne se voit que chez celui qui n'a pas le même thème que
    // l'auteur.
    const dot = row({ state: 'degraded' }).querySelector('.dot') as HTMLElement;
    assert.match(dot.getAttribute('style') ?? '', /var\(--warning-color\)/);
  });

  test('chaque état a sa propre couleur', () => {
    const colors = (['ok', 'degraded', 'repairing'] as const).map((state) => {
      const dot = row({ state }).querySelector('.dot') as HTMLElement;
      return dot.getAttribute('style');
    });
    assert.equal(new Set(colors).size, 3);
  });
});

describe('add-ons', () => {
  test('chaque add-on est nommé avec son état', () => {
    const host = row({ addons: [addon({ name: 'Frigate', state: 'held' })] });
    assert.match(text(host, '.addons'), /Frigate — maintenu arrêté/);
  });

  test('« maintenu arrêté » n’est pas confondu avec « arrêté »', () => {
    // C'est toute la valeur de l'état `held` : expliquer pourquoi l'add-on ne
    // tourne pas alors que son montage vient d'être réparé.
    const held = text(row({ addons: [addon({ state: 'held' })] }), '.addons');
    const stopped = text(row({ addons: [addon({ state: 'stopped' })] }), '.addons');
    assert.notEqual(held, stopped);
  });

  test('sans add-on, pas de ligne vide', () => {
    assert.equal(row().querySelector('.addons'), null);
  });
});

describe('remédiation en cours', () => {
  const repairing = {
    state: 'repairing' as const,
    step: 'restoring' as const,
    step_index: 4,
    started_at: '2026-09-20T18:03:00+00:00',
    files_total: 1284,
    files_done: 613,
    bytes_total: 9_817_362_432,
    bytes_done: 4_113_920_512,
    current_file: 'clips/front_door/2026-09-20/18/2026-09-20-14-02-17.mp4',
  };

  test('le stepper a autant de cases que d’étapes', () => {
    assert.equal(all(row(repairing), '.step').length, 5);
  });

  test('une seule case est active', () => {
    assert.equal(all(row(repairing), '.step.active').length, 1);
  });

  test('la barre de progression suit les octets', () => {
    // 4 113 920 512 / 9 817 362 432 ≈ 41,9 %
    const fill = row(repairing).querySelector('.fill') as HTMLElement;
    assert.match(fill.getAttribute('style') ?? '', /width: 41\.9/);
  });

  test('les compteurs de fichiers et d’octets sont tous deux affichés', () => {
    const numbers = text(row(repairing), '.numbers');
    assert.match(numbers, /613 \/ 1284 fichiers/);
    assert.match(numbers, /Go \/ /);
  });

  test('le fichier courant est tronqué mais reste entier dans l’infobulle', () => {
    const current = row(repairing).querySelector('.current') as HTMLElement;
    assert.equal(current.getAttribute('title'), repairing.current_file);
    assert.ok((current.textContent ?? '').startsWith('…'));
  });

  test('le temps écoulé vient de started_at et de l’horloge injectée', () => {
    assert.match(text(row(repairing), '.meta'), /depuis 2 min 00 s/);
  });

  test('l’étape et sa position sont dites en toutes lettres', () => {
    // Le stepper est visuel ; cette ligne est ce que lit un lecteur d'écran.
    assert.match(text(row(repairing), '.meta'), /étape 4 sur 5/);
  });

  test('pas de barre de progression hors du rapatriement', () => {
    // Pendant l'arrêt des add-ons, une barre à zéro donnerait l'impression
    // que la copie a commencé et n'avance pas.
    const host = row({ ...repairing, step: 'stopping', step_index: 1 });
    assert.equal(host.querySelector('.progress'), null);
  });
});

describe('montage dégradé', () => {
  test('le compte à rebours vers le réessai est affiché', () => {
    const host = row({
      state: 'degraded',
      last_incident_at: '2026-09-20T17:51:00+00:00',
      next_retry_at: '2026-09-20T18:06:47+00:00',
    });
    assert.match(text(host, '.meta'), /nouvelle tentative dans 01:47/);
    assert.match(text(host, '.meta'), /depuis 14 min 00 s/);
  });

  test('la dernière erreur est montrée telle quelle', () => {
    const host = row({ state: 'degraded', last_error: 'NAS injoignable (10.0.0.12)' });
    assert.equal(text(host, '.error'), 'NAS injoignable (10.0.0.12)');
  });

  test('aucune erreur, aucune ligne d’erreur', () => {
    assert.equal(row({ state: 'degraded' }).querySelector('.error'), null);
  });
});

describe('boutons', () => {
  test('chaque bouton appelle SON service, avec le bon montage', () => {
    // Un `@click` ne se distingue d'un autre qu'en le déclenchant : c'est
    // exactement le défaut que ce test existe pour attraper.
    const repaired: string[] = [];
    const cancelled: string[] = [];
    const host = mount(
      renderMountRow({
        remediation: remediation({ mount: 'nas_media', state: 'degraded' }),
        now: NOW,
        showHistory: false,
        compact: false,
        onRepair: (m) => repaired.push(m),
        onCancel: (m) => cancelled.push(m),
      })
    );
    click(host, '.repair');
    assert.deepEqual(repaired, ['nas_media']);
    assert.deepEqual(cancelled, []);
  });

  test('réparer est désactivé sur un montage sain', () => {
    const button = row({ state: 'ok' }).querySelector('.repair') as HTMLElement;
    assert.ok(button.hasAttribute('disabled'));
  });

  test('annuler n’est actif que pendant une séquence', () => {
    const idle = row({ state: 'degraded' }).querySelector('.cancel') as HTMLElement;
    const running = row({ state: 'repairing' }).querySelector('.cancel') as HTMLElement;
    assert.ok(idle.hasAttribute('disabled'));
    assert.ok(!running.hasAttribute('disabled'));
  });
});

describe('historique', () => {
  test('affiché seulement sur demande', () => {
    const entries = { history: [{ at: '2026-09-20T18:00:00+00:00', from: 'ok',
                                  to: 'degraded', step: null, error: 'boum' }] };
    assert.equal(row(entries).querySelector('.history'), null);
    assert.ok(row(entries, { showHistory: true }).querySelector('.history'));
  });

  test('replié par défaut', () => {
    // C'est un outil de diagnostic : déplié, il occupe plus de place que la
    // ligne qu'il documente.
    const entries = { history: [{ at: '2026-09-20T18:00:00+00:00', from: 'ok',
                                  to: 'degraded', step: null, error: null }] };
    const details = row(entries, { showHistory: true }).querySelector('details') as HTMLElement;
    assert.ok(!details.hasAttribute('open'));
  });
});

describe('mode compact', () => {
  test('une seule ligne, sans stepper ni boutons', () => {
    // Pour une tablette murale, où la hauteur est la ressource rare.
    const host = row(
      { state: 'repairing', step: 'restoring', step_index: 4, bytes_total: 100, bytes_done: 48 },
      { compact: true }
    );
    assert.equal(host.querySelector('.stepper'), null);
    assert.equal(host.querySelector('.actions'), null);
    assert.match(text(host, '.summary'), /Rapatriement · 48 %/);
  });

  test('le rebours reste visible en compact', () => {
    const host = row(
      { state: 'degraded', next_retry_at: '2026-09-20T18:06:47+00:00' },
      { compact: true }
    );
    assert.match(text(host, '.summary'), /01:47/);
  });
});
