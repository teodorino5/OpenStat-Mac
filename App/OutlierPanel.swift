import OpenStatCore
import SwiftUI

/// Creates a categorical outlier flag from one numeric characteristic variable.
struct OutlierPanel: View {
  @ObservedObject var model: DocumentModel
  @Environment(\.dismiss) private var dismiss
  @State private var sourceID = ""
  @State private var outputName = ""
  @State private var innerText = "1.5"
  @State private var outerText = "3"
  @State private var includeMissingCodes = false

  private var fields: [Variable] { model.dataset?.fields ?? [] }
  private var eligibleFields: [Variable] {
    fields.filter { ["int64", "float64"].contains($0.storage) && $0.role == "characteristic" }
  }
  private var source: Variable? { eligibleFields.first { $0.id == sourceID } }
  private var exceedsLimit: Bool { (model.dataset?.rowCount ?? 0) > 100_000 }

  var body: some View {
    VStack(alignment: .leading, spacing: 14) {
      Text(L.text("outliers.title")).font(.title2)
      Text(L.text("outliers.method")).font(.caption).foregroundStyle(.secondary)
      Form {
        Picker(L.text("outliers.source"), selection: $sourceID) {
          Text(L.text("outliers.choose")).tag("")
          ForEach(eligibleFields) { field in Text(field.name).tag(field.id) }
        }
        TextField(L.text("outliers.output_name"), text: $outputName)
        TextField(L.text("outliers.inner"), text: $innerText)
        TextField(L.text("outliers.outer"), text: $outerText)
        Toggle(L.text("outliers.include_missing_codes"), isOn: $includeMissingCodes)
        if includeMissingCodes {
          Text(L.text("outliers.missing_warning"))
            .font(.caption).foregroundStyle(.orange)
        }
      }.formStyle(.grouped)

      Text(L.text("outliers.strict_note")).font(.caption).foregroundStyle(.secondary)
      Text(L.text("outliers.severity_note")).font(.caption).foregroundStyle(.secondary)
      Text(L.text("outliers.open_ended_note")).font(.caption).foregroundStyle(.secondary)
      if eligibleFields.isEmpty {
        Text(L.text("outliers.no_source")).font(.caption).foregroundStyle(.secondary)
      }
      if exceedsLimit {
        Text(L.text("outliers.global_limit")).font(.caption).foregroundStyle(.red)
      }
      if parameters == nil {
        Text(L.text("outliers.invalid_input")).font(.caption).foregroundStyle(.secondary)
      }

      HStack {
        Button(L.text("action.cancel")) { dismiss() }.keyboardShortcut(.cancelAction)
        Spacer()
        Button(L.text("outliers.apply"), action: apply)
          .keyboardShortcut(.defaultAction)
          .disabled(model.busy || exceedsLimit || parameters == nil)
      }
    }
    .padding(22)
    .frame(width: 620, height: 570)
    .onAppear {
      outputName = L.text("outliers.default_name")
      resetSource()
    }
    .onChange(of: model.dataset?.revision) { _, _ in resetSource() }
  }

  private func resetSource() {
    if !eligibleFields.contains(where: { $0.id == sourceID }) {
      sourceID = eligibleFields.first?.id ?? ""
    }
  }

  private func multiplier(_ text: String) -> Double? {
    guard let value = try? CellParser.parse(text, storage: "float64", locale: .current),
      case .number(let number) = value, number.isFinite, number >= 0
    else { return nil }
    return number
  }

  private var parameters: [String: JSONValue]? {
    let name = outputName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard let source,
      !name.isEmpty,
      !name.hasPrefix("_openstat_"),
      !fields.contains(where: { $0.name == name }),
      let inner = multiplier(innerText),
      let outer = multiplier(outerText),
      outer >= inner
    else { return nil }
    return [
      "field": .string(source.id),
      "name": .string(name),
      "inner": .number(inner),
      "outer": .number(outer),
      "include_missing_codes": .bool(includeMissingCodes),
    ]
  }

  private func apply() {
    guard let parameters, !model.busy, !exceedsLimit else { return }
    model.transform(method: "columns.outliers", parameters: parameters)
    dismiss()
  }
}
