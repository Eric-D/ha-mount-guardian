import { html, nothing, type TemplateResult } from 'lit';

import { STEP_LABELS } from '../helpers/steps.js';
import type { RemediationTransition, Step } from '../types.js';

const STATE_LABELS: Record<string, string> = {
  ok: 'normal',
  degraded: 'dégradé',
  pending: 'réparation due',
  repairing: 'réparation',
};

function label(state: string): string {
  return STATE_LABELS[state] ?? state;
}

/** Journal repliable. Replié par défaut : c'est un outil de diagnostic, et
 *  déplié il occupe plus de place que la ligne qu'il documente. */
export function renderHistory(
  entries: readonly RemediationTransition[]
): TemplateResult | typeof nothing {
  if (entries.length === 0) return nothing;
  return html`
    <details class="history">
      <summary>Historique (${entries.length})</summary>
      <table>
        ${entries.map(
          (entry) => html`
            <tr>
              <td class="at">${new Date(entry.at).toLocaleString()}</td>
              <td>${label(entry.from)} → ${label(entry.to)}</td>
              <td>${entry.step ? STEP_LABELS[entry.step as Step] ?? entry.step : ''}</td>
              <td>${entry.error ?? ''}</td>
            </tr>
          `
        )}
      </table>
    </details>
  `;
}
