'use client';

import React from 'react';
import {
  Box,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  useTheme,
  useMediaQuery,
} from '@mui/material';

export interface SettingsSection {
  id: string;
  label: string;
  icon?: React.ReactNode;
}

interface SettingsNavigationProps {
  sections: SettingsSection[];
  activeSection: string;
  onSectionChange: (sectionId: string) => void;
}

export default function SettingsNavigation({
  sections,
  activeSection,
  onSectionChange,
}: SettingsNavigationProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const handleSectionClick = (sectionId: string) => {
    onSectionChange(sectionId);
    // Scroll to section
    const element = document.getElementById(sectionId);
    if (element) {
      const yOffset = -80; // Offset for fixed headers
      const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }
  };

  if (isMobile) {
    // On mobile, show horizontal scrollable tabs
    return (
      <Paper sx={{ mb: 3, overflow: 'auto' }}>
        <Box sx={{ display: 'flex', gap: 1, p: 1 }}>
          {sections.map((section) => (
            <Box
              key={section.id}
              onClick={() => handleSectionClick(section.id)}
              sx={{
                px: 2,
                py: 1,
                borderRadius: 1,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                backgroundColor:
                  activeSection === section.id
                    ? 'primary.main'
                    : 'transparent',
                color:
                  activeSection === section.id
                    ? 'primary.contrastText'
                    : 'text.primary',
                '&:hover': {
                  backgroundColor:
                    activeSection === section.id
                      ? 'primary.dark'
                      : 'action.hover',
                },
              }}
            >
              {section.label}
            </Box>
          ))}
        </Box>
      </Paper>
    );
  }

  // On desktop, show vertical sidebar
  return (
    <Paper sx={{ position: 'sticky', top: 80 }}>
      <List component="nav">
        {sections.map((section) => (
          <ListItemButton
            key={section.id}
            selected={activeSection === section.id}
            onClick={() => handleSectionClick(section.id)}
            sx={{
              '&.Mui-selected': {
                backgroundColor: 'primary.main',
                color: 'primary.contrastText',
                '&:hover': {
                  backgroundColor: 'primary.dark',
                },
                '& .MuiListItemIcon-root': {
                  color: 'primary.contrastText',
                },
              },
            }}
          >
            {section.icon && (
              <ListItemIcon
                sx={{
                  minWidth: 40,
                  color: activeSection === section.id ? 'inherit' : 'action.active',
                }}
              >
                {section.icon}
              </ListItemIcon>
            )}
            <ListItemText primary={section.label} />
          </ListItemButton>
        ))}
      </List>
    </Paper>
  );
}

