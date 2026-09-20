import { css } from 'lit';

export const stepperStyles = css`
  .stepper {
    display: flex;
    align-items: flex-start;
    gap: 4px;
    margin: 10px 0 6px;
  }

  .step {
    flex: 1 1 0;
    min-width: 0;
    text-align: center;
  }

  .bar {
    height: 4px;
    border-radius: 2px;
    background: var(--divider-color);
  }

  .step.done .bar {
    background: var(--success-color);
  }

  .step.active .bar {
    background: var(--primary-color);
  }

  .step.failed .bar {
    background: var(--error-color);
  }

  .step .label {
    margin-top: 4px;
    font-size: 0.7rem;
    color: var(--secondary-text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* L'étape en cours est la seule en couleur de texte pleine : sur une carte
     de cinq cases, mettre tout en évidence revient à ne rien mettre en
     évidence. */
  .step.active .label {
    color: var(--primary-text-color);
    font-weight: 500;
  }

  .step.failed .label {
    color: var(--error-color);
    font-weight: 500;
  }

  .progress {
    margin-top: 8px;
  }

  .track {
    height: 6px;
    border-radius: 3px;
    background: var(--divider-color);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    background: var(--primary-color);
    transition: width 0.3s ease;
  }

  .numbers {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-top: 4px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  .current {
    margin-top: 2px;
    font-size: 0.78rem;
    color: var(--secondary-text-color);
    font-family: var(--code-font-family, monospace);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
    text-align: left;
  }
`;
