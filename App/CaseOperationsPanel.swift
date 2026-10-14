import OpenStatCore
import SwiftUI

private struct PredicateDraft: Identifiable {
  let id = UUID()
  var field = ""
  var operation = "eq"
  var value = ""
}

private struct SortDraft: Identifiable {
  let id = UUID()
  var field = ""
  var ascending = true
}

/// Builds typed predicates and explicit sort and weight requests.
struct CaseOperationsPanel: View {
  @ObservedObject var model: DocumentModel
  @State private var operation = "filter"
  @State private var predicates = [PredicateDraft()]
  @State private var combination = "and"
  @State private var sorts = [SortDraft()]
  @State private var nulls = "last"
  @State private var weightField = ""
  @State private var weightKind = "frequency"
  @State private var validationKey: String?
  @State private var requestSignature = ""

  private var fields: [Variable] { model.dataset?.fields ?? [] }
  private var numericFields: [Variable] {
    fields.filter {
      ["int64", "float64"].contains($0.storage) && $0.role != "identifier"
    }
  }
  private var dataset: Dataset? { model.dataset }

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 14) {
        Text(L.text("cases.title")).font(.headline)
        Picker(L.text("cases.operation"), selection: $operation) {
          ForEach(["filter", "select", "sort", "weights"], id: \.self) {
            Text(L.text("cases.operation.\($0)")).tag($0)
          }
        }.pickerStyle(.segmented)

        if operation == "filter" || operation == "select" {
          predicateEditor
          Button(L.text(operation == "filter" ? "cases.apply_filter" : "cases.preview_selection")) {
            runPredicate()
          }
          .disabled(model.busy || predicateParameters == nil)
          if predicateParameters == nil {
            Text(L.text("cases.invalid_predicate")).font(.caption).foregroundStyle(.red)
          }
          if operation == "select" { selectionReport }
          Text(L.text("cases.predicate_note")).font(.caption).foregroundStyle(.secondary)
        } else if operation == "sort" {
          sortEditor
          Button(L.text("cases.apply_sort")) { runSort() }
            .disabled(model.busy || sortParameters == nil)
          if sortParameters == nil {
            Text(L.text("cases.invalid_sort")).font(.caption).foregroundStyle(.red)
          }
          Text(L.text("cases.ordinal_note")).font(.caption).foregroundStyle(.secondary)
        } else {
          weightEditor
          Button(L.text("cases.inspect_weights")) { runWeights() }
            .disabled(model.busy || weightFieldValue == nil)
          if weightFieldValue == nil {
            Text(L.text("cases.invalid_weight")).font(.caption).foregroundStyle(.red)
          }
          weightReport
        }
        if let validationKey {
          Text(L.text(validationKey)).font(.caption).foregroundStyle(.red)
        }
      }
      .padding(18)
      .disabled(model.busy)
    }
    .onAppear(perform: resetFields)
    .onChange(of: operation) { _, _ in
      validationKey = nil
      requestSignature = ""
      resetFields()
    }
    .onChange(of: model.dataset?.revision) { _, _ in
      requestSignature = ""
      resetFields()
    }
  }

  private var predicateEditor: some View {
    VStack(alignment: .leading, spacing: 10) {
      ForEach($predicates) { $entry in
        VStack(alignment: .leading, spacing: 8) {
          Picker(L.text("cases.field"), selection: $entry.field) {
            Text(L.text("cases.choose_field")).tag("")
            ForEach(fields) { Text($0.name).tag($0.id) }
          }
          if let field = fields.first(where: { $0.id == entry.field }) {
            Picker(L.text("cases.condition"), selection: $entry.operation) {
              ForEach(operations(for: field), id: \.self) {
                Text(L.text("cases.operator.\($0)")).tag($0)
              }
            }
            .onChange(of: entry.field) { _, _ in
              guard let index = predicates.firstIndex(where: { $0.id == entry.id }),
                let selected = fields.first(where: { $0.id == predicates[index].field })
              else { return }
              if !operations(for: selected).contains(predicates[index].operation) {
                predicates[index].operation = operations(for: selected).first ?? "eq"
              }
            }
            if takesValue(entry.operation, field: field) {
              TextField(L.text("cases.value"), text: $entry.value)
            }
          }
          Button(L.text("cases.remove_condition")) {
            predicates.removeAll { $0.id == entry.id }
          }.disabled(predicates.count <= 1)
        }
        .padding(10)
        .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
      }
      Button(L.text("cases.add_condition")) {
        predicates.append(PredicateDraft(field: fields.first?.id ?? ""))
      }.disabled(predicates.count >= 16)
      if predicates.count > 1 {
        Picker(L.text("cases.combine"), selection: $combination) {
          Text(L.text("cases.and")).tag("and")
          Text(L.text("cases.or")).tag("or")
        }.pickerStyle(.segmented)
      }
    }
  }

  private var sortEditor: some View {
    VStack(alignment: .leading, spacing: 10) {
      ForEach($sorts) { $entry in
        HStack {
          Picker(L.text("cases.sort_field"), selection: $entry.field) {
            Text(L.text("cases.choose_field")).tag("")
            ForEach(fields.filter { $0.storage != "multiple_response" }) {
              Text($0.name).tag($0.id)
            }
          }
          Picker(L.text("cases.direction"), selection: $entry.ascending) {
            Text(L.text("cases.ascending")).tag(true)
            Text(L.text("cases.descending")).tag(false)
          }
          Button(L.text("cases.remove_sort")) { sorts.removeAll { $0.id == entry.id } }
            .disabled(sorts.count <= 1)
        }
      }
      Button(L.text("cases.add_sort")) {
        sorts.append(SortDraft(field: sortableFields.first?.id ?? ""))
      }.disabled(sorts.count >= sortableFields.count || sorts.count >= 16)
      Picker(L.text("cases.missing_placement"), selection: $nulls) {
        Text(L.text("cases.missing_first")).tag("first")
        Text(L.text("cases.missing_last")).tag("last")
      }
      Text(L.text("cases.sort_note")).font(.caption).foregroundStyle(.secondary)
    }
  }

  private var weightEditor: some View {
    VStack(alignment: .leading, spacing: 10) {
      Picker(L.text("cases.weight_field"), selection: $weightField) {
        Text(L.text("cases.choose_field")).tag("")
        ForEach(numericFields) { Text($0.name).tag($0.id) }
      }
      Picker(L.text("cases.weight_kind"), selection: $weightKind) {
        Text(L.text("cases.frequency")).tag("frequency")
        Text(L.text("cases.analytic")).tag("analytic")
      }.pickerStyle(.segmented)
      Text(L.text(weightKind == "frequency" ? "cases.frequency_note" : "cases.analytic_note"))
        .font(.caption).foregroundStyle(.secondary)
    }
  }

  private var selectionReport: some View {
    Group {
      if let summary = currentSelectionSummary {
        let value = summary.object
        Divider()
        Text(L.text("cases.selection_result")).font(.subheadline.bold())
        Text(L.format("cases.selected_count", value["selected"]?.int ?? 0))
        Text(L.format("cases.false_count", value["false"]?.int ?? 0))
        Text(L.format("cases.unknown_count", value["unknown"]?.int ?? 0))
        Text(L.format("cases.total_count", value["total"]?.int ?? 0))
      }
    }
  }

  private var weightReport: some View {
    Group {
      if let summary = currentWeightSummary {
        let value = summary.object
        Divider()
        Text(L.text("cases.weight_result")).font(.subheadline.bold())
        Text(L.format("cases.eligible_count", value["eligible"]?.int ?? 0))
        Text(L.format("cases.missing_count", value["missing"]?.int ?? 0))
        Text(L.format("cases.zero_count", value["zero"]?.int ?? 0))
        Text(
          L.format(
            "cases.total_weight",
            value["total_weight_exact"]?.string ?? localizedNumber(value["total_weight"])))
      }
    }
  }

  private var currentSummary: JSONValue? {
    guard let summary = model.summary,
      summary.object["revision"]?.string == dataset?.revision
    else { return nil }
    return summary
  }

  private var currentSelectionSummary: JSONValue? {
    guard operation == "select", requestSignature.hasPrefix("select|"),
      let summary = currentSummary,
      summary.object["condition"] == predicateParameters?["condition"]
    else { return nil }
    return summary
  }

  private var currentWeightSummary: JSONValue? {
    guard operation == "weights", requestSignature.hasPrefix("weights|"),
      let summary = currentSummary,
      summary.object["field"]?.string == weightField,
      summary.object["kind"]?.string == weightKind
    else { return nil }
    return summary
  }

  private var sortableFields: [Variable] {
    fields.filter { $0.storage != "multiple_response" }
  }

  private var weightFieldValue: Variable? {
    numericFields.first { $0.id == weightField }
  }

  private var predicateParameters: [String: JSONValue]? {
    guard !predicates.isEmpty, let terms = try? predicates.map(predicate) else { return nil }
    let condition: JSONValue
    if terms.count == 1 {
      condition = terms[0]
    } else {
      condition = .object(["op": .string(combination), "args": .array(terms)])
    }
    return ["condition": condition]
  }

  private var sortParameters: [String: JSONValue]? {
    let identifiers = sorts.map(\.field)
    guard !sorts.isEmpty, Set(identifiers).count == identifiers.count,
      sorts.allSatisfy({ entry in sortableFields.contains(where: { $0.id == entry.field }) })
    else { return nil }
    return [
      "keys": .array(
        sorts.map {
          .object(["field": .string($0.field), "ascending": .bool($0.ascending)])
        }),
      "nulls": .string(nulls),
    ]
  }

  private func operations(for field: Variable) -> [String] {
    var values = ["is_null", "is_coded_missing", "is_missing"]
    if field.storage == "multiple_response" {
      values.append("contains")
    } else {
      values += ["eq", "ne"]
      if ["int64", "float64"].contains(field.storage)
        || (field.measurement == "ordinal" && !field.levels.isEmpty)
      {
        values += ["lt", "le", "gt", "ge"]
      }
    }
    return values
  }

  private func takesValue(_ operation: String, field: Variable) -> Bool {
    operation == "contains"
      || (field.storage != "multiple_response"
        && !["is_null", "is_coded_missing", "is_missing"].contains(operation))
  }

  private func predicate(_ entry: PredicateDraft) throws -> JSONValue {
    guard let field = fields.first(where: { $0.id == entry.field }),
      operations(for: field).contains(entry.operation)
    else { throw CaseInputError.invalid }
    var spec: [String: JSONValue] = ["field": .string(field.id), "op": .string(entry.operation)]
    if takesValue(entry.operation, field: field) {
      let value: JSONValue
      if entry.operation == "contains" || (field.storage == "string" && entry.value.isEmpty) {
        value = .string(entry.value)
      } else {
        do {
          value = try CellParser.parse(entry.value, storage: field.storage, locale: .current)
        } catch { throw CaseInputError.invalid }
      }
      guard value != .null else { throw CaseInputError.invalid }
      spec["value"] = value
    }
    return .object(spec)
  }

  private func resetFields() {
    if !fields.contains(where: { $0.id == predicates[0].field }) {
      predicates[0].field = fields.first?.id ?? ""
    }
    for index in predicates.indices {
      guard let field = fields.first(where: { $0.id == predicates[index].field }) else { continue }
      if !operations(for: field).contains(predicates[index].operation) {
        predicates[index].operation = operations(for: field).first ?? "eq"
      }
    }
    let validSorts = sortableFields.map(\.id)
    for index in sorts.indices where !validSorts.contains(sorts[index].field) {
      sorts[index].field = validSorts.first ?? ""
    }
    if !numericFields.contains(where: { $0.id == weightField }) {
      weightField = numericFields.first?.id ?? ""
    }
  }

  private func runPredicate() {
    guard let parameters = predicateParameters else {
      validationKey = "cases.invalid_predicate"
      return
    }
    validationKey = nil
    if operation == "select" {
      requestSignature = "select|pending"
      model.inspect(method: "dataset.select", parameters: parameters)
    } else {
      model.transform(method: "dataset.filter", parameters: parameters)
    }
  }

  private func runSort() {
    guard let parameters = sortParameters else {
      validationKey = "cases.invalid_sort"
      return
    }
    validationKey = nil
    model.transform(method: "dataset.sort", parameters: parameters)
  }

  private func runWeights() {
    guard let field = weightFieldValue else {
      validationKey = "cases.invalid_weight"
      return
    }
    validationKey = nil
    requestSignature = "weights|\(field.id)|\(weightKind)"
    model.inspect(
      method: "dataset.weights",
      parameters: ["field": .string(field.id), "kind": .string(weightKind)])
  }

  private func localizedNumber(_ value: JSONValue?) -> String {
    let number: Double
    switch value {
    case .number(let value): number = value
    case .integer(let value): number = Double(value)
    default: return "—"
    }
    return number.formatted(.number.locale(.current))
  }
}

private enum CaseInputError: Error { case invalid }
