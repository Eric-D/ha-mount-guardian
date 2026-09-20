import { mgLog } from '../version.js';

const MAX_RETRIES = 10;
const STEP_MS = 2000;
const CAP_MS = 15000;

/** Budget de retries pour une indisponibilité. Environ 100 s au total.
 *
 *  Au-delà, la carte cesse d'afficher son dernier rendu et le dit. Afficher
 *  indéfiniment une remédiation périmée sans aucun indice est exactement le
 *  comportement qu'on cherche à éviter : l'utilisateur croirait sa réparation
 *  en cours alors que Home Assistant ne répond plus. */
export class RetryScheduler {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private count = 0;

  constructor(private readonly cardName: string, private readonly fire: () => void) {}

  schedule(): void {
    if (this.timer) return;
    this.count++;
    if (this.count > MAX_RETRIES) return;
    const delay = Math.min(STEP_MS * this.count, CAP_MS);
    mgLog('info', this.cardName, 'Retry %d dans %dms…', this.count, delay);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.fire();
    }, delay);
  }

  /** Quota épuisé : plus aucun retry jusqu'au prochain reset(). */
  get exhausted(): boolean {
    return this.count > MAX_RETRIES;
  }

  reset(): void {
    this.count = 0;
    this.cancel();
  }

  cancel(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
