# Design: History Screen Layout Optimization

## Context
The History screen is a read-only interface for browsing past sessions. Current 2-column layout limits content visibility and makes filter interaction cumbersome. Users need better visibility of session details and more efficient filter controls.

## Goals
- Maximize content display area for session details
- Reduce filter interaction complexity (especially date filtering)
- Improve visual hierarchy and information flow
- Maintain all existing functionality

## Non-Goals
- Add new filtering capabilities
- Change session data model
- Implement advanced search features
- Add pagination beyond current 500-session limit

## Decisions

### Decision 1: Vertical 3-Row Layout
**What**: Replace 2-column layout with vertical 3-row layout (filters → list → details)
**Why**: 
- Vertical flow matches natural reading direction
- Maximizes horizontal space for content
- Clearer information hierarchy
**Alternatives considered**:
- Sticky header with filters: More complex, less mobile-friendly
- Collapsible filter panel: Adds interaction complexity
- Tabbed interface: Breaks workflow continuity

### Decision 2: Horizontal Filter Bar
**What**: Arrange all filters (search, date toggle, date range, tags) in single row
**Why**:
- Reduces vertical space consumption
- Keeps all controls visible at once
- Improves scanning efficiency
**Column ratio**: `[4, 1, 2, 2, 3]`
- Search: 4 units (largest, most important)
- Date toggle: 1 unit (checkbox only)
- Date from: 2 units
- Date to: 2 units
- Tags: 3 units

### Decision 3: Date Filter Toggle
**What**: Add checkbox to enable/disable date filtering
**Why**:
- Date picker is "heavy" operation (user feedback)
- Most users don't need date filtering
- Reduces cognitive load
**Implementation**: Conditional display of date inputs based on checkbox state

### Decision 4: Session List Height Constraint
**What**: Limit session list height to ~200px with scrolling
**Why**:
- Prevents list from dominating screen
- Keeps session details visible without scrolling
- Maintains compact layout
**Implementation options**:
- Option A (preferred): `st.container()` + custom CSS
- Option B: `st.dataframe()` with height parameter

### Decision 5: Remove Calendar Visualization
**What**: Remove `render_calendar_visualization()` from main layout
**Why**:
- Takes up space in compact layout
- Not essential for core workflow
- Can be restored as expandable section if needed
**Future**: Consider adding as optional expandable section

## Risks & Trade-offs

| Risk | Mitigation |
|------|-----------|
| Horizontal filter bar may wrap on narrow screens | Test on mobile/tablet; adjust column ratios if needed |
| Height constraint may hide sessions | Provide clear scrolling affordance; consider pagination |
| Date toggle adds interaction step | Checkbox is intuitive; most users won't need it |
| Removing calendar loses visualization | Can be restored as expandable section later |

## Migration Plan
- No data migration needed (UI-only change)
- No breaking changes to API or data model
- Existing sessions and filters work unchanged
- User session state (selected session) preserved

## Implementation Approach
1. Refactor filter function to horizontal layout
2. Add session list height constraint
3. Restructure main() layout from columns to vertical flow
4. Test on multiple screen sizes
5. Verify all filter combinations work correctly

## Open Questions
- Should calendar visualization be kept as expandable section?
- What's the optimal height constraint for session list (200px vs other)?
- Should filter state be persisted across page reloads?
