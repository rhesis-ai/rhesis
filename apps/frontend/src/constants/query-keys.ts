function createEntityKeys<T extends string>(root: T) {
  return {
    all: () => [root] as const,
    list: (filter = '', page = 0, pageSize = 25, sortBy = '', sortOrder = '') =>
      [root, 'list', filter, page, pageSize, sortBy, sortOrder] as const,
    detail: (id: string) => [root, 'detail', id] as const,
  };
}

export const testKeys = createEntityKeys('tests');
export const testSetKeys = createEntityKeys('test-sets');
export const testRunKeys = createEntityKeys('test-runs');
export const endpointKeys = createEntityKeys('endpoints');
export const sourceKeys = createEntityKeys('sources');
export const taskKeys = createEntityKeys('tasks');
export const experimentKeys = createEntityKeys('experiments');
export const behaviorKeys = createEntityKeys('behaviors');
export const projectKeys = createEntityKeys('projects');

export const topicKeys = {
  list: (entityType = '') => ['topics', 'list', entityType] as const,
};

export const categoryKeys = {
  list: (entityType = '') => ['categories', 'list', entityType] as const,
};

export const fileKeys = {
  all: ['files'] as const,
  metadata: (fileId: string) => ['files', 'metadata', fileId] as const,
  thumbnail: (fileId: string, size: number) =>
    ['files', 'thumbnail', fileId, size] as const,
  contentUrl: (fileId: string) => ['files', 'contentUrl', fileId] as const,
};

// Other keys that do not fit the pattern above: they are single fetches for a single value.
// These are scoped by a stable per-user identifier so cached auth data never bleeds
// across login/logout or user switches while the QueryClient is alive.

export const featureKeys = {
  all: (userScope: string) => ['features', userScope] as const,
};

export const permissionKeys = {
  all: (userScope: string, projectId: string) =>
    ['permissions', userScope, projectId] as const,
};
