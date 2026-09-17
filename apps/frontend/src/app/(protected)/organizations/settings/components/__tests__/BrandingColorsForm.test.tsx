/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BrandingColorsForm from '../BrandingColorsForm';
import { BrandPreviewContext } from '@/components/providers/ThemeProvider';
import type { Organization } from '@/utils/api-client/interfaces/organization';

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockRefresh = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: mockRefresh }),
}));

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow }),
}));

const mockUpdateSettings = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getOrganizationsClient: () => ({
      updateOrganizationSettings: mockUpdateSettings,
    }),
  })),
}));

function organization(branding: Record<string, unknown> = {}): Organization {
  return {
    id: 'org-1',
    name: 'Acme',
    createdAt: '2026-01-01',
    owner_id: 'u1' as any,
    user_id: 'u1' as any,
    organization_settings: { version: 1, branding: branding as any },
  };
}

/** Stand in for the inline script the root layout writes. */
function setDeploymentBranding(
  branding: Record<string, string> | undefined
): void {
  window.__ENV__ = branding
    ? { apiBaseUrl: '', deploymentBranding: branding }
    : { apiBaseUrl: '' };
}

describe('BrandingColorsForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUpdateSettings.mockResolvedValue({});
    setDeploymentBranding(undefined);
  });

  afterEach(() => {
    delete window.__ENV__;
  });

  describe('when branding comes from deployment environment variables', () => {
    beforeEach(() => {
      setDeploymentBranding({
        primaryColor: '#112233',
        secondaryColor: '#445566',
        productName: 'Acme Testing',
      });
    });

    it('shows the inherited colour as the placeholder, not a blank field', () => {
      render(
        <BrandingColorsForm
          organization={organization()}
          onUpdate={jest.fn()}
        />
      );

      expect(
        screen.getByRole('textbox', { name: /primary colour/i })
      ).toHaveAttribute('placeholder', '#112233');
      expect(
        screen.getByRole('textbox', { name: /secondary colour/i })
      ).toHaveAttribute('placeholder', '#445566');
    });

    it('shows the inherited product name as the placeholder', () => {
      render(
        <BrandingColorsForm
          organization={organization()}
          onUpdate={jest.fn()}
        />
      );

      expect(
        screen.getByRole('textbox', { name: /product name/i })
      ).toHaveAttribute('placeholder', 'Acme Testing');
    });

    it('starts the picker from the inherited colour, not from black', () => {
      render(
        <BrandingColorsForm
          organization={organization()}
          onUpdate={jest.fn()}
        />
      );

      expect(screen.getByLabelText('Primary Colour picker')).toHaveValue(
        '#112233'
      );
    });

    it('keeps showing the deployment value while the field is being cleared', () => {
      render(
        <BrandingColorsForm
          organization={organization({ primary_color: '#6A1B9A' })}
          onUpdate={jest.fn()}
        />
      );

      const field = screen.getByRole('textbox', { name: /primary colour/i });
      fireEvent.change(field, { target: { value: '' } });

      expect(field).toHaveAttribute('placeholder', '#112233');
    });

    it('still shows the organization value when it overrides the deployment', () => {
      render(
        <BrandingColorsForm
          organization={organization({ primary_color: '#6A1B9A' })}
          onUpdate={jest.fn()}
        />
      );

      expect(screen.getByDisplayValue('#6A1B9A')).toBeInTheDocument();
    });
  });

  it('falls back to the Rhesis name when the deployment configures none', () => {
    render(
      <BrandingColorsForm organization={organization()} onUpdate={jest.fn()} />
    );

    expect(
      screen.getByRole('textbox', { name: /product name/i })
    ).toHaveAttribute('placeholder', 'Rhesis AI');
  });

  it('shows live colour pickers without an Edit toggle', () => {
    render(
      <BrandingColorsForm
        organization={organization({ primary_color: '#6A1B9A' })}
        onUpdate={jest.fn()}
      />
    );

    const picker = screen.getByLabelText('Primary Colour picker');
    expect(picker).toHaveAttribute('type', 'color');
    expect(picker).toHaveValue('#6a1b9a');
    expect(document.querySelectorAll('input[type="color"]')).toHaveLength(2);
  });

  it('writes a colour chosen from the picker back to the hex field', () => {
    render(
      <BrandingColorsForm organization={organization()} onUpdate={jest.fn()} />
    );

    fireEvent.change(screen.getByLabelText('Primary Colour picker'), {
      target: { value: '#123456' },
    });

    expect(
      screen.getByRole('textbox', { name: /primary colour/i })
    ).toHaveValue('#123456');
  });

  it('falls back to the Rhesis default in the picker when nothing is configured', () => {
    render(
      <BrandingColorsForm organization={organization()} onUpdate={jest.fn()} />
    );

    // #0080AF is RHESIS_PRIMARY_COLOR; JSDOM normalises to lowercase.
    expect(screen.getByLabelText('Primary Colour picker')).toHaveValue(
      '#0080af'
    );
  });

  it('shows the organization’s stored branding', () => {
    render(
      <BrandingColorsForm
        organization={organization({
          primary_color: '#6A1B9A',
          product_name: 'Acme',
        })}
        onUpdate={jest.fn()}
      />
    );

    expect(screen.getByDisplayValue('#6A1B9A')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Acme')).toBeInTheDocument();
  });

  it('sends a cleared field as null on blur so it reverts to the deployment default', async () => {
    jest.useFakeTimers();
    render(
      <BrandingColorsForm
        organization={organization({ primary_color: '#6A1B9A' })}
        onUpdate={jest.fn()}
      />
    );

    const field = screen.getByDisplayValue('#6A1B9A');
    fireEvent.change(field, { target: { value: '' } });
    fireEvent.blur(field);

    await waitFor(() =>
      expect(mockUpdateSettings).toHaveBeenCalledWith({
        branding: { primary_color: null },
      })
    );
    jest.useRealTimers();
  });

  it('shows an inline error for a malformed colour without calling the API', () => {
    render(
      <BrandingColorsForm organization={organization()} onUpdate={jest.fn()} />
    );

    const field = screen.getByRole('textbox', { name: /primary colour/i });
    fireEvent.change(field, { target: { value: '#fff' } });
    fireEvent.blur(field);

    expect(screen.getByText(/6-digit hex/)).toBeInTheDocument();
    expect(mockUpdateSettings).not.toHaveBeenCalled();
  });

  it('refreshes the route after the debounce delay so the theme updates', async () => {
    jest.useFakeTimers();
    const onUpdate = jest.fn();
    render(
      <BrandingColorsForm organization={organization()} onUpdate={onUpdate} />
    );

    const field = screen.getByRole('textbox', { name: /product name/i });
    fireEvent.change(field, { target: { value: 'Acme' } });
    fireEvent.blur(field);

    // The API call fires immediately.
    await waitFor(() => expect(mockUpdateSettings).toHaveBeenCalled());

    // But router.refresh + onUpdate are debounced.
    expect(mockRefresh).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1000);
    expect(mockRefresh).toHaveBeenCalled();
    expect(onUpdate).toHaveBeenCalled();
    jest.useRealTimers();
  });

  it('previews the theme immediately on picker change and debounces the API save', async () => {
    jest.useFakeTimers();
    const mockPreview = jest.fn();
    const mockClearPreview = jest.fn();
    render(
      <BrandPreviewContext.Provider
        value={{
          previewBrandColors: mockPreview,
          clearBrandPreview: mockClearPreview,
        }}
      >
        <BrandingColorsForm
          organization={organization()}
          onUpdate={jest.fn()}
        />
      </BrandPreviewContext.Provider>
    );

    fireEvent.change(screen.getByLabelText('Primary Colour picker'), {
      target: { value: '#aa0000' },
    });

    // Theme preview fires immediately.
    expect(mockPreview).toHaveBeenCalledWith({ primary: '#AA0000' });

    // API save has not fired yet (300ms debounce).
    expect(mockUpdateSettings).not.toHaveBeenCalled();

    jest.advanceTimersByTime(300);
    await waitFor(() =>
      expect(mockUpdateSettings).toHaveBeenCalledWith({
        branding: { primary_color: '#AA0000' },
      })
    );
    jest.useRealTimers();
  });
});
