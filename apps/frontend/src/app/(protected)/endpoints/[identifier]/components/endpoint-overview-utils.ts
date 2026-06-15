import { Endpoint } from '@/utils/api-client/interfaces/endpoint';

export function connectionTarget(endpoint: Endpoint): string {
  if (endpoint.connection_type === 'SDK') {
    const fn = endpoint.endpoint_metadata?.sdk_connection?.function_name;
    return fn ? String(fn) : 'SDK function (not registered)';
  }
  return endpoint.url || 'No URL configured';
}

export function formatConfigSource(value: string): string {
  return value.replace(/_/g, ' ');
}

export function formatEnvironment(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export const detailGridSpacing = {
  columnSpacing: (isEditing: boolean) => (isEditing ? 2 : '30px'),
  rowSpacing: (isEditing: boolean) => (isEditing ? 2 : '50px'),
} as const;
