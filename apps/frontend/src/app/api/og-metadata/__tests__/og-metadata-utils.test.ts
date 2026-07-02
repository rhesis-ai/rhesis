import {
  isAllowedOgMetadataUrl,
  resolveRedirectUrl,
} from '@/app/api/og-metadata/og-metadata-utils';

describe('og-metadata-utils', () => {
  it('allows docs hostnames over http/https', () => {
    expect(
      isAllowedOgMetadataUrl(new URL('https://docs.rhesis.ai/docs/tests'))
    ).toBe(true);
    expect(
      isAllowedOgMetadataUrl(new URL('https://www.docs.rhesis.ai/docs/tests'))
    ).toBe(true);
  });

  it('rejects non-allowlisted hosts and schemes', () => {
    expect(isAllowedOgMetadataUrl(new URL('https://evil.example/docs'))).toBe(
      false
    );
    expect(isAllowedOgMetadataUrl(new URL('file://docs.rhesis.ai/docs'))).toBe(
      false
    );
  });

  it('allows same-host redirects and rejects off-host redirects', () => {
    const base = new URL('https://docs.rhesis.ai/docs/tests');

    expect(resolveRedirectUrl('/docs/other', base)?.toString()).toBe(
      'https://docs.rhesis.ai/docs/other'
    );

    expect(
      resolveRedirectUrl('https://www.docs.rhesis.ai/docs/other', base)
        ?.hostname
    ).toBe('www.docs.rhesis.ai');

    expect(resolveRedirectUrl('https://evil.example/steal', base)).toBeNull();
  });
});
