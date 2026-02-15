/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  formatDurationShort,
  getEnvironmentColor,
  truncateTraceId,
  truncateSpanId,
  formatCost,
  formatTokenCount,
  getSpanType,
  extractOperationName,
  calculateDurationPercentage,
  isLeafSpan,
  countSpansInTree,
  getTreeDepth,
  formatTraceDate,
  getStatusChipProps,
} from '../trace-utils';

describe('trace-utils', () => {
  describe('formatDurationShort', () => {
    it('formats microseconds', () => {
      expect(formatDurationShort(0.5)).toBe('500μs');
      expect(formatDurationShort(0.001)).toBe('1μs');
    });

    it('formats milliseconds', () => {
      expect(formatDurationShort(1)).toBe('1ms');
      expect(formatDurationShort(50.5)).toBe('51ms');
      expect(formatDurationShort(999)).toBe('999ms');
    });

    it('formats seconds', () => {
      expect(formatDurationShort(1000)).toBe('1.0s');
      expect(formatDurationShort(5500)).toBe('5.5s');
    });

    it('formats minutes', () => {
      expect(formatDurationShort(60000)).toBe('1.0min');
      expect(formatDurationShort(125000)).toBe('2.1min');
    });
  });

  describe('getEnvironmentColor', () => {
    it('returns error for production', () => {
      expect(getEnvironmentColor('production')).toBe('error');
      expect(getEnvironmentColor('PRODUCTION')).toBe('error');
    });

    it('returns warning for staging', () => {
      expect(getEnvironmentColor('staging')).toBe('warning');
      expect(getEnvironmentColor('STAGING')).toBe('warning');
    });

    it('returns info for development', () => {
      expect(getEnvironmentColor('development')).toBe('info');
      expect(getEnvironmentColor('DEVELOPMENT')).toBe('info');
    });

    it('returns default for unknown environments', () => {
      expect(getEnvironmentColor('test')).toBe('default');
      expect(getEnvironmentColor('')).toBe('default');
    });
  });

  describe('truncateTraceId', () => {
    it('truncates long trace IDs', () => {
      const longId = '162de7238d6138a4b0685c182d207421'; // 32 chars
      expect(truncateTraceId(longId)).toBe('162de723...2d207421'); // first 8 + ... + last 8
    });

    it('does not truncate short trace IDs', () => {
      const shortId = 'abc123';
      expect(truncateTraceId(shortId)).toBe('abc123');
    });

    it('handles empty strings', () => {
      expect(truncateTraceId('')).toBe('');
    });
  });

  describe('truncateSpanId', () => {
    it('truncates long span IDs', () => {
      const longId = 'a2eddff306dd0ec61234'; // 20 chars (>16)
      expect(truncateSpanId(longId)).toBe('a2eddff3...1234'); // first 8 + ... + last 4
    });

    it('does not truncate short span IDs', () => {
      const shortId = 'a2eddff306dd0ec6'; // exactly 16 chars
      expect(truncateSpanId(shortId)).toBe('a2eddff306dd0ec6');
    });

    it('handles empty strings', () => {
      expect(truncateSpanId('')).toBe('');
    });
  });

  describe('formatCost', () => {
    it('formats zero cost', () => {
      expect(formatCost(0)).toBe('$0.00');
    });

    it('formats very small costs', () => {
      expect(formatCost(0.0001)).toBe('$0.000100');
    });

    it('formats small costs', () => {
      expect(formatCost(0.005)).toBe('$0.0050');
    });

    it('formats regular costs', () => {
      expect(formatCost(1.5)).toBe('$1.50');
      expect(formatCost(10.25)).toBe('$10.25');
    });
  });

  describe('formatTokenCount', () => {
    it('formats small numbers', () => {
      expect(formatTokenCount(100)).toBe('100');
    });

    it('formats numbers with thousands separator', () => {
      expect(formatTokenCount(1000)).toContain('1');
      expect(formatTokenCount(10000)).toContain('10');
    });
  });

  describe('getSpanType', () => {
    it('identifies LLM spans', () => {
      expect(getSpanType('ai.llm.invoke')).toBe('LLM');
    });

    it('identifies function spans', () => {
      expect(getSpanType('function.chat')).toBe('Function');
    });

    it('identifies database spans', () => {
      expect(getSpanType('db.query')).toBe('Database');
    });

    it('identifies HTTP spans', () => {
      expect(getSpanType('http.post')).toBe('HTTP');
    });

    it('returns Other for unknown types', () => {
      expect(getSpanType('unknown')).toBe('Other');
      expect(getSpanType('')).toBe('Other');
    });
  });

  describe('extractOperationName', () => {
    it('extracts operation name from dotted notation', () => {
      expect(extractOperationName('function.chat')).toBe('chat');
      expect(extractOperationName('ai.llm.invoke')).toBe('invoke');
    });

    it('returns full name if no dot', () => {
      expect(extractOperationName('operation')).toBe('operation');
    });

    it('handles empty strings', () => {
      expect(extractOperationName('')).toBe('');
    });
  });

  describe('calculateDurationPercentage', () => {
    it('calculates percentage correctly', () => {
      expect(calculateDurationPercentage(50, 100)).toBe(50);
      expect(calculateDurationPercentage(25, 100)).toBe(25);
    });

    it('handles zero parent duration', () => {
      expect(calculateDurationPercentage(50, 0)).toBe(0);
    });

    it('handles values over 100%', () => {
      expect(calculateDurationPercentage(150, 100)).toBe(150);
    });
  });

  describe('isLeafSpan', () => {
    it('returns true for spans with no children', () => {
      expect(isLeafSpan({ children: [] } as any)).toBe(true);
      expect(isLeafSpan({} as any)).toBe(true);
    });

    it('returns false for spans with children', () => {
      expect(isLeafSpan({ children: [{} as any] } as any)).toBe(false);
    });
  });

  describe('countSpansInTree', () => {
    it('counts spans with no children', () => {
      const spans = [{ span_id: '1' }, { span_id: '2' }] as any;
      expect(countSpansInTree(spans)).toBe(2);
    });

    it('counts spans with children', () => {
      const spans = [
        {
          span_id: '1',
          children: [{ span_id: '2' }, { span_id: '3' }],
        },
      ] as any;
      expect(countSpansInTree(spans)).toBe(3);
    });

    it('counts deeply nested spans', () => {
      const spans = [
        {
          span_id: '1',
          children: [
            {
              span_id: '2',
              children: [{ span_id: '3' }],
            },
          ],
        },
      ] as any;
      expect(countSpansInTree(spans)).toBe(3);
    });

    it('handles empty arrays', () => {
      expect(countSpansInTree([])).toBe(0);
    });
  });

  describe('getTreeDepth', () => {
    it('returns 0 for empty tree', () => {
      expect(getTreeDepth([])).toBe(0);
    });

    it('returns 1 for single level', () => {
      const spans = [{ span_id: '1' }, { span_id: '2' }] as any;
      expect(getTreeDepth(spans)).toBe(1);
    });

    it('returns correct depth for nested tree', () => {
      const spans = [
        {
          span_id: '1',
          children: [
            {
              span_id: '2',
              children: [{ span_id: '3' }],
            },
          ],
        },
      ] as any;
      expect(getTreeDepth(spans)).toBe(3);
    });

    it('returns maximum depth for multiple branches', () => {
      const spans = [
        {
          span_id: '1',
          children: [{ span_id: '2' }],
        },
        {
          span_id: '3',
          children: [
            {
              span_id: '4',
              children: [{ span_id: '5' }],
            },
          ],
        },
      ] as any;
      expect(getTreeDepth(spans)).toBe(3);
    });
  });

  describe('formatTraceDate', () => {
    it('formats ISO date string', () => {
      const date = '2024-01-15T10:30:00Z';
      const result = formatTraceDate(date);
      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('handles empty strings', () => {
      expect(formatTraceDate('')).toBe('');
    });
  });

  describe('getStatusChipProps', () => {
    it('returns success props for OK status', () => {
      const props = getStatusChipProps('OK');
      expect(props.label).toBe('OK');
      expect(props.color).toBe('success');
      expect(props.variant).toBe('outlined');
    });

    it('returns error props for ERROR status', () => {
      const props = getStatusChipProps('ERROR');
      expect(props.label).toBe('ERROR');
      expect(props.color).toBe('error');
      expect(props.variant).toBe('filled');
    });

    it('returns default props for unknown status', () => {
      const props = getStatusChipProps('UNKNOWN');
      expect(props.label).toBe('UNKNOWN');
      expect(props.color).toBe('default');
      expect(props.variant).toBe('outlined');
    });
  });
});
