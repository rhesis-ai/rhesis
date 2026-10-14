import { useQuery } from '@tanstack/react-query';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { FeatureName } from '@/constants/features';
import { useFeature } from '@/contexts/FeaturesContext';
import { fetchOrgMembers } from '../../rbac/api/org-members-cache';
import { auditLogQueryKeys } from '../filters';

const NO_ROLES: ReadonlyMap<string, string> = new Map();

/**
 * Each member's current org role name, by user id, for the actor column.
 * Empty without RBAC or `member:read`; the column then shows the email.
 */
export function useMemberRoles(): ReadonlyMap<string, string> {
  const rbacOn = useFeature(FeatureName.RBAC);
  const canReadMembers = useCan(Capability.Member.READ);
  const enabled = rbacOn && canReadMembers;
  const { data } = useQuery({
    queryKey: auditLogQueryKeys.members(),
    queryFn: async () => {
      const members = await fetchOrgMembers();
      // A member without a role name falls back to the email, not a blank line.
      return new Map(
        members.flatMap(m =>
          m.role?.display_name
            ? [[m.user_id, m.role.display_name] as const]
            : []
        )
      );
    },
    enabled,
  });
  // A disabled query still returns earlier cached data.
  return (enabled && data) || NO_ROLES;
}
