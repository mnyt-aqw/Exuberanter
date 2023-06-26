{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (p: with p; [
      biopython
      xmltodict
      tkinter
      pymupdf
      pillow
      html2text
      levenshtein
      opencv4
      pytesseract
      openai
      bottle
      (
        buildPythonPackage rec {
          pname = "customtkinter";
          version = "5.1.2";
          src = fetchPypi {
            inherit pname version;
            sha256 = "sha256-7tqhHtzna2iCpgWGShG0hZZDug9PRWhBqtUdiadY0yw=";
          };
          doCheck = false;
          format = "pyproject";
          propagatedBuildInputs = [
            typing-extensions
            (buildPythonPackage rec {
              pname = "darkdetect";
              version = "0.8.0";
              src = fetchPypi {
                inherit pname version;
                sha256 = "sha256-tUKOEXAmPrXepEwl3DiV7ddeb1IwCYY1PNY1M/59+LE=";
              };
              format = "pyproject";
              propagatedBuildInputs = [
                setuptools
              ];
            })
          ];
        }
      )
    ]))
  ];
}
