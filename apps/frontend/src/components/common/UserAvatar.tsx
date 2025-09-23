import React from 'react';
import { Avatar, AvatarProps } from '@mui/material';
import { AVATAR_SIZES, AvatarSize } from '@/constants/avatar-sizes';

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
        width: size,
        height: size,
        bgcolor: 'primary.main',
        flexShrink: 0,
        ...sx
      }}
      {...props}
    >
      {userName ? userName.charAt(0).toUpperCase() : 'U'}
    </Avatar>
  );
}
