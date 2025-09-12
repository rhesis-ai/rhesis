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
        color: '#ffffff',
        background: '#1D2939', // Using primary main from theme
        border: '1px solid #1D2939',
        hoverBackground: '#344054', // Using paper background from dark theme
        disabledBackground: '#9ca3af',
        disabledBorder: '#9ca3af',
      },
      secondary: {
        color: '#1D2939',
        background: '#F38755', // Using secondary main from theme
        border: '1px solid #F38755',
        hoverBackground: '#E5762F', // Slightly darker orange for hover
        disabledBackground: '#f3f4f6',
        disabledBorder: '#e5e7eb',
        disabledColor: '#9ca3af',
      },
      outline: {
        color: '#1D2939', // Using primary main from theme
        background: 'transparent',
        border: '1px solid #1D2939',
        hoverBackground: 'rgba(29, 41, 57, 0.04)', // Light hover with primary color
        disabledBackground: 'transparent',
        disabledBorder: '#e5e7eb',
        disabledColor: '#9ca3af',
      },
      ghost: {
        color: '#1D2939', // Using primary main from theme
        background: 'transparent',
        border: '1px solid transparent',
        hoverBackground: 'rgba(29, 41, 57, 0.04)', // Light hover with primary color
        disabledBackground: 'transparent',
        disabledBorder: 'transparent',
        disabledColor: '#9ca3af',
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
    fontWeight: '600',
    boxShadow: disabled ? 'none' : '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.2s ease-in-out',
    outline: 'none',
    opacity: disabled ? 0.6 : 1,
    ...sizeStyles,
    color: disabled && variantStyles.disabledColor ? variantStyles.disabledColor : variantStyles.color,
    background: disabled && variantStyles.disabledBackground ? variantStyles.disabledBackground : variantStyles.background,
    border: disabled && variantStyles.disabledBorder ? `1px solid ${variantStyles.disabledBorder}` : variantStyles.border,
  }

  return (
    <button
      type="button"
      style={baseStyle}
      onMouseEnter={(e) => {
        if (!disabled && variantStyles.hoverBackground) {
          e.target.style.background = variantStyles.hoverBackground
          e.target.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.target.style.background = variantStyles.background
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
export const PrimaryButton = (props) => <Button variant="primary" {...props} />
export const SecondaryButton = (props) => <Button variant="secondary" {...props} />
export const OutlineButton = (props) => <Button variant="outline" {...props} />
export const GhostButton = (props) => <Button variant="ghost" {...props} />

// Navbar-specific button that handles its own click logic
export const NavbarGoToAppButton = () => {
  const handleClick = () => {
    console.log('Go to app clicked');
    // TODO: Add navigation logic here when ready
  }

  return (
    <div className="flex items-center ml-2">
      <Button 
        variant="primary" 
        size="md"
        onClick={handleClick}
        aria-label="TO APP"
      >
        Go to app
      </Button>
    </div>
  )
}

export default Button
