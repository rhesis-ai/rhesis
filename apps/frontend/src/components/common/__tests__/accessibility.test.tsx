/**
 * Accessibility tests for key common components.
 *
 * Uses jest-axe to run axe-core rules against rendered component trees.
 * These tests catch WCAG violations early in development without requiring
 * a running browser.
 */
import React from 'react';
import { render } from '@testing-library/react';
import { axe } from 'jest-axe';
import '@testing-library/jest-dom';
import { DeleteModal } from '../DeleteModal';
import { NotificationProvider } from '../NotificationContext';
import StatusChip from '../StatusChip';

describe('Accessibility — common components', () => {
  describe('DeleteModal', () => {
    it('has no axe violations when open with default props', async () => {
      const { container } = render(
        <DeleteModal
          open={true}
          onClose={jest.fn()}
          onConfirm={jest.fn()}
          title="Delete Item"
          message="Are you sure you want to delete this item?"
        />
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('has no axe violations when open with item name', async () => {
      const { container } = render(
        <DeleteModal
          open={true}
          onClose={jest.fn()}
          onConfirm={jest.fn()}
          title="Delete Project"
          itemName="My Project"
          itemType="project"
        />
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('has no axe violations when closed', async () => {
      const { container } = render(
        <DeleteModal open={false} onClose={jest.fn()} onConfirm={jest.fn()} />
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('NotificationProvider', () => {
    it('has no axe violations when rendered without active notifications', async () => {
      const { container } = render(
        <NotificationProvider>
          <div>App content</div>
        </NotificationProvider>
      );
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('StatusChip', () => {
    it('has no axe violations for a "Pass" status', async () => {
      const { container } = render(<StatusChip status="Pass" />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('has no axe violations for a "Fail" status', async () => {
      const { container } = render(<StatusChip status="Fail" />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('has no axe violations for an "Error" status', async () => {
      const { container } = render(<StatusChip status="Error" />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
