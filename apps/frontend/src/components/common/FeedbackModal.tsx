import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  CircularProgress,
  Rating,
} from '@mui/material';
import FeedbackIcon from '@mui/icons-material/Feedback';
import { useNotifications } from './NotificationContext';

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
}

export default function FeedbackModal({ open, onClose }: FeedbackModalProps) {
  const [feedback, setFeedback] = useState('');
  const [email, setEmail] = useState('');
  const [rating, setRating] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { show } = useNotifications();

  const handleSubmit = async () => {
    if (!feedback.trim()) {
      show('Please provide some feedback', { severity: 'error' });
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          feedback,
          email: email || undefined,
          rating,
        }),
      });

      if (response.ok) {
        show('Thank you for your feedback!', { severity: 'success' });
        setFeedback('');
        setEmail('');
        setRating(null);
        onClose();
      } else {
        const error = await response.json();
        throw new Error(error.message || 'Failed to send feedback');
      }
    } catch (error) {
      show(error instanceof Error ? error.message : 'Failed to send feedback', {
        severity: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <FeedbackIcon color="primary" />
        <Box sx={{ fontWeight: 'bold' }}>Provide Feedback</Box>
      </DialogTitle>
      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            We value your input! Please share any thoughts, suggestions, or
            issues you&apos;ve encountered.
          </Typography>
        </Box>

        <Box sx={{ mb: 3 }}>
          <Typography component="legend" gutterBottom>
            How would you rate your experience?
          </Typography>
          <Rating
            name="rating"
            value={rating}
            onChange={(event, newValue) => {
              setRating(newValue);
            }}
            size="large"
          />
        </Box>

        <TextField
          autoFocus
          margin="dense"
          id="feedback"
          label="Your Feedback"
          fullWidth
          multiline
          rows={4}
          value={feedback}
          onChange={e => setFeedback(e.target.value)}
          required
        />

        <TextField
          margin="dense"
          id="email"
          label="Your Email (optional, if you'd like us to follow up)"
          type="email"
          fullWidth
          value={email}
          onChange={e => setEmail(e.target.value)}
          sx={{ mt: 2 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="primary"
          disabled={isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} /> : null}
        >
          {isSubmitting ? 'Sending...' : 'Send Feedback'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
