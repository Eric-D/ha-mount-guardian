import { html, nothing, type TemplateResult } from 'lit';

/** Rendus purement présentatifs : ils ne touchent pas à l'état de la carte et
 *  reçoivent leurs gestionnaires en paramètres.
 *
 *  Les signatures à plusieurs paramètres passent par un objet nommé. Deux
 *  chaînes adjacentes dans une signature positionnelle s'inversent sans que le
 *  typage ni le linter ne disent quoi que ce soit — et le rendu reste
 *  parfaitement lisible, avec le mauvais texte.
 */

export function renderHeader({
  title,
  count,
}: {
  title: string;
  count: number;
}): TemplateResult {
  return html`
    <div class="header">
      <div class="title">${title}</div>
      <div class="count">
        ${count === 0
          ? 'aucune remédiation'
          : `${count} remédiation${count > 1 ? 's' : ''} en cours`}
      </div>
    </div>
  `;
}

export function renderNotice(message: string | null): TemplateResult | typeof nothing {
  if (!message) return nothing;
  return html`
    <div class="notice" role="status">
      <ha-icon icon="mdi:alert-outline"></ha-icon><span>${message}</span>
    </div>
  `;
}

/** Le loader est un `<ha-card>` visible, pas un rendu vide.
 *
 *  Pas parce que Home Assistant inspecterait le shadow root — il ne le fait
 *  pas — mais parce qu'un rendu vide ne donne à l'utilisateur aucune
 *  information : il ne distingue pas une carte qui charge d'une carte cassée. */
export function renderLoader(message: string): TemplateResult {
  return html`<ha-card><div class="loader">${message}</div></ha-card>`;
}

export function renderEmpty(reason: 'none-configured' | 'all-healthy'): TemplateResult {
  return html`
    <div class="empty">
      ${reason === 'none-configured'
        ? "Aucun add-on surveillé. Ajoutez-en un depuis la fiche de l'intégration."
        : 'Tous les montages sont opérationnels.'}
    </div>
  `;
}
