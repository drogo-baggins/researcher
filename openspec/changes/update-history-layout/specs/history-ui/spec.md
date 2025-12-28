# History UI Specification

## MODIFIED Requirements

### Requirement: History Screen Layout
The History screen SHALL display session browsing interface with optimized layout for maximum content visibility.

#### Scenario: Vertical 3-row layout
- **WHEN** user opens History screen
- **THEN** screen displays three distinct rows:
  1. Horizontal filter bar (top)
  2. Compact session list (middle)
  3. Full-width session details (bottom)

#### Scenario: Filter bar arrangement
- **WHEN** filter bar is displayed
- **THEN** all filters (search, date toggle, date range, tags) are arranged horizontally in single row
- **AND** filters use column ratio `[4, 1, 2, 2, 3]` for search, date toggle, date from, date to, tags

#### Scenario: Session list compaction
- **WHEN** session list is displayed
- **THEN** list height is constrained to maximum 200px
- **AND** list shows scrollbar when content exceeds height
- **AND** session count is displayed above list

#### Scenario: Session details full width
- **WHEN** session is selected
- **THEN** session details are displayed in full width below session list
- **AND** details include conversation history, tags, evaluation scores, and search results

## ADDED Requirements

### Requirement: Date Filter Toggle
The History screen SHALL provide checkbox to enable/disable date range filtering.

#### Scenario: Date filter disabled by default
- **WHEN** user opens History screen
- **THEN** date filter checkbox is unchecked
- **AND** date range input fields are hidden

#### Scenario: Enable date filtering
- **WHEN** user checks "日付で絞り込む" checkbox
- **THEN** date range input fields (from/to) become visible
- **AND** user can select date range for filtering

#### Scenario: Disable date filtering
- **WHEN** user unchecks date filter checkbox
- **THEN** date range input fields are hidden
- **AND** date filter is not applied to session list
- **AND** date_from and date_to are set to None

#### Scenario: Date filter state persistence
- **WHEN** user toggles date filter checkbox
- **THEN** checkbox state persists across page reruns
- **AND** selected dates are preserved when checkbox is checked again

### Requirement: Horizontal Filter Bar
The History screen SHALL display all filters in single horizontal row for compact layout.

#### Scenario: Filter bar components
- **WHEN** filter bar is displayed
- **THEN** it contains:
  1. Keyword search input (4 units width)
  2. Date filter toggle checkbox (1 unit width)
  3. Date from input (2 units width, conditional)
  4. Date to input (2 units width, conditional)
  5. Tag multiselect (3 units width)

#### Scenario: Filter responsiveness
- **WHEN** screen width is reduced
- **THEN** filter bar may wrap to multiple rows
- **AND** all filter functionality remains intact

### Requirement: Compact Session List
The History screen SHALL display session list with height constraint for compact layout.

#### Scenario: Session list height constraint
- **WHEN** session list is displayed
- **THEN** list height is limited to 200px maximum
- **AND** scrollbar appears when content exceeds height
- **AND** user can scroll to view all sessions

#### Scenario: Session list interaction
- **WHEN** user selects session from list
- **THEN** session details are updated below list
- **AND** selected session is highlighted
- **AND** session ID is stored in session state
