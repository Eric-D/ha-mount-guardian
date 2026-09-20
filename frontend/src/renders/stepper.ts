import { html, type TemplateResult } from 'lit';

import { formatBytes, formatDuration, truncatePath } from '../helpers/format.js';
import { percent, type Progress } from '../helpers/progress.js';
import type { Rate } from '../helpers/rate.js';
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
  rate,
}: {
  progress: Progress;
  currentFile: string | null;
  /** null tant que le débit n'est pas mesurable : mieux vaut ne rien annoncer
      qu'une estimation qui saute d'un facteur dix. */
  rate: Rate | null;
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
        <span>${progress.filesDone} / ${progress.filesTotal} fichiers</span>
        <!-- Le pourcentage est celui des OCTETS : il est donc annoncé à côté
             des octets, et non collé au compteur de fichiers, où il se lisait
             comme le leur. Sur un corpus où quelques enregistrements pèsent
             l'essentiel, les deux ratios diffèrent d'un facteur cent. -->
        <span
          >${formatBytes(progress.bytesDone)} / ${formatBytes(progress.bytesTotal)}
          ${progress.ratio === null ? '' : `(${percent(progress.ratio)})`}</span
        >
      </div>
      ${rate
        ? html`<div class="numbers rate">
            <span>${formatBytes(rate.bytesPerSecond)}/s</span>
            <span
              >${rate.etaSeconds === null
                ? ''
                : `≈ ${formatDuration(rate.etaSeconds)} restantes`}</span
            >
          </div>`
        : ''}
      ${currentFile
        ? html`<div class="current" title=${currentFile}>${truncatePath(currentFile)}</div>`
        : ''}
    </div>
  `;
}
