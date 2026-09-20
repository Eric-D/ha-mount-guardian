import { LitElement, html, type PropertyValues, type TemplateResult } from 'lit';
import { state } from 'lit/decorators.js';

import { RetryScheduler } from './helpers/retry.js';
import { emptyReason, visibleMounts } from './helpers/sort.js';
import { merge, RemediationFeed } from './helpers/subscribe.js';
import { renderEmpty, renderHeader, renderLoader, renderNotice } from './renders/chrome.js';
import { renderMountRow } from './renders/mount-row.js';
import { cardStyles } from './styles/card.js';
import { stepperStyles } from './styles/stepper.js';
import {
  DEFAULT_ENTITY,
  type HassEntityState,
  type HassLike,
  type MountGuardConfig,
  type Remediation,
  type RemediationsAttributes,
} from './types.js';
import { logBanner, mgLog } from './version.js';

import './editor.js';

interface GridOptions {
  columns: number;
  min_columns: number;
  rows: number | 'auto';
  min_rows: number;
}

/** Cadence de rafraîchissement de l'horloge.
 *
 *  La seconde, parce que la carte affiche un temps écoulé et un compte à
 *  rebours : à la minute, le rebours resterait figé sur « 01:47 » pendant
 *  soixante secondes et donnerait l'impression que rien ne se passe. C'est le
 *  seul timer de cet élément, et `disconnectedCallback` l'annule. */
const TICK_MS = 1000;

export class MountGuardCard extends LitElement {
  static override styles = [cardStyles, stepperStyles];

  public static getConfigElement(): HTMLElement {
    return document.createElement('mount-guard-card-editor');
  }

  public static getStubConfig(): MountGuardConfig {
    return { entity: DEFAULT_ENTITY };
  }

  public set hass(value: HassLike | undefined) {
    this._hass = value;
    // Aucune garde d'égalité, et ce n'est pas un oubli : un early-return
    // sauterait `_syncEntityState()` et laisserait l'état vide au premier
    // rendu. `requestUpdate()`, que Lit appelle après ce setter, filtre déjà
    // par `notEqual`. Le filtrage des re-rendus vit dans `shouldUpdate`.
    this._syncEntityState();
    void this._feed.connect(value);
  }

  public get hass(): HassLike | undefined {
    return this._hass;
  }

  @state() private _config?: MountGuardConfig;
  @state() private _now = Date.now();

  private static _instances = 0;
  private readonly _id = ++MountGuardCard._instances;

  private _hass?: HassLike;
  private _entityState?: HassEntityState;
  private _renderedEntityState?: HassEntityState;
  private _live = new Map<string, Remediation>();
  private _retry = new RetryScheduler('card', () => this.requestUpdate());
  private _feed = new RemediationFeed(
    (remediation) => {
      this._live.set(remediation.mount, remediation);
      this.requestUpdate();
    },
    () => this.requestUpdate()
  );
  private _tick: ReturnType<typeof setInterval> | null = null;
  private _lastTemplate?: TemplateResult;
  private _firstUpdateLogged = false;

  public setConfig(config: MountGuardConfig): void {
    // Seule une configuration non-objet est bloquante. Tout le reste est
    // tolérant, pour ne jamais casser un tableau de bord sur un champ
    // optionnel mal renseigné ; les anomalies partent dans la console.
    if (!config || typeof config !== 'object') {
      mgLog('error', 'card', 'setConfig rejeté, config non-objet : %o', config);
      throw new Error('Configuration manquante ou invalide');
    }

    // 'entity' absente, nulle ou vide = état transitoire légitime : stub du
    // sélecteur de cartes, éditeur ouvert avant sélection, « entity: » sans
    // valeur en YAML qui parse en null. La convention Home Assistant veut
    // qu'on lève ; ici ça rendait la carte irrécupérable depuis l'interface,
    // remplacée définitivement par « Erreur de configuration » et sans la
    // moindre trace console. On tolère, on loggue, et `_render` affiche un
    // loader explicite. L'éditeur recoerce de son côté : les deux remparts
    // sont nécessaires.
    let entity = DEFAULT_ENTITY;
    if (typeof config.entity === 'string' && config.entity !== '') {
      entity = config.entity;
    } else if (config.entity !== undefined && config.entity !== null && config.entity !== '') {
      mgLog(
        'error',
        'card',
        "'entity' doit être une chaîne, reçu %o — repli sur %s",
        config.entity,
        DEFAULT_ENTITY
      );
    }

    this._config = {
      ...config,
      entity,
      mounts: Array.isArray(config.mounts) ? config.mounts.map(String) : undefined,
    };
    this._syncEntityState();
    mgLog('info', 'card', '#%d setConfig accepté (entity=%s)', this._id, entity);
  }

