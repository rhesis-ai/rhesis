import { createContext, useContext } from 'react';
import type { ProviderInfo, SeenGroup } from '../types';
import type { Catalog } from './mapping-json';
import { GENERIC_PROVIDER } from './providers';

export interface RoleMappingData {
  provider: ProviderInfo;
  catalog: Catalog;
  /** Values seen in the mapping's claim at sign-in, most common first. */
  seenGroups: SeenGroup[];
}

export const RoleMappingContext = createContext<RoleMappingData>({
  provider: GENERIC_PROVIDER,
  catalog: { roles: [], projects: [] },
  seenGroups: [],
});

export const useRoleMappingData = () => useContext(RoleMappingContext);
