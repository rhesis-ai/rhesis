'use client';

export {
  ENVIRONMENTS,
  getProjectIcon,
} from '../../components/endpoint-icon-utils';

export const METHODS = ['POST'] as const;

export const TAB_KEYS = [
  'overview',
  'connection',
  'headers',
  'mapping',
  'connection-test',
] as const;
export type EndpointTabKey = (typeof TAB_KEYS)[number];

/** @deprecated Old tab URLs — `mappings` was the former combined test tab */
export const LEGACY_TAB_MAP: Record<string, EndpointTabKey> = {
  mappings: 'connection-test',
};

export function getEnvironmentChipColor():
  | 'default'
  | 'primary'
  | 'secondary'
  | 'error'
  | 'info'
  | 'success'
  | 'warning' {
  return 'default';
}
