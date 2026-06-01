#!/usr/bin/env sh
set -eu

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

usage() {
  printf 'usage: %s /path/to/yazelix-terminal-package\n' "$0" >&2
  printf '   or: YAZELIX_TERMINAL_PACKAGE=/path/to/package %s\n' "$0" >&2
}

package_dir="${1:-${YAZELIX_TERMINAL_PACKAGE:-}}"
if [ -z "$package_dir" ]; then
  usage
  exit 64
fi

config="$package_dir/share/yazelix-terminal/config.toml"
baseline_config="$package_dir/share/yazelix-terminal/baseline/config.toml"
wrapper="$package_dir/bin/yazelix-terminal-desktop"

[ -r "$config" ] || die "packaged config is not readable: $config"
[ -r "$baseline_config" ] || die "packaged baseline config is not readable: $baseline_config"
[ -x "$wrapper" ] || die "packaged desktop wrapper is not executable: $wrapper"

run_wrapper_without_host_config() (
  unset YAZELIX_TERMINAL_CONFIG
  unset RIO_CONFIG_HOME
  "$@"
)

if grep -Eq '^[[:space:]]*strategy[[:space:]]*=[[:space:]]*"game"' "$config"; then
  die "packaged config defaults to renderer.strategy = \"game\""
fi
if grep -Eq '^[[:space:]]*custom-shader[[:space:]]*=' "$baseline_config"; then
  die "baseline config should not enable custom shaders"
fi
if grep -Eq '^[[:space:]]*trail-cursor[[:space:]]*=' "$baseline_config"; then
  die "baseline config should not enable trail-cursor"
fi

version_log="$(mktemp "${TMPDIR:-/tmp}/yzt-event-version.XXXXXX")"
trap 'rm -f "$version_log"' EXIT INT HUP TERM

if ! YAZELIX_TERMINAL_PROFILE=full run_wrapper_without_host_config "$wrapper" --version >"$version_log" 2>&1; then
  cat "$version_log" >&2
  die "wrapper did not start with the packaged event-mode config"
fi

runtime_dir="$(mktemp -d "${TMPDIR:-/tmp}/yzt-event-runtime.XXXXXX")"
game_log="$(mktemp "${TMPDIR:-/tmp}/yzt-event-game.XXXXXX")"
baseline_runtime_dir="$(mktemp -d "${TMPDIR:-/tmp}/yzt-baseline-runtime.XXXXXX")"
baseline_log="$(mktemp "${TMPDIR:-/tmp}/yzt-baseline.XXXXXX")"
trap 'rm -rf "$runtime_dir" "$baseline_runtime_dir"; rm -f "$version_log" "$game_log" "$baseline_log"' EXIT INT HUP TERM

if ! XDG_RUNTIME_DIR="$runtime_dir" YAZELIX_TERMINAL_PROFILE=full YAZELIX_TERMINAL_RENDER_STRATEGY=game run_wrapper_without_host_config "$wrapper" --version >"$game_log" 2>&1; then
  cat "$game_log" >&2
  die "wrapper did not start with explicit game-mode override"
fi

game_config="$runtime_dir/yazelix-terminal/game-config/config.toml"
[ -r "$game_config" ] || die "explicit game-mode config was not materialized: $game_config"
if ! grep -Eq '^[[:space:]]*strategy[[:space:]]*=[[:space:]]*"game"' "$game_config"; then
  die "explicit game-mode config does not set renderer.strategy = \"game\""
fi

if ! XDG_RUNTIME_DIR="$baseline_runtime_dir" YAZELIX_TERMINAL_PROFILE=baseline YAZELIX_TERMINAL_RENDER_STRATEGY=game run_wrapper_without_host_config "$wrapper" --version >"$baseline_log" 2>&1; then
  cat "$baseline_log" >&2
  die "wrapper did not start with baseline no-effects profile"
fi

baseline_game_config="$baseline_runtime_dir/yazelix-terminal/game-config/config.toml"
[ -r "$baseline_game_config" ] || die "baseline game-mode config was not materialized: $baseline_game_config"
if ! grep -Eq '^[[:space:]]*strategy[[:space:]]*=[[:space:]]*"game"' "$baseline_game_config"; then
  die "baseline game-mode config does not set renderer.strategy = \"game\""
fi
if grep -Eq '^[[:space:]]*custom-shader[[:space:]]*=' "$baseline_game_config"; then
  die "baseline game-mode config should not enable custom shaders"
fi
if grep -Eq '^[[:space:]]*trail-cursor[[:space:]]*=' "$baseline_game_config"; then
  die "baseline game-mode config should not enable trail-cursor"
fi

printf 'Yazelix Terminal event-mode package smoke passed\n'
printf '%s\n' '- packaged config does not default to renderer.strategy = "game"'
printf '%s\n' '- desktop wrapper starts with packaged config'
printf '%s\n' '- explicit YAZELIX_TERMINAL_RENDER_STRATEGY=game escape hatch works'
printf '%s\n' '- baseline no-effects profile starts and composes with game strategy'
