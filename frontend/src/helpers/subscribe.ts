import type { HassLike, Remediation } from '../types.js';
import { mgLog } from '../version.js';

export const SUBSCRIBE_TYPE = 'addon_mount_guard/subscribe';

/** Souscription au flux de progression, avec repli silencieux.
 *
 *  **Le WebSocket est un raccourci, jamais une dépendance.** L'attribut du
 *  capteur porte déjà tout le contrat ; il arrive simplement au relevé suivant,
 *  jusqu'à une minute plus tard. Si la souscription échoue — intégration non
 *  chargée, connexion coupée, version du backend antérieure à la commande — la
 *  carte doit continuer de fonctionner avec l'attribut seul.
 *
 *  D'où la forme de cette classe : elle ne lève jamais, elle signale. Une
 *  souscription qui lèverait dans `connectedCallback` laisserait la carte à
 *  moitié montée, sans rendu et sans message.
 */
export class RemediationFeed {
  private unsubscribe: (() => void) | null = null;
  private generation = 0;
  /** Vrai dès qu'une souscription a réussi puis a été perdue. C'est ce qui
      distingue « pas de temps réel ici » de « le temps réel est tombé », et
      seul le second mérite un bandeau. */
  public lost = false;

  constructor(
    private readonly onRemediation: (remediation: Remediation) => void,
    private readonly onStateChange: () => void
  ) {}

  get active(): boolean {
    return this.unsubscribe !== null;
  }

  async connect(hass: HassLike | undefined): Promise<void> {
    if (this.unsubscribe || !hass?.connection?.subscribeMessage) return;
    const generation = ++this.generation;
    try {
      const unsubscribe = await hass.connection.subscribeMessage(
        (message) => {
          if (message?.remediation) this.onRemediation(message.remediation);
        },
        { type: SUBSCRIBE_TYPE }
      );
      // La carte a pu être détachée pendant l'attente : sans cette garde, on
      // garderait une souscription vivante sur un élément qui n'est plus dans
      // le document, et elle ne serait jamais fermée.
      if (generation !== this.generation) {
        unsubscribe();
        return;
      }
      this.unsubscribe = unsubscribe;
      this.lost = false;
    } catch (err) {
      this.lost = this.lost || false;
      mgLog('warn', 'feed', 'souscription impossible, repli sur le capteur : %o', err);
    }
    this.onStateChange();
  }

  disconnect(): void {
    this.generation++;
    if (!this.unsubscribe) return;
    try {
      this.unsubscribe();
    } catch (err) {
      mgLog('warn', 'feed', 'désabonnement en échec : %o', err);
    }
    this.unsubscribe = null;
  }

  /** Souscription perdue alors qu'elle avait fonctionné. */
  markLost(): void {
    this.unsubscribe = null;
    this.lost = true;
    this.onStateChange();
  }
}

/** Fusionne le flux temps réel dans la liste issue du capteur.
 *
 *  Par `mount`, jamais par position : l'attribut du capteur et le flux
 *  n'ordonnent rien de la même façon, et une fusion positionnelle écraserait
 *  la remédiation d'un montage avec celle d'un autre — silencieusement, et
 *  seulement quand plusieurs montages sont en panne à la fois.
 */
export function merge(
  base: readonly Remediation[],
  live: ReadonlyMap<string, Remediation>
): Remediation[] {
  const byMount = new Map<string, Remediation>();
  for (const remediation of base) byMount.set(remediation.mount, remediation);
  for (const [mount, remediation] of live) byMount.set(mount, remediation);
  return [...byMount.values()];
}
