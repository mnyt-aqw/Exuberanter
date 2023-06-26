{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    (python3.withPackages (p: with p; [
      babel
      jinja2
    ]))
    j2cli
    wine
    nodejs
    go
  ];
}
