'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';
import {
  Add as AddIcon,
  ContentCopy as CopyIcon,
  ErrorOutline as ErrorIcon,
  ExpandMore as ExpandIcon,
  WarningAmber as WarnIcon,
} from '@mui/icons-material';
import JsonMonacoField from '@/app/(protected)/endpoints/[identifier]/components/JsonMonacoField';
import { jsonFieldSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useOrgSettings } from '@/contexts/OrgSettingsContext';
import { fetchRoles } from '../../rbac/api/role-cache';
import { SSOClient } from '../api/sso-client';
import type {
  ClaimPath,
  ProviderInfo,
  RoleMapping,
  RoleMappingPreview,
  SeenClaims,
} from '../types';
import ChangeSummary from './ChangeSummary';
import { RoleMappingContext, type RoleMappingData } from './context';
import {
  claimKey,
  claimLabel,
  MAX_RULES,
  orgRoleOptions,
  parseJsonText,
  toJsonText,
  type Catalog,
  type Problem,
} from './mapping-json';
import { providerPhrase } from './providers';
import { EveryoneElseRow, GroupPicker, RULE_GRID, RuleRow } from './RuleRow';

const PREVIEW_DELAY_MS = 400;
const COMMON_CLAIMS: ClaimPath[] = [
  'groups',
  'roles',
  ['realm_access', 'roles'],
];

function JsonEditor({
  text,
  onText,
  problems,
  ruleCount,
}: {
  text: string;
  onText: (t: string) => void;
  problems: Problem[];
  ruleCount: number;
}) {
  const theme = useTheme();
  const errors = problems.filter(p => p.level === 'error');
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
          The same rules as JSON, with role and project names. Rhesis checks
          them as you type.
        </Typography>
        <Button
          size="small"
          startIcon={<CopyIcon />}
          onClick={() => navigator.clipboard?.writeText(text)}
        >
          Copy
        </Button>
      </Box>
      <JsonMonacoField
        editorKey="sso-role-mapping"
        ariaLabel="Role mapping (JSON)"
        height="280px"
        theme={theme.palette.mode === 'dark' ? 'vs-dark' : 'light'}
        value={text}
        onChange={onText}
        error={errors.length > 0}
        describedBy="role-mapping-json-problems"
        wrapperSx={jsonFieldSx}
      />
      <Box
        id="role-mapping-json-problems"
        aria-live="polite"
        sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}
      >
        {problems.length === 0 ? (
          <Typography variant="body2" color="success.main">
            {ruleCount} {ruleCount === 1 ? 'rule' : 'rules'}, no problems.
          </Typography>
        ) : (
          problems.map(p => (
            <Box
              key={`${p.where}-${p.message}`}
              sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}
            >
              {p.level === 'error' ? (
                <ErrorIcon color="error" fontSize="small" />
              ) : (
                <WarnIcon color="warning" fontSize="small" />
              )}
              <Typography variant="body2">
                <Box component="code" sx={{ color: 'text.secondary', mr: 1 }}>
                  {p.where}
                </Box>
                {p.message}
              </Typography>
            </Box>
          ))
        )}
      </Box>
    </Box>
  );
}

