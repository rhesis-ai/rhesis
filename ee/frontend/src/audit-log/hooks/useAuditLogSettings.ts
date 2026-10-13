import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { AuditLogClient } from '../api/audit-log-client';
import { auditLogQueryKeys } from '../filters';
import type { AuditLogSettings, AuditLogSettingsUpdate } from '../types';

/** The org's audit log settings. One request, shared by the header badge and the Settings section. */
export function useAuditLogSettings() {
  const canRead = useCan(Capability.AuditLog.READ);
  return useQuery({
    queryKey: auditLogQueryKeys.settings(),
    queryFn: () => new AuditLogClient().getSettings(),
    enabled: canRead,
  });
}

export function useUpdateAuditLogSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: AuditLogSettingsUpdate) =>
      new AuditLogClient().updateSettings(update),
    onSuccess: (settings: AuditLogSettings) =>
      queryClient.setQueryData(auditLogQueryKeys.settings(), settings),
  });
}