  public getCardSize(): number {
    return 1 + this._remediations().length * 2;
  }

  public getGridOptions(): GridOptions {
    // `rows: 'auto'` : la hauteur dépend du nombre de montages, du mode
    // compact et de l'historique déplié. Un nombre figé couperait la dernière
    // ligne ou laisserait un bandeau vide sous la carte.
    return { columns: 12, min_columns: 6, rows: 'auto', min_rows: 2 };
  }

  public override connectedCallback(): void {
    super.connectedCallback();
    // Quota remis à zéro à chaque rattachement : une carte qui revient après
    // un changement de page repart avec son budget complet, sinon un onglet
    // laissé ouvert une journée finirait par ne plus jamais réessayer.
    this._retry.reset();
    this._tick = setInterval(() => {
      this._now = Date.now();
    }, TICK_MS);
    void this._feed.connect(this._hass);
  }

  public override disconnectedCallback(): void {
    // AUCUN timer lié à cet élément ne survit à son détachement, et la
    // souscription WebSocket non plus : une carte détachée qui continue de
    // recevoir des messages garde en vie tout son arbre de rendu.
    this._retry.cancel();
    if (this._tick) {
      clearInterval(this._tick);
      this._tick = null;
    }
    this._feed.disconnect();
    super.disconnectedCallback();
  }

  protected override shouldUpdate(changed: PropertyValues): boolean {
    // `_config` doit toujours passer : il peut arriver dans le même lot qu'un
    // `hass` dont les états n'ont pas bougé, et le filtrer laisserait la carte
    // sur son ancienne configuration.
    if (changed.has('_config') || changed.has('_now')) return true;
    return this._entityState !== this._renderedEntityState;
  }

  protected override render(): TemplateResult {
    return this._render();
  }

  protected override updated(): void {
    this._renderedEntityState = this._entityState;
    if (!this._firstUpdateLogged) {
      this._firstUpdateLogged = true;
      mgLog('info', 'card', '#%d premier rendu effectué à t=%dms', this._id,
        Math.round(performance.now()));
    }
    // Contrat public pour les greffons tiers — card-mod notamment — sans
    // aucun consommateur dans ce dépôt. Rien en CI ne détecterait sa
    // suppression.
    this.dispatchEvent(
      new CustomEvent('mount-guard-card-update', { bubbles: true, composed: true })
    );
  }

  private _syncEntityState(): void {
    const entity = this._config?.entity;
    this._entityState = entity ? this._hass?.states[entity] : undefined;
  }

  private _remediations(): Remediation[] {
    const attributes = (this._entityState?.attributes ?? {}) as RemediationsAttributes;
    const base = Array.isArray(attributes.remediations) ? attributes.remediations : [];
    // Le flux temps réel par-dessus l'attribut, fusionné PAR MONTAGE : les deux
    // sources n'ordonnent rien de la même façon.
    return merge(base, this._live);
  }

  private _call(service: string, mount: string): void {
    void this._hass
      ?.callService('addon_mount_guard', service, { mount })
      .catch((err: unknown) => mgLog('error', 'card', '%s(%s) : %o', service, mount, err));
  }

