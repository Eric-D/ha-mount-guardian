/** Mise en forme : durées, tailles, chemins.
 *
 * Tout est ici plutôt que dans les rendus, pour une raison précise : une erreur
 * dans `renders/` se voit à l'œil au premier chargement, une erreur de calcul
 * ne se voit pas. « 1,2 Go » au lieu de « 1,2 Mo » est parfaitement lisible.
 */

const UNITS = ['o', 'ko', 'Mo', 'Go', 'To'] as const;

/** Taille en unités décimales (1 ko = 1000 o).
 *
 *  Décimales et non binaires : c'est ce qu'affichent le Superviseur, les
 *  fabricants de NAS et l'explorateur de fichiers. Compter en 1024 donnerait
 *  un nombre différent de celui que l'utilisateur lit juste à côté, et le
 *  ferait douter du bon. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1000) return `${Math.round(bytes)} o`;
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < UNITS.length - 1) {
    value /= 1000;
    unit++;
  }
  // Une décimale en dessous de 10, aucune au-dessus : « 9,4 Go » est utile,
  // « 941,3 Go » ne l'est pas et fait sauter la colonne à chaque rafraîchissement.
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${UNITS[unit]}`;
}

/** Durée écoulée, en français abrégé. Toujours positive. */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const total = Math.floor(seconds);
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} min ${String(total % 60).padStart(2, '0')} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${String(minutes % 60).padStart(2, '0')}`;
}

/** Compte à rebours mm:ss, borné à zéro.
 *
 *  Borné parce que l'horloge du navigateur et celle de Home Assistant ne sont
 *  jamais exactement d'accord : un « -00:03 » au moment où le réessai part
 *  donnerait l'impression que la carte est cassée. */
export function formatCountdown(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—';
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  return `${String(minutes).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

/** Secondes écoulées depuis un horodatage ISO, ou null s'il est illisible.
 *
 *  Le backend n'envoie que des INSTANTS en UTC, jamais des dates civiles :
 *  c'est ce qui permet de les soustraire à l'horloge du navigateur sans se
 *  soucier du fuseau configuré dans Home Assistant. Ne pas transposer ici la
 *  règle inverse, qui vaut pour les délais en jours. */
export function secondsSince(iso: string | null, now: number = Date.now()): number | null {
  if (!iso) return null;
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return null;
  return (now - parsed) / 1000;
}

export function secondsUntil(iso: string | null, now: number = Date.now()): number | null {
  const elapsed = secondsSince(iso, now);
  return elapsed === null ? null : -elapsed;
}

/** Tronque un chemin par la GAUCHE, en gardant le nom du fichier.
 *
 *  Par la gauche parce que la fin est ce qui distingue deux enregistrements :
 *  `clips/front_door/2026-09-20-14-02-17.mp4` et son voisin partagent
 *  quarante caractères de préfixe et ne diffèrent que par les derniers. Une
 *  troncature à droite les rendrait identiques à l'écran. */
export function truncatePath(path: string | null, max = 48): string {
  if (!path) return '';
  if (path.length <= max) return path;
  return `…${path.slice(path.length - max + 1)}`;
}
