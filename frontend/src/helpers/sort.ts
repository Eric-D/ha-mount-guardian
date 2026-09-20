import type { MountGuardConfig, Remediation } from '../types.js';

/** Gravité, pour le tri. Plus haut = plus haut dans la liste.
 *
 *  `repairing` avant `pending` : ce qui se passe maintenant passe avant ce qui
 *  va se passer. `degraded` ensuite, parce qu'il appelle une action humaine
 *  (rallumer le NAS) alors que les deux premiers n'en appellent aucune. */
const RANK: Record<string, number> = {
  repairing: 3,
  pending: 2,
  degraded: 1,
  ok: 0,
};

export function severity(remediation: Remediation): number {
  return RANK[remediation.state] ?? 0;
}

/** Les lignes à afficher, dans l'ordre.
 *
 *  Le tri est stable à gravité égale — sur le nom du montage — et c'est
 *  volontaire : sans second critère, deux montages sains changeraient de place
 *  à chaque rendu selon l'ordre de l'objet reçu, et la carte clignoterait.
 */
export function visibleMounts(
  remediations: readonly Remediation[],
  config: Pick<MountGuardConfig, 'mounts' | 'show_ok'>
): Remediation[] {
  const filter = config.mounts;
  const showOk = config.show_ok !== false;

  return remediations
    .filter((rem) => !filter || filter.length === 0 || filter.includes(rem.mount))
    .filter((rem) => showOk || rem.state !== 'ok')
    .slice()
    .sort((a, b) => severity(b) - severity(a) || a.mount.localeCompare(b.mount));
}

/** Y a-t-il quelque chose à montrer, tout filtre appliqué ?
 *
 *  Distinct de `visibleMounts(...).length === 0` à l'appel : la carte doit
 *  distinguer « aucun montage configuré » de « tout va bien, et vous avez
 *  demandé à masquer ce qui va bien ». Les deux donnent une liste vide et
 *  appellent deux messages différents. */
export function emptyReason(
  remediations: readonly Remediation[],
  config: Pick<MountGuardConfig, 'mounts' | 'show_ok'>
): 'none-configured' | 'all-healthy' | null {
  if (remediations.length === 0) return 'none-configured';
  if (visibleMounts(remediations, config).length === 0) return 'all-healthy';
  return null;
}
