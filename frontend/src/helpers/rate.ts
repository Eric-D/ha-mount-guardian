import type { Remediation } from '../types.js';

export interface Rate {
  bytesPerSecond: number;
  /** Secondes restantes estimées, ou null quand on ne peut pas conclure. */
  etaSeconds: number | null;
}

interface Sample {
  /** Identifie la tentative en cours : un nouveau `started_at` remet tout à
      zéro, sinon on moyennerait deux rapatriements différents. */
  startedAt: string | null;
  at: number;
  bytes: number;
}

/** Débit et temps restant, mesurés côté carte.
 *
 *  **Côté carte et non côté backend**, parce que le backend n'a rien à en
 *  dire de plus : il publierait le même calcul, au prix d'un champ de plus
 *  dans le contrat et d'un miroir de plus à tenir d'accord.
 *
 *  La mesure part du premier échantillon vu **pour cette tentative**, pas de
 *  `started_at` : celui-ci couvre aussi l'arrêt des add-ons, la mise de côté
 *  et le rechargement, qui ne transfèrent aucun octet. Les inclure
 *  sous-estimerait le débit d'autant, et sur une séquence où l'arrêt d'un
 *  Frigate prend trente secondes, l'estimation annoncerait le double du temps
 *  réel dès les premières minutes.
 */
export class RateTracker {
  private samples = new Map<string, Sample>();

  /** Rend le débit, ou null tant qu'on n'a pas de quoi conclure. */
  measure(remediation: Remediation, now: number): Rate | null {
    const { mount, started_at: startedAt, bytes_done: bytes, bytes_total: total } = remediation;
    const previous = this.samples.get(mount);

    if (!previous || previous.startedAt !== startedAt) {
      this.samples.set(mount, { startedAt, at: now, bytes });
      return null;
    }

    const seconds = (now - previous.at) / 1000;
    const transferred = bytes - previous.bytes;
    // Une seconde de recul au minimum : sur un intervalle plus court, le bruit
    // d'échantillonnage fait sauter l'estimation d'un facteur dix, et un temps
    // restant qui saute est pire que pas de temps restant du tout.
    if (seconds < 1 || transferred <= 0) return null;

    const bytesPerSecond = transferred / seconds;
    const remaining = total - bytes;
    return {
      bytesPerSecond,
      etaSeconds: remaining > 0 ? remaining / bytesPerSecond : null,
    };
  }

  /** Oublie un montage dont la remédiation est finie. Sans ça, une carte
      laissée ouverte une semaine garderait un échantillon par montage réparé. */
  forget(mount: string): void {
    this.samples.delete(mount);
  }
}
