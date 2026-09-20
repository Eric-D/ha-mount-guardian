/** La souscription temps réel, et sa fusion avec l'attribut du capteur.
 *
 * **Le WebSocket est un raccourci, jamais une dépendance.** Ces tests portent
 * surtout sur ce qui se passe quand il ne marche pas.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { merge, RemediationFeed } from '../src/helpers/subscribe.ts';
import type { HassLike, Remediation } from '../src/types.ts';
import { remediation } from './helpers.ts';

function hassWith(
  subscribe: HassLike['connection'] extends infer C
    ? C extends { subscribeMessage: infer F }
      ? F
      : never
    : never
): HassLike {
  return {
    states: {},
    callService: async () => undefined,
    connection: { subscribeMessage: subscribe },
  };
}

describe('RemediationFeed', () => {
  test('les messages reçus remontent au rappel', async () => {
    const seen: Remediation[] = [];
    const feed = new RemediationFeed((r) => seen.push(r), () => {});
    await feed.connect(
      hassWith(async (callback) => {
        callback({ remediation: remediation({ mount: 'a' }) });
        return () => {};
      })
    );
    assert.deepEqual(seen.map((r) => r.mount), ['a']);
    assert.equal(feed.active, true);
  });

  test('un message vide est ignoré au lieu de faire planter la carte', async () => {
    const seen: Remediation[] = [];
    const feed = new RemediationFeed((r) => seen.push(r), () => {});
    await feed.connect(
      hassWith(async (callback) => {
        callback({} as never);
        return () => {};
      })
    );
    assert.equal(seen.length, 0);
  });

  test('une souscription impossible ne lève pas', async () => {
    // Version du backend antérieure à la commande, intégration non chargée :
    // la carte doit continuer de fonctionner sur l'attribut du capteur. Lever
    // dans `connectedCallback` la laisserait à moitié montée, sans rendu et
    // sans message.
    const feed = new RemediationFeed(() => {}, () => {});
    await feed.connect(
      hassWith(async () => {
        throw new Error('unknown command');
      })
    );
    assert.equal(feed.active, false);
    assert.equal(feed.lost, false, 'jamais connectée ≠ connexion perdue');
  });

  test('sans connexion du tout, rien ne se passe', async () => {
    const feed = new RemediationFeed(() => {}, () => {});
    await feed.connect({ states: {}, callService: async () => undefined });
    assert.equal(feed.active, false);
  });

  test('une seule souscription, même appelée deux fois', async () => {
    let count = 0;
    const feed = new RemediationFeed(() => {}, () => {});
    const hass = hassWith(async () => {
      count++;
      return () => {};
    });
    await feed.connect(hass);
    await feed.connect(hass);
    assert.equal(count, 1);
  });

  test('un détachement pendant l’attente ferme la souscription', async () => {
    // Sans cette garde, on garderait une souscription vivante sur un élément
    // qui n'est plus dans le document, et elle ne serait jamais fermée.
    let closed = false;
    const feed = new RemediationFeed(() => {}, () => {});
    const pending = feed.connect(
      hassWith(async () => {
        await Promise.resolve();
        return () => {
          closed = true;
        };
      })
    );
    feed.disconnect();
    await pending;
    assert.equal(closed, true);
    assert.equal(feed.active, false);
  });

  test('un désabonnement qui lève ne casse pas le détachement', async () => {
    const feed = new RemediationFeed(() => {}, () => {});
    await feed.connect(
      hassWith(async () => () => {
        throw new Error('socket déjà fermée');
      })
    );
    feed.disconnect();
    assert.equal(feed.active, false);
  });

  test('markLost distingue « jamais connectée » de « tombée »', () => {
    // Seul le second mérite un bandeau : sur une installation où le WebSocket
    // n'a jamais répondu, un bandeau permanent apprendrait à l'ignorer.
    const feed = new RemediationFeed(() => {}, () => {});
    assert.equal(feed.lost, false);
    feed.markLost();
    assert.equal(feed.lost, true);
  });
});

describe('merge', () => {
  test('le flux écrase l’attribut, par montage', () => {
    const base = [remediation({ mount: 'a', state: 'degraded' }), remediation({ mount: 'b' })];
    const live = new Map([['a', remediation({ mount: 'a', state: 'repairing' })]]);
    const merged = merge(base, live);
    assert.equal(merged.find((r) => r.mount === 'a')?.state, 'repairing');
    assert.equal(merged.find((r) => r.mount === 'b')?.state, 'ok');
  });

  test('la fusion est par nom, jamais par position', () => {
    // L'attribut du capteur et le flux n'ordonnent rien de la même façon. Une
    // fusion positionnelle écraserait la remédiation d'un montage avec celle
    // d'un autre — silencieusement, et seulement quand plusieurs montages sont
    // en panne à la fois.
    const base = [remediation({ mount: 'a' }), remediation({ mount: 'b' })];
    const live = new Map([['b', remediation({ mount: 'b', state: 'repairing' })]]);
    const merged = merge(base, live);
    assert.equal(merged.find((r) => r.mount === 'a')?.state, 'ok');
    assert.equal(merged.find((r) => r.mount === 'b')?.state, 'repairing');
  });

  test('un montage connu du seul flux apparaît quand même', () => {
    const merged = merge([], new Map([['c', remediation({ mount: 'c' })]]));
    assert.deepEqual(merged.map((r) => r.mount), ['c']);
  });
});
