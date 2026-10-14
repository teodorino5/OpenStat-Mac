# Security policy

This is an early contributor build, not a production release. It contains no remote telemetry service. Private process pipes carry local data between the app and Python. Third-party plugins and arbitrary Python expressions are not enabled.

Report vulnerabilities through GitHub private vulnerability reporting when the public repository enables it. Do not include private datasets, secrets or exploit details in public issues. A dedicated contact is pending repository publication. There is no public security inbox yet.

Opening a native project verifies package-relative paths, schema and data checksums. Untrusted project validation remains under active development. Contributor app bundles use this checkout's Python environment and ad-hoc signatures; they are not notarized or standalone. Do not disable Gatekeeper globally.
