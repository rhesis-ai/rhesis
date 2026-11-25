import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import EndpointOverviewTab from '../EndpointOverviewTab';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/contexts/FeaturesContext', () => ({
  useMaxEndpointTimeoutSeconds: () => 600,
}));

const mockSaveFields = jest.fn();
const endpoint = {
  id: 'ep-1',
  name: 'Slow agent',
  connection_type: 'SDK',
  environment: 'development',
  config_source: 'manual',
  response_format: 'json',
  timeout_seconds: 120,
} as Endpoint;

jest.mock('../EndpointDetailContext', () => ({
  useEndpointDetailContext: () => ({
    endpoint,
    projects: {},
    saveFields: mockSaveFields,
  }),
}));

function editTimeout(value: string) {
  render(<EndpointOverviewTab />);
  fireEvent.click(screen.getAllByRole('button', { name: /edit/i })[0]);
  fireEvent.change(screen.getByLabelText('Timeout (seconds)'), {
    target: { value },
  });
}

describe('EndpointOverviewTab timeout', () => {
  beforeEach(() => mockSaveFields.mockReset());

  it('shows the server ceiling and does not save a value above it', async () => {
    editTimeout('601');

    expect(
      screen.getByText('Enter whole seconds from 1 to 600.')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(mockSaveFields).not.toHaveBeenCalled());
  });

  it('saves a value within the ceiling', async () => {
    editTimeout('600');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() =>
      expect(mockSaveFields).toHaveBeenCalledWith(
        expect.objectContaining({ timeout_seconds: 600 })
      )
    );
  });

  it('saves an empty value as the system default', async () => {
    editTimeout('');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() =>
      expect(mockSaveFields).toHaveBeenCalledWith(
        expect.objectContaining({ timeout_seconds: null })
      )
    );
  });
});
