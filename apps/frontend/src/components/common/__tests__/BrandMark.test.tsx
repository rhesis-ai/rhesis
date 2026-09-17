import React from 'react';
import { render, screen } from '@testing-library/react';
import BrandMark from '../BrandMark';
import { DEFAULT_FAVICON_URL, ORG_FAVICON_URL } from '@/config/branding';

// `next/image` renders an <img> too, so the two branches are indistinguishable
// in the DOM. Tag it so the tests can assert which one was taken — the whole
// point of the distinction is that the optimizer must not see brand assets.
jest.mock('next/image', () => ({
  __esModule: true,
  default: ({ src, alt, ...rest }: { src: string; alt: string }) => (
    <img data-testid="next-image" src={src} alt={alt} {...rest} />
  ),
}));

function mark(src?: string) {
  render(<BrandMark src={src} size={40} alt="Acme logo" />);
  return screen.getByAltText('Acme logo');
}

describe('BrandMark', () => {
  it('optimizes the shipped Rhesis icon', () => {
    expect(mark()).toHaveAttribute('data-testid', 'next-image');
  });

  it('falls back to the Rhesis icon when no source is given', () => {
    expect(mark()).toHaveAttribute('src', DEFAULT_FAVICON_URL);
  });

  it('optimizes other shipped local paths', () => {
    expect(mark('/logos/something.png')).toHaveAttribute(
      'data-testid',
      'next-image'
    );
  });

  it('bypasses the optimizer for a remote BRAND_FAVICON_URL', () => {
    // The optimizer rejects any host outside images.remotePatterns, and the
    // host here comes from a deployment's values file.
    expect(mark('https://cdn.example.com/icon.png')).not.toHaveAttribute(
      'data-testid'
    );
  });

  it('bypasses the optimizer for an organisation upload', () => {
    // The optimizer fetches server-side with no session cookie, so the
    // branding asset route would 401 and the mark would never render.
    expect(mark(ORG_FAVICON_URL)).not.toHaveAttribute('data-testid');
  });

  it('renders the organisation favicon at the requested size', () => {
    const img = mark(ORG_FAVICON_URL);

    expect(img).toHaveAttribute('src', ORG_FAVICON_URL);
    expect(img).toHaveStyle({ width: '40px', height: '40px' });
  });
});
