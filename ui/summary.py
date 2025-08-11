import pandas as pd


def build_daily_summary(portfolio_data: pd.DataFrame) -> str:
    """Build a daily summary of portfolio performance."""
    try:
        if portfolio_data.empty:
            return "No portfolio data available for summary."

        # Verify required columns exist
        required_columns = ["Ticker", "Shares", "Cost Basis", "Current Price", "Total Value"]
        if not all(col in portfolio_data.columns for col in required_columns):
            return "Error generating summary: Missing required columns"

        # Calculate summary metrics
        total_value = portfolio_data["Total Value"].sum() if "Total Value" in portfolio_data else 0
        cash_balance = (
            portfolio_data["Cash Balance"].iloc[0] if "Cash Balance" in portfolio_data else 0
        )
        total_equity = total_value + cash_balance
        num_positions = len(portfolio_data["Ticker"].unique())

        # Build summary text
        summary = []
        summary.append("Portfolio Summary")
        summary.append("-" * 20)
        summary.append(f"Total Value: ${total_value:,.2f}")
        summary.append(f"Cash Balance: ${cash_balance:,.2f}")
        summary.append(f"Total Equity: ${total_equity:,.2f}")
        summary.append(f"Positions: {num_positions}")

        return "\n".join(summary)

    except Exception as e:
        return f"Error generating summary: {str(e)}"
