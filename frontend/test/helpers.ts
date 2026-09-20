/** Outillage commun : rendre un TemplateResult et l'interroger comme du DOM.

On rend réellement plutôt que d'inspecter les `strings` et `values` du
TemplateResult. C'est ce qui permet de vérifier ce que ni `tsc` ni oxlint ne
voient : deux paramètres de même type inversés, et surtout un gestionnaire
branché sur le mauvais élément — un `@click` ne se distingue d'un autre qu'en le
déclenchant.

Le DOM est installé par `--import ./test/_setup.ts`, et non par un import ici :
les imports statiques d'un module de test sont évalués avant son corps, donc Lit
serait chargé avant que `HTMLElement` existe.
*/
import { render, type TemplateResult, type nothing } from 'lit';

import type { Remediation, RemediationAddon, RemediationTransition } from '../src/types.ts';

/** `nothing` est accepté : `renderNotice` et `renderHistory` le renvoient quand
    il n'y a rien à dire, et c'est un cas que les tests doivent pouvoir monter. */
export function mount(template: TemplateResult | typeof nothing): HTMLElement {
  const host = document.createElement('div');
  render(template, host);
  return host;
}

export function text(host: ParentNode, selector: string): string {
  const found = host.querySelector(selector);
  if (!found) throw new Error(`sélecteur introuvable : ${selector}`);
  return (found.textContent ?? '').replace(/\s+/g, ' ').trim();
}

export function all(host: ParentNode, selector: string): Element[] {
  return [...host.querySelectorAll(selector)];
}

export function click(host: ParentNode, selector: string): void {
  const found = host.querySelector(selector);
  if (!found) throw new Error(`sélecteur introuvable : ${selector}`);
  (found as HTMLElement).dispatchEvent(new Event('click', { bubbles: true }));
}

export function addon(overrides: Partial<RemediationAddon> = {}): RemediationAddon {
  return { slug: 'frigate', name: 'Frigate', state: 'started', ...overrides };
}

export function transition(
  overrides: Partial<RemediationTransition> = {}
): RemediationTransition {
  return {
    at: '2026-09-20T18:00:00+00:00',
    from: 'ok',
    to: 'degraded',
    step: null,
    error: null,
    ...overrides,
  };
}

/** Remédiation complète : chaque test ne surcharge que ce qu'il regarde.

    Typée, et non `as never` : si `Remediation` gagne un champ requis, c'est ici
    que ça doit se voir, à la compilation. */
export function remediation(overrides: Partial<Remediation> = {}): Remediation {
  return {
    mount: 'nas_media',
    path: '/media/nas_media',
    state: 'ok',
    mode: 'local_fallback',
    step: null,
    step_index: 0,
    step_count: 5,
    started_at: null,
    updated_at: null,
    addons: [],
    files_total: 0,
    files_done: 0,
    bytes_total: 0,
    bytes_done: 0,
    current_file: null,
    next_retry_at: null,
    last_error: null,
    last_incident_at: null,
    history: [],
    ...overrides,
  };
}
