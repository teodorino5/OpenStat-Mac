# Contributing

Install Swift 5.9 or later, the macOS 14 or later SDK, and uv. Full Xcode is required for XCTest and UI tests; Command Line Tools can build the application and run the integration smoke check.

Run `make setup`, `make check`, and `make test`. Work on one Phase 0 slice at a time. State the public method, feature ID, assumptions and test evidence in a pull request. Use Conventional Commits and small changes. Preserve original samples and numerical references separately. Expected reference values need independent provenance.

Original contributions use the MIT license. Do not submit copied proprietary documentation or assets, or dependencies with unreviewed licensing. Read AGENTS.md and docs/ADD_ANALYSIS.md before extending the engine. Statistical modules remain gated until all Phase 0 functions are verified.
