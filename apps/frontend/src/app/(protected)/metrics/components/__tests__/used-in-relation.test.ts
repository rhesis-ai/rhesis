import { tuningCasesRelation, usedInRelation } from '../MetricCard';

describe('usedInRelation', () => {
  it('shows the requirement icon with a count, names in the tooltip', () => {
    const relation = usedInRelation(['No invented facts']);
    expect(relation.count).toBe(1);
    expect(relation.label).toBe('requirement');
    expect(relation.icon).toBeDefined();
    expect(relation.tooltip).toBe('1 requirement: No invented facts');
  });

  it('lists every name in the tooltip', () => {
    const relation = usedInRelation(['A', 'B', 'C']);
    expect(relation.count).toBe(3);
    expect(relation.tooltip).toBe('3 requirements: A, B, C');
  });

  it('shows zero, which the card greys out', () => {
    const relation = usedInRelation([]);
    expect(relation.count).toBe(0);
    expect(relation.tooltip).toBe('0 requirements');
  });
});

describe('tuningCasesRelation', () => {
  it('shows the tuning icon with a count', () => {
    const relation = tuningCasesRelation(2);
    expect(relation.count).toBe(2);
    expect(relation.label).toBe('tuning cases');
    expect(relation.icon).toBeDefined();
  });

  it('uses the singular for one case', () => {
    expect(tuningCasesRelation(1).label).toBe('tuning case');
  });
});
