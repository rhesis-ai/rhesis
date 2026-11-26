import {
  frameworkInfo,
  isFrameworkMetric,
  isFrameworkPlaceholder,
} from '../metric-framework';

const withBackend = (type_value?: string | null) => ({
  backend_type: type_value === undefined ? undefined : { type_value },
});

describe('isFrameworkMetric', () => {
  it.each(['deepeval', 'garak', 'ragas', 'DeepEval'])(
    'is true for %s',
    type => {
      expect(isFrameworkMetric(withBackend(type))).toBe(true);
    }
  );

  it.each(['rhesis', 'custom', '', null, undefined])(
    'is false for %p',
    type => {
      expect(isFrameworkMetric(withBackend(type))).toBe(false);
    }
  );
});

describe('frameworkInfo', () => {
  it('names a known framework and links its docs page', () => {
    expect(frameworkInfo(withBackend('garak'))).toEqual({
      label: 'Garak',
      docsUrl: 'https://docs.rhesis.ai/docs/test-sets/import-from-garak',
    });
  });

  it('falls back to the metrics docs for one it does not know', () => {
    expect(frameworkInfo(withBackend('newlib'))).toEqual({
      label: 'Newlib',
      docsUrl: 'https://docs.rhesis.ai/docs/metrics',
    });
  });
});

describe('isFrameworkPlaceholder', () => {
  it.each(['[deepeval]', ' [garak] ', '[deep-team]'])('matches %p', value => {
    expect(isFrameworkPlaceholder(value)).toBe(true);
  });

  it.each([
    'garak.detectors.mitigation.MitigationBypass',
    'Score [0-1]',
    '',
    null,
    undefined,
  ])('does not match %p', value => {
    expect(isFrameworkPlaceholder(value)).toBe(false);
  });
});
