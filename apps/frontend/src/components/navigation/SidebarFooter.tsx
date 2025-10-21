import React, { useState } from 'react';
import { Box, Button, Typography, Tooltip } from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';
import FeedbackModal from '../common/FeedbackModal';

type SidebarFooterProps = {
  mini?: boolean;
};

export default function SidebarFooter({ mini = false }: SidebarFooterProps) {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);

  const handleOpenFeedbackModal = () => {
    setFeedbackModalOpen(true);
  };

  const handleCloseFeedbackModal = () => {
    setFeedbackModalOpen(false);
  };

  return (
    <>
      {mini ? (
        <Box
          sx={{
            padding: 1,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Tooltip title="Provide Feedback" placement="right">
            <Button
              onClick={handleOpenFeedbackModal}
              sx={{
                minWidth: '48px',
                minHeight: '48px',
                width: '48px',
                height: '48px',
                borderRadius: theme => theme.shape.borderRadius * 1.5,
                color: 'text.secondary',
                '&:hover': {
                  backgroundColor: 'action.hover',
                  color: 'primary.main',
                },
              }}
            >
              <FeedbackIcon sx={{ width: '20px', height: '20px' }} />
            </Button>
          </Tooltip>
        </Box>
      ) : (
        <Box
          sx={{
            padding: 2,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Button
            onClick={handleOpenFeedbackModal}
            startIcon={<FeedbackIcon />}
            sx={{
              width: '100%',
              justifyContent: 'flex-start',
              color: 'text.secondary',
              textTransform: 'none',
              borderRadius: theme => theme.shape.borderRadius,
              padding: theme => theme.spacing(1, 1.5),
              '&:hover': {
                backgroundColor: 'action.hover',
                color: 'primary.main',
              },
            }}
          >
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                width: '100%',
                whiteSpace: 'nowrap',
              }}
            >
              <Typography variant="body2">Provide Feedback</Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                sx={{
                  opacity: 0.6,
                  marginLeft: 1,
                  flexShrink: 0,
                }}
              >
                v{process.env.APP_VERSION || '0.0.0'}
              </Typography>
            </Box>
          </Button>
        </Box>
      )}

      <FeedbackModal
        open={feedbackModalOpen}
        onClose={handleCloseFeedbackModal}
      />
    </>
  );
}
