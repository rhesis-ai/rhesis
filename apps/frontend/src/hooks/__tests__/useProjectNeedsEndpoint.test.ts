import { renderHook } from '@testing-library/react';
import { useProjectNeedsEndpoint } from '../useProjectNeedsEndpoint';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useEndpoints } from '@/hooks/useEndpoints';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: jest.fn(),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoints: jest.fn(),
}));

const mockUseActiveProject = useActiveProject as jest.MockedFunction<
  typeof useActiveProject
>;
const mockUseEndpoints = useEndpoints as jest.MockedFunction<
  typeof useEndpoints
>;

function setProject(id: string | null) {
  mockUseActiveProject.mockReturnValue({
    activeProject: id ? { id, name: 'Demo' } : null,
  } as unknown as ReturnType<typeof useActiveProject>);
}

/** The three react-query v5 outcomes we care about, shaped as the query result. */
function setQuery(
  outcome: 'loading' | 'success' | 'error',
  endpoints: Endpoint[] = []
) {
  mockUseEndpoints.mockReturnValue({
    data: outcome === 'success' ? endpoints : undefined,
    isPending: outcome === 'loading',
    isSuccess: outcome === 'success',
    isError: outcome === 'error',
  } as unknown as ReturnType<typeof useEndpoints>);
}

describe('useProjectNeedsEndpoint', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setProject('project-1');
  });

  it('reports pending while the endpoint query is in flight', () => {
    setQuery('loading');

    const { result } = renderHook(() => useProjectNeedsEndpoint());

    expect(result.current).toEqual({ pending: true, needsEndpoint: false });
  });

  it('reports needsEndpoint when the project has none', () => {
    setQuery('success', []);

    const { result } = renderHook(() => useProjectNeedsEndpoint());

    expect(result.current).toEqual({ pending: false, needsEndpoint: true });
  });

  it('reports neither once an endpoint exists', () => {
    setQuery('success', [{ id: 'endpoint-1' } as Endpoint]);

    const { result } = renderHook(() => useProjectNeedsEndpoint());

    expect(result.current).toEqual({ pending: false, needsEndpoint: false });
  });

  it('recovers to the default UI when the query fails', () => {
    // react-query leaves isSuccess false for good on error, so keying `pending`
    // off !isSuccess would latch it on and hide the chips and the help cards
    // together, permanently. Both must be false here.
    setQuery('error');

    const { result } = renderHook(() => useProjectNeedsEndpoint());

    expect(result.current).toEqual({ pending: false, needsEndpoint: false });
  });

  it('stays quiet when there is no active project', () => {
    setProject(null);
    // Disabled queries sit at status 'pending' in react-query v5.
    setQuery('loading');

    const { result } = renderHook(() => useProjectNeedsEndpoint());

    expect(result.current).toEqual({ pending: false, needsEndpoint: false });
  });
});
