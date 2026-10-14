import OpenStatCore
import SwiftUI

/// Native controls build typed parameters rather than exposing executable formulas.
struct ColumnOperationsPanel: View {
  @ObservedObject var model: DocumentModel
  @Environment(\.dismiss) private var dismiss
  @State private var operation = "rank"
  @State private var sourceID = ""
  @State private var outputName = ""
  @State private var includeMissingCodes = false
  @State private var ties = "average"
  @State private var ascending = true
  @State private var direction = "lag"
  @State private var steps = 1
  @State private var ddof = 1
  @State private var duplicateIDs = Set<String>()
  @State private var keep = "first"
  @State private var unmatched = "keep"
  @State private var outputStorage = "same"
  @State private var recodes = [RecodeEntry()]
  @State private var arithmetic = "add"
  @State private var leftKind = "field"
  @State private var leftConstant = "0"
  @State private var rightKind = "constant"
  @State private var rightID = ""
  @State private var rightConstant = "1"

  private let operations = ["recode", "compute", "rank", "lag", "standardize", "duplicates"]
  private let storages = ["float64", "int64", "string", "bool"]
  private var fields: [Variable] { model.dataset?.fields ?? [] }
  private var numericFields: [Variable] {
    fields.filter { ["float64", "int64"].contains($0.storage) }
  }
  private var sources: [Variable] {
    if ["compute", "rank", "standardize"].contains(operation) { return numericFields }
    if operation == "recode" { return fields.filter { $0.storage != "multiple_response" } }
    return fields
  }
  private var source: Variable? { fields.first { $0.id == sourceID } }
  private var isUnary: Bool { ["negate", "abs", "sqrt", "log", "exp"].contains(arithmetic) }
  private var isGlobal: Bool { ["rank", "lag", "standardize", "duplicates"].contains(operation) }
  private var exceedsLimit: Bool { isGlobal && (model.dataset?.rowCount ?? 0) > 100_000 }

  var body: some View {
    VStack(alignment: .leading, spacing: 16) {
      Text(L.text("columns.title")).font(.title2)
      Text(L.text("columns.immutable")).font(.caption).foregroundStyle(.secondary)
      Form {
        Picker(L.text("columns.operation"), selection: $operation) {
          ForEach(operations, id: \.self) { Text(L.text("columns.operation.\($0)")).tag($0) }
        }
        TextField(L.text("columns.output_name"), text: $outputName)
        if operation != "duplicates" && !(operation == "compute" && leftKind == "constant") {
          Picker(L.text("columns.source"), selection: $sourceID) {
            Text(L.text("columns.choose")).tag("")
            ForEach(sources) { Text($0.name).tag($0.id) }
          }
        }
        operationOptions
        if operation != "duplicates" {
          Toggle(L.text("columns.include_missing"), isOn: $includeMissingCodes)
          Text(L.text("columns.missing_policy")).font(.caption).foregroundStyle(.secondary)
        }
        if isGlobal {
          Text(L.text("columns.global_limit")).font(.caption)
            .foregroundStyle(exceedsLimit ? Color.red : Color.secondary)
        }
        if parameters == nil {
          Text(L.text("columns.invalid_input")).font(.caption).foregroundStyle(.secondary)
        }
      }.formStyle(.grouped)
      HStack {
        Button(L.text("action.cancel")) { dismiss() }.keyboardShortcut(.cancelAction)
        Spacer()
        Button(L.text("columns.apply")) { apply() }
          .keyboardShortcut(.defaultAction)
          .disabled(model.busy || exceedsLimit || parameters == nil)
      }
    }
    .padding(22)
    .frame(width: 620, height: 640)
    .onAppear {
      outputName = L.text("columns.default_name")
      resetSources()
    }
    .onChange(of: operation) { _, _ in resetSources() }
    .onChange(of: model.dataset?.revision) { _, _ in resetSources() }
  }

