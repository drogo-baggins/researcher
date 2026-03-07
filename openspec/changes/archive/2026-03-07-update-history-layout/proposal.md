# Change: Update History Screen Layout for Better Content Visibility

## Why
The current History screen uses a left-right 2-column layout (1:2 ratio) where the left pane contains filters and session selection, and the right pane displays session details. This layout causes the content display area to be cramped due to:
- Left pane occupying 1/3 of the width for filters
- Filters arranged vertically, consuming vertical space
- Date range inputs always visible, adding complexity
- Limited horizontal space for session details

## What Changes
- **Layout restructure**: Change from left-right 2-column to vertical 3-row layout
  - Row 1: Horizontal filter bar (search, date toggle, date range, tags) - compact
  - Row 2: Session list with height constraint - compact
  - Row 3: Full-width session details
- **Filter optimization**: 
  - Arrange filters in single horizontal row using `st.columns()`
  - Add checkbox to enable/disable date filtering (avoids heavy date picker operations)
  - Date range inputs only visible when checkbox is enabled
- **Session list compaction**:
  - Add height constraint to session list (max 200px)
  - Reduce vertical space consumption
- **Content expansion**:
  - Session details now use full width
  - Improved readability and content visibility

## Impact
- **Affected specs**: `history-ui` (new capability)
- **Affected code**: 
  - `src/researcher/pages/2_📚_History.py` (main changes)
  - `src/researcher/session_manager.py` (no changes needed)
- **Breaking changes**: None (UI-only change, no API/data model changes)
- **User impact**: Improved visual layout, better content visibility, more efficient filter interaction
