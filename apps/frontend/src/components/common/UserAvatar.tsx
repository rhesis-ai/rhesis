import React from 'react';
import { Avatar, AvatarProps } from '@mui/material';
import { AVATAR_SIZES, AvatarSize } from '@/constants/avatar-sizes';
import { rem } from '@/styles/theme-constants';

interface UserAvatarProps extends Omit<AvatarProps, 'src' | 'alt'> {
  userName?: string;
  userPicture?: string;
  size?: AvatarSize;
}

export function UserAvatar({
  userName,
  userPicture,
  size = AVATAR_SIZES.LARGE,
  sx,
  ...props
}: UserAvatarProps) {
  return (
    <Avatar
      src={userPicture}
      alt={userName || 'User'}
      sx={{
        // rem, so the avatar grows with its initial at larger font sizes.
        width: rem(size),
        height: rem(size),
        bgcolor: 'primary.main',
        flexShrink: 0,
        ...sx,
      }}
      {...props}
    >
      {userName ? userName.charAt(0).toUpperCase() : 'U'}
    </Avatar>
  );
}