function ClaimField({
  value,
  seen,
  onChange,
}: {
  value: ClaimPath;
  seen: string[][];
  onChange: (c: ClaimPath) => void;
}) {
  const options = useMemo(() => {
    const all = [
      ...seen.map(p => (p.length === 1 ? p[0] : p)),
      ...COMMON_CLAIMS,
      value,
    ];
    const byKey = new Map(all.map(c => [claimKey(c), c] as const));
    return [...byKey.values()];
  }, [seen, value]);
  const [custom, setCustom] = useState('');
  return (
    <FormControl>
      <InputLabel id="sso-claim-label">Groups claim</InputLabel>
      <Select
        labelId="sso-claim-label"
        label="Groups claim"
        value={claimKey(value)}
        onChange={e =>
          onChange(JSON.parse(String(e.target.value)) as ClaimPath)
        }
        renderValue={v => (
          <Box component="span" sx={{ fontFamily: 'monospace' }}>
            {claimLabel(JSON.parse(v) as ClaimPath)}
          </Box>
        )}
      >
        {options.map(c => {
          const wasSeen = seen.some(
            p => claimKey(p.length === 1 ? p[0] : p) === claimKey(c)
          );
          return (
            <MenuItem
              key={claimKey(c)}
              value={claimKey(c)}
              sx={{ display: 'block' }}
            >
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {claimLabel(c)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {wasSeen ? 'Seen at sign-in' : 'Not seen yet'}
              </Typography>
            </MenuItem>
          );
        })}
      </Select>
      <TextField
        size="small"
        sx={{ mt: 1 }}
        placeholder="Other claim, e.g. https://acme.com/groups"
        value={custom}
        onChange={e => setCustom(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && custom.trim()) {
            e.preventDefault();
            onChange(custom.trim());
            setCustom('');
          }
        }}
        slotProps={{
          htmlInput: { 'aria-label': 'Other groups claim', maxLength: 256 },
        }}
        helperText="Where the token lists the groups. Press Enter to use another claim."
      />
    </FormControl>
  );
}

export interface RoleMappingTabProps {
  value: RoleMapping;
  onChange: (m: RoleMapping) => void;
  provider: ProviderInfo;
  /** Tells the form whether Save must wait for the JSON to be fixed. */
  onJsonErrors: (hasErrors: boolean) => void;
}

