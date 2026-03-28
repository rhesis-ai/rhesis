'use client';

import React from 'react';
import { Box, Typography, Avatar } from '@mui/material';

interface UserAvatarRowProps {
  displayName: string;
  email: string;
  avatarSrc?: string;
  onClick?: (event: React.MouseEvent<HTMLElement>) => void;
}

export default function UserAvatarRow({
  displayName,
  email,
  avatarSrc,
  onClick,
}: UserAvatarRowProps) {
  return (
    <Box
      onClick={onClick}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        cursor: 'pointer',
        p: 1.25,
        borderRadius: (theme: any) => `${theme.customRadius.full}px`,
        '&:hover': { bgcolor: 'grey.200' },
      }}
    >
      <Avatar
        src={avatarSrc}
        alt={displayName}
        sx={{
          width: 32,
          height: 32,
          fontSize: 14,
          border: '2px solid',
          borderColor: 'common.black',
        }}
      >
        {displayName.charAt(0).toUpperCase()}
      </Avatar>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography
          fontWeight={400}
          fontSize={14}
          lineHeight="22px"
          noWrap
          sx={{ textDecoration: 'underline', color: 'text.primary' }}
        >
          {displayName}
        </Typography>
        <Typography
          fontSize={12}
          lineHeight="18px"
          noWrap
          display="block"
          sx={{ color: 'grey.500' }}
        >
          {email}
        </Typography>
      </Box>
    </Box>
  );
}
