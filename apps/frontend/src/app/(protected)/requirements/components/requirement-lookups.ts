import { useTypeLookups } from '@/hooks/useLookups';

export const REQUIREMENT_IMPACT_NAME = 'RequirementImpact';

export const lookupFilter = (typeName: string) => `type_name eq '${typeName}'`;

/** The project's requirement impact options. */
export function useRequirementImpacts(enabled = true) {
  return useTypeLookups(lookupFilter(REQUIREMENT_IMPACT_NAME), enabled);
}

/** One dot colour per default impact; an organization's own get warning orange. */
const IMPACT_COLORS: Record<string, string> = {
  safety: 'error.main',
  'privacy & security': 'warning.main',
  'legal & compliance': 'primary.main',
  financial: 'success.main',
  reputation: 'secondary.light',
  'customer experience': 'text.disabled',
};

export const impactColor = (impact: string) =>
  IMPACT_COLORS[impact.trim().toLowerCase()] ?? 'warning.main';
