import * as React from 'react';
import { useTheme } from '@mui/material/styles';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useRouter } from 'next/navigation';
import GradingIcon from '@mui/icons-material/Grading';
import ApiIcon from '@mui/icons-material/Api';
import CodeIcon from '@mui/icons-material/Code';
import ChatIcon from '@mui/icons-material/Chat';
import Chip from '@mui/material/Chip';

interface MetricTypeOption {
  type: 'Grading' | 'API Call' | 'Custom Code' | 'Custom Prompt';
  title: string;
  description: string;
  icon: React.ReactNode;
  disabled?: boolean;
}

const metricTypes: MetricTypeOption[] = [
  {
    type: 'Custom Prompt',
    title: 'Evaluation Prompt',
    description:
      'Evaluates the response using a LLM judge and a custom evaluation prompt',
    icon: <ChatIcon />,
  },
  {
    type: 'Custom Code',
    title: 'Code Evaluation',
    description: 'Evaluates the response using the code provided',
    icon: <CodeIcon />,
    disabled: true,
  },
  {
    type: 'API Call',
    title: 'API Call',
    description: 'Uses an external API service to check the response',
    icon: <ApiIcon />,
    disabled: true,
  },
];

interface MetricTypeDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function MetricTypeDialog({
  open,
  onClose,
}: MetricTypeDialogProps) {
  const router = useRouter();
  const theme = useTheme();

  const handleTypeSelect = (type: string, disabled?: boolean) => {
    if (disabled) return;
    router.push(`/metrics/new?type=${type.toLowerCase().replace(' ', '-')}`);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create a custom metric for your evaluation</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          {metricTypes.map(option => (
            <Box
              key={option.type}
              onClick={() => handleTypeSelect(option.type, option.disabled)}
              sx={{
                p: 2,
                mb: 2,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: theme => theme.shape.borderRadius * 0.25,
                cursor: option.disabled ? 'not-allowed' : 'pointer',
                opacity: option.disabled ? 0.7 : 1,
                '&:hover': {
                  bgcolor: option.disabled ? undefined : 'action.hover',
                },
                transition: theme.transitions.create('background-color', {
                  duration: theme.transitions.duration.short,
                }),
                position: 'relative',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box
                  sx={{
                    mr: 1.5,
                    color: 'primary.main',
                    display: 'flex',
                    alignItems: 'center',
                    opacity: option.disabled ? 0.5 : 1,
                  }}
                >
                  {option.icon}
                </Box>
                <Typography
                  variant="subtitle1"
                  sx={{
                    flex: 1,
                    color: option.disabled ? 'text.disabled' : 'text.primary',
                  }}
                >
                  {option.title}
                </Typography>
                {option.disabled && (
                  <Chip
                    label="Coming Soon"
                    size="small"
                    sx={{
                      bgcolor: 'primary.main',
                      color: 'primary.contrastText',
                      fontSize:
                        theme?.typography?.chartLabel?.fontSize || '0.75rem',
                    }}
                  />
                )}
              </Box>
              <Typography
                variant="body2"
                color={option.disabled ? 'text.disabled' : 'text.secondary'}
              >
                {option.description}
              </Typography>
            </Box>
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
}
