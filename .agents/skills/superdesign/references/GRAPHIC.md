# Visual Design Principles

## Layout & Grid System

### Grid Structure
```css
.grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--space-4);
}

/* Responsive breakpoints */
@media (max-width: 1200px) {
  .grid {
    grid-template-columns: repeat(8, 1fr);
  }
}

@media (max-width: 768px) {
  .grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 480px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
```

### Spacing Guidelines
- **Component padding**: `var(--space-4)` to `var(--space-6)`
- **Section spacing**: `var(--space-8)` to `var(--space-12)`
- **Page margins**: `var(--space-4)` mobile, `var(--space-8)` desktop
- **Element gaps**: `var(--space-2)` to `var(--space-4)`

## Typography Hierarchy

### Headings
```css
h1 {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  line-height: 1.2;
  margin-bottom: var(--space-4);
}

h2 {
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-semibold);
  line-height: 1.3;
  margin-bottom: var(--space-3);
}

h3 {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  line-height: 1.4;
  margin-bottom: var(--space-2);
}
```

### Body Text
```css
p {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-normal);
  line-height: 1.6;
  color: var(--color-text-primary);
  margin-bottom: var(--space-4);
}

.small {
  font-size: var(--font-size-sm);
  line-height: 1.5;
}
```

## Color Application

### Status Colors in Context
```css
/* Success states */
.success-bg {
  background-color: rgba(52, 168, 83, 0.1);
  border: 1px solid var(--color-success);
  color: var(--color-success);
}

/* Warning states */
.warning-bg {
  background-color: rgba(251, 188, 4, 0.1);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
}

/* Danger states */
.danger-bg {
  background-color: rgba(234, 67, 53, 0.1);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}
```

### Contrast Requirements
- **Normal text**: 4.5:1 minimum contrast ratio
- **Large text**: 3:1 minimum contrast ratio
- **UI components**: 3:1 minimum contrast ratio

## Motion & Animation

### Timing Functions
```css
:root {
  --ease-in: cubic-bezier(0.4, 0, 1, 1);
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
}
```

### Duration Scale
```css
:root {
  --duration-fast: 100ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
  --duration-slower: 500ms;
}
```

### Animation Examples
```css
/* Hover transitions */
.button {
  transition: background-color var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}

.button:hover {
  transform: translateY(-1px);
}

/* Loading states */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spinner {
  animation: spin var(--duration-slow) linear infinite;
}

/* Focus indicators */
@keyframes focus-ring {
  0% { box-shadow: 0 0 0 0 var(--color-primary); }
  100% { box-shadow: 0 0 0 4px var(--color-primary); }
}

.input:focus {
  animation: focus-ring var(--duration-fast) var(--ease-out) forwards;
}
```

## Responsive Design

### Breakpoints
```css
/* Mobile first approach */
@media (min-width: 480px) { /* Small devices */ }
@media (min-width: 768px) { /* Medium devices */ }
@media (min-width: 1024px) { /* Large devices */ }
@media (min-width: 1200px) { /* Extra large devices */ }
```

### Container Widths
```css
.container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-4);
}

@media (min-width: 768px) {
  .container {
    padding: 0 var(--space-8);
  }
}
```

## Component Patterns

### Cards
```css
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-normal) var(--ease-out);
}

.card:hover {
  box-shadow: var(--shadow-md);
}
```

### Forms
```css
.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-1);
}

.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  transition: border-color var(--duration-fast) var(--ease-out);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.1);
}

.form-input.error {
  border-color: var(--color-danger);
}

.form-error {
  font-size: var(--font-size-sm);
  color: var(--color-danger);
  margin-top: var(--space-1);
}
```

### Navigation
```css
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-6);
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
}

.nav-item {
  padding: var(--space-2) var(--space-3);
  color: var(--color-text-secondary);
  text-decoration: none;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-out);
}

.nav-item:hover {
  background: var(--color-surface);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: var(--color-primary);
  color: white;
}
```

## Accessibility Patterns

### Focus Management
```css
/* Visible focus indicators */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Remove default outline for mouse users */
:focus:not(:focus-visible) {
  outline: none;
}
```

### Skip Links
```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: var(--space-2) var(--space-4);
  z-index: 100;
  transition: top var(--duration-fast) var(--ease-out);
}

.skip-link:focus {
  top: 0;
}
```

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

## Dark Mode Support

### Color Inversion
```css
@media (prefers-color-scheme: dark) {
  :root {
    --color-background: #1a1a1a;
    --color-surface: #2d2d2d;
    --color-border: #404040;
    --color-text-primary: #ffffff;
    --color-text-secondary: #b0b0b0;
  }
}
```

### Theme Toggle
```typescript
const ThemeToggle = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute(
      'data-theme',
      isDark ? 'dark' : 'light'
    );
  }, [isDark]);

  return (
    <button
      onClick={() => setIsDark(!isDark)}
      aria-label={`Switch to ${isDark ? 'light' : 'dark'} mode`}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
};
```