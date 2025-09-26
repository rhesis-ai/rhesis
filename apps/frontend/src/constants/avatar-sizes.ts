/**
 * Standardized avatar sizes across the application
 */
export const AVATAR_SIZES = {
  /** Small avatars for tables, dropdowns, and compact UI elements */
  SMALL: 24,
  /** Medium avatars for forms, cards, and standard UI elements */
  MEDIUM: 32,
  /** Large avatars for headers, profiles, and prominent UI elements */
  LARGE: 40,
} as const;

export type AvatarSize = (typeof AVATAR_SIZES)[keyof typeof AVATAR_SIZES];
