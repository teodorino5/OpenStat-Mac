# Localization

App/Resources/Localizable.xcstrings is the authoritative English/Czech catalog. The contributor script compiles it into .strings files because Command Line Tools do not include Xcode's String Catalog compiler. Generated files are ignored by Git; Xcode compiles the same catalog directly.

The current app selects Czech when the preferred macOS language begins with `cs`, otherwise English. A dedicated app-language switch is pending. Native self-checks verify real localized labels in both languages. Engine errors are stable keys, with no copied help text.

Storage, field IDs and JSON numbers are locale-independent. Native cell parsing accepts Czech decimal comma and rejects nonfinite numbers. Multiple-response cells use explicit JSON arrays. Menus, controls, alerts and cell accessibility labels come from the catalog. Native system dialogs are localized by macOS.
