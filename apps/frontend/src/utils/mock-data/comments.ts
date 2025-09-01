import { Comment, CreateCommentRequest, UpdateCommentRequest } from '@/types/comments';

// Mock comments data for different entity types
const mockComments: Comment[] = [
  // Test comments
  {
    id: '1',
    comment_text: 'This test looks comprehensive! I like how it covers both positive and negative scenarios. The edge case handling is particularly well thought out.',
    entity_id: '06f80785-0b14-43a5-9ef7-c508179a3299',
    entity_type: 'test',
    user_id: 'user-1',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(), // 12 minutes ago
    updated_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    emojis: { '👍': 2, '💡': 1 },
    user: {
      id: 'user-1',
      name: 'Joe Doe',
      email: 'joe.doe@company.com'
    }
  },
  {
    id: '2',
    comment_text: 'Have you considered adding edge cases for the boundary conditions? This might help catch some unexpected behaviors that could occur in production.',
    entity_id: '06f80785-0b14-43a5-9ef7-c508179a3299',
    entity_type: 'test',
    user_id: 'user-2',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    updated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    emojis: { '👍': 1, '🎯': 1 },
    user: {
      id: 'user-2',
      name: 'Sarah Chen',
      email: 'sarah.chen@company.com'
    }
  },
  
  // Test Set comments
  {
    id: '3',
    comment_text: 'Great work on the test coverage! This will definitely help with our CI/CD pipeline reliability. The performance tests are especially valuable.',
    entity_id: '431dc6c8-4be9-4f04-a028-ca1522caa282',
    entity_type: 'test_set',
    user_id: 'user-3',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
    updated_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    emojis: { '🚀': 1, '✅': 1 },
    user: {
      id: 'user-3',
      name: 'Alex Rodriguez',
      email: 'alex.rodriguez@company.com'
    }
  },
  {
    id: '4',
    comment_text: 'I noticed the test might fail under high load conditions. Should we add some performance testing scenarios? This could help identify bottlenecks early.',
    entity_id: '431dc6c8-4be9-4f04-a028-ca1522caa282',
    entity_type: 'test_set',
    user_id: 'user-4',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(), // 2 days ago
    updated_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    emojis: { '⚡': 1, '🔍': 1 },
    user: {
      id: 'user-4',
      name: 'Emily Watson',
      email: 'emily.watson@company.com'
    }
  },
  
  // Test Run comments
  {
    id: '5',
    comment_text: 'The test run completed successfully! All critical tests passed. The performance metrics look good compared to our baseline.',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    entity_type: 'test_run',
    user_id: 'user-1',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 minutes ago
    updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    emojis: { '🎉': 3, '✅': 2 },
    user: {
      id: 'user-1',
      name: 'Joe Doe',
      email: 'joe.doe@company.com'
    }
  },
  {
    id: '6',
    comment_text: 'I see one test failed due to a timeout issue. We should investigate the network latency in our test environment.',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    entity_type: 'test_run',
    user_id: 'user-2',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(), // 45 minutes ago
    updated_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    emojis: { '⚠️': 1, '🔧': 1 },
    user: {
      id: 'user-2',
      name: 'Sarah Chen',
      email: 'sarah.chen@company.com'
    }
  },
  {
    id: '7',
    comment_text: 'Great job on the test execution time! We reduced the overall runtime by 15% compared to the previous run.',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    entity_type: 'test_run',
    user_id: 'user-3',
    organization_id: 'org-1',
    created_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(), // 1 hour ago
    updated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    emojis: { '🚀': 2, '📈': 1 },
    user: {
      id: 'user-3',
      name: 'Alex Rodriguez',
      email: 'alex.rodriguez@company.com'
    }
  }
];

// Simulate API delay
const simulateApiDelay = (ms: number = 500) => 
  new Promise(resolve => setTimeout(resolve, ms));

// Mock comments service
export class MockCommentsService {
  private comments: Comment[] = [...mockComments];
  private nextId = 8;
  
