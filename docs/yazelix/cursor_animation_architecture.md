# Cursor Animation Architecture

Status: active policy for Yazelix Terminal dogfooding.

Date: 2026-06-02.

## Decision

Rio's native `trail-cursor` is the primary Yazelix Terminal cursor animation.
It stays enabled in the packaged `full`/`default` profile.

Ghostty-compatible `custom-shader` cursor presets remain supported, packaged,
and tested, but they are opt-in through the `shaders` profile. They are not part
of the default dogfooding profile because they add a second cursor-animation
owner on top of Rio's trail.

## Evidence

- Rio documents `trail-cursor` as a built-in smooth cursor trail using spring
  physics: <https://rioterm.com/docs/config#effects>
- Ghostty documents `custom-shader` as a postprocess shader chain over the
  current terminal texture, with cursor uniforms and an optional animation loop:
  <https://ghostty.org/docs/config/reference#custom-shader>
- Local dogfooding on 2026-06-02 first showed the focus-regain lag and fast
  catch-up rendering bug improve when `custom-shader` was removed from the
  generated `yzxterm` config while `trail-cursor = true` stayed enabled. The
  bug later reproduced without custom shaders, so shader stacking is not the
  proven root cause.
- Local code has two independent animation paths:
  - `frontends/rioterm/src/renderer/trail_cursor.rs` owns Rio's spring trail.
  - `sugarloaf/src/components/ghostty_shaders/mod.rs` owns shader time,
    previous/current cursor uniforms, and shader animation invalidation.

That combination is useful for compatibility testing, but it is not an elegant
default cursor architecture. The default should have one cursor motion owner,
even though the remaining focus catch-up bug still needs separate investigation.

## Profiles

| Profile | Renderer | Rio Trail | Ghostty Shaders | Purpose |
| --- | --- | --- | --- | --- |
| `full`, `default`, `effects` | WebGPU | enabled | disabled | Dogfooding profile with Rio's native trail |
| `baseline`, `no-effects`, `none` | WebGPU | disabled | disabled | No-effects comparison profile |
| `shaders`, `cursor-shaders`, `ghostty-shaders` | WebGPU | enabled | enabled | Compatibility and visual-effect diagnostics |

`YAZELIX_TERMINAL_RENDER_STRATEGY=game` remains a renderer scheduling
diagnostic. It composes with each profile, but it does not imply shader use.

## Integration Policy

Future shader work should build on top of Rio trail instead of replacing it.
That means one of these designs:

- non-cursor postprocess shaders that treat the already-rendered Rio trail in
  `iChannel0` as part of the terminal frame
- a Yazelix-specific shader uniform extension that exposes Rio's animated trail
  state, so shader effects can decorate the same cursor animation
- an explicit compatibility mode that intentionally stacks Ghostty cursor
  shaders over Rio trail for parity investigations

The default profile must not compute an independent Ghostty cursor trail while
Rio's trail is already active.

## Validation Matrix

- package config: `share/yazelix-terminal/config.toml` has
  `trail-cursor = true` and no `custom-shader`
- baseline config: `share/yazelix-terminal/baseline/config.toml` has neither
  `trail-cursor` nor `custom-shader`
- shader profile:
  `share/yazelix-terminal/profiles/shaders/config.toml` has both
  `trail-cursor = true` and the packaged `custom-shader` chain
- wrapper smoke: `tools/yazelix_event_mode_smoke.sh` verifies all profile
  contents and starts the default, baseline, and shader profiles
- benchmark harness: `yzt-default` means Rio trail only; `yzt-shaders` means
  the opt-in shader stack on top of Rio trail
