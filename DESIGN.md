---
name: Enterprise AI Agent
description: A composed enterprise AI workspace for grounded knowledge retrieval, document workflows, and inspectable agent execution.
colors:
  bg: "#f5f5f5"
  surface: "#ffffff"
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  danger: "#dc2626"
  danger-hover: "#b91c1c"
  text: "#1f2937"
  text-secondary: "#6b7280"
  border: "#e5e7eb"
  user-message: "#dbeafe"
  assistant-message: "#f0fdf4"
  success: "#16a34a"
  error: "#dc2626"
typography:
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.2
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.2
rounded:
  sm: "4px"
  md: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  input-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: Enterprise AI Agent

## 1. Overview

**Creative North Star: "The Evidence Desk"**

Enterprise AI Agent is a dense product workspace for users who need grounded answers, not a theatrical chatbot. The visual system should make document context, citations, tool execution, and admin state feel inspectable and trustworthy.

The current system is restrained: light surfaces, blue primary actions, compact controls, bordered panels, status chips, and system typography. Future work should preserve the serious product posture while adding hierarchy, color structure, and stronger workflow affordances so the screen no longer reads as gray boilerplate.

**Key Characteristics:**
- Compact, operational, and source-aware.
- Clear distinction between document work, session context, chat, citations, and admin state.
- Blue accent reserved for primary action, active selection, focus, and trusted traceability.
- State colors used for meaning only: success, error, warning, processing, role, visibility.

## 2. Colors

The palette is a restrained product palette: neutral surfaces, a single blue trust accent, and semantic status colors for operational clarity.

### Primary
- **Trace Blue**: Used for selected sessions, primary hover states, focus borders, citation scores, and trustworthy active state.

### Secondary
- **Document Sky**: Used sparingly for document file-type badges and user-message context.
- **Evidence Green**: Used for assistant answers, success states, and ready/healthy status.

### Neutral
- **Workspace Gray**: The application background; should remain quiet and secondary to content surfaces.
- **Panel White**: Primary surface for tool panels, chat input, citations, admin tables, and sidebars.
- **Ink**: Main readable text.
- **Muted Ink**: Secondary metadata and helper labels; must stay high enough contrast for WCAG AA.
- **Divider Gray**: Borders between persistent product regions.

### Named Rules
**The Evidence Color Rule.** Blue is not decoration. It marks action, selection, focus, citation confidence, or traceable state.

## 3. Typography

**Display Font:** System sans stack
**Body Font:** System sans stack
**Label/Mono Font:** System sans stack, with monospace only for tool names, JSON, trace IDs, and config keys

**Character:** Familiar enterprise typography. It should feel fast, readable, and low-friction, with no display-font flourish in controls or data.

### Hierarchy
- **Title** (600, 1.25rem, 1.2): App title and major panel headings.
- **Section Label** (600, 0.875rem, uppercase): Sidebar and tool group headings; use sparingly so the UI does not become a wall of shouting labels.
- **Body** (400, 0.9375rem, 1.5): Chat content and readable prose.
- **Data Label** (500-600, 0.6875rem-0.8125rem): Badges, table cells, metadata, tool state, and trace labels.

### Named Rules
**The Data First Rule.** Typography should clarify density, not perform personality. Reserve weight and size changes for hierarchy that affects task speed.

## 4. Elevation

The current system is mostly flat and uses borders plus tonal layering instead of shadows. That is appropriate for this product, but panels need clearer hierarchy through background contrast, border intent, sticky regions, and focused state styling rather than decorative drop shadows.

### Named Rules
**The Flat Confidence Rule.** Surfaces are flat at rest. Use shadows only for overlays or transient affordances, never as decoration on every card.

## 5. Components

### Buttons
- **Shape:** Compact rounded rectangle (8px radius).
- **Primary:** Blue background with white text for selected or committed actions.
- **Hover / Focus:** Hover may fill with Trace Blue; focus must use a visible ring or high-contrast border.
- **Secondary / Ghost:** White or transparent background with border; never use heavy shadow plus border together.

### Chips
- **Style:** Small tonal labels with role-specific color.
- **State:** Used for status, file type, visibility, role, and execution outcome. They must not rely on color alone; text should name the state.

### Cards / Containers
- **Corner Style:** Tight corners (8px).
- **Background:** White panels over a neutral workspace background.
- **Shadow Strategy:** Border and tonal layering first; no broad decorative shadows.
- **Internal Padding:** 12-16px for dense panels, 16-24px for primary workspace regions.

### Inputs / Fields
- **Style:** White fill, subtle border, 8px radius.
- **Focus:** Border or ring shifts to Trace Blue.
- **Error / Disabled:** Error text must be explicit; disabled controls reduce opacity but keep labels readable.

### Navigation
- **Style:** Sidebar-driven and tab-driven navigation. Active states use Trace Blue or a strong tonal selection. Mobile treatment should preserve access to documents, sessions, and chat without forcing long vertical scrolling.

## 6. Do's and Don'ts

### Do:
- **Do** make evidence visible: citations, trace IDs, tool results, and agent steps should remain easy to scan.
- **Do** use compact density for enterprise workflows, with enough contrast and spacing to prevent gray noise.
- **Do** standardize buttons, selects, tabs, chips, tables, and focus states across user and admin surfaces.
- **Do** keep motion short and state-driven, with reduced-motion alternatives.

### Don't:
- **Don't** create a toy-like AI chat interface.
- **Don't** drift into ordinary SaaS-template gloss.
- **Don't** let the UI become gray, flat, and lifeless.
- **Don't** use terminal-heavy hacker aesthetics.
- **Don't** hide source traceability behind decorative chat bubbles.
- **Don't** use gradient text, glassmorphism, side-stripe card accents, or decorative shadows as a default.
