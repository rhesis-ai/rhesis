'use client';

import React, { useState } from 'react';
import { Box, Tooltip, Avatar, IconButton, Divider } from '@mui/material';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import ForumIcon from '@mui/icons-material/ForumOutlined';
import { useSession } from 'next-auth/react';
import UserMenu from './UserMenu';
import SidebarLinkItem from './SidebarLinkItem';
import UserAvatarRow from './UserAvatarRow';

interface SidebarFooterProps {
  mini?: boolean;
}

export default function SidebarFooter({ mini = false }: SidebarFooterProps) {
  const { data: session } = useSession();
  const [userMenuAnchor, setUserMenuAnchor] = useState<HTMLElement | null>(
    null
  );

  const user = session?.user;
  const displayName = user?.name || 'User';
  const email = user?.email || '';
  const avatarSrc = user?.image || undefined;

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchor(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchor(null);
  };

  if (mini) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 0.5,
          py: 1,
          px: 0.5,
        }}
      >
        <Tooltip title="Star Rhesis" placement="right">
          <IconButton
            size="small"
            onClick={() =>
              window.open(
                'https://github.com/rhesis-ai/rhesis',
                '_blank',
                'noopener'
              )
            }
          >
            <StarBorderIcon sx={{ fontSize: 24 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Support" placement="right">
          <IconButton
            size="small"
            onClick={() =>
              window.open('https://docs.rhesis.ai', '_blank', 'noopener')
            }
          >
            <ForumIcon sx={{ fontSize: 24 }} />
          </IconButton>
        </Tooltip>
        <Divider sx={{ width: '100%', my: 0.5 }} />
        <Tooltip title={displayName} placement="right">
          <IconButton onClick={handleUserMenuOpen} size="small" sx={{ p: 0 }}>
            <Avatar
              src={avatarSrc}
              alt={displayName}
              sx={{ width: 32, height: 32, fontSize: 14 }}
            >
              {displayName.charAt(0).toUpperCase()}
            </Avatar>
          </IconButton>
        </Tooltip>
        <UserMenu
          anchorEl={userMenuAnchor}
          open={Boolean(userMenuAnchor)}
          onClose={handleUserMenuClose}
        />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2.5,
        pt: 2,
      }}
    >
      {/* Links card — white bg, rounded 16px */}
      <Box
        sx={{
          bgcolor: 'background.paper',
          borderRadius: (theme: any) => `${theme.customRadius.xl}px`,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <SidebarLinkItem
          href="https://github.com/rhesis-ai/rhesis"
          icon={<StarBorderIcon sx={{ fontSize: 24 }} />}
          label="Star Rhesis"
        />
        <SidebarLinkItem
          href="https://docs.rhesis.ai"
          icon={<ForumIcon sx={{ fontSize: 24 }} />}
          label="Support"
        />
      </Box>

      <UserAvatarRow
        displayName={displayName}
        email={email}
        avatarSrc={avatarSrc}
        onClick={handleUserMenuOpen}
      />

      <UserMenu
        anchorEl={userMenuAnchor}
        open={Boolean(userMenuAnchor)}
        onClose={handleUserMenuClose}
      />
    </Box>
  );
}