  private _render(): TemplateResult {
    const config = this._config;
    if (!config) return renderLoader('Carte en attente de configuration…');

    const states = this._hass?.states;
    if (!states) {
      // Home Assistant n'a pas encore fourni ses états. On garde le dernier
      // rendu TANT QU'IL RESTE DES RETRIES ; au-delà, message explicite —
      // afficher indéfiniment une remédiation périmée sans aucun indice est
      // le comportement qu'on cherche à éviter.
      this._retry.schedule();
      if (this._lastTemplate && !this._retry.exhausted) return this._lastTemplate;
      return renderLoader('En attente de Home Assistant…');
    }

    if (!this._entityState) {
      this._retry.schedule();
      if (this._lastTemplate && !this._retry.exhausted) return this._lastTemplate;
      return renderLoader(`Entité ${config.entity} introuvable.`);
    }

    if (this._entityState.state === 'unavailable') {
      this._retry.schedule();
      if (this._lastTemplate && !this._retry.exhausted) return this._lastTemplate;
      return renderLoader(`Entité ${config.entity} indisponible.`);
    }

    this._retry.reset();

    const remediations = this._remediations();
    const visible = visibleMounts(remediations, config);
    const reason = emptyReason(remediations, config);
    const running = remediations.filter(
      (rem) => rem.state === 'repairing' || rem.state === 'pending'
    ).length;

    const template = html`
      <ha-card>
        ${renderHeader({ title: config.title ?? 'Montages surveillés', count: running })}
        ${renderNotice(this._noticeMessage())}
        ${reason
          ? renderEmpty(reason)
          : visible.map((remediation) =>
              renderMountRow({
                remediation,
                now: this._now,
                showHistory: config.show_history === true,
                compact: config.compact === true,
                onRepair: (mount) => this._call('repair', mount),
                onCancel: (mount) => this._call('cancel', mount),
              })
            )}
      </ha-card>
    `;
    this._lastTemplate = template;
    return template;
  }

  private _noticeMessage(): string | null {
    // Seulement quand la souscription a fonctionné PUIS a été perdue. Sur une
    // installation où le WebSocket n'a jamais répondu — version ancienne,
    // intégration non chargée — un bandeau permanent apprendrait à l'ignorer,
    // alors que la carte fonctionne très bien sur l'attribut du capteur.
    if (this._feed.lost && !this._feed.active) {
      return 'Connexion temps réel perdue — données du dernier relevé.';
    }
    return null;
  }
}

// Force Home Assistant à charger ses définitions d'éléments personnalisés
// (ha-card, ha-form…). Sans cet appel, sur un chargement à froid, notre carte
// est enregistrée avant que HA ait défini ha-card, ce qui produit un rendu
// cassé.
void (window as unknown as { loadCardHelpers?: () => Promise<unknown> })
  .loadCardHelpers?.()
  .catch((e: unknown) => {
    mgLog('warn', 'card', 'loadCardHelpers() a échoué : %o', e);
  });

const CARD_TAG = 'mount-guard-card';
const MAX_REREGISTRATIONS = 5;
let reregistrations = 0;

/**
 * Garantit que le tag est résolvable par le registre d'éléments personnalisés
 * *actuellement installé*.
 *
 * Home Assistant charge @webcomponents/scoped-custom-element-registry, qui
 * REMPLACE window.customElements par sa propre implémentation, avec sa propre
 * table. Si ce module s'enregistre avant l'installation du polyfill, la
 * définition atterrit dans le registre natif : le polyfill prend ensuite la
 * main et ne nous connaît pas. HA appelle customElements.get() → rien, et
 * affiche « Custom element doesn't exist ». Son rattrapage par whenDefined()
 * est mort-né pour la même raison.
 *
 * Symptôme observé, impossible autrement : customElements.get(tag) renvoie
 * undefined alors que document.createElement(tag) produit un élément upgradé
 * avec son setConfig — document.createElement consulte, lui, le registre natif.
 *
 * D'où l'intermittence, et son inversion apparente : c'est le chargement le
 * plus RAPIDE qui échoue, le polyfill s'installant vers 110–130 ms.
 */
