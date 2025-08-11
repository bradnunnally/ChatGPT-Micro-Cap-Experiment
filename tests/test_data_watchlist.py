"""Tests for data/watchlist.py module."""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.watchlist import load_watchlist, save_watchlist


class TestWatchlist:
    """Test watchlist functionality."""

    @patch("data.watchlist.WATCHLIST_FILE")
    def test_load_watchlist_file_not_exists(self, mock_watchlist_file):
        """Test loading watchlist when file doesn't exist."""
        mock_watchlist_file.exists.return_value = False

        result = load_watchlist()

        assert result == []

    @patch("data.watchlist.WATCHLIST_FILE")
    def test_load_watchlist_success(self, mock_watchlist_file):
        """Test successful watchlist loading."""
        mock_watchlist_file.exists.return_value = True
        mock_watchlist_file.read_text.return_value = '["AAPL", "MSFT", "googl"]'

        result = load_watchlist()

        assert result == ["AAPL", "MSFT", "GOOGL"]  # Should be uppercase

    @patch("data.watchlist.WATCHLIST_FILE")
    def test_load_watchlist_mixed_types(self, mock_watchlist_file):
        """Test loading watchlist with mixed data types (filters non-strings)."""
        mock_watchlist_file.exists.return_value = True
        mock_watchlist_file.read_text.return_value = '["AAPL", 123, "MSFT", null, "GOOGL"]'

        result = load_watchlist()

        # Should only include strings, converted to uppercase
        assert result == ["AAPL", "MSFT", "GOOGL"]

    @patch("data.watchlist.WATCHLIST_FILE")
    @patch("data.watchlist.logger")
    def test_load_watchlist_json_error(self, mock_logger, mock_watchlist_file):
        """Test loading watchlist with invalid JSON."""
        mock_watchlist_file.exists.return_value = True
        mock_watchlist_file.read_text.return_value = "invalid json"

        result = load_watchlist()

        assert result == []
        mock_logger.exception.assert_called_once_with("Failed to load watchlist")

    @patch("data.watchlist.WATCHLIST_FILE")
    @patch("data.watchlist.logger")
    def test_load_watchlist_read_error(self, mock_logger, mock_watchlist_file):
        """Test loading watchlist with file read error."""
        mock_watchlist_file.exists.return_value = True
        mock_watchlist_file.read_text.side_effect = IOError("Permission denied")

        result = load_watchlist()

        assert result == []
        mock_logger.exception.assert_called_once_with("Failed to load watchlist")

    @patch("data.watchlist.WATCHLIST_FILE")
    def test_save_watchlist_success(self, mock_watchlist_file):
        """Test successful watchlist saving."""
        tickers = ["AAPL", "MSFT", "GOOGL"]

        save_watchlist(tickers)

        mock_watchlist_file.write_text.assert_called_once_with('["AAPL", "MSFT", "GOOGL"]')

    @patch("data.watchlist.WATCHLIST_FILE")
    def test_save_watchlist_empty_list(self, mock_watchlist_file):
        """Test saving empty watchlist."""
        tickers = []

        save_watchlist(tickers)

        mock_watchlist_file.write_text.assert_called_once_with("[]")

    @patch("data.watchlist.WATCHLIST_FILE")
    @patch("data.watchlist.logger")
    def test_save_watchlist_write_error(self, mock_logger, mock_watchlist_file):
        """Test saving watchlist with write error."""
        mock_watchlist_file.write_text.side_effect = IOError("Permission denied")
        tickers = ["AAPL", "MSFT"]

        save_watchlist(tickers)

        mock_logger.exception.assert_called_once_with("Failed to save watchlist")

    def test_load_save_integration(self):
        """Test loading and saving watchlist with real file operations."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Patch the WATCHLIST_FILE to use our temp file
            with patch("data.watchlist.WATCHLIST_FILE", temp_path):
                # Save a watchlist
                original_tickers = ["AAPL", "MSFT", "GOOGL"]
                save_watchlist(original_tickers)

                # Load it back
                loaded_tickers = load_watchlist()

                assert loaded_tickers == original_tickers
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()

    def test_load_save_case_conversion(self):
        """Test that tickers are properly converted to uppercase on load."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as temp_file:
            temp_path = Path(temp_file.name)

        try:
            with patch("data.watchlist.WATCHLIST_FILE", temp_path):
                # Save lowercase tickers
                save_watchlist(["aapl", "msft", "googl"])

                # Load them back (should be uppercase)
                loaded_tickers = load_watchlist()

                assert loaded_tickers == ["AAPL", "MSFT", "GOOGL"]
        finally:
            if temp_path.exists():
                temp_path.unlink()
