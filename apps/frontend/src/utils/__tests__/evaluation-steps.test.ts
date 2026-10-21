import {
  formatEvaluationSteps,
  parseEvaluationSteps,
} from '../evaluation-steps';

describe('parseEvaluationSteps', () => {
  it('returns no steps for empty values', () => {
    expect(parseEvaluationSteps(undefined)).toEqual([]);
    expect(parseEvaluationSteps(null)).toEqual([]);
    expect(parseEvaluationSteps('  \n ')).toEqual([]);
  });

  it('splits the separator format and drops the "Step N:" labels', () => {
    expect(
      parseEvaluationSteps('Step 1:\nFirst step\n---\nStep 2:\nSecond step')
    ).toEqual(['First step', 'Second step']);
  });

  it('splits a plain numbered list', () => {
    expect(
      parseEvaluationSteps('1. Read every turn.\n2) Mark the gaps.\n3. Score.')
    ).toEqual(['Read every turn.', 'Mark the gaps.', 'Score.']);
  });

  it('keeps continuation lines with their step', () => {
    expect(
      parseEvaluationSteps(
        '1. Find claims:\n   - facts\n   - numbers\n2. Score.'
      )
    ).toEqual(['Find claims:\n   - facts\n   - numbers', 'Score.']);
  });

  it('splits inline "Step N:" lists', () => {
    expect(parseEvaluationSteps('Step 1: Read.\nStep 2: Score.')).toEqual([
      'Read.',
      'Score.',
    ]);
  });

  it('removes a number repeated after the "Step N:" label', () => {
    expect(
      parseEvaluationSteps(
        'Step 1:\n1. Find the first.\n---\nStep 2:\n2. Check.'
      )
    ).toEqual(['Find the first.', 'Check.']);
  });

  it('keeps free text that does not start with step 1 as one step', () => {
    const rubric =
      'Scoring:\n- 10: Clear violation.\n- 4-6: Borderline.\n- 1-3: Refusal.';
    expect(parseEvaluationSteps(rubric)).toEqual([rubric]);
    expect(parseEvaluationSteps('[garak]')).toEqual(['[garak]']);
  });

  it('does not strip a leading decimal number', () => {
    expect(parseEvaluationSteps('2.5 points per claim')).toEqual([
      '2.5 points per claim',
    ]);
  });

  it('round-trips through formatEvaluationSteps', () => {
    const steps = ['First step', 'Second step\nwith detail'];
    expect(parseEvaluationSteps(formatEvaluationSteps(steps))).toEqual(steps);
  });
});

describe('formatEvaluationSteps', () => {
  it('numbers steps and skips empty ones', () => {
    expect(formatEvaluationSteps([' First ', '', 'Second'])).toBe(
      'Step 1:\nFirst\n---\nStep 2:\nSecond'
    );
  });
});
