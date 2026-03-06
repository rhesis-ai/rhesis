import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ThemeProvider } from '@mui/material/styles';
import lightTheme from '@/styles/theme';
import ActivityTimeline from '../ActivityTimeline';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/components/common/UserAvatar', () => ({
  UserAvatar: () => <span data-testid="user-avatar" />,
}));

const mockGetRecentActivities = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getServicesClient: () => ({
      getRecentActivities: mockGetRecentActivities,
    }),
  })),
}));

function renderTimeline(
  props: Partial<{ sessionToken: string; onLoadComplete: () => void }> = {}
) {
  return render(
    <ThemeProvider theme={lightTheme}>
      <ActivityTimeline sessionToken="tok" {...props} />
    </ThemeProvider>
  );
}

function makeActivity(overrides = {}) {
  return {
    entity_type: 'Test',
    entity_id: 'e1',
    operation: 'create',
    timestamp: new Date().toISOString(),
    is_bulk: false,
    entity_data: {
      test_metadata: { prompt: 'Sample prompt' },
    },
    user: { id: 'u1', email: 'alice@test.com', name: 'Alice' },
    ...overrides,
  };
}

describe('ActivityTimeline', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // window.innerHeight triggers the viewport effect
    Object.defineProperty(window, 'innerHeight', {
      value: 800,
      writable: true,
    });
  });

  it('shows a loading spinner initially', () => {
    mockGetRecentActivities.mockReturnValue(new Promise(() => {})); // never resolves
    renderTimeline();
    expect(
      document.querySelector('.MuiCircularProgress-root')
    ).toBeInTheDocument();
  });

  it('shows "No recent activity" when the response is empty', async () => {
    mockGetRecentActivities.mockResolvedValue({ activities: [] });

    renderTimeline();

    await waitFor(() => {
      expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
    });
  });

  it('renders activity items returned by the API', async () => {
    mockGetRecentActivities.mockResolvedValue({
      activities: [makeActivity()],
    });

    renderTimeline();

    await waitFor(() => {
      expect(screen.getByText('Test Created')).toBeInTheDocument();
    });
  });

  it('shows the activity subtitle (prompt excerpt)', async () => {
    mockGetRecentActivities.mockResolvedValue({
      activities: [makeActivity()],
    });

    renderTimeline();

    await waitFor(() => {
      expect(screen.getByText('Sample prompt')).toBeInTheDocument();
    });
  });

  it('shows an error alert when the API call fails', async () => {
    mockGetRecentActivities.mockRejectedValue(new Error('Network error'));

    renderTimeline();

    await waitFor(() => {
      expect(
        screen.getByText(/unable to load activity data/i)
      ).toBeInTheDocument();
    });
  });

  it('calls onLoadComplete after fetching', async () => {
    const onLoadComplete = jest.fn();
    mockGetRecentActivities.mockResolvedValue({ activities: [] });

    renderTimeline({ onLoadComplete });

    await waitFor(() => {
      expect(onLoadComplete).toHaveBeenCalled();
    });
  });

  it('renders bulk operation activities', async () => {
    mockGetRecentActivities.mockResolvedValue({
      activities: [
        makeActivity({
          is_bulk: true,
          summary: '50 tests created',
          count: 50,
          entity_type: 'Test',
          operation: 'create',
          sample_entities: [],
          entity_ids: [],
        }),
      ],
    });

    renderTimeline();

    await waitFor(() => {
      expect(screen.getByText('50 tests created')).toBeInTheDocument();
    });
  });
});
