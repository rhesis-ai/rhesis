import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import { entityErrorView } from '../entity-error-view';

const mockNotFound = jest.fn(() => {
  throw new Error('NEXT_NOT_FOUND');
});

jest.mock('next/navigation', () => ({
  notFound: () => mockNotFound(),
  usePathname: () => '/requirements/abc-123',
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ status: 'authenticated', data: null }),
}));

/** An error as the server API client throws it. */
function apiError(status: number, data?: Record<string, unknown>) {
  const error = new Error(`API error: ${status} - failed`) as Error & {
    status: number;
    data?: Record<string, unknown>;
  };
  error.status = status;
  error.data = data;
  return error;
}

describe('entityErrorView', () => {
  it('sends a missing record to the not-found page', () => {
    expect(() => entityErrorView(apiError(404))).toThrow('NEXT_NOT_FOUND');
  });

  it('renders the access-denied page for a forbidden record', () => {
    render(<>{entityErrorView(apiError(403))}</>);
    expect(
      screen.getByRole('heading', { name: 'Requirements — Access denied' })
    ).toBeInTheDocument();
  });

  it('renders the restore page for a deleted record', () => {
    const view = entityErrorView(
      apiError(410, {
        can_restore: true,
        model_name: 'Requirement',
        item_id: 'abc-123',
        item_name: 'Safety requirement',
        table_name: 'requirement',
        restore_url: '/recycle/requirement/abc-123/restore',
        message: 'This requirement has been deleted.',
      })
    );
    render(<>{view}</>);
    expect(
      screen.getByRole('heading', { name: 'Safety requirement (Deleted)' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /restore/i })
    ).toBeInTheDocument();
  });

  it('leaves any other failure to the caller', () => {
    expect(entityErrorView(apiError(500))).toBeNull();
    expect(entityErrorView(new Error('network down'))).toBeNull();
  });
});
