# Dataset Card: Breadcrumbs Synthetic RMG Compliance Corpus

**Document Version:** 1.0.0  
**Context:** Academic Research Prototype & Competition Submission (Blockchain Olympiad Bangladesh)  
**Artifact Scope:** Synthetic compliance documents, continually evolving anomaly waves, and ledger adversary traces.

---

## 1. Explicit Disclaimers & Synthetic Grounding

> [!WARNING]
> **No Real Data Represented.**  
> Every factory, worker identifier, inspector reference, buyer code, certificate number, chemical record, and measurement in this dataset is entirely synthetic and algorithmically generated. No actual RMG factory, enterprise, auditor, or human worker was sampled, interviewed, or represented in the construction of this corpus.

> [!IMPORTANT]
> **Parameters are Assumptions, Not Empirical Measurements.**  
> The baseline anomaly rate (4.0%), the distribution of adversary attacks, the non-IID Dirichlet concentration ($\alpha = 0.60$), the site wage distributions, and the seasonal overtime scaling factors were **chosen by design to test algorithmic properties**, not derived from field observations of the Bangladeshi garment sector. No empirical or sociological claim is made regarding the prevalence, structure, or distribution of compliance violations in the real-world manufacturing sector.

---

## 2. Intended Purpose and Valid Uses

This dataset is an **evaluative instrument** designed to measure and compare technical mechanisms under controlled, reproducible conditions:

### Valid Uses
1. **Evaluating Ledger Guarantees (Ledger Axis):** Testing whether a permissioned blockchain and cryptographic accumulator can mathematically detect retroactive document mutation, period withholding, equivocated histories, backdated seals, and collusion among counter-signatories.
2. **Measuring Continual Learning & Catastrophic Forgetting (Detector Axis):** Evaluating whether a machine learning detector trained on non-stationary, streaming data forgets earlier anomaly distributions when exposed to new violation types over time.
3. **Benchmarking Federated Non-IID Optimization:** Providing a reproducible non-IID partition across six distinct nodes to test federated aggregation methods without privacy leakage.

### Invalid Uses & Out-of-Scope Interpretations
- **Prevalence Claims:** Drawing inferences about the frequency or nature of fraud or compliance defects in Bangladesh's RMG industry.
- **Direct Operational Deployment:** Training a production model intended for deployment in real factories without domain retraining on audited industrial records.
- **Generalization Claims:** Claiming that a model achieving high detection accuracy on this synthetic corpus will transfer that accuracy to organic, human-written documents.

---

## 3. Known Limitations & Potential Flattery Modes

A synthetic corpus runs the risk of inadvertently flattering the models or ledgers evaluated against it. The following known failure modes and inductive biases are documented explicitly:

### 3.1 Summary Statistic Flattery
- **Mechanism:** In synthetic tabular data, aggregate features (such as row-level sum residuals, mean overtime, or certificate check digits) often concentrate discriminative signals into simple scalar projections.
- **Flattery Risk:** A detector operating solely on hand-crafted summary statistics may achieve high precision because the generator implements mathematical invariants that summary statistics directly invert.
- **Suggested Diagnostic Control:** Evaluators must benchmark raw row-level sequence and tabular models against simple linear baselines and deliberately noisy, corrupted inputs.

### 3.2 Discrete Anomaly Signatures
- **Mechanism:** Certain anomalies (such as invalid Mod-97 check digits or CAS checksums) are binary mathematical invariants.
- **Flattery Risk:** Rule-based heuristics will achieve 100% precision on these specific features.
- **Countermeasure in Generator:** Check digit errors represent only a minority slice of Wave 2; continuous severity scaling (e.g. 1-3% arithmetic discrepancies and slight overtime elevations) ensures that rule-based thresholds suffer from false positives under realistic noise.

### 3.3 Single-Document vs. Cross-Document Detectability
- **Mechanism:** `cross_inconsistency` anomalies and `cross_document_fraud` attacks intentionally produce payroll and production documents that are **100% valid and consistent in isolation**.
- **Flattery Risk:** Any single-document detector evaluated on these records will score 0% accuracy by mathematical design.
- **Evaluator Note:** Scoring these cases requires paired cross-ledger reconciliation, justifying a multi-party shared ledger architecture over isolated notarization.

---

## 4. Dataset Taxonomy & Technical Specifications

| Parameter | Specification |
|---|---|
| **Temporal Span** | 36 monthly reporting periods (January 2025 to December 2027) |
| **Continual Waves** | Wave 1 (2025: Arithmetic & Overtime), Wave 2 (2026: Checksums & Backdating), Wave 3 (2027: Chemicals & Outliers + Wave 1 Recurrence) |
| **Site Count** | 6 synthetic factories (`gazipur`, `ashulia`, `narayanganj`, `savar`, `chattogram`, `mirpur`) |
| **Partition Alpha** | Dirichlet $\alpha = 0.60$ over anomaly kinds per site |
| **Record Types** | 5 types: `payroll_register`, `safety_inspection`, `chemical_inventory`, `machine_maintenance`, `production_output` |
| **Adversary Attacks** | 8 canonical attacks logged in `adversary_trace.json` |
| **Determinism** | Pure PRNG threading with byte-level identity across OS and platforms |
| **Output Formats** | Canonical JSONL (`.jsonl.gz`), JSON, and optional Apache Parquet |