export default function RoleMappingTab({
  value,
  onChange,
  provider,
  onJsonErrors,
}: RoleMappingTabProps) {
  const { organization } = useOrgSettings();
  const set = (patch: Partial<RoleMapping>) => onChange({ ...value, ...patch });
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [seen, setSeen] = useState<SeenClaims>({ groups: [], claims: [] });
  const [preview, setPreview] = useState<RoleMappingPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [addAnchor, setAddAnchor] = useState<HTMLElement | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const [jsonText, setJsonText] = useState('');
  const [problems, setProblems] = useState<Problem[]>([]);
  const hasJsonErrors =
    mode === 'json' && problems.some(p => p.level === 'error');
  const who = providerPhrase(provider);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchRoles(),
      new ApiClientFactory().getProjectsClient().getAllProjects(),
    ])
      .then(([roles, projects]) => {
        if (cancelled) return;
        setCatalog({
          roles,
          projects: projects.map(p => ({ id: String(p.id), name: p.name })),
        });
      })
      .catch(() => {
        if (!cancelled)
          setLoadError(
            'Couldn’t load roles and projects. Role mapping needs roles and permissions.'
          );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const claimId = claimKey(value.claim);
  useEffect(() => {
    let cancelled = false;
    new SSOClient()
      .getSeenClaims(organization.id, JSON.parse(claimId) as ClaimPath)
      .then(s => !cancelled && setSeen(s))
      .catch(() => !cancelled && setSeen({ groups: [], claims: [] }));
    return () => {
      cancelled = true;
    };
  }, [organization.id, claimId]);

  // Ask the backend who changes, a moment after the last edit.
  const mappingId = JSON.stringify(value);
  const complete = value.rules.every(r => r.role_id || r.projects.length);
  useEffect(() => {
    if (!value.enabled || hasJsonErrors || !complete) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setPreviewing(true);
    const timer = setTimeout(() => {
      new SSOClient()
        .previewRoleMapping(
          organization.id,
          JSON.parse(mappingId) as RoleMapping
        )
        .then(p => !cancelled && setPreview(p))
        .catch(() => !cancelled && setPreview(null))
        .finally(() => !cancelled && setPreviewing(false));
    }, PREVIEW_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [organization.id, mappingId, value.enabled, hasJsonErrors, complete]);

  useEffect(() => onJsonErrors(hasJsonErrors), [hasJsonErrors, onJsonErrors]);

  const seenValues = seen.groups.map(g => g.value);
  const onJsonText = (t: string) => {
    if (!catalog) return;
    setJsonText(t);
    const { mapping, problems: found } = parseJsonText(
      t,
      value.enabled,
      catalog,
      seenValues
    );
    setProblems(found);
    if (mapping) onChange(mapping);
  };

  const levelOf = (id: string | null) =>
    catalog?.roles.find(r => r.id === id)?.level ?? -1;
  // Highest role first, so the order reads like "highest role wins". Sorted
  // once per add/remove, not on every role change, so rows don't jump.
  const order = useMemo(
    () =>
      value.rules
        .map((r, index) => ({ r, index }))
        .sort((a, b) => levelOf(b.r.role_id) - levelOf(a.r.role_id))
        .map(x => x.r.group),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [value.rules.length, catalog]
  );
  const rows = value.rules
    .map((r, index) => ({ r, index }))
    .sort((a, b) => {
      const ia = order.indexOf(a.r.group);
      const ib = order.indexOf(b.r.group);
      return (ia < 0 ? Infinity : ia) - (ib < 0 ? Infinity : ib);
    });
  const taken = value.rules.map(r => r.group);
  const suggestions = seen.groups
    .filter(g => !taken.includes(g.value))
    .slice(0, 4);
  const defaultRole = catalog
    ? (orgRoleOptions(catalog.roles).find(
        r => r.is_built_in && r.name === 'Member'
      ) ?? null)
    : null;
  const addRule = (group: string) => {
    if (value.rules.length >= MAX_RULES) return;
    set({
      rules: [
        ...value.rules,
        { group, role_id: defaultRole?.id ?? null, projects: [] },
      ],
    });
  };

  if (!provider.supports_groups) {
    return (
      <Box
        sx={{
          p: 2,
          border: 1,
          borderColor: 'divider',
          borderRadius: t => `${t.shape.borderRadius}px`,
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
          {provider.name} doesn&apos;t send groups at sign-in
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Roles can&apos;t follow {provider.name} groups, so manage them on the
          Team tab. To map groups, connect {provider.name} through a provider
          that sends them.
        </Typography>
      </Box>
    );
  }
  if (loadError) return <Alert severity="warning">{loadError}</Alert>;
  if (!catalog) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  const data: RoleMappingData = { provider, catalog, seenGroups: seen.groups };

  return (
    <RoleMappingContext.Provider value={data}>
      <Box sx={{ width: '100%' }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <FormControlLabel
            control={
              <Switch
                checked={value.enabled}
                onChange={(_, c) => set({ enabled: c })}
              />
            }
            label={`Give people roles based on their ${provider.key === 'oidc' ? '' : `${provider.name} `}groups`}
          />
          {value.enabled && (
            <Tooltip
              title={hasJsonErrors ? 'Fix the errors in the JSON first' : ''}
            >
              <ToggleButtonGroup
                size="small"
                exclusive
                value={mode}
                onChange={(_, m: 'visual' | 'json' | null) => {
                  if (!m || m === mode) return;
                  if (m === 'json') {
                    setJsonText(toJsonText(value, catalog));
                    setProblems([]);
                  }
                  setMode(m);
                }}
                aria-label="Editor"
              >
                <ToggleButton
                  value="visual"
                  disabled={hasJsonErrors}
                  sx={{ px: 1.5 }}
                >
                  Visual
                </ToggleButton>
                <ToggleButton value="json" sx={{ px: 1.5 }}>
                  JSON
                </ToggleButton>
              </ToggleButtonGroup>
            </Tooltip>
          )}
        </Box>

        <Collapse in={value.enabled}>
          <Box
            sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, pt: 2 }}
          >
            <Typography variant="body2" color="text.secondary" sx={{ px: 0.5 }}>
              {provider.groups_hint}
            </Typography>
            {mode === 'json' ? (
              <JsonEditor
                text={jsonText}
                onText={onJsonText}
                problems={problems}
                ruleCount={value.rules.length}
              />
            ) : (
              <>
                <Box
                  sx={{
                    ...RULE_GRID,
                    px: 1.5,
                    display: { xs: 'none', md: 'grid' },
                  }}
                >
                  <Typography variant="overline" color="text.secondary">
                    In {who}
                  </Typography>
                  <span />
                  <Typography variant="overline" color="text.secondary">
                    In Rhesis
                  </Typography>
                  <span />
                </Box>

                {rows.map(({ r, index }) => (
                  <RuleRow
                    key={`${index}-${r.group}`}
                    rule={r}
                    taken={taken}
                    onChange={next =>
                      set({
                        rules: value.rules.map((x, j) =>
                          j === index ? next : x
                        ),
                      })
                    }
                    onRemove={() =>
                      set({ rules: value.rules.filter((_, j) => j !== index) })
                    }
                  />
                ))}

                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 1,
                  }}
                >
                  <Button
                    startIcon={<AddIcon />}
                    onClick={e => setAddAnchor(e.currentTarget)}
                    disabled={value.rules.length >= MAX_RULES}
                  >
                    Add a group
                  </Button>
                  {suggestions.length > 0 && (
                    <>
                      <Typography variant="body2" color="text.secondary">
                        or
                      </Typography>
                      {suggestions.map(g => (
                        <Chip
                          key={g.value}
                          size="small"
                          variant="outlined"
                          icon={<AddIcon />}
                          label={g.value}
                          onClick={() => addRule(g.value)}
                        />
                      ))}
                    </>
                  )}
                </Box>
                <GroupPicker
                  anchor={addAnchor}
                  taken={taken}
                  onClose={() => setAddAnchor(null)}
                  onPick={v => {
                    addRule(v);
                    setAddAnchor(null);
                  }}
                />

                <EveryoneElseRow
                  value={value.everyone_else}
                  onChange={v => set({ everyone_else: v })}
                />

                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ px: 0.5 }}
                >
                  In several groups? People get the highest role. Owners are
                  never changed.
                </Typography>
              </>
            )}

            {!hasJsonErrors && (
              <Box sx={{ mt: 1 }}>
                <ChangeSummary preview={preview} loading={previewing} />
              </Box>
            )}

            <Box sx={{ display: mode === 'json' ? 'none' : 'block' }}>
              <Button
                size="small"
                onClick={() => setAdvanced(!advanced)}
                aria-expanded={advanced}
                endIcon={
                  <ExpandIcon
                    sx={{ transform: advanced ? 'rotate(180deg)' : 'none' }}
                  />
                }
                sx={{ color: 'text.secondary', px: 0.5 }}
              >
                Advanced
              </Button>
              <Collapse in={advanced}>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                    gap: 2,
                    pt: 2,
                    alignItems: 'start',
                  }}
                >
                  <FormControl>
                    <InputLabel id="sso-apply-label">Apply roles</InputLabel>
                    <Select
                      labelId="sso-apply-label"
                      label="Apply roles"
                      value={value.apply}
                      onChange={e =>
                        set({ apply: e.target.value as RoleMapping['apply'] })
                      }
                      renderValue={v =>
                        v === 'every_sign_in'
                          ? 'At every sign-in'
                          : 'Only at the first SSO sign-in'
                      }
                    >
                      <MenuItem
                        value="every_sign_in"
                        sx={{ display: 'block', whiteSpace: 'normal' }}
                      >
                        <Typography variant="body2">
                          At every sign-in
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {who.charAt(0).toUpperCase() + who.slice(1)} stays in
                          charge. These roles can&apos;t be changed in Rhesis.
                        </Typography>
                      </MenuItem>
                      <MenuItem
                        value="on_create"
                        sx={{ display: 'block', whiteSpace: 'normal' }}
                      >
                        <Typography variant="body2">
                          Only at the first SSO sign-in
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Sets the starting role. After that, roles are managed
                          in Rhesis.
                        </Typography>
                      </MenuItem>
                    </Select>
                  </FormControl>
                  <ClaimField
                    value={value.claim}
                    seen={seen.claims}
                    onChange={c => set({ claim: c })}
                  />
                </Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 1.5 }}
                >
                  Roles update when someone signs in. Removing a person from a
                  group takes effect at their next sign-in.
                </Typography>
              </Collapse>
            </Box>
          </Box>
        </Collapse>
      </Box>
    </RoleMappingContext.Provider>
  );
}
