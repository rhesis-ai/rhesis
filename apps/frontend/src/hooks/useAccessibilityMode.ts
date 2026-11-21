import { useTheme } from '@mui/material/styles';

/**
 * True when the deployment, the organization or the user turned on the
 * accessibility mode. Extra safeguards such as confirming reversible removals
 * only apply then, so the default product behaves as before.
 */
export function useAccessibilityMode(): boolean {
  return Boolean(useTheme().palette.accessibilityMode);
}
