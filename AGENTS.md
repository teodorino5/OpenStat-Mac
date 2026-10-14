# Contributor instructions

This is an original MIT-licensed macOS statistics application. Use public statistical methods and permissive dependencies only. Never introduce proprietary vendor code, help passages, sample datasets, screenshots, icons or internal file formats. Do not bundle copyleft components. Audit exact runtime and wheel contents before distribution; top-level package licenses are insufficient.

Swift owns document/UI state; Python owns immutable typed data revisions and numerical methods. Communication uses private Content-Length-framed JSON-RPC pipes. Never print logs on protocol stdout. Field IDs and row IDs remain stable. Missing values and user-coded missing categories stay distinguishable. Persist full precision and explicitly label numerical conventions. Do not run arbitrary formulas or project code on file open.

Complete Phase 0 before implementing Phase 1 statistics. Later phases follow the same gate. Do not delete unfinished features to improve coverage. Update docs/feature_catalog.json, then run scripts/feature_matrix.py --write. Implemented claims require executed acceptance tests. Verified claims require independently sourced fixtures actually loaded by passing tests. Never generate expected values using the method under test. Unknown evidence stays unknown.

Run make check for available local checks. Run make test with full Xcode for XCTest. The Command Line Tools smoke executable does not replace XCTest/UI tests. Report unavailable checks explicitly. Run the complete applicable suite after each feature slice and commit with Conventional Commits.

Author all visible UI text through App/Resources/Localizable.xcstrings, including errors and accessibility labels. Generate contributor .strings resources with scripts/localization.py. English and Czech are required. Never parse localized presentation strings as protocol data.

Developer ID is unavailable. Contributor builds use ad-hoc signatures and require this checkout's Python environment. Do not describe them as notarized, portable or release-ready. A separately audited embedded runtime, both architecture tests and clean-system launch are required for distributable builds. No GitHub release or external publication occurs merely because local code is ready.

Use normal prose in source comments, docs, commits and PR descriptions. Chat brevity does not change repository writing style. Do not delegate to subagents unless the user explicitly requests delegation. Preserve manual files and source data. Never log source data or credentials by default.
