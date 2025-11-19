import { isQuickStartEnabled } from '../quick_start';

describe('quick_start', () => {
  describe('isQuickStartEnabled', () => {
    const originalEnv = process.env;

    beforeEach(() => {
      // Reset process.env before each test
      jest.resetModules();
      process.env = { ...originalEnv };
    });

    afterAll(() => {
      // Restore original process.env after all tests
      process.env = originalEnv;
    });

    describe('Environment variable validation', () => {
      it('should return false when NEXT_PUBLIC_QUICK_START is not set', () => {
        delete process.env.NEXT_PUBLIC_QUICK_START;
        delete process.env.QUICK_START;

        const result = isQuickStartEnabled();

        expect(result).toBe(false);
      });

      it('should return false when NEXT_PUBLIC_QUICK_START is false', () => {
        process.env.NEXT_PUBLIC_QUICK_START = 'false';

        const result = isQuickStartEnabled();

        expect(result).toBe(false);
      });

      it('should return false when NEXT_PUBLIC_QUICK_START is empty', () => {
        process.env.NEXT_PUBLIC_QUICK_START = '';

        const result = isQuickStartEnabled();

        expect(result).toBe(false);
      });

      it('should return true when NEXT_PUBLIC_QUICK_START is true and no cloud signals', () => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';
        // Mock window.location.hostname to be localhost
        Object.defineProperty(window, 'location', {
          value: { hostname: 'localhost' },
          writable: true,
        });

        const result = isQuickStartEnabled();

        expect(result).toBe(true);
      });

      it('should accept QUICK_START as fallback', () => {
        delete process.env.NEXT_PUBLIC_QUICK_START;
        process.env.QUICK_START = 'true';
        Object.defineProperty(window, 'location', {
          value: { hostname: 'localhost' },
          writable: true,
        });

        const result = isQuickStartEnabled();

        expect(result).toBe(true);
      });
    });

    describe('Hostname pattern matching', () => {
      beforeEach(() => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';
      });

      it.each([
        'app.rhesis.ai',
        'dev-app.rhesis.ai',
        'stg-app.rhesis.ai',
        'api.rhesis.ai',
        'dev-api.rhesis.ai',
        'stg-api.rhesis.ai',
        'rhesis.ai',
        'subdomain.rhesis.ai',
        'any.rhesis.ai',
        'test-app.rhesis.ai',
      ])('should return false for rhesis.ai domain: %s', (hostname) => {
        const result = isQuickStartEnabled(hostname);

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
      ])('should return true for local/non-cloud domain: %s', (hostname) => {
        const result = isQuickStartEnabled(hostname);

        expect(result).toBe(true);
      });

      it.each([
        'my-service.run.app',
        'app.cloudrun.dev',
        'service.appspot.com',
        'subdomain.run.app',
      ])('should return false for Cloud Run domain: %s', (hostname) => {
        const result = isQuickStartEnabled(hostname);

        expect(result).toBe(false);
      });

      it('should be case-insensitive for hostname matching', () => {
        const result = isQuickStartEnabled('APP.RHESIS.AI');

        expect(result).toBe(false);
      });

      it('should use window.location.hostname when hostname not provided', () => {
        Object.defineProperty(window, 'location', {
          value: { hostname: 'localhost' },
          writable: true,
        });

        const result = isQuickStartEnabled();

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai from window.location.hostname', () => {
        Object.defineProperty(window, 'location', {
          value: { hostname: 'app.rhesis.ai' },
          writable: true,
        });

        const result = isQuickStartEnabled();

        expect(result).toBe(false);
      });

      it('should handle undefined window (SSR)', () => {
        const originalWindow = global.window;
        // @ts-ignore - intentionally removing window for SSR test
        delete global.window;

        const result = isQuickStartEnabled('localhost');

        expect(result).toBe(true);

        global.window = originalWindow;
      });
    });

    describe('Edge cases', () => {
      beforeEach(() => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';
      });

      it('should handle empty hostname string', () => {
        // Mock window.location.hostname to be localhost when empty string is passed
        Object.defineProperty(window, 'location', {
          value: { hostname: 'localhost' },
          writable: true,
        });

        const result = isQuickStartEnabled('');

        expect(result).toBe(true);
      });

      it('should handle hostname with port', () => {
        const result = isQuickStartEnabled('localhost:3000');

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai even with port', () => {
        const result = isQuickStartEnabled('app.rhesis.ai:443');

        expect(result).toBe(false);
      });

      it('should not have false positive for substring match', () => {
        // Should not match "rhesis.ai" in "my-rhesis-ai-app.com"
        const result = isQuickStartEnabled('my-rhesis-ai-app.com');

        expect(result).toBe(true);
      });

      it('should detect rhesis.ai as part of larger domain', () => {
        const result = isQuickStartEnabled('subdomain.app.rhesis.ai');

        expect(result).toBe(false);
      });

      it('should handle whitespace in hostname', () => {
        const result = isQuickStartEnabled('  localhost  ');

        expect(result).toBe(true);
      });
    });

    describe('Fail-secure behavior', () => {
      it('should return false if environment is true but hostname is cloud', () => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';

        const result = isQuickStartEnabled('app.rhesis.ai');

        expect(result).toBe(false);
      });

      it('should return false if environment is true but hostname is Cloud Run', () => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';

        const result = isQuickStartEnabled('my-service.run.app');

        expect(result).toBe(false);
      });

      it('should return true only when all checks pass', () => {
        process.env.NEXT_PUBLIC_QUICK_START = 'true';

        const result = isQuickStartEnabled('localhost');

        expect(result).toBe(true);
      });
    });
  });
});

