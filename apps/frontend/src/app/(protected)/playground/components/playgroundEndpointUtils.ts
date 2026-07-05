export interface EndpointOption {
  endpointId: string;
  endpointName: string;
  projectId: string;
  projectName: string;
  environment: string;
}

export function formatEnvironment(env: string): string {
  return env.charAt(0).toUpperCase() + env.slice(1);
}

export function getEnvironmentColor(env: string): string {
  switch (env.toLowerCase()) {
    case 'production':
      return 'error.main';
    case 'staging':
      return 'warning.main';
    case 'development':
      return 'info.main';
    default:
      return 'text.secondary';
  }
}

export function formatEndpointLabel(option: EndpointOption): string {
  return `${option.projectName} › ${option.endpointName}`;
}