function ensureRegisteredInCurrentRegistry(): boolean {
  if (customElements.get(CARD_TAG)) return false;
  if (reregistrations >= MAX_REREGISTRATIONS) return false;
  reregistrations++;
  try {
    // Constructeur neuf obligatoire : une même classe ne peut pas être
    // enregistrée deux fois, y compris dans un registre différent.
    customElements.define(CARD_TAG, class extends MountGuardCard {});
    mgLog(
      'warn',
      'card',
      "ré-enregistré à t=%dms : le registre d'éléments personnalisés avait été remplacé depuis le premier enregistrement",
      Math.round(performance.now())
    );
    return true;
  } catch (e) {
    mgLog('error', 'card', 'ré-enregistrement impossible : %o', e);
    return false;
  }
}

// Garde idempotente : sur WebView Android, le script peut être ré-évalué au
// retour de veille. Sans elle, customElements.define lève « already defined »
// et la carte est définitivement cassée.
if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, MountGuardCard);
  mgLog('info', 'card', 'élément enregistré à t=%dms', Math.round(performance.now()));
} else {
  mgLog('info', 'card', 'module déjà enregistré, ce chargement est ignoré');
}

/**
 * Répare les cartes d'erreur laissées orphelines par le rattrapage de HA.
 *
 * Quand HA construit la vue avant que ce module ne soit évalué, il fabrique une
 * carte « Custom element doesn't exist: mount-guard-card. », puis arme
 * customElements.whenDefined(tag) pour émettre 'll-rebuild' et la reconstruire.
 * Mais whenDefined se résout dans une microtâche : si notre définition arrive
 * juste après la création de la carte d'erreur, l'événement part avant que
 * hui-card n'ait attaché son écouteur, et se perd. Le setTimeout de 2 s de HA
 * révèle alors l'erreur définitivement.
 *
 * On réémet donc 'll-rebuild' nous-mêmes, plus tard, quand l'écouteur est en
 * place. Ciblé sur les seules cartes d'erreur qui nomment notre tag : une fois
 * reconstruites elles disparaissent, donc aucune boucle possible.
 */
function repairOrphanErrorCards(): number {
  let repaired = 0;
  const walk = (node: Element): void => {
    if (node.localName === 'hui-error-card') {
      const holder = node as unknown as {
        _config?: { message?: string };
        config?: { message?: string };
      };
      const message = (holder._config ?? holder.config)?.message ?? '';
      if (message.includes(CARD_TAG)) {
        node.dispatchEvent(new CustomEvent('ll-rebuild', { bubbles: true, composed: true }));
        repaired++;
      }
      return;
    }
    for (const child of [...(node.shadowRoot?.children ?? []), ...node.children]) {
      walk(child as Element);
    }
  };
  if (document.body) walk(document.body);
  return repaired;
}

// Plusieurs passes avant le seuil de 2 s à partir duquel HA rend l'erreur
// visible : la vue peut aussi se construire juste après notre définition. Ces
// timers ne dépendent d'aucun élément et ne sont annulés par rien — légitime,
// ils sont à usage unique et plafonnés à quatre secondes.
for (const delay of [0, 50, 150, 400, 1000, 2000, 4000]) {
  window.setTimeout(() => {
    try {
      // D'abord le registre : réémettre 'll-rebuild' ne sert à rien tant que HA
      // ne sait pas résoudre le tag.
      ensureRegisteredInCurrentRegistry();
      const repaired = repairOrphanErrorCards();
      if (repaired > 0) {
        mgLog(
          'warn',
          'card',
          "%d carte(s) d'erreur reconstruite(s) après %dms",
          repaired,
          delay
        );
      }
    } catch (e) {
      mgLog('error', 'card', "réparation des cartes d'erreur impossible : %o", e);
    }
  }, delay);
}

// Nécessaire au sélecteur de cartes. Rien en CI ne détecterait sa suppression.
interface CustomCard {
  type: string;
  name: string;
  description: string;
}
const w = window as unknown as { customCards?: CustomCard[] };
w.customCards = w.customCards ?? [];
if (!w.customCards.some((c) => c.type === CARD_TAG)) {
  w.customCards.push({
    type: CARD_TAG,
    name: 'Add-on Mount Guard',
    description: 'Suit les remédiations des stockages réseau tombés sous les add-ons',
  });
}

logBanner();
