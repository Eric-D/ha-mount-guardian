/** Le stepper.
 *
 * Il dit à l'utilisateur où en est une opération qui arrête ses add-ons et
 * déplace ses fichiers. Une case allumée au mauvais endroit lui fait croire
 * que la copie est finie alors qu'elle commence.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { canCancel, canRepair, stepper } from '../src/helpers/steps.ts';
import { remediation } from './helpers.ts';

describe('stepper', () => {
  test('les cinq étapes du repli local, dans l’ordre', () => {
    const cells = stepper(remediation({ state: 'repairing', step: 'reloading', step_index: 3 }));
    assert.deepEqual(cells.map((c) => c.step), [
      'stopping',
      'stashing',
      'reloading',
      'restoring',
      'starting',
    ]);
  });

  test('l’étape courante est active, les précédentes faites', () => {
    const cells = stepper(remediation({ state: 'repairing', step: 'reloading', step_index: 3 }));
    assert.deepEqual(cells.map((c) => c.state), [
      'done',
      'done',
      'active',
      'todo',
      'todo',
    ]);
  });

  test('stop_only garde le rechargement, et n’a que trois cases', () => {
    // Le Superviseur ne recharge pas un montage tombé — c'est la raison d'être
    // de l'intégration. Sans cette étape, le montage ne reviendrait jamais.
    const cells = stepper(
      remediation({ mode: 'stop_only', state: 'repairing', step: 'reloading', step_index: 2 })
    );
    assert.deepEqual(cells.map((c) => c.step), ['stopping', 'reloading', 'starting']);
    assert.equal(cells[1].state, 'active');
  });

  test('rolling_back prend la place de restoring, en rouge', () => {
    // Ce n'est pas une sixième étape : lui donner une case de plus ferait
    // déborder le stepper d'une largeur que rien n'a prévue.
    const cells = stepper(
      remediation({ state: 'repairing', step: 'rolling_back', step_index: 4 })
    );
    assert.equal(cells.length, 5);
    assert.equal(cells[3].state, 'failed');
    assert.equal(cells[3].label, 'Retour arrière');
  });

  test('hors séquence, aucune case n’est allumée', () => {
    const cells = stepper(remediation({ state: 'degraded' }));
    assert.equal(cells.every((c) => c.state === 'todo'), true);
  });

  test('un mode inconnu retombe sur la séquence la plus longue', () => {
    // Plutôt qu'un stepper vide : un mode ajouté côté Python doit s'afficher
    // de façon plausible, pas disparaître.
    const cells = stepper(
      remediation({ mode: 'futur' as never, state: 'repairing', step_index: 1 })
    );
    assert.equal(cells.length, 5);
  });
});

describe('canRepair / canCancel', () => {
  test('réparer n’a de sens que sur un montage en panne', () => {
    assert.equal(canRepair(remediation({ state: 'degraded' })), true);
    assert.equal(canRepair(remediation({ state: 'pending' })), true);
    assert.equal(canRepair(remediation({ state: 'ok' })), false);
    assert.equal(canRepair(remediation({ state: 'repairing' })), false);
  });

  test('annuler n’a de sens que pendant une séquence', () => {
    assert.equal(canCancel(remediation({ state: 'repairing' })), true);
    for (const state of ['ok', 'degraded', 'pending'] as const) {
      assert.equal(canCancel(remediation({ state })), false);
    }
  });
});
