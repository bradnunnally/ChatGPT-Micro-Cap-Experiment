"""
UI Components for Data Migration (Import/Export)
Provides Streamlit interface for portfolio backup and restore functionality.
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from services.data_migration import DataMigrationService
from services.portfolio_service import PortfolioService


def render_data_migration_page():
    """Render the data migration page with import/export functionality."""
    
    st.title("📁 Portfolio Data Migration")
    st.markdown("Backup and restore your portfolios with all holdings and historical data.")
    
    # Initialize services
    migration_service = DataMigrationService()
    portfolio_service = PortfolioService()
    
    # Create tabs for different operations
    export_tab, import_tab, bulk_tab = st.tabs(["📤 Export Portfolio", "📥 Import Portfolio", "🔄 Bulk Operations"])
    
    with export_tab:
        _render_export_section(migration_service, portfolio_service)
    
    with import_tab:
        _render_import_section(migration_service)
    
    with bulk_tab:
        _render_bulk_operations_section(migration_service, portfolio_service)


def _render_export_section(migration_service: DataMigrationService, portfolio_service: PortfolioService):
    """Render the export portfolio section."""
    
    st.subheader("Export Portfolio")
    st.markdown("Download a complete backup of a portfolio including holdings and historical data.")
    
    # Get available portfolios
    portfolios = portfolio_service.get_all_active_portfolios()
    
    if not portfolios:
        st.warning("No active portfolios found.")
        return
    
    # Portfolio selection
    portfolio_options = {f"{p.name} (ID: {p.id})": p.id for p in portfolios}
    selected_portfolio_label = st.selectbox(
        "Select Portfolio to Export",
        options=list(portfolio_options.keys()),
        key="export_portfolio_select"
    )
    
    selected_portfolio_id = portfolio_options[selected_portfolio_label]
    selected_portfolio = next(p for p in portfolios if p.id == selected_portfolio_id)
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        include_history = st.checkbox(
            "Include Historical Data",
            value=True,
            help="Include portfolio snapshots and historical performance data"
        )
    
    with col2:
        use_timestamp = st.checkbox(
            "Add Timestamp to Filename",
            value=True,
            help="Add current date/time to the exported filename"
        )
    
    # Portfolio info display
    with st.expander("Portfolio Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {selected_portfolio.name}")
            st.write(f"**Strategy:** {selected_portfolio.strategy_type}")
        with col2:
            st.write(f"**Benchmark:** {selected_portfolio.benchmark_symbol}")
            st.write(f"**Created:** {selected_portfolio.created_date}")
        
        if selected_portfolio.description:
            st.write(f"**Description:** {selected_portfolio.description}")
    
    # Export button
    if st.button("📤 Export Portfolio", key="export_button"):
        with st.spinner("Exporting portfolio..."):
            try:
                # Generate filename
                safe_name = "".join(c for c in selected_portfolio.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                timestamp = f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}" if use_timestamp else ""
                filename = f"{safe_name}_export{timestamp}.json"
                
                # Export portfolio
                export_data = migration_service.export_portfolio(selected_portfolio_id, include_history)
                
                # Convert to JSON
                export_dict = {
                    "portfolio": export_data.portfolio,
                    "holdings": export_data.holdings,
                    "snapshots": export_data.snapshots,
                    "export_metadata": export_data.export_metadata
                }
                
                export_json = json.dumps(export_dict, indent=2, default=str)
                
                # Display success and download button
                st.success(f"✅ Portfolio '{selected_portfolio.name}' exported successfully!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="💾 Download Export File",
                        data=export_json,
                        file_name=filename,
                        mime="application/json",
                        key="download_export"
                    )
                
                with col2:
                    # Show export statistics
                    metadata = export_data.export_metadata
                    st.metric("Holdings Exported", metadata["holdings_count"])
                    if include_history:
                        st.metric("Historical Snapshots", metadata["snapshots_count"])
                
            except Exception as e:
                st.error(f"❌ Export failed: {str(e)}")


def _render_import_section(migration_service: DataMigrationService):
    """Render the import portfolio section."""
    
    st.subheader("Import Portfolio")
    st.markdown("Restore a portfolio from a previously exported backup file.")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose Portfolio Export File",
        type=['json'],
        help="Select a .json file exported from this application",
        key="import_file_upload"
    )
    
    if uploaded_file is not None:
        try:
            # Parse the uploaded file
            import_data = json.load(uploaded_file)
            
            # Get import summary
            portfolio_data = import_data.get("portfolio", {})
            metadata = import_data.get("export_metadata", {})
            
            # Display import preview
            st.subheader("Import Preview")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Portfolio Name:** {portfolio_data.get('name', 'Unknown')}")
                st.write(f"**Strategy:** {portfolio_data.get('strategy_type', 'Unknown')}")
                st.write(f"**Benchmark:** {portfolio_data.get('benchmark_symbol', 'Unknown')}")
            
            with col2:
                st.write(f"**Export Date:** {metadata.get('export_date', 'Unknown')[:10]}")
                st.write(f"**Holdings:** {metadata.get('holdings_count', 0)}")
                st.write(f"**Historical Data:** {'Yes' if metadata.get('include_history', False) else 'No'}")
            
            if portfolio_data.get('description'):
                st.write(f"**Description:** {portfolio_data['description']}")
            
            # Import options
            st.subheader("Import Options")
            
            overwrite_existing = st.checkbox(
                "Overwrite Existing Portfolio",
                value=False,
                help="If a portfolio with the same name exists, replace it with the imported data"
            )
            
            if overwrite_existing:
                st.warning("⚠️ This will permanently delete the existing portfolio and all its data.")
            
            # Import button
            if st.button("📥 Import Portfolio", key="import_button"):
                with st.spinner("Importing portfolio..."):
                    try:
                        # Save uploaded file temporarily
                        temp_path = f"/tmp/{uploaded_file.name}"
                        with open(temp_path, 'w') as f:
                            json.dump(import_data, f)
                        
                        # Import portfolio
                        new_portfolio_id = migration_service.import_portfolio_from_file(
                            temp_path,
                            overwrite_existing=overwrite_existing
                        )
                        
                        if new_portfolio_id:
                            st.success(f"✅ Portfolio '{portfolio_data['name']}' imported successfully!")
                            st.info(f"New Portfolio ID: {new_portfolio_id}")
                            
                            # Cleanup temp file
                            Path(temp_path).unlink(missing_ok=True)
                            
                            # Show option to refresh page
                            if st.button("🔄 Refresh Page", key="refresh_after_import"):
                                st.rerun()
                        else:
                            st.error("❌ Import failed. Check the logs for details.")
                    
                    except Exception as e:
                        st.error(f"❌ Import failed: {str(e)}")
        
        except json.JSONDecodeError:
            st.error("❌ Invalid JSON file. Please select a valid portfolio export file.")
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")


def _render_bulk_operations_section(migration_service: DataMigrationService, portfolio_service: PortfolioService):
    """Render the bulk operations section."""
    
    st.subheader("Bulk Operations")
    st.markdown("Export all portfolios at once for complete system backup.")
    
    # Get portfolio count
    portfolios = portfolio_service.get_all_active_portfolios()
    portfolio_count = len(portfolios)
    
    if portfolio_count == 0:
        st.warning("No active portfolios found.")
        return
    
    # Display portfolio summary
    st.write(f"**Active Portfolios:** {portfolio_count}")
    
    with st.expander("Portfolio List", expanded=False):
        for portfolio in portfolios:
            st.write(f"• {portfolio.name} ({portfolio.strategy_type})")
    
    # Bulk export options
    col1, col2 = st.columns(2)
    
    with col1:
        include_history = st.checkbox(
            "Include Historical Data",
            value=True,
            help="Include portfolio snapshots for all portfolios",
            key="bulk_include_history"
        )
    
    with col2:
        create_zip = st.checkbox(
            "Create ZIP Archive",
            value=True,
            help="Package all export files into a single ZIP file"
        )
    
    # Bulk export button
    if st.button("📦 Export All Portfolios", key="bulk_export_button"):
        with st.spinner(f"Exporting {portfolio_count} portfolios..."):
            try:
                # Create temporary directory for exports
                export_dir = f"/tmp/portfolio_exports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Export all portfolios
                exported_files = migration_service.export_all_portfolios(export_dir, include_history)
                
                if exported_files:
                    st.success(f"✅ Successfully exported {len(exported_files)} portfolios!")
                    
                    if create_zip:
                        # Create ZIP archive
                        import zipfile
                        zip_filename = f"all_portfolios_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                        zip_path = f"/tmp/{zip_filename}"
                        
                        with zipfile.ZipFile(zip_path, 'w') as zipf:
                            for file_path in exported_files:
                                zipf.write(file_path, Path(file_path).name)
                        
                        # Offer ZIP download
                        with open(zip_path, 'rb') as f:
                            st.download_button(
                                label="💾 Download All Portfolios (ZIP)",
                                data=f.read(),
                                file_name=zip_filename,
                                mime="application/zip",
                                key="download_bulk_zip"
                            )
                    else:
                        # Offer individual file downloads
                        st.write("**Individual Downloads:**")
                        for file_path in exported_files:
                            filename = Path(file_path).name
                            with open(file_path, 'r') as f:
                                st.download_button(
                                    label=f"💾 {filename}",
                                    data=f.read(),
                                    file_name=filename,
                                    mime="application/json",
                                    key=f"download_{filename}"
                                )
                else:
                    st.error("❌ No portfolios were exported successfully.")
            
            except Exception as e:
                st.error(f"❌ Bulk export failed: {str(e)}")


# Additional utility functions for integration with existing UI
def render_migration_sidebar():
    """Render migration quick actions in sidebar."""
    
    with st.sidebar:
        st.markdown("---")
        st.subheader("🔄 Quick Actions")
        
        if st.button("📤 Export Current Portfolio", key="sidebar_export"):
            st.session_state.show_migration_page = True
            st.rerun()
        
        if st.button("📥 Import Portfolio", key="sidebar_import"):
            st.session_state.show_migration_page = True
            st.rerun()