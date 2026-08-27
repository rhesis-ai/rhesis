import {
  outcomeOf,
  displayStatusOf,
  allMetricsPassed,
  passRate,
  getReviewBand,
  STATUS_LABEL,
  type Outcome,
  type TestResultStatus,
} from '../outcomes';

describe('outcomeOf', () => {
  it('projects each verdict when execution is ok', () => {
    expect(outcomeOf('ok', 'pass')).toBe('pass');
    expect(outcomeOf('ok', 'fail')).toBe('fail');
    expect(outcomeOf('ok', 'inconclusive')).toBe('inconclusive');
  });

  it('keeps error and cancelled distinct', () => {
    expect(outcomeOf('error', null)).toBe('error');
    expect(outcomeOf('cancelled', null)).toBe('cancelled');
    expect(outcomeOf('error', null)).not.toBe(outcomeOf('cancelled', null));
  });

  it('treats not_run and running as pending', () => {
    expect(outcomeOf('not_run', null)).toBe('pending');
    expect(outcomeOf('running', null)).toBe('pending');
  });

  it('ignores a stray verdict when execution is not ok', () => {
    // The backend's CHECK constraint makes this unrepresentable, but the
    // projection must not silently report a pass if one ever arrives.
    expect(outcomeOf('error', 'pass')).toBe('error');
  });
});

describe('displayStatusOf', () => {
  it('maps the four reachable outcomes', () => {
    expect(displayStatusOf({ execution: 'ok', verdict: 'pass' })).toBe('Pass');
    expect(displayStatusOf({ execution: 'ok', verdict: 'fail' })).toBe('Fail');
    expect(displayStatusOf({ execution: 'ok', verdict: 'inconclusive' })).toBe(
      'Inconclusive'
    );
    expect(displayStatusOf({ execution: 'error', verdict: null })).toBe(
      'Error'
    );
  });

  it('is total over every outcome', () => {
    const outcomes: Outcome[] = [
      'pass',
      'fail',
      'inconclusive',
      'error',
      'cancelled',
      'pending',
    ];
    const statuses: TestResultStatus[] = [
      'Pass',
      'Fail',
      'Error',
      'Inconclusive',
    ];
    for (const o of outcomes) {
      expect(STATUS_LABEL).toBeDefined();
      // every outcome must land on a known display status
      const pair =
        o === 'pass'
          ? { execution: 'ok' as const, verdict: 'pass' as const }
          : o === 'fail'
            ? { execution: 'ok' as const, verdict: 'fail' as const }
            : o === 'inconclusive'
              ? { execution: 'ok' as const, verdict: 'inconclusive' as const }
              : o === 'error'
                ? { execution: 'error' as const, verdict: null }
                : o === 'cancelled'
                  ? { execution: 'cancelled' as const, verdict: null }
                  : { execution: 'not_run' as const, verdict: null };
      expect(statuses).toContain(displayStatusOf(pair));
    }
  });
});

describe('STATUS_LABEL', () => {
  it('has a label for every display status', () => {
    const statuses: TestResultStatus[] = [
      'Pass',
      'Fail',
      'Error',
      'Inconclusive',
    ];
    for (const s of statuses) {
      expect(STATUS_LABEL[s]).toBeTruthy();
    }
  });
});

describe('allMetricsPassed', () => {
  it('is true only when every metric explicitly passed', () => {
    expect(allMetricsPassed([{ is_successful: true }])).toBe(true);
    expect(
      allMetricsPassed([{ is_successful: true }, { is_successful: false }])
    ).toBe(false);
  });

  it('is false for an empty list -- nothing evaluated is not a pass', () => {
    expect(allMetricsPassed([])).toBe(false);
  });

  it('does not treat a null/undefined metric verdict as a pass', () => {
    expect(allMetricsPassed([{ is_successful: null }])).toBe(false);
    expect(allMetricsPassed([{}])).toBe(false);
  });
});

describe('passRate', () => {
  it('divides by what actually resolved, not by the total', () => {
    // 1 passed, 1 failed, plus (implicitly) any number of errored/unrun --
    // those never enter the denominator.
    expect(passRate(1, 1)).toBe(50);
    expect(passRate(3, 1)).toBe(75);
  });

  it('returns null rather than 0 when nothing resolved', () => {
    expect(passRate(0, 0)).toBeNull();
  });
});

describe('getReviewBand', () => {
  it('bands on the single 100/70 scale', () => {
    expect(getReviewBand(100).colorKey).toBe('success');
    expect(getReviewBand(85).colorKey).toBe('warning');
    expect(getReviewBand(69).colorKey).toBe('error');
  });

  it('treats 70 as the watch boundary', () => {
    expect(getReviewBand(70).band).toBe('watch');
    expect(getReviewBand(69.9).band).toBe('review');
  });
});
