/** Miroir TypeScript du contrat défini dans `custom_components/addon_mount_guard/models.py`.

    `tests/test_models.py` croise les deux : les clés de chaque interface et les
    littéraux de chaque union doivent coïncider avec la définition Python. Un
    état ajouté côté backend et oublié ici se rendrait en pastille grise sans
    libellé, ce qu'aucun typage ne voit — les deux fichiers sont dans deux
    langages, et rien d'autre ne les relie.

    Aucun champ n'est optionnel : le backend sérialise la dataclasse entière à
    chaque envoi, donc tout est toujours présent. Les typer `?:` inviterait des
    `??` qui masqueraient un champ réellement disparu. */

/** État d'un montage.

    `degraded` et `pending` ne se confondent pas, et c'est la distinction dont
    dépend toute la gestion des add-ons partagés :

    - `degraded` : le NAS ne répond pas, l'add-on écrit en local, c'est le
      comportement voulu. Il n'y a rien à faire qu'attendre.
    - `pending` : le NAS a répondu, la réparation est due mais n'a pas commencé
      (verrou tenu par un autre montage, ou réessai programmé). */
export type MountState = 'ok' | 'degraded' | 'pending' | 'repairing';

export type Mode = 'local_fallback' | 'stop_only';

/** `rolling_back` n'est pas une sixième étape : c'est l'échec de `restoring`,
    et il porte le même `step_index`. */
export type Step =
  | 'stopping'
  | 'stashing'
  | 'reloading'
  | 'restoring'
  | 'rolling_back'
  | 'starting';

/** `held` : arrêté, et maintenu arrêté parce qu'un AUTRE montage de cet add-on
    attend sa réparation. Sans ce mot, la carte n'afficherait qu'« arrêté » sur
    un add-on dont l'utilisateur vient de voir un voisin redémarrer. */
export type AddonState = 'started' | 'stopped' | 'held' | 'unknown';

export interface RemediationAddon {
  slug: string;
  name: string;
  state: AddonState;
}

export interface RemediationTransition {
  at: string;
  from: string;
  to: string;
  step: string | null;
  error: string | null;
}

export interface Remediation {
  mount: string;
  path: string;
  state: MountState;
  mode: Mode;
  step: Step | null;
  step_index: number;
  step_count: number;
  started_at: string | null;
  updated_at: string | null;
  addons: RemediationAddon[];
  files_total: number;
  files_done: number;
  bytes_total: number;
  bytes_done: number;
  current_file: string | null;
  next_retry_at: string | null;
  last_error: string | null;
  last_incident_at: string | null;
  history: RemediationTransition[];
}

// --- configuration de la carte ------------------------------------------
//
// Rien de ce qui suit ne fait partie du contrat croisé avec Python : ce sont
// les réglages du YAML, que seul l'utilisateur écrit.

/** Entité par défaut. Écrite ici et pas dans `card.ts` pour que l'éditeur et la
    carte proposent exactement la même, sans que personne n'ait à se souvenir de
    changer les deux. */
export const DEFAULT_ENTITY = 'sensor.mount_guard_remediations';

export interface MountGuardConfig {
  type?: string;
  entity: string;
  title?: string;
  /** Montages affichés. Absent = tous. */
  mounts?: string[];
  /** Afficher les montages sains. Vrai par défaut : masquer ce qui va bien
      donne une carte vide en temps normal, et une carte vide ressemble à une
      carte cassée. */
  show_ok?: boolean;
  /** Journal repliable sous chaque ligne. */
  show_history?: boolean;
  /** Une ligne par montage, sans stepper ni barre — pour une tablette murale,
      où la hauteur est la ressource rare. */
  compact?: boolean;
}

export interface RemediationsAttributes {
  remediations?: Remediation[];
}

export interface HassEntityState {
  state: string;
  attributes: Record<string, unknown>;
}

/** Ce que la carte utilise de `hass`. Volontairement étroit : un type large
    invite à s'en servir, et chaque usage supplémentaire est une chose de plus
    à simuler dans les tests. */
export interface HassLike {
  states: Record<string, HassEntityState | undefined>;
  callService: (
    domain: string,
    service: string,
    serviceData?: Record<string, unknown>
  ) => Promise<unknown>;
  connection?: {
    subscribeMessage: (
      callback: (message: { remediation?: Remediation }) => void,
      subscription: { type: string }
    ) => Promise<() => void>;
  };
}
