'use client';

import { useState, useCallback, useRef } from 'react';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import TokensGrid from './TokensGrid';
import CreateTokenDrawer from './CreateTokenDrawer';
import TokenDisplay from './TokenDisplay';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TokenResponse } from '@/utils/api-client/interfaces/token';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { Can, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useBulkActionsBridge } from '@/hooks/useBulkActionsBridge';

export default function TokensPageClient() {
  const { allowed: canManage, loading: permsLoading } = useCanWithStatus(
    Capability.Token.MANAGE
  );

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newToken, setNewToken] = useState<TokenResponse | null>(null);
  const [refreshedToken, setRefreshedToken] = useState<TokenResponse | null>(
    null
  );
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const { bulkActionsVisible, onBulkDelete, handleBulkActionsChange } =
    useBulkActionsBridge();

  // Stable tokens client across renders
  const tokensClientRef = useRef(new ApiClientFactory().getTokensClient());

  const handleOpenCreateModal = useCallback(() => {
    setNewToken(null);
    setIsCreateModalOpen(true);
  }, []);

  const handleCreateToken = async (
    name: string,
    expiresInDays: number | null,
    scopes: string[] | null
  ) => {
    const response = await tokensClientRef.current.createToken(
      name,
      expiresInDays,
      scopes
    );
    setNewToken({ ...response, name });
    setIsCreateModalOpen(false);
    setRefreshTrigger(prev => prev + 1);
    return response;
  };

  const handleRefreshToken = useCallback(
    async (tokenId: string, expiresInDays: number | null) => {
      const response = await tokensClientRef.current.refreshToken(
        tokenId,
        expiresInDays
      );
      setRefreshedToken(response);
    },
    []
  );

  if (permsLoading) return <PageLoadingState />;
  if (!canManage) return <AccessDenied resource="API tokens" />;

  return (
    <PageLayout
      title="API Tokens"
      description="Create API tokens to authenticate with the Rhesis SDK and programmatically manage your testing workflows from your code."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          {bulkActionsVisible && (
            <Can capability={Capability.Token.MANAGE}>
              <Fab
                icon={<DeleteOutlineIcon sx={{ fontSize: 28 }} />}
                tooltip="Delete Tokens"
                aria-label="Delete Tokens"
                onClick={onBulkDelete}
                sx={{
                  bgcolor: 'error.main',
                  '&:hover': { bgcolor: 'error.dark' },
                }}
              />
            </Can>
          )}
          <Can capability={Capability.Token.MANAGE}>
            <Fab
              icon={<FabAddIcon />}
              tooltip="Create API token"
              aria-label="Create API token"
              onClick={handleOpenCreateModal}
            />
          </Can>
        </FabGroup>
      }
    >
      <TokensGrid
        canCreate={canManage}
        onCreateClick={handleOpenCreateModal}
        onRefreshToken={handleRefreshToken}
        onBulkActionsChange={handleBulkActionsChange}
        refreshTrigger={refreshTrigger}
      />

      <CreateTokenDrawer
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateToken={handleCreateToken}
      />

      <TokenDisplay
        open={newToken !== null}
        onClose={() => setNewToken(null)}
        token={newToken}
      />

      <TokenDisplay
        title="Your Refreshed API Token"
        open={refreshedToken !== null}
        onClose={() => setRefreshedToken(null)}
        token={refreshedToken}
      />
    </PageLayout>
  );
}
