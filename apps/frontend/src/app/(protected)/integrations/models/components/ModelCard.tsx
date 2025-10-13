import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
} from '@mui/material';
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
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
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

        <Box>
          {/* Model header */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                display: 'flex',
                alignItems: 'center',
                color: 'primary.main',
              }}
            >
              {PROVIDER_ICONS[model.icon || 'custom'] || <SmartToyIcon />}
              <CheckCircleIcon
                sx={{
                  ml: -0.5,
                  mt: -1.5,
                  fontSize: 16,
                  color: 'success.main',
                }}
              />
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
              }}
            >
              {model.name}
            </Typography>
          </Box>

          {/* Model description and details */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            {model.description}
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          {/* Model name */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 1.5,
              minHeight: '1.5em',
            }}
          >
            Model: {model.model_name}
          </Typography>

          {/* Connected button */}
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
      </CardContent>
    </Card>
  );
}

interface AddModelCardProps {
  onClick: () => void;
}

export function AddModelCard({ onClick }: AddModelCardProps) {
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'action.hover',
        cursor: 'pointer',
        transition: 'all 0.2s',
        '&:hover': {
          bgcolor: 'action.selected',
          transform: 'translateY(-2px)',
        },
      }}
      onClick={onClick}
    >
      <CardContent
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          pb: 2,
          pt: 3,
        }}
      >
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                display: 'flex',
                alignItems: 'center',
                color: 'primary.main',
              }}
            >
              <AddIcon />
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
              }}
            >
              Add Model
            </Typography>
          </Box>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            Connect a new model
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 1.5,
              minHeight: '1.5em',
            }}
          >
            {/* Empty space for alignment */}
          </Typography>

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
      </CardContent>
    </Card>
  );
}
