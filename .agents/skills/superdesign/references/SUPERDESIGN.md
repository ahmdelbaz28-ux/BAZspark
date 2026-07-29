# Superdesign Methodology

## Overview
Superdesign is a systematic approach to building design systems that scale across teams and applications. It emphasizes consistency, accessibility, and maintainability through token-driven design and composable components.

## Design Token System

### Color Tokens
```css
:root {
  /* Semantic Colors */
  --color-primary: #1a73e8;
  --color-primary-hover: #1557b0;
  --color-secondary: #5f6368;
  
  /* Status Colors */
  --color-success: #34a853;
  --color-warning: #fbbc04;
  --color-danger: #ea4335;
  --color-info: #4285f4;
  
  /* Surface Colors */
  --color-background: #ffffff;
  --color-surface: #f8f9fa;
  --color-border: #dadce0;
  
  /* Text Colors */
  --color-text-primary: #202124;
  --color-text-secondary: #5f6368;
  --color-text-disabled: #9aa0a6;
}
```

### Typography Scale
```css
:root {
  --font-family-primary: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-family-mono: 'JetBrains Mono', 'Fira Code', monospace;
  
  /* Font Sizes */
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */
  --font-size-xl: 1.25rem;    /* 20px */
  --font-size-2xl: 1.5rem;    /* 24px */
  --font-size-3xl: 1.875rem;  /* 30px */
  --font-size-4xl: 2.25rem;   /* 36px */
  
  /* Font Weights */
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
}
```

### Spacing System
```css
:root {
  --space-0: 0;
  --space-1: 0.25rem;  /* 4px */
  --space-2: 0.5rem;   /* 8px */
  --space-3: 0.75rem;  /* 12px */
  --space-4: 1rem;     /* 16px */
  --space-5: 1.25rem;  /* 20px */
  --space-6: 1.5rem;   /* 24px */
  --space-8: 2rem;     /* 32px */
  --space-10: 2.5rem;  /* 40px */
  --space-12: 3rem;    /* 48px */
}
```

## Component Architecture

### Atomic Design Levels
1. **Atoms**: Button, Input, Icon, Label
2. **Molecules**: FormField, SearchBar, CardHeader
3. **Organisms**: Navigation, DataTable, Modal
4. **Templates**: PageLayout, DashboardGrid
5. **Pages**: Complete views assembled from templates

### Component Documentation Template
```typescript
interface ButtonProps {
  /** Button variant */
  variant: 'primary' | 'secondary' | 'danger' | 'ghost';
  /** Button size */
  size: 'sm' | 'md' | 'lg';
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Icon before label */
  leftIcon?: React.ReactNode;
  /** Icon after label */
  rightIcon?: React.ReactNode;
  /** Click handler */
  onClick?: () => void;
  /** Button content */
  children: React.ReactNode;
}
```

## Safety-Critical UI Patterns

### Alarm State Indicators
- **Normal**: Green background, checkmark icon
- **Warning**: Yellow background, alert icon
- **Alarm**: Red background, flashing icon, sound indicator
- **Fault**: Orange background, wrench icon

### Redundant Feedback
1. Color coding (always paired with icon/text)
2. Iconography (unique shapes for each state)
3. Text labels (clear, concise descriptions)
4. Motion (subtle animations for state changes)

### Error Prevention
- Confirmation dialogs for destructive actions
- Input validation with clear error messages
- Undo functionality where possible
- Progressive disclosure for complex operations