import { markdownToSpeech } from '../markdown-to-speech';

describe('markdownToSpeech', () => {
  it('drops markdown symbols and keeps link text', () => {
    expect(
      markdownToSpeech(
        '## Plan\n\n- **Three** tests for [refunds](https://x.y)\n- `safety` metric'
      )
    ).toBe('Plan - Three tests for refunds - safety metric');
  });

  it('says a code block is there instead of reading it out', () => {
    expect(markdownToSpeech('Use this:\n```json\n{"a": 1}\n```\nDone')).toBe(
      'Use this: (code block) Done'
    );
  });
});