  @ViewBuilder private var operationOptions: some View {
    switch operation {
    case "recode": recodeOptions
    case "compute": computeOptions
    case "rank":
      Picker(L.text("columns.ties"), selection: $ties) {
        ForEach(["average", "min", "max", "dense", "first"], id: \.self) {
          Text(L.text("columns.ties.\($0)")).tag($0)
        }
      }
      Toggle(L.text("columns.ascending"), isOn: $ascending)
    case "lag":
      Picker(L.text("columns.direction"), selection: $direction) {
        Text(L.text("columns.lag")).tag("lag")
        Text(L.text("columns.lead")).tag("lead")
      }
      Stepper(L.format("columns.steps", steps), value: $steps, in: 1...100_000)
      Text(L.text("columns.row_order")).font(.caption).foregroundStyle(.secondary)
    case "standardize":
      Picker(L.text("columns.divisor"), selection: $ddof) {
        Text(L.text("columns.sample_sd")).tag(1)
        Text(L.text("columns.population_sd")).tag(0)
      }
      Text(L.text("columns.standardize_note")).font(.caption).foregroundStyle(.secondary)
    case "duplicates": duplicateOptions
    default: EmptyView()
    }
  }

  private var recodeOptions: some View {
    VStack(alignment: .leading, spacing: 10) {
      Picker(L.text("columns.output_type"), selection: $outputStorage) {
        Text(L.text("columns.same_type")).tag("same")
        ForEach(storages, id: \.self) { Text(L.text("storage.\($0)")).tag($0) }
      }
      ForEach($recodes) { $entry in
        HStack {
          TextField(L.text("columns.from"), text: $entry.before)
          TextField(L.text("columns.to"), text: $entry.after).disabled(entry.isNull)
          Toggle(L.text("columns.to_missing"), isOn: $entry.isNull).toggleStyle(.checkbox)
          Button {
            recodes.removeAll { $0.id == entry.id }
          } label: {
            Image(systemName: "minus.circle")
          }.accessibilityLabel(L.text("columns.remove_mapping")).disabled(recodes.count == 1)
        }
      }
      Button(L.text("columns.add_mapping")) { recodes.append(RecodeEntry()) }
        .disabled(recodes.count >= 1000)
      Picker(L.text("columns.unmatched"), selection: $unmatched) {
        Text(L.text("columns.unmatched.keep")).tag("keep")
        Text(L.text("columns.unmatched.null")).tag("null")
      }
      Text(L.text("columns.recode_note")).font(.caption).foregroundStyle(.secondary)
      if source?.storage == "bool" || outputStorage == "bool" {
        Text(L.text("columns.boolean_input")).font(.caption).foregroundStyle(.secondary)
      }
    }
  }

  private var computeOptions: some View {
    VStack(alignment: .leading, spacing: 10) {
      Picker(L.text("columns.arithmetic"), selection: $arithmetic) {
        ForEach(
          ["add", "subtract", "multiply", "divide", "negate", "abs", "sqrt", "log", "exp"],
          id: \.self
        ) {
          Text(L.text("columns.arithmetic.\($0)")).tag($0)
        }
      }
      Picker(L.text("columns.left_operand"), selection: $leftKind) {
        Text(L.text("columns.variable")).tag("field")
        Text(L.text("columns.constant")).tag("constant")
      }
      if leftKind == "constant" {
        TextField(L.text("columns.constant_value"), text: $leftConstant)
      }
      if !isUnary {
        Picker(L.text("columns.right_operand"), selection: $rightKind) {
          Text(L.text("columns.variable")).tag("field")
          Text(L.text("columns.constant")).tag("constant")
        }
        if rightKind == "field" {
          Picker(L.text("columns.right_variable"), selection: $rightID) {
            Text(L.text("columns.choose")).tag("")
            ForEach(numericFields) { Text($0.name).tag($0.id) }
          }
        } else {
          TextField(L.text("columns.constant_value"), text: $rightConstant)
        }
      }
      Text(L.text("columns.compute_note")).font(.caption).foregroundStyle(.secondary)
    }
  }

