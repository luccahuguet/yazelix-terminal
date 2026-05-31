# Kitty Drag And Drop Tracking Policy

Status: explicit runtime deferral, no support advertised.

Source spec: https://sw.kovidgoyal.net/kitty/dnd-protocol/

Kitty OSC 72 drag and drop is a frontier terminal protocol. It is attractive
for Yazelix because Yazi already appears in the upstream support list, and real
terminal drag/drop would be a major usability upgrade. It should not be treated
as parser-only work.

Reviewed on 2026-05-31. The official Kitty spec still marks the protocol as
under development and points to upstream issue `#9984`.

## Current Decision

Yazelix-terminal must not claim OSC 72 support yet.

Reasons:

- Kitty documents the protocol as still under development
- the protocol requires OS drag/drop integration, not just escape parsing
- accepting drops requires MIME negotiation and cell/pixel coordinate reporting
- data requests can cause local filesystem reads
- remote-machine support depends on machine-id handling and `file://` URI rules
- starting drags from terminal programs requires terminal-to-OS source data,
  images, status events, cancel handling, and resource limits
- same-window drags must be denied with `EPERM` to avoid self-exfiltration
- the current `rio-window` drop events are path-level convenience events, not an
  OSC 72 data channel

## Supported Behavior For Now

Until the protocol stabilizes and Yazelix-terminal has a product/security design:

- ignore OSC 72 commands
- do not answer `t=q` support queries
- do not register OS drop targets on behalf of terminal programs
- do not expose dropped data to PTYs
- do not read files for remote drag/drop requests

This is intentionally different from file transfer, where a deny-by-default
parser skeleton is useful. For OSC 72, a support response would cause clients to
expect live OS drag/drop behavior that does not exist yet.

## Local Windowing Boundary

Current useful but insufficient primitives:

- `rio-window/src/event.rs` exposes `HoveredFile`, `DroppedFile`, and
  `HoveredFileCancelled`
- Windows `rio-window/src/platform_impl/windows/drop_handler.rs` accepts
  `CF_HDROP` file paths and emits path events
- macOS `rio-window/src/platform_impl/macos/window_delegate.rs` reads
  `NSFilenamesPboardType` and emits path events
- X11 `rio-window/src/platform_impl/linux/x11/event_processor.rs` has XDND file
  path handling

These are not enough for OSC 72 because the protocol requires per-move cell and
pixel coordinates, MIME negotiation, chunked payload data, URI-list item
requests, directory/symlink resource handles, drag-source offers, final
operation reporting, and same-window source/drop denial. Wayland coverage is
also absent in the local audit.

## Implementation Prerequisites

Before implementing support:

- upstream Kitty issue `#9984` should be resolved or the spec should be stable
  enough that behavior is unlikely to churn
- a local security policy should cover dropped file reads, same-window denial,
  URI handling, symlink/directory traversal, MIME allow lists, size limits,
  quiet/error behavior, and logging
- the frontend must expose OS drag enter/move/leave/drop events with MIME lists
  and pixel positions
- the backend must route OSC 72 events to the correct PTY route
- the renderer/input layer must translate pixels to terminal cells accurately
  across splits, margins, scale factors, and alternate screens
- tests must cover support query behavior, accepting/unaccepting drops,
  movement/drop events, data request errors, cancellation, and same-window
  denial

## First Safe Slice

The first implementation slice, after stabilization, should be support-query
only with a deliberately empty payload:

- parse `OSC 72 ; t=q[:i=id] ST`
- reply only after the product decision says support can be advertised
- echo the optional `i` value exactly when safe
- keep every non-query command unsupported until OS event routing exists

## Non-Goals

- no Kitty remote-control integration
- no automatic file reads from dropped URIs
- no support claim based only on parser recognition
- no terminal-native drag source until inbound drops are correct and safe
