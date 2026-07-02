"use client";

import React from "react";
import EntityEmptyState from "@/components/common/EntityEmptyState";
import SecurityIcon from "@mui/icons-material/Security";

export default function RolesEmptyState() {
  return (
    <EntityEmptyState
      icon={SecurityIcon}
      title="Roles are an Enterprise feature"
      description="Fine-grained role-based access control lets you define custom roles, assign them to team members, and control who can do what across your organization."
      actionLabel="Learn about Enterprise"
      onAction={() => window.open("https://rhesis.ai/pricing", "_blank")}
    />
  );
}
