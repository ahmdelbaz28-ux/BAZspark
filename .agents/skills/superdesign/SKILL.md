# Superdesign Skill

## Purpose
A comprehensive design system methodology for building consistent, scalable, and accessible user interfaces. Emphasizes systematic design thinking, component architecture, and design tokens.

## When to Use
- Building or refactoring design systems
- Creating reusable component libraries
- Establishing design tokens and theming
- Implementing consistent UI patterns across large applications
- Safety-critical interfaces requiring high reliability

## Core Principles

### 1. Design Tokens First
- Define color, typography, spacing, and motion tokens before components
- Use semantic naming (e.g., `color-danger`, not `color-red`)
- Support theming through token overrides

### 2. Component Architecture
- Build from atomic elements up (atoms → molecules → organisms)
- Ensure components are self-contained and composable
- Document props, variants, and usage patterns

### 3. Accessibility by Default
- WCAG 2.1 AA compliance minimum
- Semantic HTML, ARIA labels, keyboard navigation
- Color contrast ratios validated against tokens

### 4. Safety-Critical Considerations
- Clear visual hierarchy for alarm states
- Redundant feedback mechanisms (color + icon + text)
- Error prevention and recovery patterns

## Workflow

1. **Audit** existing UI for inconsistencies
2. **Define** design token system (colors, type, spacing, motion)
3. **Build** component library with variants and states
4. **Document** usage guidelines and patterns
5. **Validate** against accessibility and safety requirements

## References
- `references/SUPERDESIGN.md` — Full methodology guide
- `references/INIT.md` — Project initialization checklist
- `references/GRAPHIC.md` — Visual design principles