  private var duplicateOptions: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(L.text("columns.compare_fields"))
      ForEach(fields) { field in
        Toggle(
          field.name,
          isOn: Binding(
            get: { duplicateIDs.contains(field.id) },
            set: { selected in
              if selected { duplicateIDs.insert(field.id) } else { duplicateIDs.remove(field.id) }
            }
          )
        ).toggleStyle(.checkbox)
      }
      Picker(L.text("columns.keep"), selection: $keep) {
        ForEach(["first", "last", "none"], id: \.self) {
          Text(L.text("columns.keep.\($0)")).tag($0)
        }
      }
      Text(L.text("columns.duplicates_note")).font(.caption).foregroundStyle(.secondary)
    }
  }

  private func resetSources() {
    if !sources.contains(where: { $0.id == sourceID }) {
      sourceID = sources.first?.id ?? ""
    }
    if !numericFields.contains(where: { $0.id == rightID }) {
      rightID = numericFields.first?.id ?? ""
    }
    duplicateIDs.formIntersection(fields.map(\.id))
    if duplicateIDs.isEmpty, let first = fields.first { duplicateIDs.insert(first.id) }
  }

  private func operand(kind: String, field: String, literal: String) -> JSONValue? {
    if kind == "field" {
      guard numericFields.contains(where: { $0.id == field }) else { return nil }
      return .object(["field": .string(field)])
    }
    guard let value = try? CellParser.parse(literal, storage: "float64", locale: .current),
      value != .null
    else { return nil }
    return .object(["constant": value])
  }

  private var parameters: [String: JSONValue]? {
    let name = outputName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !name.isEmpty, !name.hasPrefix("_openstat_"), !fields.contains(where: { $0.name == name })
    else { return nil }
    var result: [String: JSONValue] = ["name": .string(name)]
    if operation != "duplicates" { result["include_missing_codes"] = .bool(includeMissingCodes) }
    if operation == "duplicates" {
      guard !duplicateIDs.isEmpty else { return nil }
      result["fields"] = .array(
        fields.filter { duplicateIDs.contains($0.id) }.map { .string($0.id) })
      result["keep"] = .string(keep)
      return result
    }
    if operation == "compute" {
      guard let left = operand(kind: leftKind, field: sourceID, literal: leftConstant) else {
        return nil
      }
      var operands = [left]
      if !isUnary {
        guard let right = operand(kind: rightKind, field: rightID, literal: rightConstant) else {
          return nil
        }
        operands.append(right)
      }
      result["expression"] = .object(["op": .string(arithmetic), "args": .array(operands)])
      return result
    }
    guard let source, sources.contains(where: { $0.id == source.id }) else { return nil }
    result["field"] = .string(source.id)
    switch operation {
    case "recode":
      let storage = outputStorage == "same" ? source.storage : outputStorage
      var mapping: [JSONValue] = []
      var seen: [JSONValue] = []
      for entry in recodes {
        guard
          let before = try? CellParser.parse(
            entry.before, storage: source.storage, locale: .current),
          before != .null, !seen.contains(before)
        else { return nil }
        let after: JSONValue
        if entry.isNull {
          after = .null
        } else {
          guard let parsed = try? CellParser.parse(entry.after, storage: storage, locale: .current),
            parsed != .null
          else { return nil }
          after = parsed
        }
        seen.append(before)
        mapping.append(.object(["from": before, "to": after]))
      }
      result["mapping"] = .array(mapping)
      result["unmatched"] = .string(unmatched)
      if outputStorage != "same" { result["storage"] = .string(outputStorage) }
    case "rank":
      result["ties"] = .string(ties)
      result["ascending"] = .bool(ascending)
    case "lag":
      result["steps"] = .integer(Int64(steps))
      result["direction"] = .string(direction)
    case "standardize": result["ddof"] = .integer(Int64(ddof))
    default: return nil
    }
    return result
  }

  private func apply() {
    guard let parameters, !exceedsLimit, !model.busy else { return }
    model.transform(method: "columns.\(operation)", parameters: parameters)
    dismiss()
  }
}

private struct RecodeEntry: Identifiable {
  let id = UUID()
  var before = ""
  var after = ""
  var isNull = false
}
