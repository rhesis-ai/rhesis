'use client';

import React, { ReactNode } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
} from '@mui/material';
import { Grid } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export interface SelectionCardConfig {
  id: string;
  title: string;
  description: string;
  icon: ReactNode;
  iconBgColor: string;
  iconColor: string;
  buttonLabel: string;
  buttonVariant: 'contained' | 'outlined';
  buttonColor?:
    | 'primary'
    | 'secondary'
    | 'warning'
    | 'error'
    | 'info'
    | 'success';
  onClick: () => void;
  preview?: ReactNode;
}

interface SelectionModalProps {
  open: boolean;
  onClose: () => void;
  onBack?: () => void;
  title: string;
  subtitle: string;
  cards: SelectionCardConfig[];
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
  additionalContent?: ReactNode;
  cardMinHeight?: string;
  fillHeight?: boolean;
  showIcons?: boolean;
}

/**
 * SelectionModal Component
 * Reusable modal for displaying selection cards in a consistent layout
 */
export default function SelectionModal({
  open,
  onClose,
  onBack,
  title,
  subtitle,
  cards,
  maxWidth = 'lg',
  additionalContent,
  cardMinHeight,
  fillHeight = false,
  showIcons = true,
}: SelectionModalProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={maxWidth}
      fullWidth
      scroll="paper"
      PaperProps={{
        sx: {
          borderRadius: theme => theme.shape.borderRadius,
          bgcolor: 'background.paper',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {onBack && (
            <IconButton onClick={onBack} size="small">
              <ArrowBackIcon />
            </IconButton>
          )}
          <Box>
            <Typography variant="h6">{title}</Typography>
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          </Box>
        </Box>
        <IconButton edge="end" onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent
        sx={{
          pt: 3,
          px: 3,
          pb: 3,
          overflow: 'visible',
          ...(fillHeight &&
            {
              // display: 'flex',
              // flexDirection: 'column',
            }),
        }}
      >
        {/* Primary Action Cards */}
        <Grid
          container
          spacing={3}
          sx={{
            mt: 0,
            mb: additionalContent ? 6 : 0,
            ...(fillHeight &&
              {
                // flex: 1,
              }),
          }}
        >
          {cards.map(card => (
            <Grid size={{ xs: 12, md: 6 }} key={card.id}>
              <Card
                sx={{
                  height: '100%',
                  ...(cardMinHeight && { minHeight: cardMinHeight }),
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'all 0.2s ease-in-out',
                  '&:hover': {
                    bgcolor: 'background.light3',
                    transform: 'translateY(-2px)',
                  },
                }}
                onClick={card.onClick}
              >
                <CardContent
                  sx={{
                    p: 4,
                    textAlign: 'center',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                    height: '100%',
                  }}
                >
                  {showIcons && (
                    <Box
                      sx={{
                        bgcolor: card.iconBgColor,
                        borderRadius: theme => theme.shape.circular,
                        width: 64,
                        height: 64,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mx: 'auto',
                      }}
                    >
                      <Box sx={{ fontSize: 48, color: card.iconColor }}>
                        {card.icon}
                      </Box>
                    </Box>
                  )}
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                      flex: 1,
                    }}
                  >
                    <Box
                      sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}
                    >
                      <Typography variant="h6" component="h3">
                        {card.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {card.description}
                      </Typography>
                    </Box>
                    {card.preview && <Box>{card.preview}</Box>}
                  </Box>
                  <Button
                    variant={card.buttonVariant}
                    size="large"
                    fullWidth
                    color={card.buttonColor || 'secondary'}
                  >
                    {card.buttonLabel}
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Additional Content Section (e.g., Templates) */}
        {additionalContent && <Box sx={{ mb: 4 }}>{additionalContent}</Box>}
      </DialogContent>
    </Dialog>
  );
}
