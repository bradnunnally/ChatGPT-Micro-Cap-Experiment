# Changelog

## v0.5.0 (Governance + Risk Monitor)

Phases covered: 7 (risk overlays foundations), 9 (optimization suite), 10 (governance core), partial 11 (risk monitor + new rules), selected 14 (turnover budget & regime engine).

### Added
- Governance schema: policy_rule, audit_event (hash chain), config_snapshot (hash chain per kind), breach_log (with notes), risk_event (hash chain).
- Policy rule engine with pre-trade blocking (position_weight, max_trade_notional_pct, sector_aggregate_weight).
- Governance console UI: rule CRUD, config snapshots, audit chain verification, breaches panel, risk events panel.
- Risk monitor service: compute_snapshot (equity, cash, concentration, rolling vol, max drawdown, VaR95) and heuristic event emission.
- Exposure scalar heuristic blending regime probabilities & open breaches.
- Turnover budget enforcement (rolling window %, predictive blocking) and ledger.
- Regime engine (probabilistic) & integration hooks for future scaling.
- Extended test suite (≥80% coverage maintained) including governance, turnover, risk monitor, new rules.

### Changed
- Updated user guide with governance & risk monitoring sections.
- Added project metadata & version to pyproject.

### Fixed
- Ensured hash-chain functions are idempotent & verifiable; added resilience in snapshot / audit logging.

### Pending (Not in 0.5.0)
- Full Phase 11: scheduled integrity checks, UI breach notes editing, JSON params editor.
- Advanced execution microstructure refinements (Phase 13).
- Strategy parameter versioning (Phase 12).

---

## Prior Milestones (Summary)
- Phase 7: Sector/ticker caps, strategy registry persistence.
- Phase 9: Optimization strategies (MV, RP, MinVar, CRP), turnover penalty, factor neutralization, vol cap, regime risk scaling overlay, diagnostics & profiling.
- Phase 14 (selected): Adaptive regime probabilities + turnover budget module.
