/** Avancement du rapatriement.
 *
 * La barre est ce que l'utilisateur regarde pendant deux minutes. Une barre qui
 * saute à 99 % puis n'avance plus est indiscernable d'un blocage.
 */
import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { percent, progressOf } from '../src/helpers/progress.ts';
import { remediation } from './helpers.ts';

describe('progressOf', () => {
  test('la progression se calcule sur les OCTETS', () => {
    // Mille vignettes et un enregistrement d'une heure font 1001 fichiers,
    // dont un seul pèse. En fichiers, la barre sauterait à 99 % en deux
    // secondes puis n'avancerait plus pendant dix minutes.
    const progress = progressOf(
      remediation({ files_total: 1001, files_done: 1000, bytes_total: 1000, bytes_done: 100 })
    );
    assert.equal(progress.ratio, 0.1);
  });

  test('repli sur les fichiers quand rien ne pèse', () => {
    // Rapatriement de fichiers vides : rare, mais une barre figée à zéro
    // serait le seul retour.
    const progress = progressOf(
      remediation({ files_total: 4, files_done: 2, bytes_total: 0, bytes_done: 0 })
    );
    assert.equal(progress.ratio, 0.5);
  });

  test('sans total, pas de ratio inventé', () => {
    assert.equal(progressOf(remediation()).ratio, null);
  });

  test('la barre ne déborde jamais', () => {
    // `files_done` peut dépasser le total quand des fichiers apparaissent
    // pendant la copie ; une barre à 140 % sortirait de la carte.
    const progress = progressOf(
      remediation({ files_total: 5, files_done: 9, bytes_total: 10, bytes_done: 40 })
    );
    assert.equal(progress.ratio, 1);
  });

  test('les compteurs bruts sont transmis tels quels', () => {
    const progress = progressOf(
      remediation({ files_total: 10, files_done: 3, bytes_total: 100, bytes_done: 30 })
    );
    assert.deepEqual(
      [progress.filesDone, progress.filesTotal, progress.bytesDone, progress.bytesTotal],
      [3, 10, 30, 100]
    );
  });
});

describe('percent', () => {
  test('arrondi à l’entier', () => {
    assert.equal(percent(0.476), '48 %');
  });

  test('sans ratio, rien — surtout pas « 0 % »', () => {
    // « 0 % » sur une remédiation dont on ne connaît pas le total ferait
    // croire que rien n'a commencé.
    assert.equal(percent(null), '');
  });
});
