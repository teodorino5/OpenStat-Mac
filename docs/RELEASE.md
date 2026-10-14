# Release status

There is no portable app or release DMG yet. The public source repository is https://github.com/teodorino5/OpenStat-Mac. A source upload does not establish binary release readiness; no release DMG or successful public CI execution is claimed.

`make package` creates a local contributor app, ad-hoc signs it and verifies that signature. The app's development-runtime.json intentionally references this checkout's Python environment. Moving the app without its checkout is unsupported. The source-release workflow creates a source archive only; it never presents this developer app as a distributable artifact.

Developer ID is unavailable. Initial future distribution will offer source and reviewed unsigned/ad-hoc architecture-specific builds. Open-source hosting does not remove Gatekeeper checks. Document and test Apple's per-app Privacy & Security → Open Anyway workflow for trusted downloaded builds rather than disabling Gatekeeper globally.

Before app/DMG distribution: resolve an exact license-clean Python runtime; audit every native component and wheel; remove absolute runtime paths; validate relocation and app translocation; execute clean-system tests on arm64 and Intel; measure exact app/DMG bytes. Preserve full required component notices. The current top-level pyarrow license check is not clearance of all wheel/runtime components.

Future Developer ID signing must sign nested native code inside out with secure timestamps and hardened runtime, then use notarytool, inspect logs, staple and validate. Signing/notarization is deferred by user choice; it is not falsely marked passed. Secret placeholders remain comments in the workflow. Sparkle/Homebrew and App Store distribution are not implemented.
