'use client';

import * as React from 'react';
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  type SelectProps,
} from '@mui/material';

import {
  SmartToyIcon,
  DevicesIcon,
  WebIcon,
  StorageIcon,
  CodeIcon,
  DataObjectIcon,
  CloudIcon,
  AnalyticsIcon,
  ShoppingCartIcon,
  TerminalIcon,
  VideogameAssetIcon,
  ChatIcon,
  PsychologyIcon,
  DashboardIcon,
  SearchIcon,
  AutoFixHighIcon,
  PhoneIphoneIcon,
  SchoolIcon,
  ScienceIcon,
  AccountTreeIcon,
} from '@/components/icons';

export type ProjectOption = {
  readonly id: string;
  readonly name: string;
  readonly description?: string | null;
  readonly icon?: string | null;
};

const ICON_MAP: Record<string, React.ComponentType<{ fontSize?: any }>> = {
  SmartToy: SmartToyIcon,
  Devices: DevicesIcon,
  Web: WebIcon,
  Storage: StorageIcon,
  Code: CodeIcon,
  DataObject: DataObjectIcon,
  Cloud: CloudIcon,
  Analytics: AnalyticsIcon,
  ShoppingCart: ShoppingCartIcon,
  Terminal: TerminalIcon,
  VideogameAsset: VideogameAssetIcon,
  Chat: ChatIcon,
  Psychology: PsychologyIcon,
  Dashboard: DashboardIcon,
  Search: SearchIcon,
  AutoFixHigh: AutoFixHighIcon,
  PhoneIphone: PhoneIphoneIcon,
  School: SchoolIcon,
  Science: ScienceIcon,
  AccountTree: AccountTreeIcon,
};

function ProjectIcon({ icon }: { icon?: string | null }) {
  if (icon && ICON_MAP[icon]) {
    const Cmp = ICON_MAP[icon];
    return <Cmp fontSize="small" />;
  }
  return <SmartToyIcon fontSize="small" />;
}

export type ProjectSelectionProps = {
  readonly isEditing: boolean;
  readonly loading: boolean;
  readonly options: readonly ProjectOption[];
  /** Selected project id (or null/undefined) */
  readonly value: string | null | undefined;
  /** Called with selected id (or null) */
  readonly onChange?: (nextId: string | null) => void;
  readonly label?: string;
  /** Show an explicit "None" choice (select mode) / allow clear (autocomplete) */
  readonly allowUnset?: boolean;
};
/**
 * The ProjectSelection Component is a Wrapper around the MIUI Select Component to
 * fix the width to use the width of the select box size
 * @param isEditing
 * @param loading
 * @param options
 * @param value
 * @param onChange
 * @param label
 * @param allowUnset
 * @constructor
 */
export default function ProjectSelection({
  isEditing,
  loading,
  options,
  value,
  onChange,
  label = 'Project',
  allowUnset = true,
}: ProjectSelectionProps) {
  const selected = options.find(o => o.id === value) ?? null;

  const fieldRef = React.useRef<HTMLDivElement | null>(null);
  const [overlayWidth, setOverlayWidth] = React.useState<string>('auto');
  const measureWidth = React.useCallback(() => {
    const el = fieldRef.current;
    if (!el) return;
    const { width } = el.getBoundingClientRect();
    setOverlayWidth(`${Math.round(width)}px`);
  }, []);
  const anchorOrigin: NonNullable<SelectProps['MenuProps']>['anchorOrigin'] = {
    vertical: 'bottom',
    horizontal: 'left',
  };
  const transformOrigin: NonNullable<
    SelectProps['MenuProps']
  >['transformOrigin'] = {
    vertical: 'top',
    horizontal: 'left',
  };

  if (!isEditing) {
    return selected ? (
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
          <ProjectIcon icon={selected.icon} />
        </Box>
        <Typography variant="body1">{selected.name}</Typography>
      </Box>
    ) : (
      <Typography variant="body1">No project assigned</Typography>
    );
  }
  return (
    <Box ref={fieldRef}>
      <FormControl fullWidth>
        <InputLabel>{label}</InputLabel>
        <Select
          label={label}
          value={value ?? (allowUnset ? '' : '')}
          onOpen={measureWidth}
          onChange={e =>
            onChange?.(e.target.value ? String(e.target.value) : null)
          }
          MenuProps={{
            anchorOrigin,
            transformOrigin,
            PaperProps: {
              sx: {
                width: overlayWidth,
                overflowY: 'auto',
              },
            },
          }}
        >
          {allowUnset && (
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
          )}

          {loading ? (
            <MenuItem disabled>
              <CircularProgress size={20} />
              <Box component="span" sx={{ ml: 1 }}>
                Loading projects...
              </Box>
            </MenuItem>
          ) : (
            options.map(project => (
              <MenuItem key={project.id} value={project.id}>
                <ListItemIcon>
                  <ProjectIcon icon={project.icon} />
                </ListItemIcon>
                <ListItemText
                  slotProps={{
                    primary: { overflow: 'hidden', textOverflow: 'ellipsis' },
                    secondary: { overflow: 'hidden', textOverflow: 'ellipsis' },
                  }}
                  primary={project.name}
                  secondary={project.description ?? undefined}
                />
              </MenuItem>
            ))
          )}
        </Select>
      </FormControl>
    </Box>
  );
}
