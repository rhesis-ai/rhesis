import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NotFoundAlert } from '../NotFoundAlert';

describe('NotFoundAlert', () => {
  const defaultEntityData = {
    model_name: 'TestRun',
    model_name_display: 'Test Run',
    identifier: 'abc-123',
    list_url: '/test-runs',
    message: 'The requested Test Run was not found.',
  };

  it('renders the entity message', () => {
    render(<NotFoundAlert entityData={defaultEntityData} />);
    expect(
      screen.getByText('The requested Test Run was not found.')
    ).toBeInTheDocument();
  });

  it('renders Back button', () => {
    render(<NotFoundAlert entityData={defaultEntityData} />);
    expect(screen.getByText('Back')).toBeInTheDocument();
  });

  it('renders Explore button using display name', () => {
    render(<NotFoundAlert entityData={defaultEntityData} />);
    expect(screen.getByText('Explore Test Runs')).toBeInTheDocument();
  });

  it('falls back to model_name when display name is missing', () => {
    const entityData = {
      ...defaultEntityData,
      model_name_display: undefined,
    };
    render(<NotFoundAlert entityData={entityData} />);
    expect(screen.getByText('Explore TestRuns')).toBeInTheDocument();
  });

  it('uses backUrl when provided', () => {
    render(
      <NotFoundAlert entityData={defaultEntityData} backUrl="/custom-back" />
    );
    const exploreLink = screen.getByText('Explore Test Runs');
    expect(exploreLink.closest('a')).toHaveAttribute('href', '/custom-back');
  });

  it('uses list_url from entityData as default explore link', () => {
    render(<NotFoundAlert entityData={defaultEntityData} />);
    const exploreLink = screen.getByText('Explore Test Runs');
    expect(exploreLink.closest('a')).toHaveAttribute('href', '/test-runs');
  });

  it('renders as a warning alert', () => {
    const { container } = render(
      <NotFoundAlert entityData={defaultEntityData} />
    );
    expect(
      container.querySelector('.MuiAlert-standardWarning')
    ).toBeInTheDocument();
  });
});
