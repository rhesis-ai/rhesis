import {
  CLIENT_HEADER,
  CLIENT_IP_HEADER,
  browserIp,
  webClientHeaders,
} from '../provenance';

/**
 * The headers the Next.js server adds when it calls the backend for a browser.
 * The backend's audit log and IP rate limits read them; without the IP header
 * every UI call looks like it came from the frontend pod.
 */
describe('browserIp', () => {
  it('takes the address the nearest proxy appended to X-Forwarded-For', () => {
    const headers = new Headers({
      'x-forwarded-for': '198.51.100.1, 203.0.113.7',
    });
    expect(browserIp(headers)).toBe('203.0.113.7');
  });

  it('ignores entries and an X-Real-IP the client sent itself', () => {
    // Behind an ALB, which appends to X-Forwarded-For but leaves X-Real-IP
    // alone, both spoofed values reach this server unchanged.
    const headers = new Headers({
      'x-real-ip': '1.2.3.4',
      'x-forwarded-for': '1.2.3.4, 203.0.113.7',
    });
    expect(browserIp(headers)).toBe('203.0.113.7');
  });

  it('falls back to X-Real-IP without X-Forwarded-For', () => {
    expect(browserIp(new Headers({ 'x-real-ip': '203.0.113.7' }))).toBe(
      '203.0.113.7'
    );
  });

  it('returns null when neither is present', () => {
    expect(browserIp(new Headers())).toBeNull();
  });
});

describe('webClientHeaders', () => {
  it('names the web client and passes the browser IP on', () => {
    const headers = webClientHeaders(
      new Headers({ 'x-real-ip': '203.0.113.7' })
    );
    expect(headers).toEqual({
      [CLIENT_HEADER]: 'web',
      [CLIENT_IP_HEADER]: '203.0.113.7',
    });
  });

  it('leaves the IP out when the browser address is unknown', () => {
    expect(webClientHeaders(new Headers())).toEqual({ [CLIENT_HEADER]: 'web' });
  });
});
