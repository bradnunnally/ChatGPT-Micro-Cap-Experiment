-- Migration 0001: initial schema with indexes
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Portfolio, cash, trade_log, portfolio_history already created by app init.
-- Add a few useful indexes and constraints.
CREATE INDEX IF NOT EXISTS idx_portfolio_ticker ON portfolio(ticker);
CREATE INDEX IF NOT EXISTS idx_trade_log_ticker_date ON trade_log(ticker, date);
CREATE INDEX IF NOT EXISTS idx_history_date_ticker ON portfolio_history(date, ticker);

INSERT OR IGNORE INTO schema_version(version) VALUES('0001');

COMMIT;
