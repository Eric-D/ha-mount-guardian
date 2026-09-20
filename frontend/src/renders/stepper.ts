import { html, type TemplateResult } from 'lit';

import { formatBytes, truncatePath } from '../helpers/format.js';
import { percent, type Progress } from '../helpers/progress.js';
import type { StepCell } from '../helpers/steps.js';

/** Le stepper dessine **`step_count` cases**, pas la longueur de la séquence
 *  connue de la carte. C'est le backend qui fait foi : un désaccord doit se
 *  voir comme un stepper incomplet plutôt que se corriger en silence, sinon un
 *  mode ajouté côté Python s'afficherait avec les étapes d'un autre. */
export function renderStepper(cells: readonly StepCell[]): TemplateResult {
  return html`
    <div class="stepper" role="list">
      ${cells.map(
        (cell) => html`
          <div class="step ${cell.state}" role="listitem" aria-current=${cell.state === 'active'}>
            <div class="bar"></div>
            <div class="label" title=${cell.label}>${cell.label}</div>
          </div>
        `
      )}
    </div>
  `;
}

export function renderProgress({
  progress,
  currentFile,
}: {
  progress: Progress;
  currentFile: string | null;
}): TemplateResult {
  const width = progress.ratio === null ? 0 : progress.ratio * 100;
  return html`
    <div class="progress">
      <div
        class="track"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${Math.round(width)}
      >
        <div class="fill" style="width: ${width}%"></div>
      </div>
      <div class="numbers">
        <span
          >${progress.filesDone} / ${progress.filesTotal} fichiers
          ${progress.ratio === null ? '' : `(${percent(progress.ratio)})`}</span
        >
        <span>${formatBytes(progress.bytesDone)} / ${formatBytes(progress.bytesTotal)}</span>
      </div>
      ${currentFile
        ? html`<div class="current" title=${currentFile}>${truncatePath(currentFile)}</div>`
        : ''}
    </div>
  `;
}
