# Reviewed upstream attribution files

These files are preserved verbatim because their exact Cargo releases omit full license files.
`provenance.json` records the package/version, published `.cargo_vcs_info.json` commit,
official source URL, source revision, and SHA256. The offline collector rejects changed hashes or
crate revisions. This directory is not a legal interpretation or an invented copyright notice.

Most files come from the crate's upstream repository at its published commit. The `objc2` family
provides a referral-only `LICENSE.md`; its text (including the upstream SDK discussion) is retained,
along with separately labelled canonical license terms from the official SPDX license-list-data
repository at a pinned commit. `selectors` refers to MPL-2.0 in its source header, so the small
upstream `lib.rs` notice is preserved unchanged together with the full canonical MPL-2.0 terms.
`siphasher` supplies a `COPYING` copyright/referral notice without the linked MIT/Apache texts;
the copyright notice is retained verbatim and those full canonical terms are supplied separately.
Canonical reference texts supplement the supplied upstream notices; they do not invent missing
copyright holders or assert that every distribution obligation has been legally adjudicated.

The `libappindicator-sys` Cargo metadata lacks a repository URL. Its exact published VCS commit
is verified in `tauri-apps/libappindicator-rs`; the preserved MIT/Apache files come from that commit.
Published source code remains addressable through each package's exact crates.io version URL in
the generated manifest. No user filesystem paths are included in the distributable manifest.

When a dependency version changes, review the new published crate's notices and VCS commit.
If it still omits full text, retrieve only its applicable upstream attribution files, preserve raw
bytes, and update the version/commit/hash provenance. Builds never fetch legal text from the network.
