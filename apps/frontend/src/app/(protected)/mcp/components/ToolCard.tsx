import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Chip,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import EditIcon from '@mui/icons-material/Edit';
import { DeleteIcon, AddIcon } from '@/components/icons';
import { Tool } from '@/utils/api-client/interfaces/tool';
import { MCP_PROVIDER_ICONS } from '@/config/mcp-providers';

interface ConnectedToolCardProps {
  tool: Tool;
  onEdit: (tool: Tool, e: React.MouseEvent) => void;
  onDelete: (tool: Tool, e: React.MouseEvent) => void;
}

export function ConnectedToolCard({
  tool,
  onEdit,
  onDelete,
}: ConnectedToolCardProps) {
  const providerName = tool.tool_provider_type?.type_value || 'Unknown';
  const providerIconKey = providerName;
  const providerIcon = MCP_PROVIDER_ICONS[providerIconKey] || (
    <SmartToyIcon sx={{ fontSize: theme => theme.iconSizes.medium }} />
  );

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
            onClick={e => onEdit(tool, e)}
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
            onClick={e => onDelete(tool, e)}
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
          {/* Tool header */}
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Box
              sx={{
                mr: 1.5,
                display: 'flex',
                alignItems: 'center',
                color: 'primary.main',
              }}
            >
              {providerIcon}
            </Box>
            <Typography
              variant="subtitle1"
              component="div"
              sx={{
                fontWeight: 500,
                lineHeight: 1.2,
              }}
            >
              {tool.name}
            </Typography>
          </Box>

          {/* Tool description */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            {tool.description || 'MCP connection'}
          </Typography>
        </Box>

        <Box sx={{ mt: 2 }}>
          {/* Provider info */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mb: 0.5,
              minHeight: '1.5em',
            }}
          >
            Provider: {tool.tool_provider_type?.description || providerName}
          </Typography>

          {/* Repository info for GitHub */}
          {providerName === 'github' && tool.tool_metadata?.repository && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{
                display: 'block',
                mb: 1.5,
                fontStyle: 'italic',
              }}
            >
              Repository: {tool.tool_metadata.repository.full_name}
            </Typography>
          )}

          {/* Spacing for non-GitHub or GitHub without repository */}
          {!(providerName === 'github' && tool.tool_metadata?.repository) && (
            <Box sx={{ mb: 1.5 }} />
          )}

          {/* Connected status */}
          <Chip
            icon={<CheckCircleIcon />}
            label="Connected"
            size="small"
            variant="outlined"
            sx={{
              width: '100%',
              color: 'text.secondary',
              borderColor: 'divider',
              '& .MuiChip-icon': {
                color: 'primary.main',
                opacity: 0.7,
              },
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
}

interface AddToolCardProps {
  onClick: () => void;
}

export function AddToolCard({ onClick }: AddToolCardProps) {
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
              Add MCP
            </Typography>
          </Box>

          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 'auto', minHeight: '2.5em' }}
          >
            Connect a new MCP provider
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
