import { LitElement, html, type TemplateResult } from 'lit';
import { property, state } from 'lit/decorators.js';

import { DEFAULT_ENTITY, type HassLike, type MountGuardConfig } from './types.js';

const EDITOR_LABELS: Record<string, string> = {
  entity: 'Entité (capteur des remédiations)',
  title: 'Titre personnalisé',
  mounts: 'Montages affichés (vide = tous)',
  show_ok: 'Afficher les montages sains',
  show_history: "Afficher l'historique",
  compact: 'Mode compact (tableau de bord mural)',
};

// Constante de module : si l'identité du tableau change à chaque rendu,
// ha-form se reconstruit entièrement et le champ en cours de saisie perd le
// focus à chaque frappe.
const EDITOR_SCHEMA = [
  {
    name: 'entity',
    required: true,
    selector: { entity: { domain: 'sensor', integration: 'addon_mount_guard' } },
  },
  { name: 'title', selector: { text: {} } },
  { name: 'mounts', selector: { text: { multiple: true } } },
  { name: 'show_ok', selector: { boolean: {} } },
  { name: 'show_history', selector: { boolean: {} } },
  { name: 'compact', selector: { boolean: {} } },
] as const;

const computeEditorLabel = (s: { name: string }): string => EDITOR_LABELS[s.name] ?? s.name;

interface ValueChangedEvent extends CustomEvent {
  detail: { value: MountGuardConfig };
}

export class MountGuardCardEditor extends LitElement {
  @property({ attribute: false }) public hass?: HassLike;

  @state() private _config: MountGuardConfig = { entity: DEFAULT_ENTITY };

  public setConfig(config: MountGuardConfig): void {
    this._config = config ?? { entity: DEFAULT_ENTITY };
  }

  protected override createRenderRoot(): HTMLElement {
    // Light DOM : indispensable pour que ha-form trouve les selectors HA.
    return this;
  }

  protected override render(): TemplateResult {
    if (!this.hass) return html``;
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${EDITOR_SCHEMA}
        .computeLabel=${computeEditorLabel}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `;
  }

  private _valueChanged(ev: ValueChangedEvent): void {
    const next = { ...ev.detail.value } as Record<string, unknown>;
    for (const key of Object.keys(next)) {
      // 'entity' n'est JAMAIS supprimée : ha-form émet `undefined` quand on
      // vide le champ, et une config sans clé 'entity' cassait définitivement
      // la carte sur le dépôt dont celui-ci reprend les conventions —
      // `setConfig` levait, Home Assistant la remplaçait par sa carte d'erreur
      // et il n'y avait plus aucun moyen de revenir en arrière depuis
      // l'interface. `setConfig` tolère aussi, en second rempart : les DEUX
      // sont nécessaires, retirer l'un en croyant l'autre suffisant restaure
      // la panne.
      if (key === 'entity') {
        if (typeof next[key] !== 'string') next[key] = '';
        continue;
      }
      const value = next[key];
      // `false` est légitime pour les trois interrupteurs : `show_ok: false`
      // est précisément ce que règle quelqu'un qui ne veut voir que les
      // problèmes. Un test de véracité le supprimerait, et la carte
      // reprendrait son défaut à `true`.
      if (value === '' || value === undefined || value === null) delete next[key];
      if (Array.isArray(value) && value.length === 0) delete next[key];
    }
    this.dispatchEvent(
      new CustomEvent('config-changed', {
        detail: { config: next },
        bubbles: true,
        composed: true,
      })
    );
  }
}

// Même garde idempotente que la carte : sur WebView Android, le script peut
// être ré-évalué au retour de veille.
if (!customElements.get('mount-guard-card-editor')) {
  customElements.define('mount-guard-card-editor', MountGuardCardEditor);
}
