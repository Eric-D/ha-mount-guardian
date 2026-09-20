export const MOUNT_GUARD_CARD_VERSION = '1.0.0';

export function logBanner(): void {
  // console volontaire : c'est la convention des cartes Lovelace, et le bandeau
  // de version est le premier élément de diagnostic de ce projet.
  console.info(
    `%c MOUNT-GUARD-CARD %c ${MOUNT_GUARD_CARD_VERSION} IS INSTALLED `,
    'color: white; background: #1565c0; font-weight: bold;',
    'color: #1565c0; background: #bbdefb; font-weight: bold;'
  );
}

type LogLevel = 'info' | 'warn' | 'error';

export function mgLog(level: LogLevel, card: string, msg: string, ...args: unknown[]): void {
  const prefix = `%c MOUNT-GUARD-CARD %c [${card}]`;
  const styles = [
    'color: white; background: #1565c0; font-weight: bold;',
    'color: #1565c0; font-weight: bold;',
  ];
  // console volontaire : voir logBanner.
  console[level](prefix + ' ' + msg, ...styles, ...args);
}
