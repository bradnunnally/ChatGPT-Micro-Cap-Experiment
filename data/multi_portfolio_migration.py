"""
Multi-Portfolio Database Migration

This migration adds multi-portfolio support while preserving all existing data.

STRATEGY:
1. Add new 'portfolios' table for portfolio management
2. Add 'portfolio_id' columns to existing tables
3. Create default "Micro-Cap" portfolio (ID=1) 
4. Migrate all existing data to portfolio_id=1
5. Update all queries to be portfolio-aware

BACKWARD COMPATIBILITY:
- All existing data is preserved and accessible
- Default portfolio_id=1 maintains existing behavior
- New portfolio functionality is additive, not breaking
"""

# Multi-Portfolio Schema Extensions
MULTI_PORTFOLIO_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        strategy_type TEXT,
        benchmark_symbol TEXT DEFAULT '^GSPC',
        created_date TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        is_default BOOLEAN DEFAULT 0
    );
    """,
    
    # Portfolio table extension (existing data preserved)
    """
    -- Add portfolio_id column if it doesn't exist
    -- SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we handle this in migration
    """,
    
    # Cash table extension (existing data preserved)  
    """
    -- Add portfolio_id column to cash table
    -- Will be handled in migration code
    """,
    
    # Trade log extension (existing data preserved)
    """
    -- Add portfolio_id column to trade_log table
    -- Will be handled in migration code
    """,
    
    # Portfolio history extension (existing data preserved)
    """
    -- Add portfolio_id column to portfolio_history table
    -- Will be handled in migration code
    """,
]

def check_column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_to_multi_portfolio(conn) -> None:
    """
    Migrate existing single-portfolio data to multi-portfolio structure.
    
    This migration:
    1. Creates the portfolios table
    2. Creates default "Micro-Cap" portfolio 
    3. Adds portfolio_id columns to existing tables
    4. Migrates all existing data to portfolio_id=1
    5. Preserves all existing data and functionality
    """
    
    # Step 1: Create portfolios table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            strategy_type TEXT,
            benchmark_symbol TEXT DEFAULT '^GSPC',
            created_date TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            is_default BOOLEAN DEFAULT 0
        )
    """)
    
    # Step 2: Insert default "Micro-Cap" portfolio if it doesn't exist
    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn.execute("""
        INSERT OR IGNORE INTO portfolios 
        (id, name, description, strategy_type, benchmark_symbol, created_date, is_active, is_default)
        VALUES (1, 'Micro-Cap Growth', 
                'Original micro-cap focused portfolio with high-growth potential companies under $300M market cap',
                'Micro-Cap Growth', '^RUT', ?, 1, 1)
    """, (current_date,))
    
    # Step 3: Add portfolio_id columns to existing tables if they don't exist
    
    # Portfolio table
    if not check_column_exists(conn, 'portfolio', 'portfolio_id'):
        conn.execute("ALTER TABLE portfolio ADD COLUMN portfolio_id INTEGER DEFAULT 1")
    
    # Cash table
    if not check_column_exists(conn, 'cash', 'portfolio_id'):
        # Cash table needs special handling because of the CHECK constraint
        # Create new table, copy data, drop old, rename new
        conn.execute("""
            CREATE TABLE cash_new (
                id INTEGER PRIMARY KEY CHECK (id = 0),
                balance REAL,
                portfolio_id INTEGER DEFAULT 1
            )
        """)
        
        # Copy existing data
        conn.execute("""
            INSERT INTO cash_new (id, balance, portfolio_id)
            SELECT id, balance, 1 FROM cash
        """)
        
        # Replace old table
        conn.execute("DROP TABLE cash")
        conn.execute("ALTER TABLE cash_new RENAME TO cash")
    
    # Trade log table
    if not check_column_exists(conn, 'trade_log', 'portfolio_id'):
        conn.execute("ALTER TABLE trade_log ADD COLUMN portfolio_id INTEGER DEFAULT 1")
    
    # Portfolio history table
    if not check_column_exists(conn, 'portfolio_history', 'portfolio_id'):
        conn.execute("ALTER TABLE portfolio_history ADD COLUMN portfolio_id INTEGER DEFAULT 1")
    
    # Step 4: Ensure all existing data has portfolio_id=1 (default portfolio)
    conn.execute("UPDATE portfolio SET portfolio_id = 1 WHERE portfolio_id IS NULL OR portfolio_id = 0")
    conn.execute("UPDATE cash SET portfolio_id = 1 WHERE portfolio_id IS NULL OR portfolio_id = 0")  
    conn.execute("UPDATE trade_log SET portfolio_id = 1 WHERE portfolio_id IS NULL OR portfolio_id = 0")
    conn.execute("UPDATE portfolio_history SET portfolio_id = 1 WHERE portfolio_id IS NULL OR portfolio_id = 0")
    
    conn.commit()
    print("✅ Multi-portfolio migration completed successfully")
    print("✅ All existing data preserved in 'Micro-Cap Growth' portfolio")


def get_schema_version(conn) -> int:
    """Get current schema version."""
    try:
        cursor = conn.execute("SELECT value FROM schema_info WHERE key = 'version'")
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except:
        # Schema info table doesn't exist yet
        return 0

def set_schema_version(conn, version: int) -> None:
    """Set schema version."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_info (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        INSERT OR REPLACE INTO schema_info (key, value)
        VALUES ('version', ?)
    """, (str(version),))
    conn.commit()

def ensure_multi_portfolio_schema(conn) -> None:
    """
    Ensure database has multi-portfolio schema.
    Performs migration if needed while preserving all existing data.
    """
    current_version = get_schema_version(conn)
    
    if current_version < 2:  # Version 2 = Multi-Portfolio Support
        print("🔄 Migrating to multi-portfolio schema...")
        migrate_to_multi_portfolio(conn)
        set_schema_version(conn, 2)
        print("✅ Migration complete - all data preserved!")
    else:
        print("✅ Multi-portfolio schema already up to date")