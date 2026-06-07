'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import MenuBookIcon from '@mui/icons-material/MenuBookOutlined';
import GitHubIcon from '@mui/icons-material/GitHub';
import EmailOutlinedIcon from '@mui/icons-material/EmailOutlined';
import { FilterDrawerShell } from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import DiscordIcon from '@/components/DiscordIcon';

interface SupportDrawerProps {
  open: boolean;
  onClose: () => void;
}

interface SectionProps {
  title: string;
  description: string;
  children: React.ReactNode;
}

function SupportSection({ title, description, children }: SectionProps) {
  return (
    <Box
      sx={{
        borderTop: theme => `1px solid ${theme.palette.divider}`,
        pt: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <Box>
        <Typography
          sx={{
            fontSize: 18,
            fontWeight: 700,
            lineHeight: '25px',
            color: theme => theme.palette.greyscale.title,
          }}
        >
          {title}
        </Typography>
        <Typography
          sx={{
            fontSize: 12,
            fontWeight: 400,
            lineHeight: '18px',
            color: theme => theme.palette.greyscale.subtitle,
            mt: '4px',
          }}
        >
          {description}
        </Typography>
      </Box>
      {children}
    </Box>
  );
}

interface CommunityLinkProps {
  icon: React.ReactNode;
  label: string;
  href: string;
}

function CommunityLink({ icon, label, href }: CommunityLinkProps) {
  return (
    <Box
      component="a"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        px: '14px',
        py: '8px',
        borderRadius: BORDER_RADIUS.sm,
        textDecoration: 'none',
        cursor: 'pointer',
        '&:hover': {
          bgcolor: theme => theme.palette.greyscale.surface2,
        },
        transition: 'background-color 0.15s ease',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexShrink: 0,
          color: theme => theme.palette.greyscale.body,
          '& svg': { width: 24, height: 24 },
        }}
      >
        {icon}
      </Box>
      <Typography
        sx={{
          fontSize: 14,
          fontWeight: 400,
          lineHeight: '22px',
          color: theme => theme.palette.greyscale.body,
          flex: 1,
        }}
      >
        {label}
      </Typography>
      <OpenInNewIcon
        sx={{
          fontSize: 14,
          color: theme => theme.palette.greyscale.subtitle,
          flexShrink: 0,
        }}
      />
    </Box>
  );
}

export default function SupportDrawer({ open, onClose }: SupportDrawerProps) {
  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      title="Support"
      anchor="right"
    >
      <SupportSection
        title="Docs"
        description="Explore guides, API references, and examples to get the most out of Rhesis."
      >
        <Button
          component="a"
          href="https://docs.rhesis.ai"
          target="_blank"
          rel="noopener noreferrer"
          variant="outlined"
          startIcon={<MenuBookIcon />}
          fullWidth
          sx={{
            borderWidth: 2,
            borderColor: 'primary.main',
            color: 'primary.main',
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
            justifyContent: 'flex-start',
            '&:hover': { borderWidth: 2 },
          }}
        >
          View documentation
        </Button>
      </SupportSection>

      <SupportSection
        title="Email a Support Engineer"
        description="Still stuck? Our support team is happy to help you get unblocked."
      >
        <Button
          component="a"
          href="mailto:hello@rhesis.ai"
          variant="outlined"
          startIcon={<EmailOutlinedIcon />}
          fullWidth
          sx={{
            borderWidth: 2,
            borderColor: 'primary.main',
            color: 'primary.main',
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
            justifyContent: 'flex-start',
            '&:hover': { borderWidth: 2 },
          }}
        >
          Email a Support Engineer
        </Button>
      </SupportSection>

      <SupportSection
        title="Community & Resources"
        description="Join the conversation and connect with the Rhesis community."
      >
        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
          <CommunityLink
            icon={<GitHubIcon />}
            label="GitHub"
            href="https://github.com/rhesis-ai/rhesis"
          />
          <CommunityLink
            icon={<DiscordIcon />}
            label="Discord"
            href="https://discord.rhesis.ai"
          />
        </Box>
      </SupportSection>
    </FilterDrawerShell>
  );
}
