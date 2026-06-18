'use client';

export {
  ENVIRONMENTS,
  getProjectIcon,
} from '../../components/endpoint-icon-utils';

export const METHODS = ['POST'] as const;

export const TAB_KEYS = ['overview', 'connection', 'mapping', 'test'] as const;
export type EndpointTabKey = (typeof TAB_KEYS)[number];

export const LEGACY_TAB_MAP: Record<string, EndpointTabKey> = {
  mappings: 'test',
  'connection-test': 'test',
  headers: 'connection',
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
