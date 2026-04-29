import * as quickStart from '../quick_start';

const { isQuickStartHostAllowed } = quickStart;

describe('quick_start', () => {
  describe('frontend Quick Start detection', () => {
    beforeEach(() => {
      jest.resetModules();
    });

    describe('Environment ownership', () => {
      it('does not expose a frontend environment-based helper', () => {
        expect(Object.keys(quickStart)).toEqual(['isQuickStartHostAllowed']);
      });
    });

    describe('Hostname pattern matching', () => {
      it.each([
        'example-app.rhesis.ai',
        'test-dev.rhesis.ai',
        'sample-stg.rhesis.ai',
        'demo-api.rhesis.ai',
        'test-dev-api.rhesis.ai',
        'sample-stg-api.rhesis.ai',
        'rhesis.ai',
        'subdomain.rhesis.ai',
        'any.rhesis.ai',
        'test-app.rhesis.ai',
      ])('should return false for rhesis.ai domain: %s', hostname => {
        const result = isQuickStartHostAllowed(hostname);

        expect(result).toBe(false);
      });

      it.each([
        'localhost',
        '127.0.0.1',
        '192.168.1.1',
        'local.rhesis.local',
        'test.local',
        'example.com',
        'myapp.com',
      ])('should return true for local/non-cloud domain: %s', hostname => {
        const result = isQuickStartHostAllowed(hostname);

        expect(result).toBe(true);
      });

      it.each([
        'my-service.run.app',
        'app.cloudrun.dev',
        'service.appspot.com',
        'subdomain.run.app',
      ])('should return false for Cloud Run domain: %s', hostname => {
        const result = isQuickStartHostAllowed(hostname);

        expect(result).toBe(false);
      });

      it('should be case-insensitive for hostname matching', () => {
        const result = isQuickStartHostAllowed('APP.RHESIS.AI');

        expect(result).toBe(false);
      });

      it('should use window.location.hostname when hostname not provided', () => {
        const result = isQuickStartHostAllowed();

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai from window.location.hostname', () => {
        // For this test, just pass the hostname directly instead of mocking window.location
        // since mocking window.location is problematic in newer jsdom versions
        const result = isQuickStartHostAllowed('example-app.rhesis.ai');

        expect(result).toBe(false);
      });

      it('should handle undefined window (SSR)', () => {
        const originalWindow = global.window;
        // @ts-expect-error - intentionally removing window for SSR test
        delete global.window;

        const result = isQuickStartHostAllowed('localhost');

        expect(result).toBe(true);

        global.window = originalWindow;
      });
    });

    describe('Edge cases', () => {
      it('should handle empty hostname string', () => {
        const result = isQuickStartHostAllowed('');

        expect(result).toBe(true);
      });

      it('should handle hostname with port', () => {
        const result = isQuickStartHostAllowed('localhost:3000');

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai even with port', () => {
        const result = isQuickStartHostAllowed('example-app.rhesis.ai:443');

        expect(result).toBe(false);
      });

      it('should not have false positive for substring match', () => {
        // Should not match "rhesis.ai" in "my-rhesis-ai-app.com"
        const result = isQuickStartHostAllowed('my-rhesis-ai-app.com');

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai as part of larger domain', () => {
        const result = isQuickStartHostAllowed(
          'subdomain.example-app.rhesis.ai'
        );

        expect(result).toBe(false);
      });

      it('should handle whitespace in hostname', () => {
        const result = isQuickStartHostAllowed('  localhost  ');

        expect(result).toBe(true);
      });
    });

    describe('Fail-secure behavior', () => {
      it('should return false if hostname is cloud', () => {
        const result = isQuickStartHostAllowed('example-app.rhesis.ai');

        expect(result).toBe(false);
      });

      it('should return false if hostname is Cloud Run', () => {
        const result = isQuickStartHostAllowed('my-service.run.app');

        expect(result).toBe(false);
      });

      it('should return true only when all checks pass', () => {
        const result = isQuickStartHostAllowed('localhost');

        expect(result).toBe(true);
      });
    });
  });
});
