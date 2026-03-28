# Control Console Guide

The built-in browser console is now organized by scenario preset first, with advanced controls collapsed behind explicit disclosure.

## Design Goal

The console should help a Human Operator do the next correct thing without forcing them to think like an MCP protocol implementer.

That means:

- the top of the page is task-first
- the top-right language switch keeps English and Traditional Chinese one click away
- the top-right layout switch lets operators widen the canvas or stack cards vertically
- advanced identifiers are still available
- diagnostics still exist
- every existing server action remains reachable

## Scenario Presets

### Quick Pairing

Default for:

- launching a Host + Guest pair
- starting a bridge
- watching the live room
- sending short operator guidance

Primary controls:

- backend
- profile
- session
- `Init Session`
- `Start Collaboration`
- `Stop Bridge`

Visible panels:

- session launch
- live room
- operator message composer
- compact status summary

### Approval Gate

Default for:

- human-reviewed forwarding
- code mutation or shell-risk tasks

Changes from Quick Pairing:

- `auto_forward=true`
- `intervention=true`
- pending queue becomes a first-class panel

Primary controls:

- refresh pending
- selected handoff detail
- approve selected
- reject selected
- approve all
- reject all

### MCP Operator

Default for:

- supervising an external MCP client
- watching room state while another app drives tool calls

Primary controls:

- room and bridge summary
- transport health
- operator room message post
- raw status snapshot

Advanced controls remain available for:

- explicit `backend_id`
- explicit `bridge_id`
- explicit `room_id`

### Diagnostics

Default for:

- smoke tests
- backend validation
- capture, interrupt, and audit triage workflows

Primary controls:

- terminal capture
- interrupt Host
- interrupt Guest
- interrupt both
- audit status
- recent audit entries
- audit event filter
- audit entry limit
- raw status

### Handoff Radar

Default for:

- dense review loops where the Host watches the room and the queue together
- repeated approve / reject decisions while the bridge stays active

Primary controls:

- live room stream
- review queue
- approve selected
- reject selected

### Quiet Loop

Default for:

- low-noise pairing
- a human operator who mainly wants launch plus live messaging

Primary controls:

- launch card
- live room
- operator message composer

Status and diagnostics intentionally recede unless the operator asks for them.

### Mission Control

Default for:

- host-led coordination shifts
- topology inspection plus diagnostics plus room supervision at the same time

Primary controls:

- raw status snapshot
- live room
- diagnostics
- review queue

## Information Hierarchy

### 1. Hero strip

Show:

- active preset
- current endpoint
- transport state
- current language
- one-sentence explanation of the preset

### 2. Main task card

Show only the fields required to complete the current preset.

For Quick Pairing this should be:

- backend
- profile
- session
- auto-forward
- intervention

### 3. Live collaboration card

Always visible after a bridge exists.

Show:

- room stream
- operator message composer
- send to Host
- send to Guest
- post to room

### 4. Review queue card

Visible by default only in `Approval Gate`.

Collapsed in other presets unless pending items exist.

Show:

- pending list
- selected handoff detail
- edited approval text
- approve / reject controls

### 5. Diagnostics card

Collapsed by default unless the preset is `Diagnostics`.

Contains:

- capture Host
- capture Guest
- interrupt controls
- audit enabled state
- recent persisted audit events
- audit event filter
- audit entry limit
- raw status JSON

### 6. Status card

Show:

- structured guard / pending / subscriber / audit summary
- raw status JSON
- activity log

### 7. Advanced details

Always available, never primary.

Collapse:

- `backend_id`
- `bridge_id`
- `room_id`
- pane A / pane B raw IDs
- transport selection

## Actions That Must Remain Preserved

The simplified console still needs full reachability for:

- `terminal_init`
- `bridge_start`
- `bridge_stop`
- `room_post`
- `terminal_capture`
- `terminal_interrupt`
- `intervention_list`
- `intervention_approve`
- `intervention_reject`
- `audit_recent`
- `status`

## Recommended Defaults

| Preset | Transport | Auto-forward | Intervention |
| --- | --- | --- | --- |
| Quick Pairing | `sse` | on | off |
| Approval Gate | `sse` | on | on |
| MCP Operator | `ws` or `sse` | off | off |
| Diagnostics | `room_poll` | off | off |
| Handoff Radar | `sse` | on | on |
| Quiet Loop | `sse` | on | off |
| Mission Control | `ws` | off | off |

## Operational Rule

If the user cannot explain why they need a raw ID, that control should probably be hidden behind Advanced.
