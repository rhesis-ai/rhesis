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

// Other keys that do not fit the pattern above: they are single fetches for a single value

export const featureKeys = {
  all: () => ['features'] as const,
};

export const permissionKeys = {
  all: (projectId: string) => ['permissions', projectId] as const,
};
