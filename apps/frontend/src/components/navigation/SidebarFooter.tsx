import React, { useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';
import FeedbackModal from '../common/FeedbackModal';

type SidebarFooterProps = {
  mini?: boolean;
  sidebarExpandedWidth?: number;
};

export default function SidebarFooter({
  mini = false,
}: SidebarFooterProps) {
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
          <Button
            onClick={handleOpenFeedbackModal}
            sx={{
              minWidth: '3rem',
              minHeight: '3rem',
              '&:hover': {
                backgroundColor: 'action.hover',
                color: 'primary.main',
              },
            }}
          >
            <FeedbackIcon sx={{ width: '20px', height: '20px' }} />
          </Button>
        </Box>
      ) : (
        <Box
          sx={{
            padding: 2,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          {' '}
          <Button
            onClick={handleOpenFeedbackModal}
            startIcon={<FeedbackIcon />}
            sx={{
              minWidth: 0, // allow content to shrink within early expansion frames
              maxWidth: '100%',
              color: 'text.secondary',
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
                gap: 1,
              }}
            >
              <Typography variant="body2">Provide Feedback</Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                sx={{ opacity: 0.6, marginLeft: 'auto' }}
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
