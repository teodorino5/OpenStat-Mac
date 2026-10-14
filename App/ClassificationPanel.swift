import OpenStatCore
import SwiftUI

private struct CategoryDraft: Identifiable {
  let id = UUID()
  var value = ""
  var label = ""
  var emptyString = false
}

private struct IntervalDraft: Identifiable {
  let id = UUID()
  var label = ""
  var lower = ""
  var upper = ""
  var includeLower = true
  var includeUpper = false
}

struct ClassificationPanel: View {
  @ObservedObject var model: DocumentModel
  @State private var operation = "category"
  @State private var source = ""
  @State private var secondSource = ""
  @State private var outputName = ""
  @State private var measurement = "nominal"
  @State private var unmatched = "error"
  @State private var responseMode = false
  @State private var mappings = [CategoryDraft()]
  @State private var classes = [IntervalDraft()]
  @State private var validationKey: String?

  private var fields: [Variable] { model.dataset?.fields ?? [] }
  private var eligible: [Variable] {
    fields.filter { field in
      switch operation {
      case "interval": return ["int64", "float64"].contains(field.storage)
      case "contingency":
        return field.role != "identifier"
          && !["continuous", "discrete"].contains(field.measurement)
          && (responseMode || field.storage != "multiple_response")
      default: return field.storage != "multiple_response"
      }
    }
  }
  private var selected: Variable? { eligible.first { $0.id == source } }

