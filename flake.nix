{
  description = "Yazelix Terminal | A Rio-derived GPU terminal emulator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
    rust-overlay.url = "github:oxalica/rust-overlay";
    rust-overlay.inputs.nixpkgs.follows = "nixpkgs";
    systems.url = "github:nix-systems/default";
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;} {
      imports = [flake-parts.flakeModules.easyOverlay];

      systems = import inputs.systems;

      perSystem = {
        self',
        inputs',
        pkgs,
        system,
        lib,
        ...
      }: let
        # Defines a devshell using the `rust-toolchain`, allowing for
        # different versions of rust to be used.
        mkDevShell = rust-toolchain: let
          runtimeDeps = self'.packages."yazelix-terminal".runtimeDependencies;
          tools =
            self'.packages."yazelix-terminal".nativeBuildInputs
            ++ self'.packages."yazelix-terminal".buildInputs
            ++ [rust-toolchain];
        in
          pkgs.mkShell {
            packages = [self'.formatter] ++ tools;
            LD_LIBRARY_PATH = "${lib.makeLibraryPath runtimeDeps}";
          };
        toolchains = rec {
          msrv = pkgs.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
          stable = pkgs.rust-bin.stable.latest.minimal;
          nightly = pkgs.rust-bin.selectLatestNightlyWith (toolchain: toolchain.minimal);
          rio = msrv;
          default = rio;
        };
        packageFor = rust-toolchain:
          pkgs.callPackage ./pkgRio.nix {inherit rust-toolchain;};
        defaultPackage = packageFor toolchains.default;
        msrvPackage = packageFor toolchains.msrv;
        stablePackage = packageFor toolchains.stable;
        nightlyPackage = packageFor toolchains.nightly;
        appFor = package: {
          type = "app";
          program = "${package}/bin/yazelix-terminal";
        };
      in {
        formatter = pkgs.alejandra;
        _module.args.pkgs = import inputs.nixpkgs {
          inherit system;
          overlays = [(import inputs.rust-overlay)];
        };

        overlayAttrs = {
          yazelix-terminal = self'.packages."yazelix-terminal";
          rio = self'.packages."yazelix-terminal";
        };
        packages = {
          default = defaultPackage;
          yazelix-terminal = defaultPackage;
          rio = defaultPackage;
          yazelix-terminal-msrv = msrvPackage;
          yazelix-terminal-stable = stablePackage;
          yazelix-terminal-nightly = nightlyPackage;
          rio-msrv = msrvPackage;
          rio-stable = stablePackage;
          rio-nightly = nightlyPackage;
        };
        apps = {
          default = appFor self'.packages."yazelix-terminal";
          yazelix-terminal = appFor self'.packages."yazelix-terminal";
          rio = appFor self'.packages.rio;
        };
        checks = {
          package = self'.packages."yazelix-terminal";
          conformance = pkgs.runCommand "yazelix-terminal-conformance" {nativeBuildInputs = [pkgs.python3];} ''
            cd ${./.}
            python3 tools/yazelix_conformance.py verify
            touch "$out"
          '';
        };
        # Different devshells for different rust versions
        devShells = lib.mapAttrs (_: v: mkDevShell v) toolchains;
      };
    };
}
