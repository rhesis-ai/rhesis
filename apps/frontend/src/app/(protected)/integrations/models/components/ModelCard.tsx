import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Chip,
  Stack,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import StarIcon from '@mui/icons-material/Star';
import { DeleteIcon, AddIcon } from '@/components/icons';
import { Model } from '@/utils/api-client/interfaces/model';
import { UserSettings } from '@/utils/api-client/interfaces/user';
import { PROVIDER_ICONS } from '@/config/model-providers';

interface ConnectedModelCardProps {
  model: Model;
  userSettings?: UserSettings | null;
  onEdit: (model: Model, e: React.MouseEvent) => void;
  onDelete: (model: Model, e: React.MouseEvent) => void;
}

export function ConnectedModelCard({
  model,
  userSettings,
  onEdit,
  onDelete,
}: ConnectedModelCardProps) {
  // Check if this model is set as default for generation or evaluation
  const isGenerationDefault = userSettings?.models?.generation?.model_id === model.id;
  const isEvaluationDefault = userSettings?.models?.evaluation?.model_id === model.id;
  const isAnyDefault = isGenerationDefault || isEvaluationDefault;

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
          {/* Allow editing settings for all models, but only show delete for non-protected */}
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
          {!model.is_protected && (
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
          )}
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
          {/* Model name and default indicator */}
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
            {isAnyDefault && (
              <Box
                component="span"
                sx={{
                  ml: 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.5,
                }}
              >
                <StarIcon sx={{ fontSize: '0.875rem', color: 'primary.main' }} />
                <Box component="span" sx={{ fontWeight: 500, color: 'primary.main' }}>
                  Default: {isGenerationDefault && isEvaluationDefault
                    ? 'Generation & Evaluation'
                    : isGenerationDefault
                    ? 'Generation'
                    : 'Evaluation'}
                </Box>
              </Box>
            )}
          </Typography>

          {/* Connected status or System badge */}
          <Chip
            icon={<CheckCircleIcon />}
            label={model.is_protected ? "Rhesis Managed" : "Connected"}
            size="small"
            variant="outlined"
            sx={{
              width: '100%',
              color: 'text.secondary',
              borderColor: model.is_protected ? 'info.main' : 'divider',
              '& .MuiChip-icon': {
                color: model.is_protected ? 'info.main' : 'primary.main',
                opacity: 0.7,
              },
            }}
          />
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

          <Chip
            icon={<AddIcon />}
            label="New"
            size="small"
            variant="outlined"
            sx={{
              width: '100%',
              '& .MuiChip-icon': {
                color: 'text.secondary',
              },
              borderColor: 'divider',
              color: 'text.secondary',
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
}
