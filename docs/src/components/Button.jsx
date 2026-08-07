'use client'

import React from 'react'

const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  onClick,
  disabled = false,
  className = '',
  ...props
}) => {
  const getVariantStyles = () => {
    const variants = {
      primary: {
        color: 'var(--rh-on-accent)',
        background: 'var(--rh-blue-cta)', // Primary CTA Blue
        border: '1px solid var(--rh-blue-cta)',
        hoverBackground: 'var(--rh-blue)', // Primary Blue on hover
        disabledBackground: 'var(--rh-text-muted)',
        disabledBorder: 'var(--rh-text-muted)',
      },
      secondary: {
        color: 'var(--rh-on-accent)',
        background: 'var(--rh-orange)', // Secondary CTA Orange
        border: '1px solid var(--rh-orange)',
        hoverBackground: 'var(--rh-yellow)', // Accent Yellow on hover
        hoverColor: 'var(--rh-heading)', // Dark text on yellow hover
        disabledBackground: 'var(--rh-surface-sunken)',
        disabledBorder: 'var(--rh-border)',
        disabledColor: 'var(--rh-text-muted)',
      },
      outline: {
        color: 'var(--rh-blue-cta)', // Primary CTA Blue
        background: 'transparent',
        border: '1px solid var(--rh-blue-cta)',
        hoverBackground: 'var(--rh-blue-cta)', // Fill with primary on hover
        hoverColor: 'var(--rh-on-accent)',
        disabledBackground: 'transparent',
        disabledBorder: 'var(--rh-border)',
        disabledColor: 'var(--rh-text-muted)',
      },
      ghost: {
        color: 'var(--rh-blue-cta)', // Primary CTA Blue
        background: 'transparent',
        border: '1px solid transparent',
        hoverBackground: 'rgba(42, 161, 206, 0.1)', // Light blue hover
        disabledBackground: 'transparent',
        disabledBorder: 'transparent',
        disabledColor: 'var(--rh-text-muted)',
      },
    }
    return variants[variant] || variants.primary
  }

  const getSizeStyles = () => {
    const sizes = {
      sm: {
        padding: '6px 12px',
        fontSize: '12px',
        height: '32px',
        borderRadius: '6px',
      },
      md: {
        padding: '8px 16px',
        fontSize: '14px',
        height: '33.5px', // Adjusted height as requested
        borderRadius: '8px',
      },
      lg: {
        padding: '12px 24px',
        fontSize: '16px',
        height: '48px',
        borderRadius: '10px',
      },
    }
    return sizes[size] || sizes.md
  }

  const variantStyles = getVariantStyles()
  const sizeStyles = getSizeStyles()

  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'var(--rh-font-sans)',
    fontWeight: '600',
    boxShadow: disabled ? 'none' : '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s ease-in-out',
    outline: 'none',
    opacity: disabled ? 0.6 : 1,
    textTransform: 'none',
    ...sizeStyles,
    color:
      disabled && variantStyles.disabledColor ? variantStyles.disabledColor : variantStyles.color,
    background:
      disabled && variantStyles.disabledBackground
        ? variantStyles.disabledBackground
        : variantStyles.background,
    border:
      disabled && variantStyles.disabledBorder
        ? `1px solid ${variantStyles.disabledBorder}`
        : variantStyles.border,
  }

  return (
    <button
      type="button"
      style={baseStyle}
      onMouseEnter={e => {
        if (!disabled && variantStyles.hoverBackground) {
          e.target.style.background = variantStyles.hoverBackground
          if (variantStyles.hoverColor) {
            e.target.style.color = variantStyles.hoverColor
          }
          e.target.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
        }
      }}
      onMouseLeave={e => {
        if (!disabled) {
          e.target.style.background = variantStyles.background
          e.target.style.color = variantStyles.color
          e.target.style.boxShadow = '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
        }
      }}
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={className}
      {...props}
    >
      {children}
    </button>
  )
}

// Specific button variants as named exports (following Langfuse pattern)
export const PrimaryButton = props => <Button variant="primary" {...props} />
export const SecondaryButton = props => <Button variant="secondary" {...props} />
export const OutlineButton = props => <Button variant="outline" {...props} />
export const GhostButton = props => <Button variant="ghost" {...props} />

// Navbar-specific button that handles its own click logic
export const NavbarGoToAppButton = () => {
  const handleClick = () => {
    // eslint-disable-next-line no-console
    console.log('Go to app clicked')
    // TODO: Add navigation logic here when ready
  }

  return (
    <div className="flex items-center ml-2">
      <Button variant="primary" size="md" onClick={handleClick} aria-label="TO APP">
        Go to app
      </Button>
    </div>
  )
}

export default Button
