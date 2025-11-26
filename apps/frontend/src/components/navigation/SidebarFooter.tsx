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
            padding: 0.5,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Tooltip title="Feedback" placement="right">
            <Button
              onClick={handleOpenFeedbackModal}
              sx={{
                minWidth: '36px',
                minHeight: '36px',
                width: '36px',
                height: '36px',
                borderRadius: theme => theme.shape.borderRadius * 1.5,
                color: 'text.secondary',
                '&:hover': {
                  backgroundColor: 'action.hover',
                  color: 'primary.main',
                },
              }}
            >
              <FeedbackIcon sx={{ width: '16px', height: '16px' }} />
            </Button>
          </Tooltip>
        </Box>
      ) : (
        <Box
          sx={{
            padding: 1,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Button
            onClick={handleOpenFeedbackModal}
            startIcon={<FeedbackIcon sx={{ width: '16px', height: '16px' }} />}
            sx={{
              width: '100%',
              justifyContent: 'flex-start',
              color: 'text.secondary',
              textTransform: 'none',
              borderRadius: theme => theme.shape.borderRadius,
              padding: theme => theme.spacing(0.5, 1),
              minHeight: '36px',
              maxHeight: '42px',
              '&:hover': {
                backgroundColor: 'action.hover',
                color: 'primary.main',
              },
              '& .MuiButton-startIcon': {
                marginRight: theme => theme.spacing(1.5),
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
              <Typography variant="body2">Feedback</Typography>
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
