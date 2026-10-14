import OpenStatCore
import SwiftUI

/// Edits categorical metadata while keeping raw codes separate from presentation labels.
struct CodebookPanel: View {
  @ObservedObject var model: DocumentModel
  @Environment(\.dismiss) private var dismiss
  @State private var levelRows: [CodeRow] = []
  @State private var missingRows: [CodeRow] = []
  @State private var labelRows: [LabelRow] = []

  private var field: Variable? {
    model.dataset?.fields.first { $0.id == model.selectedField }
  }

  private var validationMessage: String? {
    guard let field else { return L.text("codebook.no_selection") }
    let levels = levelRows.map(\.value)
    let missing = missingRows.map(\.value)
    let labelKeys = labelRows.map(\.code)
    if zip(levelRows, levels).contains(where: { !$0.0.isEmpty && $0.1.isEmpty })
      || zip(missingRows, missing).contains(where: { !$0.0.isEmpty && $0.1.isEmpty })
      || labelRows.contains(where: { !$0.isEmpty && $0.code.isEmpty })
    {
      return L.text("codebook.empty_requires_toggle")
    }
    if Set(levels).count != levels.count || Set(missing).count != missing.count
      || Set(labelKeys).count != labelKeys.count
    {
      return L.text("codebook.duplicate")
    }
    if field.measurement == "binary", field.storage != "bool", levels.count != 2 {
      return L.text("codebook.binary_count")
    }
    return nil
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 12) {
      Text(L.text("codebook.title")).font(.title2)
      if let field {
        Text(field.name).font(.headline)
        Text(L.text("codebook.raw_codes"))
          .font(.caption).foregroundStyle(.secondary)
        Form {
          Section(L.text("codebook.levels")) {
            ForEach($levelRows) { $row in
              codeRow(row: $row, rows: levelRows, move: moveLevel, remove: removeLevel)
            }
            Button(L.text("codebook.add_level")) { levelRows.append(CodeRow()) }
              .disabled(levelRows.count >= 1000)
            Text(L.text("codebook.order_note"))
              .font(.caption).foregroundStyle(.secondary)
          }
          Section(L.text("codebook.missing_codes")) {
            ForEach($missingRows) { $row in
              codeRow(row: $row, rows: missingRows, move: nil, remove: removeMissing)
            }
            Button(L.text("codebook.add_missing")) { missingRows.append(CodeRow()) }
              .disabled(missingRows.count >= 1000)
            Text(L.text("codebook.missing_note"))
              .font(.caption).foregroundStyle(.secondary)
          }
          Section(L.text("codebook.value_labels")) {
            ForEach($labelRows) { $row in
              HStack {
                codeEditor(value: $row.code, placeholder: L.text("codebook.code"))
                  .disabled(row.isEmpty)
                Toggle(
                  L.text("codebook.empty_string"),
                  isOn: Binding(
                    get: { row.isEmpty },
                    set: {
                      row.isEmpty = $0
                      if $0 { row.code = "" }
                    }
                  )
                )
                .toggleStyle(.checkbox).fixedSize()
                TextField(L.text("codebook.label"), text: $row.label)
                Button {
                  labelRows.removeAll { $0.id == row.id }
                } label: {
                  Image(systemName: "minus.circle")
                }
                .accessibilityLabel(L.text("codebook.remove_label"))
              }
              if !levelRows.contains(where: { $0.value == row.code }) {
                Text(L.text("codebook.orphan_label"))
                  .font(.caption).foregroundStyle(.secondary)
              }
            }
            Button(L.text("codebook.add_label")) { labelRows.append(LabelRow()) }
              .disabled(labelRows.count >= 1000)
            if field.role == "multiple_response" {
              Text(L.text("codebook.multiple_response_note"))
                .font(.caption).foregroundStyle(.secondary)
            }
          }
        }
        if let validationMessage {
          Text(validationMessage).font(.caption).foregroundStyle(.red)
        }
      } else {
        Text(L.text("codebook.no_selection")).foregroundStyle(.secondary)
      }
      HStack {
        Button(L.text("action.cancel")) { dismiss() }
          .keyboardShortcut(.cancelAction)
        Spacer()
        Button(L.text("codebook.apply")) { apply() }
          .keyboardShortcut(.defaultAction)
          .disabled(model.busy || field == nil || validationMessage != nil)
      }
    }
    .padding(20)
    .frame(width: 600, height: 690)
    .onAppear(perform: loadDraft)
    .onChange(of: model.selectedField) { _, _ in loadDraft() }
    .onChange(of: model.dataset?.revision) { _, _ in loadDraft() }
  }

  private func codeRow(
    row: Binding<CodeRow>, rows: [CodeRow],
    move: ((UUID, Int) -> Void)?, remove: @escaping (UUID) -> Void
  ) -> some View {
    HStack {
      codeEditor(value: row.value, placeholder: L.text("codebook.code"))
        .disabled(row.isEmpty.wrappedValue)
      Toggle(
        L.text("codebook.empty_string"),
        isOn: Binding(
          get: { row.wrappedValue.isEmpty },
          set: {
            row.wrappedValue.isEmpty = $0
            if $0 { row.wrappedValue.value = "" }
          }
        )
      )
      .toggleStyle(.checkbox).fixedSize()
      if let move, let index = rows.firstIndex(where: { $0.id == row.wrappedValue.id }) {
        Button {
          move(row.wrappedValue.id, -1)
        } label: {
          Image(systemName: "arrow.up")
        }
        .disabled(index == 0)
        .accessibilityLabel(L.text("codebook.move_up"))
        Button {
          move(row.wrappedValue.id, 1)
        } label: {
          Image(systemName: "arrow.down")
        }
        .disabled(index == rows.count - 1)
        .accessibilityLabel(L.text("codebook.move_down"))
      }
      Button {
        remove(row.wrappedValue.id)
      } label: {
        Image(systemName: "minus.circle")
      }
      .accessibilityLabel(L.text("codebook.remove_code"))
    }
  }

  private func codeEditor(value: Binding<String>, placeholder: String) -> some View {
    TextField(placeholder, text: value)
  }

  private func loadDraft() {
    guard let field else {
      levelRows = []
      missingRows = []
      labelRows = []
      return
    }
    levelRows = field.levels.map { CodeRow(value: $0) }
    missingRows = field.missingCodes.map { CodeRow(value: $0) }
    labelRows = field.valueLabels.keys.sorted().map {
      LabelRow(code: $0, label: field.valueLabels[$0] ?? "", isEmpty: $0.isEmpty)
    }
  }

  private func moveLevel(_ id: UUID, _ offset: Int) {
    guard let index = levelRows.firstIndex(where: { $0.id == id }) else { return }
    let destination = index + offset
    guard levelRows.indices.contains(destination) else { return }
    levelRows.swapAt(index, destination)
  }

  private func removeLevel(_ id: UUID) { levelRows.removeAll { $0.id == id } }
  private func removeMissing(_ id: UUID) { missingRows.removeAll { $0.id == id } }

  private func apply() {
    guard let field else { return }
    let labels = Dictionary(uniqueKeysWithValues: labelRows.map { ($0.code, $0.label) })
    model.updateCodebook(
      fieldID: field.id,
      levels: levelRows.map(\.value),
      missingCodes: missingRows.map(\.value),
      labels: labels
    )
    dismiss()
  }
}

private struct CodeRow: Identifiable {
  let id = UUID()
  var value: String
  var isEmpty: Bool

  init(value: String = "", isEmpty: Bool = false) {
    self.value = value
    self.isEmpty = isEmpty
  }
}

private struct LabelRow: Identifiable {
  let id = UUID()
  var code: String
  var label: String
  var isEmpty: Bool

  init(code: String = "", label: String = "", isEmpty: Bool = false) {
    self.code = code
    self.label = label
    self.isEmpty = isEmpty
  }
}
