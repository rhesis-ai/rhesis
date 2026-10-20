import { renderHook, act } from '@testing-library/react';

const mockPush = jest.fn();
const mockRefresh = jest.fn();
const mockWriteActiveProjectId = jest.fn();
const calls: string[] = [];

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: (path: string) => mockPush(path) }),
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ refresh: mockRefresh }),
}));

jest.mock('@/utils/active-project', () => ({
  writeActiveProjectId: (id: string) => mockWriteActiveProjectId(id),
}));

import { useOpenNewProject } from '@/hooks/useOpenNewProject';

describe('useOpenNewProject', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    calls.length = 0;
    mockWriteActiveProjectId.mockImplementation(() => calls.push('write'));
    mockRefresh.mockImplementation(async () => {
      calls.push('refresh');
    });
    mockPush.mockImplementation(() => calls.push('push'));
  });

  it('makes the project active, refreshes, then opens it', async () => {
    const { result } = renderHook(() => useOpenNewProject());

    await act(async () => {
      await result.current({ id: 'proj-1' });
    });

    expect(mockWriteActiveProjectId).toHaveBeenCalledWith('proj-1');
    expect(mockRefresh).toHaveBeenCalledWith({ listOnly: false });
    expect(mockPush).toHaveBeenCalledWith('/projects/proj-1');
    expect(calls).toEqual(['write', 'refresh', 'push']);
  });
});
