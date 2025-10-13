import React from 'react';
import { Box, Paper, Typography, Button, IconButton } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import { DeleteIcon, AddIcon } from '@/components/icons';
import { Model } from '@/utils/api-client/interfaces/model';
import { PROVIDER_ICONS } from '@/config/model-providers';

interface ConnectedModelCardProps {
  model: Model;
  onEdit: (model: Model, e: React.MouseEvent) => void;
  onDelete: (model: Model, e: React.MouseEvent) => void;
}

export function ConnectedModelCard({
  model,
  onEdit,
  onDelete,
}: ConnectedModelCardProps) {
  return (
    <Paper
      sx={{
        p: 3,
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        minHeight: 'inherit',
      }}
    >
      {/* Action buttons */}
      <Box
        sx={{
          position: 'absolute',
          top: theme => theme.spacing(1),
          right: theme => theme.spacing(1),
          display: 'flex',
          gap: theme => theme.spacing(0.5),
          zIndex: 1,
        }}
      >
        <IconButton
          size="small"
          onClick={e => onEdit(model, e)}
          sx={{
            padding: '2px',
            '& .MuiSvgIcon-root': {
              fontSize: theme =>
                theme?.typography?.helperText?.fontSize || '0.75rem',
              color: 'currentColor',
            },
          }}
        >
          <EditIcon fontSize="inherit" />
        </IconButton>
        <IconButton
          size="small"
          onClick={e => onDelete(model, e)}
          sx={{
            padding: '2px',
            '& .MuiSvgIcon-root': {
              fontSize: theme =>
                theme?.typography?.helperText?.fontSize || '0.75rem',
              color: 'currentColor',
            },
          }}
        >
          <DeleteIcon fontSize="inherit" />
        </IconButton>
      </Box>

      {/* Model header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: 'text.secondary',
          }}
        >
          {PROVIDER_ICONS[model.icon || 'custom'] || (
            <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.large }} />
          )}
          <CheckCircleIcon
            sx={{
              ml: -1,
              mt: -2,
              fontSize: 16,
              color: 'success.main',
            }}
          />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">{model.name}</Typography>
          <Typography color="text.secondary" variant="body2">
            {model.description}
          </Typography>
        </Box>
      </Box>

      {/* Model details */}
      <Box sx={{ mt: 1, mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Model: {model.model_name}
        </Typography>
      </Box>

      {/* Connected button */}
      <Box sx={{ mt: 'auto' }}>
        <Button
          fullWidth
          variant="contained"
          color="success"
          size="small"
          disableElevation
          disableRipple
          sx={{
            textTransform: 'none',
            borderRadius: theme => theme.shape.borderRadius * 0.375,
            pointerEvents: 'none',
            cursor: 'default',
          }}
        >
          Connected
        </Button>
      </Box>
    </Paper>
  );
}

interface AddModelCardProps {
  onClick: () => void;
}

export function AddModelCard({ onClick }: AddModelCardProps) {
  return (
    <Paper
      sx={{
        p: 3,
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'action.hover',
        cursor: 'pointer',
        transition: 'all 0.2s',
        minHeight: 'inherit',
        '&:hover': {
          bgcolor: 'action.selected',
          transform: 'translateY(-2px)',
        },
      }}
      onClick={onClick}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: 'text.secondary',
          }}
        >
          <AddIcon
            sx={{
              fontSize: theme => theme.iconSizes.large,
              border: 2,
              borderRadius: '50%',
              borderColor: 'text.secondary',
            }}
          />
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6">Add Model</Typography>
          <Typography color="text.secondary" variant="body2">
            Connect a new model
          </Typography>
        </Box>
      </Box>

      <Box sx={{ mt: 'auto' }}>
        <Button
          fullWidth
          variant="outlined"
          size="small"
          sx={{
            textTransform: 'none',
            borderRadius: theme => theme.shape.borderRadius * 0.375,
          }}
        >
          Add Model
        </Button>
      </Box>
    </Paper>
  );
}

