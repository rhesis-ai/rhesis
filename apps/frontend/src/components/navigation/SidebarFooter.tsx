'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Tooltip,
  Avatar,
  IconButton,
  Divider,
} from '@mui/material';
import StarBorderIcon from '@mui/icons-material/StarBorder';
import ForumIcon from '@mui/icons-material/ForumOutlined';
import { useSession } from 'next-auth/react';
import UserMenu from './UserMenu';

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
          borderRadius: 2,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box
          component="a"
          href="https://github.com/rhesis-ai/rhesis"
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            textDecoration: 'none',
            color: 'text.secondary',
            px: 1.75,
            py: 1,
            borderRadius: 1,
            '&:hover': { bgcolor: 'grey.200' },
          }}
        >
          <StarBorderIcon sx={{ fontSize: 24 }} />
          <Typography fontSize={14} lineHeight="22px">
            Star Rhesis
          </Typography>
        </Box>
        <Box
          component="a"
          href="https://docs.rhesis.ai"
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            textDecoration: 'none',
            color: 'text.secondary',
            px: 1.75,
            py: 1,
            borderRadius: 1,
            '&:hover': { bgcolor: 'grey.200' },
          }}
        >
          <ForumIcon sx={{ fontSize: 24 }} />
          <Typography fontSize={14} lineHeight="22px">
            Support
          </Typography>
        </Box>
      </Box>

      {/* User avatar row */}
      <Box
        onClick={handleUserMenuOpen}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.25,
          cursor: 'pointer',
          p: 1.25,
          borderRadius: '999px',
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

      <UserMenu
        anchorEl={userMenuAnchor}
        open={Boolean(userMenuAnchor)}
        onClose={handleUserMenuClose}
      />
    </Box>
  );
}
