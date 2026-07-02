"use client";

import React, { useEffect, useState } from "react";
import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
} from "@mui/material";
import { drawerOutlinedFieldSx } from "@/components/common/drawerFormFieldSx";
import { fetchRoles } from "../api/role-cache";
import type { RoleRead } from "../types";

interface RoleSelectFieldProps {
  sessionToken: string;
  value: string | null;
  onChange: (roleId: string | null) => void;
}

export default function RoleSelectField({
  sessionToken,
  value,
  onChange,
}: RoleSelectFieldProps) {
  const [roles, setRoles] = useState<RoleRead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    fetchRoles(sessionToken)
      .then((data) => {
        if (!cancelled) {
          setRoles(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  const assignableRoles = roles.filter(
    (r) => !r.is_built_in || (r.name !== "owner" && r.name !== "none"),
  );

  if (loading) {
    return <Skeleton variant="rounded" height={56} />;
  }

  return (
    <FormControl fullWidth sx={drawerOutlinedFieldSx}>
      <InputLabel id="role-select-label">Project role</InputLabel>
      <Select
        labelId="role-select-label"
        label="Project role"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      >
        <MenuItem value="">
          <em>Default (Member)</em>
        </MenuItem>
        {assignableRoles.map((role) => (
          <MenuItem key={role.id} value={role.id}>
            {role.display_name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
