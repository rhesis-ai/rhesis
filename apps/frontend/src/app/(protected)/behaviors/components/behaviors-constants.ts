import { Capability } from '@/constants/capabilities';

/** Default page size for the behaviors directory grid. */
export const DEFAULT_BEHAVIORS_PAGE_SIZE = 25;

/**
 * Read capability gating the behaviors directory. Shared between the server
 * component's `prefetchList` call and the client component's
 * `useCanWithStatus` check so the two gates can't drift onto different
 * capability values.
 */
export const BEHAVIORS_READ_CAPABILITY = Capability.Behavior.READ;
