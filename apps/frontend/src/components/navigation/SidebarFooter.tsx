import React, { useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';
import FeedbackModal from '../common/FeedbackModal';

export default function SidebarFooter() {
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);

  const handleOpenFeedbackModal = () => {
    setFeedbackModalOpen(true);
  };

  const handleCloseFeedbackModal = () => {
    setFeedbackModalOpen(false);
  };

  return (
    <>
      <Box
        sx={{
          padding: 2,
          borderTop: '1px solid',
          borderColor: 'divider',
          marginTop: 'auto', // Push to bottom of sidebar
        }}
      >
        <Button
          fullWidth
          startIcon={<FeedbackIcon />}
          onClick={handleOpenFeedbackModal}
          sx={{
            justifyContent: 'flex-start',
            color: 'text.secondary',
            '&:hover': {
              backgroundColor: 'action.hover',
              color: 'primary.main',
            },
            textTransform: 'none',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              width: '100%',
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

      <FeedbackModal
        open={feedbackModalOpen}
        onClose={handleCloseFeedbackModal}
      />
    </>
  );
}
