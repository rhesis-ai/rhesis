import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import ArchitectHelpSection from '../ArchitectHelpSection';
import { useProjectNeedsEndpoint } from '@/hooks/useProjectNeedsEndpoint';

jest.mock('@/hooks/useProjectNeedsEndpoint', () => ({
  useProjectNeedsEndpoint: jest.fn(),
}));

const mockUseProjectNeedsEndpoint =
  useProjectNeedsEndpoint as jest.MockedFunction<
    typeof useProjectNeedsEndpoint
  >;

const ARTICLE_URLS = [
  'https://docs.rhesis.ai/docs/getting-started/connecting-application',
  'https://docs.rhesis.ai/docs/endpoints',
];

function setEndpointState(state: { pending: boolean; needsEndpoint: boolean }) {
  mockUseProjectNeedsEndpoint.mockReturnValue(state);
}

function setArticles(urls: string[]) {
  window.__ENV__ = { architectHelpArticleUrls: urls };
}

describe('ArchitectHelpSection', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // EmptyStateArticleCard fetches OG metadata per card; keep it inert.
    global.fetch = jest.fn().mockResolvedValue({ ok: false }) as jest.Mock;
    setEndpointState({ pending: false, needsEndpoint: true });
    setArticles(ARTICLE_URLS);
  });

  it('renders the help articles when the project has no endpoint', () => {
    render(<ArchitectHelpSection />);

    expect(screen.getByText('Top Help Articles')).toBeInTheDocument();
  });

  it('never renders community links', () => {
    render(<ArchitectHelpSection />);

    expect(screen.queryByText('Community & Support')).not.toBeInTheDocument();
    expect(screen.queryByText('Documentation')).not.toBeInTheDocument();
  });

  it('renders nothing once the project has an endpoint', () => {
    setEndpointState({ pending: false, needsEndpoint: false });

    render(<ArchitectHelpSection />);

    expect(screen.queryByText('Top Help Articles')).not.toBeInTheDocument();
  });

  it('renders nothing while the endpoint check is still loading', () => {
    setEndpointState({ pending: true, needsEndpoint: false });

    render(<ArchitectHelpSection />);

    expect(screen.queryByText('Top Help Articles')).not.toBeInTheDocument();
  });

  it('renders nothing when no article URLs are configured', () => {
    setArticles([]);

    render(<ArchitectHelpSection />);

    expect(screen.queryByText('Top Help Articles')).not.toBeInTheDocument();
  });
});
