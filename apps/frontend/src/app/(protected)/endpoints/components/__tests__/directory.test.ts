import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { endpointsDirectory } from '../directory';

const empty = emptyFilters(endpointsDirectory);

describe('endpointsDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(endpointsDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/environment/connection_type/description, matching the old builder', () => {
    expect(
      buildDirectoryFilter(endpointsDirectory, { ...empty, search: 'abc' })
    ).toBe(
      "(contains(tolower(name),tolower('abc')) or " +
        "contains(tolower(environment),tolower('abc')) or " +
        "contains(tolower(connection_type),tolower('abc')) or " +
        "contains(tolower(description),tolower('abc')))"
    );
  });

  it('maps connectionType to the connection_type column, case-insensitively', () => {
    expect(
      buildDirectoryFilter(endpointsDirectory, {
        ...empty,
        connectionType: 'REST',
      })
    ).toBe("tolower(connection_type) eq tolower('REST')");
  });

  it('maps status to status/name', () => {
    expect(
      buildDirectoryFilter(endpointsDirectory, { ...empty, status: 'Active' })
    ).toBe("tolower(status/name) eq tolower('Active')");
  });

  it('leaves environment as-is (no field remap)', () => {
    expect(
      buildDirectoryFilter(endpointsDirectory, {
        ...empty,
        environment: 'production',
      })
    ).toBe("tolower(environment) eq tolower('production')");
  });

  it('ANDs an extra project-scoping clause in for the embedded (Project > Endpoints) grid', () => {
    expect(
      buildDirectoryFilter(endpointsDirectory, empty, ["project_id eq 'p-1'"])
    ).toBe("project_id eq 'p-1'");
    expect(
      buildDirectoryFilter(endpointsDirectory, { ...empty, status: 'Active' }, [
        "project_id eq 'p-1'",
      ])
    ).toBe("project_id eq 'p-1' and tolower(status/name) eq tolower('Active')");
  });
});
