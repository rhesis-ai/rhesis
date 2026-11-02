import { useTypeLookups } from '@/hooks/useLookups';

export const REQUIREMENT_TYPE_NAME = 'RequirementType';
export const REQUIREMENT_IMPACT_NAME = 'RequirementImpact';

export const lookupFilter = (typeName: string) => `type_name eq '${typeName}'`;

/** The project's requirement type options. */
export function useRequirementTypes(enabled = true) {
  return useTypeLookups(lookupFilter(REQUIREMENT_TYPE_NAME), enabled);
}

/** The project's requirement impact options. */
export function useRequirementImpacts(enabled = true) {
  return useTypeLookups(lookupFilter(REQUIREMENT_IMPACT_NAME), enabled);
}
