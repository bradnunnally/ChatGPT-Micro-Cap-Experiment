-- Add attribution columns to portfolio_history if not present
ALTER TABLE portfolio_history ADD COLUMN pnl_price REAL DEFAULT 0.0;
ALTER TABLE portfolio_history ADD COLUMN pnl_position REAL DEFAULT 0.0;
ALTER TABLE portfolio_history ADD COLUMN pnl_total_attr REAL DEFAULT 0.0;
