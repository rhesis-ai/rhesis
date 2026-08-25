import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { sourcesDirectory } from '../directory';

const empty = emptyFilters(sourcesDirectory);

describe('sourcesDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(sourcesDirectory, empty)).toBeUndefined();
  });

  it('ORs the quick search across title/description plus a tags-relationship match, matching the old builder', () => {
    expect(
      buildDirectoryFilter(sourcesDirectory, { ...empty, search: 'docs' })
    ).toBe(
      "(contains(tolower(title),tolower('docs')) or " +
        "contains(tolower(description),tolower('docs')) or " +
        "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('docs'))))"
    );
  });

  it('maps sourceType to source_type/type_value, case-insensitively', () => {
    expect(
      buildDirectoryFilter(sourcesDirectory, { ...empty, sourceType: 'Tool' })
    ).toBe("tolower(source_type/type_value) eq tolower('Tool')");
  });

  it('matches creator with contains (not eq), matching the old builder', () => {
    expect(
      buildDirectoryFilter(sourcesDirectory, { ...empty, creator: 'Alice' })
    ).toBe("contains(tolower(user/name),tolower('Alice'))");
  });

  it('matches tag with a tags-relationship contains, matching the old builder', () => {
    expect(
      buildDirectoryFilter(sourcesDirectory, { ...empty, tag: 'urgent' })
    ).toBe(
      "_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('urgent')))"
    );
  });
});
