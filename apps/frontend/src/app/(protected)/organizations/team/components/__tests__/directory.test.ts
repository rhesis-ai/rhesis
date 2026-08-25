import { emptyFilters, buildDirectoryFilter } from '@/utils/directory';
import { teamDirectory } from '../directory';

const empty = emptyFilters(teamDirectory);

describe('teamDirectory filters', () => {
  it('contributes nothing when no filter is active', () => {
    expect(buildDirectoryFilter(teamDirectory, empty)).toBeUndefined();
  });

  it('ORs the global search across email/name/given_name/family_name, case-sensitively, matching the old builder', () => {
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, search: 'abc' })
    ).toBe(
      "(contains(email,'abc') or contains(name,'abc') or contains(given_name,'abc') or contains(family_name,'abc'))"
    );
  });

  it('matches only the email column for the drawer email filter', () => {
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, email: 'a@b.com' })
    ).toBe("contains(email,'a@b.com')");
  });

  it('ORs name/given_name/family_name for the drawer name filter', () => {
    expect(buildDirectoryFilter(teamDirectory, { ...empty, name: 'Ada' })).toBe(
      "(contains(name,'Ada') or contains(given_name,'Ada') or contains(family_name,'Ada'))"
    );
  });

  it('maps active member status to joined_at OData checks, matching the old builder', () => {
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, memberStatus: 'active' })
    ).toBe('joined_at ne null');
  });

  it('maps invited member status to missing joined_at OData checks, matching the old builder', () => {
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, memberStatus: 'invited' })
    ).toBe('joined_at eq null');
  });

  it('maps accountStatus to is_active checks', () => {
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, accountStatus: 'true' })
    ).toBe('is_active eq true');
    expect(
      buildDirectoryFilter(teamDirectory, { ...empty, accountStatus: 'false' })
    ).toBe('is_active eq false');
  });

  it('ANDs multiple active filters together', () => {
    expect(
      buildDirectoryFilter(teamDirectory, {
        ...empty,
        memberStatus: 'active',
        accountStatus: 'true',
      })
    ).toBe('joined_at ne null and is_active eq true');
  });
});
