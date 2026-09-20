import { css } from 'lit';

/** Couleurs : **uniquement des jetons de thème.**
 *
 *  Pas de littéral hexadécimal, pas de `rgb()` : une couleur figée ici est
 *  illisible dans la moitié des thèmes installés, et le défaut ne se voit que
 *  chez celui qui n'utilise pas le même thème que l'auteur. Les contrastes
 *  reposent donc sur les paires que Home Assistant garantit
 *  (`--primary-text-color` sur `--card-background-color`), et les pastilles
 *  colorées ne portent jamais de texte.
 */
export const cardStyles = css`
  :host {
    display: block;
  }

  ha-card {
    padding: 0;
    overflow: hidden;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 8px;
  }

  .title {
    font-size: 1.15rem;
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .count {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .notice {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 16px 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font-size: 0.85rem;
  }

  .notice ha-icon {
    --mdc-icon-size: 18px;
    color: var(--warning-color);
    flex: 0 0 auto;
  }

  .empty {
    padding: 8px 16px 20px;
    color: var(--secondary-text-color);
  }

  .mount {
    padding: 12px 16px;
    border-top: 1px solid var(--divider-color);
  }

  .mount:first-of-type {
    border-top: none;
  }

  .row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  /* La pastille ne porte jamais de texte : sa couleur est un renfort, et le
     libellé à côté porte l'information. Une pastille seule serait illisible
     pour un daltonien, et le contraste ne distingue pas trois états. */
  .dot {
    flex: 0 0 auto;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--dot-color, var(--disabled-text-color));
  }

  .name {
    font-weight: 500;
    color: var(--primary-text-color);
  }

  .path {
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
  }

  .addons,
  .meta {
    margin-top: 4px;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  .error {
    margin-top: 6px;
    font-size: 0.85rem;
    color: var(--error-color);
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 10px;
  }

  mwc-button[disabled] {
    opacity: 0.5;
  }

  .history {
    margin-top: 8px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .history summary {
    cursor: pointer;
    user-select: none;
  }

  .history table {
    margin-top: 6px;
    border-collapse: collapse;
    width: 100%;
  }

  .history td {
    padding: 2px 8px 2px 0;
    vertical-align: top;
  }

  .history .at {
    white-space: nowrap;
    font-family: var(--code-font-family, monospace);
  }

  .compact .row {
    align-items: center;
  }

  .compact .summary {
    color: var(--secondary-text-color);
    font-size: 0.85rem;
    margin-left: auto;
  }

  .loader {
    padding: 24px 16px;
    color: var(--secondary-text-color);
  }
`;
