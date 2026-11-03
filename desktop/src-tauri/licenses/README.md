# Packaged runtime license texts

`desktop/scripts/build_license_bundle.py` generates full runtime LICENSE, copyright and NOTICE
texts here: installed Python dependencies (including Pillow's bundled-library credits), PyInstaller
runtime support, the Python interpreter, production Node packages and the native Cargo graph.
`INDEX.md` and `manifest.json` record versions, source
provenance and SHA-256 values. Tauri copies this directory into its application resources.

Generated platform-specific files are not committed. Only reviewed version-pinned source overrides
for packages that omit their full license texts are committed under `assets/licenses/`.
The Core build and CI verify inventory and hashes; a missing license is a packaging failure.
