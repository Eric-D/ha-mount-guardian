import type { Mode, Remediation, Step } from '../types.js';

/** Les étapes numérotées, par mode. **Miroir de `models.STEPS_BY_MODE`.**
 *
 *  `stop_only` garde `reloading` : le Superviseur ne recharge pas un montage
 *  tombé — c'est la raison d'être de l'intégration — donc sans cette étape le
 *  montage ne reviendrait jamais. Ce que ce mode retire, c'est le déplacement
 *  de fichiers.
 *
 *  La carte lit néanmoins `step_count` du contrat plutôt que la longueur de ces
 *  tableaux pour dessiner le stepper : c'est le backend qui fait foi, et un
 *  désaccord doit se voir comme un stepper incomplet, pas se corriger en
 *  silence. Ces libellés ne servent qu'à nommer les cases. */
const SEQUENCES: Record<Mode, readonly Step[]> = {
  local_fallback: ['stopping', 'stashing', 'reloading', 'restoring', 'starting'],
  stop_only: ['stopping', 'reloading', 'starting'],
};

export const STEP_LABELS: Record<Step, string> = {
  stopping: 'Arrêt',
  stashing: 'Mise de côté',
  reloading: 'Rechargement',
  restoring: 'Rapatriement',
  rolling_back: 'Retour arrière',
  starting: 'Relance',
};

export interface StepCell {
  index: number;
  step: Step;
  label: string;
  state: 'done' | 'active' | 'failed' | 'todo';
}

/** Les cases du stepper, dans l'ordre.
 *
 *  `rolling_back` n'est pas une sixième case : c'est l'échec de `restoring`,
 *  et il prend sa place en rouge. Lui donner une case de plus ferait déborder
 *  le stepper d'une largeur que rien n'a prévue.
 */
export function stepper(remediation: Remediation): StepCell[] {
  const sequence = SEQUENCES[remediation.mode] ?? SEQUENCES.local_fallback;
  const failed = remediation.step === 'rolling_back';
  const current = remediation.step_index;

  return sequence.map((step, position) => {
    const index = position + 1;
    let state: StepCell['state'] = 'todo';
    if (index < current) state = 'done';
    else if (index === current) state = failed ? 'failed' : 'active';
    return {
      index,
      step,
      label: STEP_LABELS[failed && index === current ? 'rolling_back' : step],
      state,
    };
  });
}

/** Le bouton « Annuler » est-il utilisable ?
 *
 *  Miroir de `entities.cancel_available`, mais la carte ajoute une nuance que
 *  le backend n'a pas : pendant `restoring`, l'abandon est accepté mais ne
 *  prend effet qu'entre deux fichiers. Le bouton reste donc actif — c'est le
 *  libellé qui prévient. */
export function canCancel(remediation: Remediation): boolean {
  return remediation.state === 'repairing';
}

export function canRepair(remediation: Remediation): boolean {
  return remediation.state === 'degraded' || remediation.state === 'pending';
}
