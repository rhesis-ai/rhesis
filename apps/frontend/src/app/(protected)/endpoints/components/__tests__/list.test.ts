import { emptyFilters, buildListFilter } from '@/utils/list';
import { endpointsList } from '../list';

const empty = emptyFilters(endpointsList);

describe('endpointsList filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildListFilter(endpointsList, empty)).toBeUndefined();
  });

  it('ORs the quick search across name/environment/connection_type/description, matching the old builder', () => {
    expect(buildListFilter(endpointsList, { ...empty, search: 'abc' })).toBe(
      "(contains(tolower(name),tolower('abc')) or " +
        "contains(tolower(environment),tolower('abc')) or " +
        "contains(tolower(connection_type),tolower('abc')) or " +
        "contains(tolower(description),tolower('abc')))"
    );
  });

  it('maps connectionType to the connection_type column, case-insensitively', () => {
    expect(
      buildListFilter(endpointsList, {
        ...empty,
        connectionType: 'REST',
      })
    ).toBe("tolower(connection_type) eq tolower('REST')");
  });

  it('maps status to status/name', () => {
    expect(buildListFilter(endpointsList, { ...empty, status: 'Active' })).toBe(
      "tolower(status/name) eq tolower('Active')"
    );
  });

  it('leaves environment as-is (no field remap)', () => {
    expect(
      buildListFilter(endpointsList, {
        ...empty,
        environment: 'production',
      })
    ).toBe("tolower(environment) eq tolower('production')");
  });

  it('ANDs an extra project-scoping clause in for the embedded (Project > Endpoints) grid', () => {
    expect(buildListFilter(endpointsList, empty, ["project_id eq 'p-1'"])).toBe(
      "project_id eq 'p-1'"
    );
    expect(
      buildListFilter(endpointsList, { ...empty, status: 'Active' }, [
        "project_id eq 'p-1'",
      ])
    ).toBe("project_id eq 'p-1' and tolower(status/name) eq tolower('Active')");
  });
});
