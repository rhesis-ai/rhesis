'use client';

export {
  ENVIRONMENTS,
  getProjectIcon,
} from '../../components/endpoint-icon-utils';

export const METHODS = ['POST'] as const;

export const TAB_KEYS = ['overview', 'connection', 'mapping', 'test'] as const;
export type EndpointTabKey = (typeof TAB_KEYS)[number];
