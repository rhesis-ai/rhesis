'use client';

import React, { useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonBase from '@mui/material/ButtonBase';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListSubheader from '@mui/material/ListSubheader';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Popover from '@mui/material/Popover';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import {
  Add as AddIcon,
  ArrowDropDown as DropIcon,
  ArrowForward as ArrowIcon,
  DeleteOutline as RemoveIcon,
  Groups as GroupIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { getRoleChipSx } from '../../rbac/role-display';
import type { RoleRead } from '../../rbac/types';
import type { EveryoneElse, MappingRule } from '../types';
import { useRoleMappingData } from './context';
import { orgRoleOptions, projectRoleOptions, roleById } from './mapping-json';

/** Group column, arrow, Rhesis column, remove button. Stacks on small screens. */
export const RULE_GRID = {
  display: 'grid',
  gridTemplateColumns: {
    xs: '1fr',
    md: 'minmax(0, 2fr) auto minmax(0, 3fr) auto',
  },
  alignItems: 'center',
  columnGap: 2,
  rowGap: 1,
} as const;

const shortId = (v: string) =>
  /^[0-9a-f-]{30,}$/i.test(v) ? `${v.slice(0, 8)}…` : v;

export function RoleChip({ role }: { role: RoleRead }) {
  return (
    <Chip
      label={role.display_name || role.name}
      size="small"
      sx={getRoleChipSx(role)}
    />
  );
}

/** A clickable value inside a rule sentence: looks like text with a caret. */
function Pill({
  children,
  onClick,
  ariaLabel,
}: {
  children: React.ReactNode;
  onClick: (e: React.MouseEvent<HTMLElement>) => void;
  ariaLabel: string;
}) {
  return (
    <ButtonBase
      onClick={onClick}
      aria-label={ariaLabel}
      sx={{
        display: 'inline-flex',
        justifySelf: 'start',
        justifyContent: 'flex-start',
        alignItems: 'center',
        gap: 0.25,
        minWidth: 0,
        maxWidth: '100%',
        pl: 0.5,
        pr: 0.25,
        py: 0.25,
        borderRadius: t => `${t.shape.borderRadius}px`,
        border: 1,
        borderColor: 'transparent',
        '&:hover': { borderColor: 'divider', bgcolor: 'action.hover' },
        '&.Mui-focusVisible': {
          outline: '2px solid',
          outlineColor: 'primary.main',
        },
      }}
    >
      {children}
      <DropIcon fontSize="small" sx={{ color: 'text.secondary' }} />
    </ButtonBase>
  );
}

function GroupLabel({ value }: { value: string }) {
  const { seenGroups } = useRoleMappingData();
  const seen = seenGroups.find(g => g.value === value);
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
      <GroupIcon fontSize="small" sx={{ color: 'text.secondary' }} />
      <Box sx={{ minWidth: 0, textAlign: 'left' }}>
        <Typography
          variant="body2"
          title={value}
          sx={{
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {shortId(value)}
        </Typography>
        <Typography
          variant="caption"
          color={seen ? 'text.secondary' : 'warning.main'}
        >
          {seen
            ? `Seen for ${seen.members} ${seen.members === 1 ? 'person' : 'people'}`
            : 'Not seen at sign-in yet'}
        </Typography>
      </Box>
    </Box>
  );
}

/** Groups seen at sign-in, searchable, with "use as typed" for anything else. */
export function GroupPicker({
  anchor,
  taken,
  onClose,
  onPick,
}: {
  anchor: HTMLElement | null;
  taken: string[];
  onClose: () => void;
  onPick: (v: string) => void;
}) {
  const { seenGroups } = useRoleMappingData();
  const [q, setQ] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const typed = q.trim();
  const shown = seenGroups
    .filter(g => g.value.toLowerCase().includes(typed.toLowerCase()))
    .sort(
      (a, b) =>
        Number(taken.includes(a.value)) - Number(taken.includes(b.value))
    );
  const exact = seenGroups.some(g => g.value === typed);
  const close = () => {
    setQ('');
    onClose();
  };
  const pick = (v: string) => {
    setQ('');
    onPick(v);
  };
  return (
    <Popover
      open={!!anchor}
      anchorEl={anchor}
      onClose={close}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      // Typing should start in the search box once the picker opens.
      TransitionProps={{ onEntered: () => searchRef.current?.focus() }}
      slotProps={{
        paper: { sx: { width: t => t.spacing(45), maxWidth: '100%', p: 1.5 } },
      }}
    >
      <TextField
        inputRef={searchRef}
        fullWidth
        size="small"
        placeholder="Search or type a group"
        value={q}
        onChange={e => setQ(e.target.value)}
        onKeyDown={e => {
          if (e.key !== 'Enter') return;
          // Never let Enter submit the SSO form behind the picker.
          e.preventDefault();
          if (typed && !taken.includes(typed)) pick(typed);
        }}
        slotProps={{
          htmlInput: { 'aria-label': 'Group', maxLength: 256 },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mt: 1, px: 0.5 }}
      >
        {seenGroups.length
          ? 'Seen at sign-in'
          : 'No groups seen yet. Sign in once with SSO, or type the group exactly as the token sends it.'}
      </Typography>
      <List
        dense
        disablePadding
        sx={{ mt: 0.5, maxHeight: t => t.spacing(35), overflow: 'auto' }}
      >
        {shown.map(g => {
          const isTaken = taken.includes(g.value);
          return (
            <ListItemButton
              key={g.value}
              disabled={isTaken}
              onClick={() => pick(g.value)}
              sx={{ gap: 1.5, borderRadius: 1 }}
            >
              <GroupIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              <Typography
                variant="body2"
                sx={{
                  flex: 1,
                  minWidth: 0,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {g.value}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {isTaken ? 'Mapped' : g.members}
              </Typography>
            </ListItemButton>
          );
        })}
        {typed && !exact && !taken.includes(typed) && (
          <ListItemButton
            onClick={() => pick(typed)}
            sx={{ gap: 1.5, borderRadius: 1 }}
          >
            <AddIcon fontSize="small" sx={{ color: 'text.secondary' }} />
            <Typography variant="body2">Use “{typed}” as typed</Typography>
          </ListItemButton>
        )}
      </List>
    </Popover>
  );
}

function RoleMenu({
  anchor,
  options,
  value,
  onClose,
  onPick,
  allowNoRole,
}: {
  anchor: HTMLElement | null;
  options: RoleRead[];
  value: string | null;
  onClose: () => void;
  onPick: (v: string | null) => void;
  allowNoRole?: boolean;
}) {
  return (
    <Menu
      anchorEl={anchor}
      open={!!anchor}
      onClose={onClose}
      slotProps={{ paper: { sx: { width: t => t.spacing(38) } } }}
    >
      {options.map(r => (
        <MenuItem
          key={r.id}
          selected={value === r.id}
          onClick={() => onPick(r.id)}
          sx={{ display: 'block', whiteSpace: 'normal', py: 1 }}
        >
          <RoleChip role={r} />
          {r.description && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: 'block', mt: 0.5 }}
            >
              {r.description}
            </Typography>
          )}
        </MenuItem>
      ))}
      {allowNoRole && <Divider />}
      {allowNoRole && (
        <MenuItem
          selected={value === null}
          onClick={() => onPick(null)}
          sx={{ display: 'block', whiteSpace: 'normal' }}
        >
          <Typography variant="body2">No organization role</Typography>
          <Typography variant="caption" color="text.secondary">
            Only give project access.
          </Typography>
        </MenuItem>
      )}
    </Menu>
  );
}

export function RuleRow({
  rule,
  taken,
  onChange,
  onRemove,
}: {
  rule: MappingRule;
  taken: string[];
  onChange: (r: MappingRule) => void;
  onRemove: () => void;
}) {
  const { catalog } = useRoleMappingData();
  const [groupAnchor, setGroupAnchor] = useState<HTMLElement | null>(null);
  const [roleAnchor, setRoleAnchor] = useState<HTMLElement | null>(null);
  const [addAnchor, setAddAnchor] = useState<HTMLElement | null>(null);
  const [grantMenu, setGrantMenu] = useState<{
    el: HTMLElement;
    i: number;
  } | null>(null);
  const orgRoles = orgRoleOptions(catalog.roles);
  const projectRoles = projectRoleOptions(catalog.roles);
  const defaultProjectRole =
    projectRoles.find(r => r.is_built_in && r.name === 'Member') ??
    projectRoles[0];
  const freeProjects = catalog.projects.filter(
    p => !rule.projects.some(g => g.project_id === p.id)
  );
  const role = roleById(catalog.roles, rule.role_id);
  const nothingGranted = !rule.role_id && rule.projects.length === 0;

  return (
    <Box
      sx={{
        ...RULE_GRID,
        px: 1.5,
        py: 1,
        border: 1,
        borderColor: nothingGranted ? 'error.main' : 'divider',
        borderRadius: t => `${t.shape.borderRadius}px`,
        '& .rule-remove': { opacity: { md: 0 } },
        '&:hover .rule-remove, &:focus-within .rule-remove': { opacity: 1 },
      }}
    >
      <Pill
        onClick={e => setGroupAnchor(e.currentTarget)}
        ariaLabel={`Change group ${rule.group}`}
      >
        <GroupLabel value={rule.group} />
      </Pill>
      <ArrowIcon
        fontSize="small"
        sx={{ color: 'text.secondary', display: { xs: 'none', md: 'block' } }}
      />
      <Box
        sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}
      >
        <Pill
          onClick={e => setRoleAnchor(e.currentTarget)}
          ariaLabel="Change organization role"
        >
          {role ? (
            <RoleChip role={role} />
          ) : (
            <Typography variant="body2" color="text.secondary">
              {rule.role_id ? 'Deleted role' : 'No org role'}
            </Typography>
          )}
        </Pill>
        {rule.projects.map((g, i) => {
          const project = catalog.projects.find(p => p.id === g.project_id);
          const prole = roleById(catalog.roles, g.role_id);
          return (
            <Chip
              key={g.project_id}
              size="small"
              variant="outlined"
              color={project && prole ? 'default' : 'error'}
              label={`${project?.name ?? 'Deleted project'} as ${prole?.display_name ?? prole?.name ?? '?'}`}
              onClick={e => setGrantMenu({ el: e.currentTarget, i })}
              onDelete={() =>
                onChange({
                  ...rule,
                  projects: rule.projects.filter((_, j) => j !== i),
                })
              }
            />
          );
        })}
        {freeProjects.length > 0 && defaultProjectRole && (
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={e => setAddAnchor(e.currentTarget)}
            sx={{ color: 'text.secondary' }}
          >
            Project
          </Button>
        )}
        {nothingGranted && (
          <Typography variant="caption" color="error.main">
            Pick a role or a project
          </Typography>
        )}
      </Box>
      <Tooltip title="Remove rule">
        <IconButton
          className="rule-remove"
          size="small"
          aria-label={`Remove rule for ${rule.group}`}
          onClick={onRemove}
        >
          <RemoveIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <GroupPicker
        anchor={groupAnchor}
        taken={taken.filter(t => t !== rule.group)}
        onClose={() => setGroupAnchor(null)}
        onPick={v => {
          onChange({ ...rule, group: v });
          setGroupAnchor(null);
        }}
      />
      <RoleMenu
        anchor={roleAnchor}
        options={orgRoles}
        value={rule.role_id}
        allowNoRole
        onClose={() => setRoleAnchor(null)}
        onPick={v => {
          onChange({ ...rule, role_id: v });
          setRoleAnchor(null);
        }}
      />
      <Menu
        anchorEl={addAnchor}
        open={!!addAnchor}
        onClose={() => setAddAnchor(null)}
      >
        <ListSubheader>Add access to</ListSubheader>
        {freeProjects.map(p => (
          <MenuItem
            key={p.id}
            onClick={() => {
              if (defaultProjectRole)
                onChange({
                  ...rule,
                  projects: [
                    ...rule.projects,
                    { project_id: p.id, role_id: defaultProjectRole.id },
                  ],
                });
              setAddAnchor(null);
            }}
          >
            {p.name}
          </MenuItem>
        ))}
      </Menu>
      <RoleMenu
        anchor={grantMenu?.el ?? null}
        options={projectRoles}
        value={grantMenu ? (rule.projects[grantMenu.i]?.role_id ?? null) : null}
        onClose={() => setGrantMenu(null)}
        onPick={v => {
          if (grantMenu && v)
            onChange({
              ...rule,
              projects: rule.projects.map((x, j) =>
                j === grantMenu.i ? { ...x, role_id: v } : x
              ),
            });
          setGrantMenu(null);
        }}
      />
    </Box>
  );
}

const FALLBACKS: { v: EveryoneElse; title: string }[] = [
  { v: 'keep', title: 'Keep their current role' },
  { v: 'Viewer', title: 'Make them Viewer' },
  { v: 'None', title: 'Remove their access (None)' },
  { v: 'block', title: 'Block their sign-in' },
];

export function EveryoneElseRow({
  value,
  onChange,
}: {
  value: EveryoneElse;
  onChange: (v: EveryoneElse) => void;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const current = FALLBACKS.find(f => f.v === value) ?? FALLBACKS[0];
  return (
    <Box
      sx={{
        ...RULE_GRID,
        p: 1.5,
        border: 1,
        borderStyle: 'dashed',
        borderColor: 'divider',
        borderRadius: t => `${t.shape.borderRadius}px`,
      }}
    >
      <Box sx={{ pl: 0.5 }}>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Everyone else
        </Typography>
        <Typography variant="caption" color="text.secondary">
          In none of the groups above
        </Typography>
      </Box>
      <ArrowIcon
        fontSize="small"
        sx={{ color: 'text.secondary', display: { xs: 'none', md: 'block' } }}
      />
      <Box>
        <Pill
          onClick={e => setAnchor(e.currentTarget)}
          ariaLabel="Change what happens to everyone else"
        >
          <Typography
            variant="body2"
            color={value === 'block' ? 'error.main' : 'text.primary'}
          >
            {current.title}
          </Typography>
        </Pill>
      </Box>
      <span />
      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
        {FALLBACKS.map(f => (
          <MenuItem
            key={f.v}
            selected={f.v === value}
            onClick={() => {
              onChange(f.v);
              setAnchor(null);
            }}
          >
            <Typography
              variant="body2"
              color={f.v === 'block' ? 'error.main' : undefined}
            >
              {f.title}
            </Typography>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