  var body: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 16) {
        Text(L.text("classification.title")).font(.headline)
        Picker(L.text("classification.operation"), selection: $operation) {
          Text(L.text("classification.category")).tag("category")
          Text(L.text("classification.interval")).tag("interval")
          Text(L.text("classification.contingency")).tag("contingency")
          Text(L.text("classification.audit")).tag("audit")
        }
        if operation == "audit" {
          Text(L.text("classification.audit_note")).font(.caption).foregroundStyle(.secondary)
          Button(L.text("classification.audit_action")) {
            model.inspect(method: "dataset.missing_audit", parameters: [:])
          }.disabled(model.busy || fields.isEmpty)
        } else {
          if operation == "contingency" {
            Toggle(L.text("classification.response_mode"), isOn: $responseMode)
            Text(L.text("classification.response_note")).font(.caption).foregroundStyle(.secondary)
          }
          fieldPicker("classification.source", selection: $source)
          if eligible.isEmpty {
            Text(L.text("classification.no_source")).font(.caption).foregroundStyle(.secondary)
          }
          if operation == "contingency" {
            fieldPicker("classification.column_source", selection: $secondSource)
            Button(L.text("classification.count_action")) {
              validationKey = nil
              model.inspect(
                method: "dataset.contingency",
                parameters: [
                  "row_field": .string(source), "column_field": .string(secondSource),
                  "mode": .string(responseMode ? "response_membership" : "exclusive"),
                ])
            }.disabled(
              model.busy || selected == nil || !eligible.contains { $0.id == secondSource })
          } else {
            TextField(L.text("classification.output_name"), text: $outputName)
            if operation == "category" {
              Picker(L.text("inspector.measurement"), selection: $measurement) {
                Text(L.text("measurement.nominal")).tag("nominal")
                Text(L.text("measurement.ordinal")).tag("ordinal")
              }
              categoryForm
            } else {
              intervalForm
            }
            Picker(L.text("classification.unmatched"), selection: $unmatched) {
              Text(L.text("classification.unmatched_error")).tag("error")
              Text(L.text("classification.unmatched_missing")).tag("missing")
            }
            Text(L.text("classification.missing_note")).font(.caption).foregroundStyle(.secondary)
            Button(L.text("classification.derive_action"), action: derive)
              .disabled(model.busy || selected == nil)
          }
        }
        if let validationKey {
          Text(L.text(validationKey)).font(.caption).foregroundStyle(.red)
        }
        if let summary = model.summary,
          summary.object["revision"]?.string == model.dataset?.revision
        {
          report(summary)
        }
      }.padding(18).disabled(model.busy)
    }
    .onAppear(perform: chooseSources)
    .onChange(of: operation) { _, _ in
      validationKey = nil
      chooseSources()
    }
    .onChange(of: responseMode) { _, _ in chooseSources() }
    .onChange(of: model.dataset?.revision) { _, _ in chooseSources() }
  }

  private func fieldPicker(_ key: String, selection: Binding<String>) -> some View {
    Picker(L.text(key), selection: selection) {
      Text(L.text("classification.choose_source")).tag("")
      ForEach(eligible) { Text($0.name).tag($0.id) }
    }
  }

  private var categoryForm: some View {
    VStack(alignment: .leading, spacing: 12) {
      Text(L.text("classification.category_note")).font(.caption).foregroundStyle(.secondary)
      ForEach($mappings) { $entry in
        VStack(alignment: .leading, spacing: 8) {
          if selected?.storage == "bool" {
            Picker(L.text("classification.value"), selection: $entry.value) {
              Text(L.text("classification.choose_value")).tag("")
              Text(L.text("classification.true")).tag("true")
              Text(L.text("classification.false")).tag("false")
            }
          } else {
            TextField(L.text("classification.value"), text: $entry.value)
              .disabled(entry.emptyString)
            if selected?.storage == "string" {
              Toggle(L.text("classification.empty_string"), isOn: $entry.emptyString)
            }
          }
          HStack {
            TextField(L.text("classification.label"), text: $entry.label)
            Button(L.text("classification.remove")) { mappings.removeAll { $0.id == entry.id } }
              .disabled(mappings.count <= 1)
          }
        }.padding(10).background(
          Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
      }
      Button(L.text("classification.add_mapping")) { mappings.append(CategoryDraft()) }
    }
  }

  private var intervalForm: some View {
    VStack(alignment: .leading, spacing: 12) {
      Text(L.text("classification.interval_note")).font(.caption).foregroundStyle(.secondary)
      Text(L.text("classification.open_note")).font(.caption).foregroundStyle(.secondary)
      ForEach($classes) { $entry in
        VStack(alignment: .leading, spacing: 8) {
          HStack {
            TextField(L.text("classification.label"), text: $entry.label)
            Button(L.text("classification.remove")) { classes.removeAll { $0.id == entry.id } }
              .disabled(classes.count <= 1)
          }
          TextField(L.text("classification.lower"), text: $entry.lower)
          Toggle(L.text("classification.include_lower"), isOn: $entry.includeLower)
            .disabled(entry.lower.isEmpty)
          TextField(L.text("classification.upper"), text: $entry.upper)
          Toggle(L.text("classification.include_upper"), isOn: $entry.includeUpper)
            .disabled(entry.upper.isEmpty)
          Text(intervalPreview(entry)).font(.caption.monospaced()).foregroundStyle(.secondary)
        }.padding(10).background(
          Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
      }
      Button(L.text("classification.add_interval")) { classes.append(IntervalDraft()) }
    }
  }

  private func intervalPreview(_ entry: IntervalDraft) -> String {
    let lower = entry.lower.isEmpty ? "−∞" : entry.lower
    let upper = entry.upper.isEmpty ? "+∞" : entry.upper
    let left = !entry.lower.isEmpty && entry.includeLower ? "[" : "("
    let right = !entry.upper.isEmpty && entry.includeUpper ? "]" : ")"
    return "\(entry.label): \(left)\(lower), \(upper)\(right)"
  }

  private func chooseSources() {
    if !eligible.contains(where: { $0.id == source }) { source = eligible.first?.id ?? "" }
    if !eligible.contains(where: { $0.id == secondSource }) {
      secondSource = eligible.dropFirst().first?.id ?? eligible.first?.id ?? ""
    }
  }

  private func derive() {
    guard let selected else { return }
    validationKey = nil
    let name = outputName.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !name.isEmpty, !fields.contains(where: { $0.name == name }) else {
      validationKey = "classification.invalid_name"
      return
    }
    do {
      var parameters: [String: JSONValue] = [
        "source": .string(source), "unmatched": .string(unmatched),
        "output": .object([
          "id": .string(UUID().uuidString), "name": .string(name), "storage": .string("string"),
          "measurement": .string(operation == "interval" ? "ordinal" : measurement),
        ]),
      ]
      if operation == "category" {
        var seen: [JSONValue] = []
        parameters["mapping"] = .array(
          try mappings.map { entry in
            let value =
              selected.storage == "string" && entry.emptyString
              ? JSONValue.string("")
              : try CellParser.parse(entry.value, storage: selected.storage, locale: .current)
            guard value != .null, !seen.contains(value), !entry.label.isEmpty else {
              throw ClassificationInputError.invalid
            }
            seen.append(value)
            return .object(["value": value, "label": .string(entry.label)])
          })
      } else {
        var labels = Set<String>()
        parameters["classes"] = .array(
          try classes.map { entry in
            guard !entry.label.isEmpty, labels.insert(entry.label).inserted else {
              throw ClassificationInputError.invalid
            }
            let lower = try CellParser.parse(
              entry.lower, storage: selected.storage, locale: .current)
            let upper = try CellParser.parse(
              entry.upper, storage: selected.storage, locale: .current)
            return .object([
              "label": .string(entry.label), "lower": lower, "upper": upper,
              "include_lower": .bool(lower != .null && entry.includeLower),
              "include_upper": .bool(upper != .null && entry.includeUpper),
            ])
          })
      }
      model.transform(
        method: "classification.\(operation == "category" ? "categories" : "intervals")",
        parameters: parameters)
    } catch { validationKey = "classification.invalid_input" }
  }

  @ViewBuilder
  private func report(_ summary: JSONValue) -> some View {
    let value = summary.object
    if value["counts"] != nil && operation == "contingency"
      && value["row_field"]?.string == source && value["column_field"]?.string == secondSource
      && value["mode"]?.string == (responseMode ? "response_membership" : "exclusive")
    {
      Divider()
      Text(L.text("classification.count_result")).font(.headline)
      Text(L.format("classification.eligible_count", value["eligible_cases"]?.int ?? 0))
      Text(L.format("classification.pair_count", value["pair_count"]?.int ?? 0))
      Text(L.format("classification.null_count", value["excluded_null_cases"]?.int ?? 0))
      Text(L.format("classification.coded_count", value["excluded_coded_missing_cases"]?.int ?? 0))
      if value["mode"]?.string == "response_membership" {
        Text(L.text("classification.pair_note")).font(.caption).foregroundStyle(.secondary)
        Text(L.format("classification.empty_count", value["empty_response_cases"]?.int ?? 0))
      }
      let columns = value["column_levels"]?.array ?? []
      let rows = value["row_levels"]?.array ?? []
      let counts = value["counts"]?.array ?? []
      let totals = value["row_totals"]?.array ?? []
      let columnTotals = value["column_totals"]?.array ?? []
      if rows.count <= 30 && columns.count <= 12 {
        VStack(alignment: .leading, spacing: 10) {
          ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
            VStack(alignment: .leading, spacing: 4) {
              Text(row.string).font(.subheadline.bold())
              ForEach(Array(columns.enumerated()), id: \.offset) { column, label in
                let count =
                  index < counts.count && column < counts[index].array.count
                  ? counts[index].array[column].int : 0
                HStack {
                  Text(label.string)
                  Spacer()
                  Text(String(count)).monospacedDigit()
                }
              }
              if index < totals.count {
                Text(L.format("classification.row_total", totals[index].int)).font(.caption)
              }
            }
          }
          Divider()
          Text(L.text("classification.column_totals")).font(.subheadline.bold())
          ForEach(Array(columns.enumerated()), id: \.offset) { index, label in
            HStack {
              Text(label.string)
              Spacer()
              Text(String(index < columnTotals.count ? columnTotals[index].int : 0))
                .monospacedDigit()
            }
          }
        }
      } else {
        Text(L.text("classification.large_table")).font(.caption).foregroundStyle(.secondary)
      }
    } else if value["fields"] != nil && value["complete_cases"] != nil && operation == "audit" {
      Divider()
      Text(L.text("classification.audit_result")).font(.headline)
      Text(L.format("classification.total_count", value["total_cases"]?.int ?? 0))
      Text(L.format("classification.complete_count", value["complete_cases"]?.int ?? 0))
      ForEach(fields) { field in
        if let counts = value["fields"]?.object[field.id]?.object {
          VStack(alignment: .leading, spacing: 4) {
            Text(field.name).font(.subheadline.bold())
            Text(L.format("classification.null_count", counts["null"]?.int ?? 0))
            Text(L.format("classification.coded_count", counts["coded_missing"]?.int ?? 0))
            Text(L.format("classification.valid_count", counts["valid"]?.int ?? 0))
            if field.storage == "multiple_response" {
              Text(L.format("classification.empty_count", counts["empty_response"]?.int ?? 0))
            }
          }
        }
      }
    }
  }
}

private enum ClassificationInputError: Error { case invalid }
