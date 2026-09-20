/** DOM minimal pour Lit, sans navigateur ni Home Assistant.

  `--conditions=browser` est nécessaire côté runner : sans lui Node résout
  l'export « node » de Lit, qui suppose un rendu serveur et lève dès l'import.
*/
import { existsSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { fileURLToPath } from 'node:url';

import { Window } from 'happy-dom';

// Les sources importent leurs voisines en « .js », convention du dépôt —
// `moduleResolution` vaut `Bundler`, esbuild s'en accommode — mais le
// dépouillement de types de Node ne sait pas la suivre : il cherche un .js qui
// n'existe qu'après le build. On réécrit donc vers le .ts quand il existe, sans
// toucher aux sources pour les seuls tests.
registerHooks({
  resolve(specifier, context, nextResolve) {
    const parent = context.parentURL ?? '';
    // Restreint à nos propres fichiers : node_modules publie de vrais .js, et
    // sonder un .ts voisin y ferait lever la résolution au lieu de la laisser
    // suivre son cours.
    if (specifier.startsWith('.') && specifier.endsWith('.js') && parent.includes('/frontend/')) {
      const candidate = new URL(specifier.slice(0, -3) + '.ts', parent);
      if (existsSync(fileURLToPath(candidate))) {
        return { url: candidate.href, shortCircuit: true };
      }
    }
    return nextResolve(specifier, context);
  },
});

const window = new Window({ url: 'http://localhost' });

// Recopie en bloc plutôt qu'une liste : Lit touche des globales qu'on ne
// devine pas (Document, CSSStyleSheet, ShadyCSS…), et une liste incomplète
// échoue à l'import, loin de la cause.
//
// Node définit ses propres Event, CustomEvent, EventTarget, DOMException… que
// le DOM de happy-dom refuse (« parameter 1 is not of type Event »). Une règle
// plutôt qu'une liste de noms : tout ce qui, chez happy-dom, dérive de
// EventTarget ou d'Event doit l'emporter, sinon le premier test qui dispatche
// un événement échoue à cinquante lignes de la cause.
const belongsToTheEventFamily = (value: unknown): boolean => {
  if (typeof value !== 'function') return false;
  for (let proto: unknown = value; proto; proto = Object.getPrototypeOf(proto)) {
    if (proto === window.Event || proto === window.EventTarget) return true;
  }
  return false;
};

for (const key of Object.getOwnPropertyNames(window)) {
  const value = (window as unknown as Record<string, unknown>)[key];
  if (key in globalThis && !belongsToTheEventFamily(value)) continue;
  Object.defineProperty(globalThis, key, {
    configurable: true,
    get: () => (window as unknown as Record<string, unknown>)[key],
  });
}

for (const [key, value] of [['window', window], ['document', window.document]] as const) {
  Object.defineProperty(globalThis, key, { configurable: true, value });
}