  // Track emoji reactions per user per comment
  private emojiReactions: Record<string, Record<string, string[]>> = {
    // commentId -> emoji -> userIds[]
    '1': { '👍': ['user-2', 'user-3'], '💡': ['user-4'] },
    '2': { '👍': ['user-1'], '🎯': ['user-3'] },
    '3': { '🚀': ['user-1'], '✅': ['user-2'] },
    '4': { '⚡': ['user-1'], '🔍': ['user-2'] },
    '5': { '🎉': ['user-2', 'user-3', 'user-4'], '✅': ['user-1', 'user-2'] },
    '6': { '⚠️': ['user-1'], '🔧': ['user-3'] },
    '7': { '🚀': ['user-1', 'user-4'], '📈': ['user-2'] }
  };

  async getComments(entityType: string, entityId: string): Promise<Comment[]> {
    await simulateApiDelay();
    return this.comments.filter(
      comment => comment.entity_type === entityType && comment.entity_id === entityId
    );
  }

  async createComment(commentData: CreateCommentRequest): Promise<Comment> {
    await simulateApiDelay();
    
    const newComment: Comment = {
      id: this.nextId.toString(),
      comment_text: commentData.comment_text,
      entity_id: commentData.entity_id,
      entity_type: commentData.entity_type,
      user_id: 'current-user', // Mock current user
      organization_id: 'org-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      emojis: {},
      user: {
        id: 'current-user',
        name: 'You',
        email: 'you@company.com'
      }
    };

    this.comments.push(newComment);
    this.emojiReactions[newComment.id] = {};
    this.nextId++;
    
    return newComment;
  }

  async updateComment(commentId: string, updateData: UpdateCommentRequest): Promise<Comment> {
    await simulateApiDelay();
    
    const commentIndex = this.comments.findIndex(c => c.id === commentId);
    if (commentIndex === -1) {
      throw new Error('Comment not found');
    }

    const updatedComment = {
      ...this.comments[commentIndex],
      comment_text: updateData.comment_text,
      updated_at: new Date().toISOString()
    };

    this.comments[commentIndex] = updatedComment;
    return updatedComment;
  }

  async deleteComment(commentId: string): Promise<void> {
    await simulateApiDelay();
    
    const commentIndex = this.comments.findIndex(c => c.id === commentId);
    if (commentIndex === -1) {
      throw new Error('Comment not found');
    }

    this.comments.splice(commentIndex, 1);
    delete this.emojiReactions[commentId];
  }

  async addEmojiReaction(commentId: string, emoji: string, userId: string): Promise<void> {
    await simulateApiDelay();
    
    const comment = this.comments.find(c => c.id === commentId);
    if (!comment) {
      throw new Error('Comment not found');
    }

    // Initialize emoji reactions for this comment if it doesn't exist
    if (!this.emojiReactions[commentId]) {
      this.emojiReactions[commentId] = {};
    }
    
    if (!this.emojiReactions[commentId][emoji]) {
      this.emojiReactions[commentId][emoji] = [];
    }

    const userReactions = this.emojiReactions[commentId][emoji];
    const userIndex = userReactions.indexOf(userId);

    if (userIndex === -1) {
      // User hasn't reacted with this emoji, add it
      userReactions.push(userId);
    } else {
      // User already reacted with this emoji, remove it (toggle)
      userReactions.splice(userIndex, 1);
    }

    // Update the comment's emoji count
    comment.emojis[emoji] = userReactions.length;
    
    // Remove emoji from comment if no users reacted
    if (userReactions.length === 0) {
      delete comment.emojis[emoji];
    }
  }

  // Helper method to get current user ID
  getCurrentUserId(): string {
    return 'current-user';
  }

  // Helper method to check if current user has reacted with a specific emoji
  hasUserReacted(commentId: string, emoji: string): boolean {
    const userId = this.getCurrentUserId();
    return this.emojiReactions[commentId]?.[emoji]?.includes(userId) || false;
  }

  // Helper method to get current emoji state for a comment
  getCommentEmojis(commentId: string): Record<string, number> {
    const comment = this.comments.find(c => c.id === commentId);
    return comment ? { ...comment.emojis } : {};
  }
}

// Export singleton instance
export const mockCommentsService = new MockCommentsService();
