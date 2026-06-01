# TKDE Drift Type Sufficiency & PhD Validation Report
================================================================================
This module evaluates the schema drift types implemented in the framework
for an IEEE TKDE paper on resilient semantic reconciliation under drift.
================================================================================

## 1. Classification & Evaluation of Current Drift Types

### 1.1 Drift Type: `missing_keys`
- **Classification**: Structural / Lexical
- **Example (Original -> Drifted)**: {"price": 182.50, "currency": "USD"}  ==>  {"currency": "USD"}
- **Production Realism**: High. Occurs when upstream API fields are deprecated or removed without notice.
- **Semantic Reconciliation Stress**: Medium. Stresses whether the downstream pipeline can reconcile fields with partial data.
- **Method Differentiation Capacity**: Differentiates well: Regex/Levenshtein fail completely (missing target key); BERT/Gemma can locate semantic fallbacks.

### 1.2 Drift Type: `extra_keys`
- **Classification**: Structural / Lexical
- **Example (Original -> Drifted)**: {"price": 182.50}  ==>  {"price": 182.50, "price_extra": "dummy"}
- **Production Realism**: High. Standard occurrence in backward-compatible API expansions.
- **Semantic Reconciliation Stress**: Low. Usually ignored unless it causes strict-schema validation errors.
- **Method Differentiation Capacity**: Weak differentiation: Simple filters can discard unmapped fields. Regex/Levenshtein handle it easily.

### 1.3 Drift Type: `renamed_keys`
- **Classification**: Lexical / Semantic
- **Example (Original -> Drifted)**: {"temperature": 22.5}  ==>  {"tempC": 22.5} (or "ambient_atmospheric_thermal_reading_celsius")
- **Production Realism**: Very High. Occurs during major API refactorings or standardisation initiatives.
- **Semantic Reconciliation Stress**: High. Requires matching the new name back to the canonical schema.
- **Method Differentiation Capacity**: Strongest differentiator: Levenshtein/Regex only succeed on simple contractions (tempC). BERT handles moderate semantic shift, whereas Gemma successfully maps extreme adversarial renames.

### 1.4 Drift Type: `split_fields`
- **Classification**: Structural / Syntactic
- **Example (Original -> Drifted)**: {"location": "37.7 -122.4"}  ==>  {"location_lat": 37.7, "location_lng": -122.4}
- **Production Realism**: High. Standard database normalisation or payload restructuring.
- **Semantic Reconciliation Stress**: High. Violates 1:1 field mappings, requiring semantic grouping.
- **Method Differentiation Capacity**: Regex and Levenshtein fail completely. BERT can calculate similarity for parts, while Gemma excels at recognizing 1:N structural refactorings.

### 1.5 Drift Type: `merged_fields`
- **Classification**: Structural / Syntactic
- **Example (Original -> Drifted)**: {"first_name": "Max", "last_name": "Verstappen"}  ==>  {"full_name": "Max Verstappen"}
- **Production Realism**: High. Simplification of payloads for lightweight mobile clients.
- **Semantic Reconciliation Stress**: High. Downstream reconciler must merge N fields into 1 representation.
- **Method Differentiation Capacity**: Differentiates Regex/Levenshtein (fail) vs LLM/Gemma (can synthesize full payload merge map).

### 1.6 Drift Type: `nested_corruption`
- **Classification**: Structural
- **Example (Original -> Drifted)**: {"address": "123 Main St"}  ==>  {"address": {"raw": "123 Main St"}}
- **Production Realism**: Medium. Happens when APIs shift from raw fields to object-oriented payloads.
- **Semantic Reconciliation Stress**: Very High. Breaks flat parsing paths and type expectations.
- **Method Differentiation Capacity**: Differentiates traditional string metric reconcilers (which crash or ignore nesting) vs deep semantic parsers (BERT/Gemma).

