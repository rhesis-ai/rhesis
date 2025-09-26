'use client';

import React from 'react';
import { Chip } from '@mui/material';
import { useRouter } from 'next/navigation';
import BaseTable from '@/components/common/BaseTable';
import { Organization } from '@/utils/api-client/interfaces/organization';
import AddIcon from '@mui/icons-material/Add';

interface OrganizationsTableProps {
  organizations: Organization[];
}

export default function OrganizationsTable({
  organizations,
}: OrganizationsTableProps) {
  const router = useRouter();

  const handleRowClick = (organization: Organization) => {
    router.push(`/organizations/${organization.id}`);
  };

  const columns = [
    {
      id: 'name',
      label: 'Name',
      render: (organization: Organization) => organization.name,
    },
    {
      id: 'description',
      label: 'Description',
      render: (organization: Organization) => organization.description,
    },
    {
      id: 'status',
      label: 'Status',
      render: (organization: Organization) => (
        <Chip
          label={organization.is_active ? 'Active' : 'Inactive'}
          size="small"
          variant="outlined"
          color={organization.is_active ? 'success' : 'error'}
        />
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      render: (organization: Organization) =>
        organization.domain && (
          <Chip
            label={organization.domain}
            size="small"
            variant="outlined"
            color={organization.is_domain_verified ? 'success' : 'warning'}
          />
        ),
    },
  ];

  return (
    <BaseTable
      columns={columns}
      data={organizations}
      onRowClick={handleRowClick}
      title="Organizations"
      actionButtons={[
        {
          label: 'New Organization',
          href: '/organizations/new',
          icon: <AddIcon />,
          variant: 'contained',
        },
      ]}
    />
  );
}
