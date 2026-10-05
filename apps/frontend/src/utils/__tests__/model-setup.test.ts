import {
  MODEL_NOT_CONFIGURED_ERROR_CODE,
  isModelNotConfigured,
  onModelNotConfigured,
  reportModelNotConfigured,
} from '../model-setup';

describe('isModelNotConfigured', () => {
  it('matches the HTTP detail body and the WebSocket payload', () => {
    expect(
      isModelNotConfigured({
        message: 'No usable generation model is set up.',
        error_code: MODEL_NOT_CONFIGURED_ERROR_CODE,
      })
    ).toBe(true);
  });

  it('matches a preflight summary with a failed model check', () => {
    expect(
      isModelNotConfigured({
        summary: 'failed',
        checks: [
          { check_id: 'endpoint', status: 'passed' },
          {
            check_id: 'evaluation_model',
            status: 'failed',
            error_code: MODEL_NOT_CONFIGURED_ERROR_CODE,
          },
        ],
      })
    ).toBe(true);
  });

  it.each([
    ['a string detail', 'Something failed'],
    ['another error code', { error_code: 'password_not_set' }],
    ['a validation array', [{ loc: ['body'], msg: 'required' }]],
    ['undefined', undefined],
    ['null', null],
  ])('ignores %s', (_label, value) => {
    expect(isModelNotConfigured(value)).toBe(false);
  });
});

describe('reportModelNotConfigured', () => {
  it('calls listeners until they unsubscribe', () => {
    const listener = jest.fn();
    const unsubscribe = onModelNotConfigured(listener);

    reportModelNotConfigured();
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    reportModelNotConfigured();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
