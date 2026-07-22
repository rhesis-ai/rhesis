import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import KnowledgeClientWrapper from '../KnowledgeClientWrapper';

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

// SourcesGrid owns the query and the loading/empty/populated decision
// itself — the wrapper's only job is to wire `canCreate`/`onCreateClick`
// through to it correctly.
jest.mock('../SourcesGrid', () => {
  return function MockSourcesGrid({
    canCreate,
    onCreateClick,
  }: {
    canCreate?: boolean;
    onCreateClick?: () => void;
  }) {
    return (
      <button onClick={onCreateClick} disabled={!canCreate}>
        mock-upload-source
      </button>
    );
  };
});

jest.mock('../UploadSourceDrawer', () => {
  return function MockUploadSourceDrawer({ open }: { open: boolean }) {
    return open ? <div data-testid="upload-source-drawer" /> : null;
  };
});

jest.mock('../ToolImportDrawer', () => {
  return function MockToolImportDrawer() {
    return null;
  };
});

describe('KnowledgeClientWrapper', () => {
  it('passes canCreate through to the grid', () => {
    render(<KnowledgeClientWrapper />);
    expect(screen.getByText('mock-upload-source')).toBeEnabled();
  });

  it('opens the upload drawer when the grid invokes onCreateClick', async () => {
    render(<KnowledgeClientWrapper />);
    await userEvent.click(screen.getByText('mock-upload-source'));
    expect(screen.getByTestId('upload-source-drawer')).toBeInTheDocument();
  });
});
