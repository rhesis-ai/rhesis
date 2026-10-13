import { toCreateBody } from '../components/CreateDestinationDrawer';
import {
  DestinationStatus,
  destinationStatus,
  destinationTarget,
  isHttpsUrl,
  withoutSecret,
  type AuditDestination,
} from '../destinations';

function makeDestination(
  overrides: Partial<AuditDestination> = {}
): AuditDestination {
  return {
    id: 'd1',
    name: 'SIEM',
    kind: 'webhook',
    settings: { url: 'https://siem.example.com/hook' },
    paused: false,
    paused_reason: null,
    delivered_through: '2026-10-13T10:00:00Z',
    last_success_at: null,
    last_error: null,
    last_error_at: null,
    consecutive_failures: 0,
    next_attempt_at: null,
    created_at: '2026-10-13T09:00:00Z',
    ...overrides,
  };
}

describe('destinationStatus', () => {
  it('tells active, paused and auto-paused apart', () => {
    expect(destinationStatus(makeDestination())).toBe(DestinationStatus.ACTIVE);
    expect(
      destinationStatus(
        makeDestination({ paused: true, paused_reason: 'manual' })
      )
    ).toBe(DestinationStatus.PAUSED);
    expect(
      destinationStatus(
        makeDestination({ paused: true, paused_reason: 'failures' })
      )
    ).toBe(DestinationStatus.AUTO_PAUSED);
  });
});

describe('destinationTarget', () => {
  it('shows the URL, or the Datadog site', () => {
    expect(destinationTarget(makeDestination())).toBe(
      'https://siem.example.com/hook'
    );
    expect(
      destinationTarget(
        makeDestination({ kind: 'datadog', settings: { site: 'datadoghq.eu' } })
      )
    ).toBe('datadoghq.eu');
  });
});

describe('isHttpsUrl', () => {
  it('accepts only https URLs', () => {
    expect(isHttpsUrl('https://a.example.com/x')).toBe(true);
    expect(isHttpsUrl('http://a.example.com/x')).toBe(false);
    expect(isHttpsUrl('a.example.com')).toBe(false);
  });
});

describe('withoutSecret', () => {
  it('drops the signing secret', () => {
    const row = withoutSecret({
      ...makeDestination(),
      signing_secret: 'whsec_abc',
    });
    expect(row).not.toHaveProperty('signing_secret');
  });
});

describe('toCreateBody', () => {
  const base = {
    kind: 'webhook' as const,
    name: ' SIEM ',
    url: ' https://siem.example.com/hook ',
    token: '',
    site: 'datadoghq.com' as const,
    apiKey: '',
  };

  it('sends only the fields of the chosen kind, trimmed', () => {
    expect(toCreateBody(base)).toEqual({
      kind: 'webhook',
      name: 'SIEM',
      url: 'https://siem.example.com/hook',
    });
    expect(toCreateBody({ ...base, kind: 'splunk_hec', token: ' t ' })).toEqual(
      {
        kind: 'splunk_hec',
        name: 'SIEM',
        url: 'https://siem.example.com/hook',
        token: 't',
      }
    );
    expect(
      toCreateBody({ ...base, kind: 'datadog', url: '', apiKey: 'k' })
    ).toEqual({
      kind: 'datadog',
      name: 'SIEM',
      site: 'datadoghq.com',
      api_key: 'k',
    });
  });

  it('is null while a required field is missing or the URL is not https', () => {
    expect(toCreateBody({ ...base, name: ' ' })).toBeNull();
    expect(
      toCreateBody({ ...base, url: 'http://siem.example.com' })
    ).toBeNull();
    expect(toCreateBody({ ...base, kind: 'splunk_hec' })).toBeNull();
    expect(toCreateBody({ ...base, kind: 'datadog' })).toBeNull();
  });
});
