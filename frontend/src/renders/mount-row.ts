import { html, nothing, type TemplateResult } from 'lit';

import { formatCountdown, formatDuration, secondsSince, secondsUntil } from '../helpers/format.js';
import { percent, progressOf } from '../helpers/progress.js';
import { canCancel, canRepair, STEP_LABELS, stepper } from '../helpers/steps.js';
import type { MountState, Remediation, Step } from '../types.js';
import { renderHistory } from './history.js';
import { renderProgress, renderStepper } from './stepper.js';

/** Jeton de thème par état. Les quatre sont garantis par Home Assistant ; une
 *  couleur figée serait illisible dans la moitié des thèmes installés. */
const DOT: Record<MountState, string> = {
  ok: 'var(--success-color)',
  degraded: 'var(--warning-color)',
  pending: 'var(--primary-color)',
  repairing: 'var(--primary-color)',
};

const STATE_LABELS: Record<MountState, string> = {
  ok: 'Normal',
  degraded: 'Dégradé',
  pending: 'Réparation en attente',
  repairing: 'Réparation',
};

const ADDON_LABELS: Record<string, string> = {
  started: 'démarré',
  stopped: 'arrêté',
  held: 'maintenu arrêté',
  unknown: 'état inconnu',
};

function addonLine(remediation: Remediation): string {
  if (remediation.addons.length === 0) return '';
  return remediation.addons
    .map((addon) => `${addon.name} — ${ADDON_LABELS[addon.state] ?? addon.state}`)
    .join(' · ');
}

/** Une ligne de montage.
 *
 *  Tous les gestionnaires arrivent en paramètres nommés : ce rendu ne connaît
 *  ni `hass`, ni la configuration de la carte, ni les services. C'est ce qui
 *  permet de le monter dans un vrai DOM et de déclencher ses boutons — un
 *  `@click` ne se distingue d'un autre qu'en l'appelant.
 */
export function renderMountRow({
  remediation,
  now,
  showHistory,
  compact,
  onRepair,
  onCancel,
}: {
  remediation: Remediation;
  /** Injecté et non lu de `Date.now()` ici : c'est ce qui rend le temps écoulé
      testable, et ce qui garantit que toutes les lignes d'un même rendu
      affichent le même instant. */
  now: number;
  showHistory: boolean;
  compact: boolean;
  onRepair: (mount: string) => void;
  onCancel: (mount: string) => void;
}): TemplateResult {
  const repairing = remediation.state === 'repairing';
  const cells = stepper(remediation);
  const progress = progressOf(remediation);

  if (compact) {
    return html`
      <div class="mount compact" data-mount=${remediation.mount}>
        <div class="row">
          <span class="dot" style="--dot-color: ${DOT[remediation.state]}"></span>
          <span class="name">${remediation.mount}</span>
          <span class="summary">${compactSummary(remediation, progress.ratio, now)}</span>
        </div>
      </div>
    `;
  }

  return html`
    <div class="mount" data-mount=${remediation.mount}>
      <div class="row">
        <span class="dot" style="--dot-color: ${DOT[remediation.state]}"></span>
        <span class="name">${remediation.mount}</span>
        <span class="path">${remediation.path}</span>
      </div>

      ${addonLine(remediation) ? html`<div class="addons">${addonLine(remediation)}</div>` : ''}

      ${repairing
        ? html`
            ${renderStepper(cells)}
            ${remediation.step === 'restoring' || remediation.step === 'rolling_back'
              ? renderProgress({ progress, currentFile: remediation.current_file })
              : nothing}
            <div class="meta">${elapsed(remediation, now)}</div>
          `
        : html`<div class="meta">${idleSummary(remediation, now)}</div>`}

      ${remediation.last_error
        ? html`<div class="error">${remediation.last_error}</div>`
        : ''}

      <div class="actions">
        <mwc-button
          class="repair"
          ?disabled=${!canRepair(remediation)}
          @click=${() => onRepair(remediation.mount)}
          >Réparer maintenant</mwc-button
        >
        <mwc-button
          class="cancel"
          ?disabled=${!canCancel(remediation)}
          @click=${() => onCancel(remediation.mount)}
          >Annuler</mwc-button
        >
      </div>

      ${showHistory ? renderHistory(remediation.history) : nothing}
    </div>
  `;
}

function elapsed(remediation: Remediation, now: number): string {
  const seconds = secondsSince(remediation.started_at, now);
  const step = remediation.step ? STEP_LABELS[remediation.step as Step] : '';
  const position = `étape ${remediation.step_index} sur ${remediation.step_count}`;
  if (seconds === null) return `${step} — ${position}`;
  return `${step} — ${position} · depuis ${formatDuration(seconds)}`;
}

function idleSummary(remediation: Remediation, now: number): string {
  if (remediation.state === 'ok') return STATE_LABELS.ok;
  const countdown = secondsUntil(remediation.next_retry_at, now);
  const since = secondsSince(remediation.last_incident_at, now);
  const parts = [STATE_LABELS[remediation.state]];
  if (since !== null) parts.push(`depuis ${formatDuration(since)}`);
  if (countdown !== null) parts.push(`nouvelle tentative dans ${formatCountdown(countdown)}`);
  return parts.join(' · ');
}

function compactSummary(
  remediation: Remediation,
  ratio: number | null,
  now: number
): string {
  if (remediation.state === 'repairing') {
    const step = remediation.step ? STEP_LABELS[remediation.step as Step] : '';
    const pct = percent(ratio);
    return pct ? `${step} · ${pct}` : step;
  }
  if (remediation.state === 'ok') return STATE_LABELS.ok;
  const countdown = secondsUntil(remediation.next_retry_at, now);
  return countdown === null
    ? STATE_LABELS[remediation.state]
    : `${STATE_LABELS[remediation.state]} · ${formatCountdown(countdown)}`;
}
