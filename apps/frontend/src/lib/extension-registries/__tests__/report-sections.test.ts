import {
  getReportRequirementColumns,
  getReportSections,
  registerReportRequirementColumn,
  registerReportSection,
  resetReportSections,
} from '../report-sections';

const Empty = () => null;

describe('report-sections registry', () => {
  beforeEach(() => resetReportSections());

  it('sorts sections by order and ignores a repeated id', () => {
    registerReportSection({
      id: 'b',
      slot: 'details',
      order: 20,
      component: Empty,
    });
    registerReportSection({
      id: 'a',
      slot: 'details',
      order: 10,
      component: Empty,
    });
    registerReportSection({
      id: 'a',
      slot: 'footer',
      order: 1,
      component: Empty,
    });

    expect(getReportSections().map(s => s.id)).toEqual(['a', 'b']);
    expect(getReportSections()[0].slot).toBe('details');
  });

  it('keeps a stable array until something new registers', () => {
    registerReportSection({
      id: 'a',
      slot: 'details',
      order: 1,
      component: Empty,
    });
    const first = getReportSections();
    expect(getReportSections()).toBe(first);
    registerReportSection({
      id: 'b',
      slot: 'details',
      order: 2,
      component: Empty,
    });
    expect(getReportSections()).not.toBe(first);
  });

  it('registers columns separately', () => {
    registerReportRequirementColumn({
      id: 'impact',
      order: 10,
      header: 'Impact',
      sectionKey: 'by_impact',
      cell: Empty,
    });
    expect(getReportRequirementColumns().map(c => c.id)).toEqual(['impact']);
    expect(getReportSections()).toHaveLength(0);
  });
});