### 1.7 Drift Type: `type_mismatch`
- **Classification**: Syntactic
- **Example (Original -> Drifted)**: {"active": true}  ==>  {"active": "true"} (or {"price": 100} ==> {"price": ""})
- **Production Realism**: Very High. Loose type conversions (e.g. PHP/JS backends or serialization bugs).
- **Semantic Reconciliation Stress**: Medium. Downstream must coerce types without data loss.
- **Method Differentiation Capacity**: Weak differentiation for semantic models, but highly stresses parser robustness.

### 1.8 Drift Type: `value_contradiction`
- **Classification**: Semantic / Lexical
- **Example (Original -> Drifted)**: {"price": 100.0}  ==>  {"price": 103.45} (or value paraphrases)
- **Production Realism**: High. Data drift, sensor noise, or paraphrase mutation in textual fields.
- **Semantic Reconciliation Stress**: High. Evaluates if the system can identify drift when keys match but content drifts.
- **Method Differentiation Capacity**: Differentiates string metric reconcilers (which do not look at values) vs BERT/Gemma (which analyze semantic value similarity).

## 2. TKDE/PhD Sufficiency Critique

> [!NOTE]
> **Sufficiency Verdict: CONDITIONAL SUFFICIENCY (Needs Expansion)**
> The current 8 drift types provide a robust baseline covering standard lexical, 
> syntactic, and structural mutations. They adequately stress simple string reconcilers 
> (Levenshtein, Regex) and show the value of local BERT/Gemma semantic reconciliation. 
> However, to satisfy the rigor expected of a **PhD-level IEEE TKDE (Transactions on Knowledge 
> and Data Engineering)** paper, the framework must move beyond simple structural and typo 
> changes to include complex **semantic and scale mutations** that heavily differentiate 
> local embedding models and lightweight LLMs from classical techniques.

## 3. Proposed Academic-Grade Novel Drift Types

### 3.1 Non-Linear Scale & Unit Transformation (Syntactic/Semantic)
- **Concept**: A field's unit and scale change concurrently under a mathematical formula 
  (e.g., Fahrenheit to Celsius $F = 1.8C + 32$, or USD to EUR with exchange fluctuations).
- **Example**: `{'temperature': 20.0}` $\rightarrow$ `{'temperature_fahrenheit': 68.0}`.
- **TKDE Contribution**: Evaluates if semantic reconcilers can recognize unit scales and 
  perform value reconciliation using structural logic rather than just string similarity.
- **Method Differentiation**: Levenshtein and Regex fail. BERT recognizes the semantic field 
  relationship but cannot verify value correctness. Gemma can identify the math conversion 
  and verify physical equivalence offline.

### 3.2 Temporal & Epoch Representation Drift (Syntactic/Structural)
- **Concept**: Timestamps drift between ISO-8601, Unix epoch seconds, Unix epoch milliseconds, 
  and localized formatted date strings.
- **Example**: `{'timestamp': '2026-05-29T10:30:00Z'}` $\rightarrow$ `{'epoch_ms': 1780069800000}`.
- **TKDE Contribution**: Temporal tracking is a core database requirement in TKDE. Managing 
  temporal notation drift is critical for downstream time-series alignment.
- **Method Differentiation**: Pure lexical methods fail. Deep semantic models must be 
  equipped to map epoch names to canonical timestamps.

### 3.3 Semantic State Flag Paraphrasing (Semantic)
- **Concept**: API state flags (usually booleans or short enums) drift into complex, 
  academic, or domain-specific semantic phrases that carry identical meaning but share 
  zero character overlap.
- **Example**: `{'status': 'active'}` $\rightarrow$ `{'operational_state': 'nominal_operational_live'}`.
- **TKDE Contribution**: Directly tests deep linguistic representation limits of BERT vs 
  local generative LLMs (Gemma) in domain-specific tasks.
- **Method Differentiation**: Levenshtein (0% similarity), Regex (no pattern match) and 
  small BERT models fail. Only generative LLMs (Gemma) with instruction-following offline 
  capabilities can map these complex states correctly.

