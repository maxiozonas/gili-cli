"""Flexxus Stock and Price Synchronization Connector.

This module provides the FlexxusSync class for synchronizing stock and price
data from Flexxus CSV files with Magento.
"""

import os
import glob
from typing import Optional, List, Dict, Set
from datetime import datetime
from pathlib import Path

import pandas as pd
import structlog

from ..utils.helpers import normalize_sku
from ..config.settings import Settings, get_settings
from ..config.constants import FIXED_STOCK_OVERRIDES
from ..core.exceptions import DataProcessingError, FileNotFoundError

logger = structlog.get_logger(__name__)


class FlexxusSync:
    """Synchronize Flexxus data with Magento.
    
    This class handles:
    - Finding and loading Flexxus CSV files
    - Data validation and normalization
    - Filtering by existing Magento SKUs
    - Applying fixed stock overrides
    - Exporting synchronized data
    
    Example:
        >>> sync = FlexxusSync()
        >>> result = sync.synchronize(magento_skus=magento_skus)
        >>> print(f"Exported to: {result}")
    """
    
    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the Flexxus sync connector.
        
        Args:
            settings: Settings instance (uses global if not provided)
        """
        self.settings = settings or get_settings()
        self.flexxus_folder = self.settings.flexxus_stock_folder
        
        logger.debug(
            "flexxus_sync_initialized",
            folder=self.flexxus_folder
        )
    
    def find_latest_csv(self) -> str:
        """Find the most recent Flexxus CSV file.
        
        Returns:
            Path to the latest CSV file
            
        Raises:
            FileNotFoundError: If no CSV files found
        """
        csv_pattern = os.path.join(self.flexxus_folder, "*.csv")
        csv_files = glob.glob(csv_pattern)
        
        if not csv_files:
            logger.error(
                "no_csv_files_found",
                folder=self.flexxus_folder
            )
            raise FileNotFoundError(
                self.flexxus_folder,
                file_type="Flexxus CSV"
            )
        
        # Filter out sync files and get modification times
        files_with_time = []
        for f in csv_files:
            if 'Sync' not in os.path.basename(f):
                files_with_time.append((f, os.path.getmtime(f)))
        
        if not files_with_time:
            # If all files have 'Sync' in name, use all files
            files_with_time = [(f, os.path.getmtime(f)) for f in csv_files]
        
        # Get most recent file
        latest_file = max(files_with_time, key=lambda x: x[1])[0]
        
        logger.info(
            "csv_file_selected",
            file=os.path.basename(latest_file),
            folder=self.flexxus_folder
        )
        
        return latest_file
    
    def load_flexxus_data(self, csv_path: str) -> pd.DataFrame:
        """Load and validate Flexxus CSV data.
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            DataFrame with normalized data
            
        Raises:
            DataProcessingError: If loading fails
        """
        logger.info("loading_flexxus_data", file=csv_path)
        
        # Try different encodings and separators
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-8-sig']
        separators = [';', ',', '\t']
        
        df: Optional[pd.DataFrame] = None
        used_encoding = None
        used_separator = None
        
        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(csv_path, encoding=encoding, sep=sep)
                    if len(df.columns) >= 3:
                        used_encoding = encoding
                        used_separator = sep
                        break
                except Exception:
                    continue
            if df is not None and len(df.columns) >= 3:
                break
        
        if df is None:
            logger.error("failed_to_load_csv", tried_encodings=encodings)
            raise DataProcessingError(
                "Could not load CSV with any known format",
                operation="load_flexxus_data"
            )
        
        # Normalize column names
        df.columns = df.columns.str.lower().str.strip()
        
        # Check required columns
        required_cols = ['sku', 'qty', 'price']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(
                "missing_required_columns",
                columns=missing_cols,
                available=list(df.columns)
            )
            raise DataProcessingError(
                f"Missing required columns: {missing_cols}",
                operation="load_flexxus_data"
            )
        
        # Select and copy only required columns
        df = df[required_cols].copy()
        
        # Normalize SKUs
        df['sku'] = df['sku'].apply(normalize_sku)
        
        # Clean numeric columns
        df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(int)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
        
        # Filter out invalid SKUs
        df = df[df['sku'] != '']
        df = df[df['sku'] != 'nan']
        df = df[df['sku'] != '00000']
        
        logger.info(
            "flexxus_data_loaded",
            rows=len(df),
            encoding=used_encoding,
            separator=used_separator,
            qty_min=df['qty'].min(),
            qty_max=df['qty'].max(),
            price_min=df['price'].min(),
            price_max=df['price'].max()
        )
        
        return df
    
    def filter_by_magento_skus(
        self, 
        df_flexxus: pd.DataFrame, 
        magento_skus: Set[str]
    ) -> pd.DataFrame:
        """Filter Flexxus data to include only existing Magento SKUs.
        
        Args:
            df_flexxus: Flexxus data DataFrame
            magento_skus: Set of valid Magento SKUs
            
        Returns:
            Filtered DataFrame
        """
        logger.info(
            "filtering_by_magento_skus",
            flexxus_count=len(df_flexxus),
            magento_count=len(magento_skus)
        )
        
        initial_count = len(df_flexxus)
        df_filtered = df_flexxus[df_flexxus['sku'].isin(magento_skus)].copy()
        final_count = len(df_filtered)
        
        logger.info(
            "filtering_complete",
            initial_count=initial_count,
            final_count=final_count,
            matched=final_count
        )
        
        return df_filtered
    
    def apply_stock_overrides(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply fixed stock overrides to specific SKUs.
        
        Args:
            df: DataFrame with SKU and qty columns
            
        Returns:
            DataFrame with overrides applied
        """
        logger.info("applying_stock_overrides")
        
        df = df.copy()
        overridden_count = 0
        
        for sku, fixed_qty in FIXED_STOCK_OVERRIDES.items():
            # Normalize SKU from overrides
            normalized_sku = normalize_sku(sku)
            
            if normalized_sku in df['sku'].values:
                df.loc[df['sku'] == normalized_sku, 'qty'] = fixed_qty
                overridden_count += 1
                logger.debug(
                    "stock_override_applied",
                    sku=normalized_sku,
                    qty=fixed_qty
                )
        
        logger.info(
            "stock_overrides_applied",
            overridden_count=overridden_count,
            total_overrides=len(FIXED_STOCK_OVERRIDES)
        )
        
        return df
    
    def export_synced_data(
        self, 
        df_synced: pd.DataFrame,
        output_dir: Optional[str] = None
    ) -> str:
        """Export synchronized data to CSV file.
        
        Args:
            df_synced: Synchronized data DataFrame
            output_dir: Output directory (uses flexxus_folder if not specified)
            
        Returns:
            Path to exported file
            
        Raises:
            DataProcessingError: If export fails
        """
        output_dir = output_dir or self.flexxus_folder
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            output_filename = f'Flexxus_Magento_Sync_{timestamp}.csv'
            output_path = os.path.join(output_dir, output_filename)
            
            # Prepare export data
            df_export = df_synced.copy()
            df_export['special_price'] = df_export['price']
            
            # Format prices
            df_export['price'] = df_export['price'].apply(lambda x: f"{x:.2f}")
            df_export['special_price'] = df_export['special_price'].apply(lambda x: f"{x:.2f}")
            
            # Reorder columns
            cols_order = ['sku', 'qty', 'price', 'special_price']
            df_export = df_export[cols_order]
            
            # Export to CSV
            df_export.to_csv(
                output_path,
                index=False,
                sep=';',
                encoding='utf-8-sig',
                quoting=0  # csv.QUOTE_MINIMAL
            )
            
            logger.info(
                "data_exported",
                path=output_path,
                rows=len(df_export)
            )
            
            return output_path
            
        except Exception as e:
            logger.error("export_failed", error=str(e))
            raise DataProcessingError(
                f"Failed to export data: {e}",
                operation="export_synced_data"
            )
    
    def synchronize(
        self, 
        magento_skus: Set[str],
        apply_overrides: bool = True
    ) -> str:
        """Execute complete synchronization workflow.
        
        Args:
            magento_skus: Set of valid Magento SKUs
            apply_overrides: Whether to apply fixed stock overrides
            
        Returns:
            Path to exported sync file
            
        Raises:
            DataProcessingError: If synchronization fails
        """
        logger.info("starting_flexxus_synchronization")
        
        # Find and load Flexxus data
        csv_path = self.find_latest_csv()
        df_flexxus = self.load_flexxus_data(csv_path)
        
        if df_flexxus.empty:
            raise DataProcessingError(
                "No data loaded from Flexxus",
                operation="synchronize"
            )
        
        # Filter by Magento SKUs
        df_synced = self.filter_by_magento_skus(df_flexxus, magento_skus)
        
        if df_synced.empty:
            logger.warning("no_matching_skus_found")
            raise DataProcessingError(
                "No SKUs match between Flexxus and Magento",
                operation="synchronize"
            )
        
        # Apply stock overrides if enabled
        if apply_overrides:
            df_synced = self.apply_stock_overrides(df_synced)
        
        # Export result
        output_path = self.export_synced_data(df_synced)
        
        logger.info(
            "synchronization_complete",
            output_path=output_path,
            total_skus=len(df_synced)
        )
        
        return output_path
    
    def get_statistics(self, df: pd.DataFrame) -> Dict[str, any]:
        """Get statistics about the synchronized data.
        
        Args:
            df: Synchronized DataFrame
            
        Returns:
            Dictionary with statistics
        """
        return {
            "total_skus": len(df),
            "total_qty": int(df['qty'].sum()),
            "avg_qty": float(df['qty'].mean()),
            "min_price": float(df['price'].min()),
            "max_price": float(df['price'].max()),
            "avg_price": float(df['price'].mean()),
            "stock_overrides_applied": len([
                sku for sku in df['sku'] 
                if sku in [normalize_sku(k) for k in FIXED_STOCK_OVERRIDES.keys()]
            ])
        }
