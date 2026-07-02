"use client";

import React, { useState } from "react";
import {
  alpha,
  Box,
  Checkbox,
  Collapse,
  FormControlLabel,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import type { Theme } from "@mui/material/styles";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { BORDER_RADIUS } from "@/styles/theme-constants";
import {
  CapabilityLevel,
  LEVEL_LABELS,
  capabilityLabel,
  type ResourceArea,
} from "../capability-groups";

interface PermissionGroupControlProps {
  area: ResourceArea;
  currentLevel: CapabilityLevel;
  onLevelChange: (level: CapabilityLevel) => void;
  permissions: ReadonlySet<string>;
  onToggleCapability: (cap: string) => void;
  maxLevel?: CapabilityLevel;
  readOnly?: boolean;
}

const LEVELS = [
  CapabilityLevel.NONE,
  CapabilityLevel.VIEW,
  CapabilityLevel.EDIT,
  CapabilityLevel.MANAGE,
] as const;

export default function PermissionGroupControl({
  area,
  currentLevel,
  onLevelChange,
  permissions,
  onToggleCapability,
  maxLevel = CapabilityLevel.MANAGE,
  readOnly = false,
}: PermissionGroupControlProps) {
  const [expanded, setExpanded] = useState(false);

  const allCaps = new Set(
    Object.values(area.levels).flatMap((caps) => [...caps]),
  );
  const grantedCount = [...allCaps].filter((c) => permissions.has(c)).length;

  return (
    <Box
      sx={{
        border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
        borderRadius: BORDER_RADIUS.sm,
        overflow: "hidden",
      }}
    >
      {/* Header row */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          px: 2,
          py: 1.5,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {area.label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {area.description}
            {grantedCount > 0 && ` · ${grantedCount} granted`}
          </Typography>
        </Box>

        {/* Segmented level selector */}
        <ToggleButtonGroup
          value={currentLevel}
          exclusive
          onChange={(_, val) => {
            if (val !== null && !readOnly) onLevelChange(val);
          }}
          size="small"
          sx={{
            flexShrink: 0,
            border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
            borderRadius: BORDER_RADIUS.sm,
            "& .MuiToggleButtonGroup-grouped": {
              border: "none",
              borderRadius: `${BORDER_RADIUS.sm} !important`,
              mx: "1px",
              px: 1.5,
              py: 0.5,
              fontSize: 12,
              fontWeight: 600,
              textTransform: "none",
              color: (t: Theme) => t.palette.greyscale.subtitle,
              "&.Mui-disabled": {
                color: (t: Theme) => t.palette.greyscale.border,
              },
            },
          }}
        >
          {LEVELS.map((lvl) => {
            const isNone = lvl === CapabilityLevel.NONE;
            const aboveMax = lvl > maxLevel;
            return (
              <ToggleButton
                key={lvl}
                value={lvl}
                disabled={readOnly || aboveMax}
                title={aboveMax ? "Above your own access" : undefined}
                sx={{
                  "&.Mui-selected": isNone
                    ? {
                        bgcolor: (t: Theme) => t.palette.greyscale.surface2,
                        color: (t: Theme) =>
                          `${t.palette.greyscale.subtitle} !important`,
                        "&:hover": {
                          bgcolor: (t: Theme) => t.palette.greyscale.surface2,
                        },
                      }
                    : {
                        bgcolor: "primary.main",
                        color: (t: Theme) =>
                          `${t.palette.primary.contrastText} !important`,
                        "&:hover": {
                          bgcolor: "primary.dark",
                        },
                      },
                }}
              >
                {LEVEL_LABELS[lvl]}
              </ToggleButton>
            );
          })}
        </ToggleButtonGroup>

        {/* Expand chevron */}
        <IconButton
          size="small"
          onClick={() => setExpanded((v) => !v)}
          sx={{
            flexShrink: 0,
            transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s",
          }}
        >
          <ExpandMoreIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Expandable detail — individual capability checkboxes */}
      <Collapse in={expanded}>
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderTop: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
            bgcolor: (t: Theme) => alpha(t.palette.greyscale.surface1, 0.5),
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: 0,
          }}
        >
          {[...allCaps].map((cap) => (
            <FormControlLabel
              key={cap}
              control={
                <Checkbox
                  size="small"
                  checked={permissions.has(cap)}
                  onChange={() => onToggleCapability(cap)}
                  disabled={readOnly}
                />
              }
              label={
                <Typography variant="caption">
                  {capabilityLabel(cap)}
                </Typography>
              }
              sx={{ mr: 0 }}
            />
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
