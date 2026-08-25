import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { tasksDirectory } from '../directory';

const empty = emptyFilters(tasksDirectory);

describe('tasksDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(tasksDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across title/description, matching the old builder', () => {
    expect(
      buildDirectoryFilter(tasksDirectory, { ...empty, search: 'bug' })
    ).toBe(
      "(contains(tolower(title),tolower('bug')) or " +
        "contains(tolower(description),tolower('bug')))"
    );
  });

  it('maps status to status/name, matching the old builder', () => {
    expect(
      buildDirectoryFilter(tasksDirectory, { ...empty, status: 'Open' })
    ).toBe("tolower(status/name) eq tolower('Open')");
  });

  it('maps priority to priority/type_value, matching the old builder', () => {
    expect(
      buildDirectoryFilter(tasksDirectory, { ...empty, priority: 'High' })
    ).toBe("tolower(priority/type_value) eq tolower('High')");
  });

  it('maps assignee to assignee/name, matching the old builder', () => {
    expect(
      buildDirectoryFilter(tasksDirectory, { ...empty, assignee: 'Alice' })
    ).toBe("tolower(assignee/name) eq tolower('Alice')");
  });
});
