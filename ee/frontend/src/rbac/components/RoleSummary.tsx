"use client";

import React from "react";
import { alpha, Box, Typography } from "@mui/material";
import type { Theme } from "@mui/material/styles";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import CancelOutlinedIcon from "@mui/icons-material/CancelOutlined";
import { BORDER_RADIUS } from "@/styles/theme-constants";
import { summarizePermissions } from "../capability-groups";

interface RoleSummaryProps {
  permissions: ReadonlySet<string>;
}

export default function RoleSummary({ permissions }: RoleSummaryProps) {
  const { granted, denied } = summarizePermissions(permissions);
  const isEmpty = granted.length === 0;

  return (
    <Box
      sx={{
        border: (t: Theme) =>
          `1px solid ${alpha(t.palette.primary.light, 0.3)}`,
        borderRadius: BORDER_RADIUS.sm,
        bgcolor: (t: Theme) => alpha(t.palette.primary.main, 0.04),
        p: 2,
      }}
    >
      <Typography
        variant="body2"
        sx={{
          fontWeight: 600,
          mb: 1,
          display: "flex",
          alignItems: "center",
          gap: 0.5,
        }}
      >
        <CheckCircleOutlineIcon sx={{ fontSize: 16, color: "primary.main" }} />
        This role can
      </Typography>

      {isEmpty ? (
        <Typography variant="caption" color="text.secondary">
          No permissions yet. Set access levels above to build the role.
        </Typography>
      ) : (
        <Box
          sx={{ display: "flex", flexDirection: "column", gap: 0.5, ml: 0.5 }}
        >
          {granted.map((text) => (
            <Box
              key={text}
              sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
            >
              <CheckCircleOutlineIcon
                sx={{ fontSize: 14, color: "success.main" }}
              />
              <Typography variant="caption">{text}</Typography>
            </Box>
          ))}
          {denied.map((text) => (
            <Box
              key={text}
              sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
            >
              <CancelOutlinedIcon
                sx={{ fontSize: 14, color: "text.disabled" }}
              />
              <Typography variant="caption" color="text.disabled">
                {text}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
