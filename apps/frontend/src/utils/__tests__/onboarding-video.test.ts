import {
  getOnboardingVideoEmbedUrl,
  getYouTubeThumbnailUrl,
} from '@/utils/onboarding-video';

describe('onboarding-video utils', () => {
  it('parses YouTube watch URLs', () => {
    expect(
      getOnboardingVideoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    ).toBe('https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0');
  });

  it('parses youtu.be short URLs', () => {
    expect(getOnboardingVideoEmbedUrl('https://youtu.be/dQw4w9WgXcQ')).toBe(
      'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&rel=0'
    );
  });

  it('parses Vimeo URLs', () => {
    expect(getOnboardingVideoEmbedUrl('https://vimeo.com/123456789')).toBe(
      'https://player.vimeo.com/video/123456789?autoplay=1'
    );
  });

  it('returns null for invalid URLs', () => {
    expect(getOnboardingVideoEmbedUrl('not-a-url')).toBeNull();
    expect(getOnboardingVideoEmbedUrl('')).toBeNull();
  });

  it('builds YouTube thumbnail URLs', () => {
    expect(
      getYouTubeThumbnailUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    ).toBe('https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg');
  });
});
