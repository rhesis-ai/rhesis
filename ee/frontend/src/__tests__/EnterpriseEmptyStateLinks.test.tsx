import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { UPGRADE_URL } from '@/constants/quota';
import RolesEmptyState from '../rbac/components/RolesEmptyState';
import SSOEmptyState from '../sso/components/SSOEmptyState';
import ApiClientsEmptyState from '../api-clients/components/ApiClientsEmptyState';

/**
 * Every "Learn about Enterprise" prompt must resolve its destination from the
 * shared `UPGRADE_URL`, never from its own string.
 *
 * These three each hardcoded `https://rhesis.ai/editions`, so when the page
 * moved to `/pricing` the change had to be found in four separate files — and
 * three of them are EE, which a core-only search misses. Asserting against the
 * constant means a re-hardcoded URL fails here instead of quietly pointing a
 * gated customer at a redirect, or eventually a 404.
 */
const EMPTY_STATES = [
  ['Roles', RolesEmptyState],
  ['SSO', SSOEmptyState],
  ['API Clients', ApiClientsEmptyState],
] as const;

describe('Enterprise empty-state upgrade links', () => {
  let openSpy: jest.SpyInstance;

  beforeEach(() => {
    openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
  });

  afterEach(() => {
    openSpy.mockRestore();
  });

  it.each(EMPTY_STATES)(
    '%s sends the reader to the shared pricing URL',
    async (_name, Component) => {
      render(<Component />);

      await userEvent.click(
        screen.getByRole('button', { name: /learn about enterprise/i })
      );

      expect(openSpy).toHaveBeenCalledWith(
        UPGRADE_URL,
        '_blank',
        'noopener,noreferrer'
      );
    }
  );

  it('has no empty state pointing at the retired /editions path', () => {
    // Guards the migration itself: `/editions` only 301s to `/pricing`, and an
    // upgrade prompt is the wrong place to spend a redirect.
    expect(UPGRADE_URL).toBe('https://rhesis.ai/pricing');
    expect(UPGRADE_URL).not.toContain('/editions');
  });
});
