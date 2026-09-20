/** En-tête, bandeaux, messages vides. */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import {
  renderEmpty,
  renderHeader,
  renderLoader,
  renderNotice,
} from '../src/renders/chrome.ts';
import { mount, text } from './helpers.ts';

describe('renderHeader', () => {
  test('le titre et le compte ne sont pas intervertis', () => {
    const host = mount(renderHeader({ title: 'Montages surveillés', count: 2 }));
    assert.equal(text(host, '.title'), 'Montages surveillés');
    assert.match(text(host, '.count'), /2 remédiations en cours/);
  });

  test('le pluriel suit le compte', () => {
    assert.match(text(mount(renderHeader({ title: 't', count: 1 })), '.count'), /1 remédiation en/);
    assert.equal(text(mount(renderHeader({ title: 't', count: 0 })), '.count'), 'aucune remédiation');
  });
});

describe('renderNotice', () => {
  test('rien à dire, rien de rendu', () => {
    // Un bandeau vide occuperait une ligne et apprendrait à ignorer les
    // bandeaux.
    assert.equal(mount(renderNotice(null)).querySelector('.notice'), null);
  });

  test('le message est rendu comme du TEXTE', () => {
    // Jamais `unsafeHTML` : ce qui arrive ici vient de `last_error`, donc du
    // backend, donc potentiellement d'un message d'erreur système.
    const host = mount(renderNotice('<b>injection</b>'));
    assert.equal(host.querySelector('.notice b'), null);
    assert.match(text(host, '.notice'), /<b>injection<\/b>/);
  });

  test('le bandeau est annoncé aux lecteurs d’écran', () => {
    const notice = mount(renderNotice('perdu')).querySelector('.notice') as HTMLElement;
    assert.equal(notice.getAttribute('role'), 'status');
  });
});

describe('renderLoader', () => {
  test('rend toujours une ha-card visible', () => {
    // Pas parce que Home Assistant inspecterait le shadow root — il ne le
    // fait pas — mais parce qu'un rendu vide ne distingue pas une carte qui
    // charge d'une carte cassée.
    const host = mount(renderLoader('En attente…'));
    assert.ok(host.querySelector('ha-card'));
    assert.equal(text(host, '.loader'), 'En attente…');
  });
});

describe('renderEmpty', () => {
  test('les deux raisons donnent deux messages différents', () => {
    // L'une demande d'ajouter un add-on, l'autre dit que tout va bien.
    const none = text(mount(renderEmpty('none-configured')), '.empty');
    const healthy = text(mount(renderEmpty('all-healthy')), '.empty');
    assert.notEqual(none, healthy);
    assert.match(none, /Ajoutez/);
  });
});
