/**
 * Creates a grammatically correct tooltip text for emoji reactions
 * @param reactions Array of reaction objects with user_name property
 * @param emoji The emoji that was reacted with
 * @returns Formatted tooltip text
 */
export function createReactionTooltipText(
  reactions: Array<{ user_name?: string }>,
  emoji: string
): string {
  const reactionCount = reactions.length;

  if (reactionCount === 1) {
    const userName = reactions[0].user_name || 'Unknown User';
    return `${userName} reacted with ${emoji}`;
  }

  if (reactionCount === 2) {
    const userNames = reactions.map(
      reaction => reaction.user_name || 'Unknown User'
    );
    return `${userNames[0]} and ${userNames[1]} reacted with ${emoji}`;
  }

  if (reactionCount === 3) {
    const userNames = reactions.map(
      reaction => reaction.user_name || 'Unknown User'
    );
    return `${userNames[0]}, ${userNames[1]} and ${userNames[2]} reacted with ${emoji}`;
  }

  // 4+ reactions
  const firstThreeNames = reactions
    .slice(0, 3)
    .map(reaction => reaction.user_name || 'Unknown User');
  const remainingCount = reactionCount - 3;
  const otherText = remainingCount === 1 ? 'other' : 'others';

  return `${firstThreeNames[0]}, ${firstThreeNames[1]} and ${firstThreeNames[2]} and ${remainingCount} ${otherText} reacted with ${emoji}`;
}
