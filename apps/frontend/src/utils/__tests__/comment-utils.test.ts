import { createReactionTooltipText } from '../comment-utils';

describe('createReactionTooltipText', () => {
  it('handles single reaction', () => {
    const reactions = [{ user_name: 'Alice' }];
    expect(createReactionTooltipText(reactions, '👍')).toBe(
      'Alice reacted with 👍'
    );
  });

  it('handles two reactions', () => {
    const reactions = [{ user_name: 'Alice' }, { user_name: 'Bob' }];
    expect(createReactionTooltipText(reactions, '❤️')).toBe(
      'Alice and Bob reacted with ❤️'
    );
  });

  it('handles three reactions', () => {
    const reactions = [
      { user_name: 'Alice' },
      { user_name: 'Bob' },
      { user_name: 'Charlie' },
    ];
    expect(createReactionTooltipText(reactions, '🎉')).toBe(
      'Alice, Bob and Charlie reacted with 🎉'
    );
  });

  it('handles four reactions with "other"', () => {
    const reactions = [
      { user_name: 'Alice' },
      { user_name: 'Bob' },
      { user_name: 'Charlie' },
      { user_name: 'Dave' },
    ];
    expect(createReactionTooltipText(reactions, '👍')).toBe(
      'Alice, Bob and Charlie and 1 other reacted with 👍'
    );
  });

  it('handles five+ reactions with "others"', () => {
    const reactions = [
      { user_name: 'Alice' },
      { user_name: 'Bob' },
      { user_name: 'Charlie' },
      { user_name: 'Dave' },
      { user_name: 'Eve' },
    ];
    expect(createReactionTooltipText(reactions, '🔥')).toBe(
      'Alice, Bob and Charlie and 2 others reacted with 🔥'
    );
  });

  it('handles missing user names', () => {
    const reactions = [{ user_name: undefined }];
    expect(createReactionTooltipText(reactions, '👍')).toBe(
      'Unknown User reacted with 👍'
    );
  });

  it('handles mixed known and unknown users', () => {
    const reactions = [{ user_name: 'Alice' }, { user_name: undefined }];
    expect(createReactionTooltipText(reactions, '👍')).toBe(
      'Alice and Unknown User reacted with 👍'
    );
  });
});
