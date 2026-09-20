import type { Remediation } from '../types.js';

export interface Progress {
  /** 0 à 1, ou null quand le total n'est pas connu. */
  ratio: number | null;
  filesDone: number;
  filesTotal: number;
  bytesDone: number;
  bytesTotal: number;
}

/** Avancement du rapatriement.
 *
 *  Calculé sur les OCTETS et non sur les fichiers : mille vignettes et un
 *  enregistrement d'une heure font 1001 fichiers, dont un seul pèse. Une barre
 *  en fichiers sauterait à 99 % en deux secondes puis n'avancerait plus
 *  pendant dix minutes — le comportement qui fait croire à un blocage.
 *
 *  Repli sur les fichiers quand `bytes_total` vaut 0 : c'est le cas d'un
 *  rapatriement de fichiers vides, rare mais légitime, où une barre figée à
 *  zéro serait le seul retour.
 */
export function progressOf(remediation: Remediation): Progress {
  const { files_done: filesDone, files_total: filesTotal } = remediation;
  const { bytes_done: bytesDone, bytes_total: bytesTotal } = remediation;

  let ratio: number | null = null;
  if (bytesTotal > 0) ratio = bytesDone / bytesTotal;
  else if (filesTotal > 0) ratio = filesDone / filesTotal;

  return {
    // Borné : `files_done` peut dépasser le total quand des fichiers
    // apparaissent pendant la copie, et une barre à 140 % déborde de la carte.
    ratio: ratio === null ? null : Math.min(Math.max(ratio, 0), 1),
    filesDone,
    filesTotal,
    bytesDone,
    bytesTotal,
  };
}

export function percent(ratio: number | null): string {
  return ratio === null ? '' : `${Math.round(ratio * 100)} %`;
}
