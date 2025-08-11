"""Tests for data/db.py module."""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.db import get_connection, init_db, SCHEMA


class TestDatabase:
    """Test database functionality."""

    def test_schema_defined(self):
        """Test that the database schema is properly defined."""
        assert "portfolio" in SCHEMA
        assert "cash" in SCHEMA
        assert "trade_log" in SCHEMA
        assert "portfolio_history" in SCHEMA
        assert "CREATE TABLE" in SCHEMA

    def test_get_connection(self):
        """Test getting a database connection."""
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_path = temp_file.name

        try:
            # Patch the DB_FILE to use our temp file
            with patch("data.db.DB_FILE", temp_path):
                conn = get_connection()
                assert isinstance(conn, sqlite3.Connection)
                conn.close()
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @patch("data.db.get_connection")
    def test_init_db(self, mock_get_connection):
        """Test database initialization."""
        # Mock connection
        mock_conn = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        init_db()

        # Verify that executescript was called with the schema
        mock_conn.executescript.assert_called_once_with(SCHEMA)

    def test_init_db_creates_tables(self):
        """Test that init_db actually creates the expected tables."""
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_db_path = temp_file.name

        try:
            # Patch the DB_FILE config to use our temp file
            with patch("data.db.DB_FILE", temp_db_path):
                init_db()

                # Verify tables were created
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()

                # Check that all expected tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]

                assert "portfolio" in tables
                assert "cash" in tables
                assert "trade_log" in tables
                assert "portfolio_history" in tables

                conn.close()
        finally:
            # Clean up
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_portfolio_table_structure(self):
        """Test that the portfolio table has the correct structure."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_db_path = temp_file.name

        try:
            with patch("data.db.DB_FILE", temp_db_path):
                init_db()

                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()

                # Check portfolio table structure
                cursor.execute("PRAGMA table_info(portfolio);")
                columns = {row[1]: row[2] for row in cursor.fetchall()}

                assert "ticker" in columns
                assert "shares" in columns
                assert "stop_loss" in columns
                assert "buy_price" in columns
                assert "cost_basis" in columns

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_cash_table_constraint(self):
        """Test that the cash table has the id=0 constraint."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_db_path = temp_file.name

        try:
            with patch("data.db.DB_FILE", temp_db_path):
                init_db()

                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()

                # Insert valid cash record
                cursor.execute("INSERT INTO cash (id, balance) VALUES (0, 1000.0)")

                # Try to insert invalid cash record (should fail)
                with pytest.raises(sqlite3.IntegrityError):
                    cursor.execute("INSERT INTO cash (id, balance) VALUES (1, 2000.0)")

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

    def test_trade_log_autoincrement(self):
        """Test that trade_log table has autoincrement primary key."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_db_path = temp_file.name

        try:
            with patch("data.db.DB_FILE", temp_db_path):
                init_db()

                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()

                # Insert trade log entries without specifying id
                cursor.execute(
                    """
                    INSERT INTO trade_log (date, ticker, shares_bought, buy_price, cost_basis, pnl, reason)
                    VALUES ('2023-01-01', 'AAPL', 100, 150.0, 15000.0, 0.0, 'TEST')
                """
                )

                cursor.execute(
                    """
                    INSERT INTO trade_log (date, ticker, shares_bought, buy_price, cost_basis, pnl, reason)
                    VALUES ('2023-01-02', 'MSFT', 50, 300.0, 15000.0, 0.0, 'TEST')
                """
                )

                # Check that IDs were auto-assigned
                cursor.execute("SELECT id FROM trade_log ORDER BY id")
                ids = [row[0] for row in cursor.fetchall()]

                assert len(ids) == 2
                assert ids[0] == 1
                assert ids[1] == 2

                conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)
