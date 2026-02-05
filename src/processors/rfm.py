"""RFM Analysis Processor.

This module provides the RFMProcessor class for calculating Recency, Frequency,
and Monetary value metrics from customer order data.
"""

from typing import Tuple, Optional, List
from datetime import datetime
from dataclasses import dataclass

import pandas as pd
import numpy as np
import structlog

from ..utils.helpers import clean_category, format_date_to_dmy, format_to_comma_decimal
from ..core.exceptions import DataProcessingError
from tqdm import tqdm

logger = structlog.get_logger(__name__)


@dataclass
class RFMMetrics:
    """Container for RFM metrics of a customer."""
    recency_days: int
    frequency: int
    ltv_total: float
    avg_order_value: float
    max_order_value: float
    min_order_value: float
    avg_monthly_ticket: float
    days_as_customer: int
    avg_days_between_purchases: Optional[float]
    first_purchase_date: datetime
    last_purchase_date: datetime


class RFMProcessor:
    """Process customer data to calculate RFM metrics.
    
    This class handles the complete pipeline of RFM analysis including:
    - Data cleaning and normalization
    - RFM metric calculations
    - Product preference analysis
    - Final DataFrame assembly
    
    Example:
        >>> processor = RFMProcessor(min_year=2024)
        >>> df_rfm = processor.process(
        ...     customers=df_customers,
        ...     orders=df_orders,
        ...     catalog=df_catalog,
        ...     items=df_items
        ... )
    """
    
    # Column definitions
    # Note: These are the output column names, not Magento API field names
    CLIENT_COLS = [
        'id', 'email', 'created_at',
        'Name',
        'Phone', 'Postal_Code', 'Es_Bahia_Blanca', 'Tax_VAT_Number', 'VAT_Number'
    ]

    ORDER_COLS = [
        'ID', 'Customer Email', 'Purchase Date',
        'Grand Total (Purchased)', 'Status', 'Payment_Method'
    ]
    
    def __init__(self, min_year: int) -> None:
        """Initialize the RFM processor.
        
        Args:
            min_year: Minimum year for order inclusion
        """
        self.min_year = min_year
        self.current_date = datetime.now()
        logger.info("rfm_processor_initialized", min_year=min_year)
    
    def process(
        self,
        customers: pd.DataFrame,
        orders: pd.DataFrame,
        catalog: pd.DataFrame,
        items: pd.DataFrame
    ) -> pd.DataFrame:
        """Execute the complete RFM processing pipeline.
        
        Args:
            customers: Customer data from Magento
            orders: Order data from Magento
            catalog: Product catalog data
            items: Order items data
            
        Returns:
            DataFrame with complete RFM analysis
            
        Raises:
            DataProcessingError: If processing fails
        """
        try:
            logger.info("starting_rfm_processing")
            
            # Step 1: Clean and prepare data
            customers, orders = self._clean_data(customers, orders)
            
            # Step 2: Calculate RFM metrics
            df_rfm = self._calculate_rfm_metrics(orders)
            
            # Step 3: Calculate additional KPIs
            df_kpis = self._calculate_additional_kpis(orders)
            
            # Step 4: Analyze product preferences
            df_prefs = self._analyze_preferences(items, catalog, orders)
            
            # Step 5: Merge all data
            df_final = self._merge_all_data(customers, df_rfm, df_kpis, df_prefs)
            
            # Step 6: Final formatting
            df_final = self._format_output(df_final)
            
            logger.info("rfm_processing_complete", rows=len(df_final))
            return df_final
            
        except Exception as e:
            logger.error("rfm_processing_failed", error=str(e))
            raise DataProcessingError(
                f"RFM processing failed: {e}",
                operation="process"
            )
    
    def _clean_data(
        self,
        customers: pd.DataFrame,
        orders: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Clean and normalize input data.

        Args:
            customers: Raw customer data from Magento API
            orders: Order data with pre-mapped columns from API client

        Returns:
            Tuple of cleaned (customers, orders) DataFrames
        """
        logger.debug("cleaning_data")

        # Extract customer fields from Magento API structure
        customers = self._extract_customer_fields(customers)

        # Normalize emails
        customers['email'] = customers['email'].astype(str).str.lower()
        
        # Orders already have Customer Email from client - just normalize
        orders['Customer Email'] = orders['Customer Email'].astype(str).str.lower()

        # Parse dates - client already mapped to 'Purchase Date'
        orders['Purchase Date'] = pd.to_datetime(
            orders['Purchase Date'].str.split(' ').str[0],
            errors='coerce',
            format='%Y-%m-%d'
        )
        customers['created_at'] = pd.to_datetime(
            customers['created_at'].str.split(' ').str[0],
            errors='coerce',
            format='%Y-%m-%d'
        )

        # Convert Grand Total to numeric (client already mapped column)
        orders['Grand Total (Purchased)'] = pd.to_numeric(
            orders['Grand Total (Purchased)'], 
            errors='coerce'
        ).fillna(0)
        
        # Filter by year
        orders = orders[orders['Purchase Date'].dt.year >= self.min_year]

        logger.debug("data_cleaned", orders_count=len(orders))
        return customers, orders

    def _extract_customer_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and transform customer fields from Magento API.

        Magento returns fields like: email, firstname, lastname, addresses, taxvat
        We need to transform these to match the expected output format.

        Args:
            df: Raw customer DataFrame from Magento

        Returns:
            DataFrame with extracted and transformed fields
        """
        logger.debug("extracting_customer_fields")

        df = df.copy()

        # Create Name from firstname + lastname
        df['Name'] = (df['firstname'].fillna('') + ' ' + df['lastname'].fillna('')).str.strip()
        df['Name'] = df['Name'].replace('', 'Sin Nombre')

        # Extract phone and postal code from addresses
        def extract_from_addresses(addresses, field):
            """Extract field from first address."""
            if isinstance(addresses, list) and len(addresses) > 0:
                return addresses[0].get(field, '')
            return ''

        df['Phone'] = df['addresses'].apply(lambda x: extract_from_addresses(x, 'telephone'))
        df['Postal_Code'] = df['addresses'].apply(lambda x: extract_from_addresses(x, 'postcode'))

        # Calculate Es_Bahia_Blanca from postal code
        df['Es_Bahia_Blanca'] = df['Postal_Code'].apply(
            lambda x: 'Si' if '8000' in str(x) else 'No'
        )

        # Map taxvat to Tax_VAT_Number and VAT_Number
        df['Tax_VAT_Number'] = df['taxvat'].fillna('')
        df['VAT_Number'] = df['taxvat'].fillna('')

        # Ensure ID is string
        df['ID'] = df['id'].astype(str)

        # Map email to Customer Email format for merging
        df['Customer Email'] = df['email']

        logger.debug("customer_fields_extracted", rows=len(df))
        return df
    
    def _calculate_rfm_metrics(self, orders: pd.DataFrame) -> pd.DataFrame:
        """Calculate core RFM metrics.
        
        Args:
            orders: Cleaned order data
            
        Returns:
            DataFrame with RFM metrics per customer
        """
        logger.debug("calculating_rfm_metrics")
        
        # Recency
        df_recency = orders.groupby('Customer Email')['Purchase Date'].max().reset_index()
        df_recency['Recencia_Fecha'] = df_recency['Purchase Date']
        df_recency['Recencia_Dias'] = (
            self.current_date - df_recency['Recencia_Fecha']
        ).dt.days
        
        # Frequency and Monetary
        df_fm = orders.groupby('Customer Email').agg(
            Frecuencia=('ID', 'count'),
            LTV_Gasto_Total=('Grand Total (Purchased)', 'sum'),
            Gasto_Promedio_Compra=('Grand Total (Purchased)', 'mean'),
            Gasto_Maximo_Compra=('Grand Total (Purchased)', 'max'),
            Gasto_Minimo_Compra=('Grand Total (Purchased)', 'min'),
            Primera_Compra_Fecha=('Purchase Date', 'min')
        ).reset_index()
        
        # Calculate derived metrics
        df_fm['Dias_Como_Cliente'] = (
            self.current_date - df_fm['Primera_Compra_Fecha']
        ).dt.days.replace(0, 1)
        
        df_fm['Ticket_Promedio_Mensual'] = (
            df_fm['LTV_Gasto_Total'] / (df_fm['Dias_Como_Cliente'] / 30.416)
        ).fillna(0)
        
        # Merge recency with frequency/monetary
        df_rfm = df_fm.merge(
            df_recency[['Customer Email', 'Recencia_Fecha', 'Recencia_Dias']], 
            on='Customer Email', 
            how='left'
        )
        
        logger.debug("rfm_metrics_calculated", customers=len(df_rfm))
        return df_rfm
    
    def _calculate_additional_kpis(self, orders: pd.DataFrame) -> pd.DataFrame:
        """Calculate additional KPIs beyond basic RFM.
        
        Args:
            orders: Cleaned order data
            
        Returns:
            DataFrame with additional KPIs
        """
        logger.debug("calculating_additional_kpis")
        
        # Time between purchases
        def calculate_avg_time_between_purchases(dates: pd.Series) -> Optional[float]:
            dates = dates.sort_values().to_list()
            if len(dates) <= 1:
                return None
            diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            return np.mean(diffs)
        
        df_tpec = orders.groupby('Customer Email')['Purchase Date'].apply(
            calculate_avg_time_between_purchases
        ).reset_index(name='Tiempo_Promedio_Entre_Compras')
        
        # Quarterly purchase tracking
        df_quarterly = orders.groupby('Customer Email')['Purchase Date'].agg(
            lambda x: x.max().to_period('Q').strftime('%Y-Q%q')
        ).reset_index(name='Ultimo_Trimestre_Compra')
        
        # Preferred day of week
        df_day = orders.copy()
        df_day['Dia_Semana'] = df_day['Purchase Date'].dt.dayofweek
        day_map = {
            0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 
            3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
        }
        
        df_day_freq = df_day.groupby('Customer Email')['Dia_Semana'].apply(
            lambda x: day_map.get(x.mode()[0], 'N/A')
        ).reset_index(name='Dia_Semana_Max_Frec')
        
        # Merge all KPIs
        df_kpis = df_tpec.merge(df_quarterly, on='Customer Email', how='left')
        df_kpis = df_kpis.merge(df_day_freq, on='Customer Email', how='left')
        
        logger.debug("additional_kpis_calculated")
        return df_kpis
    
    def _analyze_preferences(
        self,
        items: pd.DataFrame,
        catalog: pd.DataFrame,
        orders: pd.DataFrame
    ) -> pd.DataFrame:
        """Analyze customer product and category preferences.

        Args:
            items: Order items data with customer_email from API client
            catalog: Product catalog data
            orders: Order data (for invoice A detection)

        Returns:
            DataFrame with preference data
        """
        logger.debug("analyzing_preferences")

        # Normalize SKUs
        items['sku'] = items['sku'].astype(str).str.strip().str.replace(' ', '').str.zfill(5)
        catalog['sku'] = catalog['sku'].astype(str).str.strip().str.replace(' ', '').str.zfill(5)

        # Items already have customer_email from API client
        # Just rename to standard column name
        df_items = items.copy()
        df_items.rename(columns={'customer_email': 'Customer Email'}, inplace=True)

        # Merge items with catalog
        df_items = df_items.merge(
            catalog[['sku', 'categories', 'brand', 'product_name']],
            on='sku',
            how='left'
        )

        # Clean categories and brands
        df_items['Categoria_Limpia'] = df_items['categories'].apply(clean_category)
        df_items['brand'] = df_items['brand'].fillna('Sin Marca')

        # Ensure email column exists and is clean
        df_items = df_items.dropna(subset=['Customer Email'])
        df_items['Customer Email'] = df_items['Customer Email'].astype(str).str.lower()
        
        # Category preferences
        df_cat_qty = df_items.groupby(['Customer Email', 'Categoria_Limpia'])['qty_ordered'].sum().reset_index()
        df_cat_pref = df_cat_qty.loc[df_cat_qty.groupby('Customer Email')['qty_ordered'].idxmax()].copy()
        df_cat_pref.rename(columns={'Categoria_Limpia': 'Categoria_Preferida'}, inplace=True)
        df_cat_pref = df_cat_pref[['Customer Email', 'Categoria_Preferida']]
        
        # List of all categories purchased
        df_cat_list = df_items.groupby('Customer Email')['Categoria_Limpia'].apply(
            lambda x: ', '.join(x.unique())
        ).reset_index(name='Lista_Categorias_Compradas')
        
        # Brand preferences
        df_brand_qty = df_items.groupby(['Customer Email', 'brand'])['qty_ordered'].sum().reset_index()
        df_brand_pref = df_brand_qty.loc[df_brand_qty.groupby('Customer Email')['qty_ordered'].idxmax()].copy()
        df_brand_pref.rename(columns={'brand': 'Marca_Preferida'}, inplace=True)
        df_brand_pref = df_brand_pref[['Customer Email', 'Marca_Preferida']]
        
        # List of all brands purchased
        df_brand_list = df_items.groupby('Customer Email')['brand'].apply(
            lambda x: ', '.join(x.unique())
        ).reset_index(name='Lista_Marcas_Compradas')
        
        # Favorite product (by quantity)
        df_prod_qty = df_items.groupby(['Customer Email', 'sku']).agg(
            Total_Qty=('qty_ordered', 'sum'),
            Total_Row=('row_total', 'sum')
        ).reset_index()
        
        df_prod_fav = df_prod_qty.loc[df_prod_qty.groupby('Customer Email')['Total_Qty'].idxmax()].copy()
        df_prod_fav.rename(
            columns={'sku': 'Producto_Favorito_SKU', 'Total_Qty': 'Producto_Favorito_Qty'}, 
            inplace=True
        )
        df_prod_fav = df_prod_fav[['Customer Email', 'Producto_Favorito_SKU', 'Producto_Favorito_Qty']]
        
        # Add product name
        df_prod_fav = df_prod_fav.merge(
            catalog[['sku', 'product_name']], 
            left_on='Producto_Favorito_SKU', 
            right_on='sku', 
            how='left'
        ).rename(columns={'product_name': 'Producto_Favorito_Nombre'}).drop(columns=['sku'])
        
        # Count unique products purchased
        df_unique_prod = df_items.groupby('Customer Email')['sku'].nunique().reset_index(
            name='Total_Productos_Unicos'
        )
        
        # Order history mapping
        df_history = orders.sort_values(by='Purchase Date', ascending=False).groupby('Customer Email').apply(
            lambda x: '; '.join([
                f"{row['ID']} ({format_to_comma_decimal(row['Grand Total (Purchased)'])} {row['Status']})" 
                for _, row in x.iterrows()
            ])
        ).reset_index(name='Historial_Ordenes_Mapeo')
        
        # Invoice A detection
        logger.debug("detecting_invoice_a_customers")
        df_invoice_a = self._detect_invoice_a(orders)
        
        # Merge all preference data
        df_prefs = df_cat_pref.merge(df_cat_list, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_brand_pref, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_brand_list, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_prod_fav, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_unique_prod, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_history, on='Customer Email', how='left')
        df_prefs = df_prefs.merge(df_invoice_a, on='Customer Email', how='left')
        
        logger.debug("preferences_analyzed")
        return df_prefs
    
    def _detect_invoice_a(self, orders: pd.DataFrame) -> pd.DataFrame:
        """Detect customers with Invoice A.
        
        Args:
            orders: Order data with payment method
            
        Returns:
            DataFrame with Invoice A flag per customer
        """
        if 'Payment_Method' not in orders.columns:
            return pd.DataFrame({'Customer Email': [], 'Tiene_Factura_A': []})
        
        # Check which customers have at least one Invoice A order
        has_invoice_a = orders.groupby('Customer Email')['Payment_Method'].apply(
            lambda x: x.astype(str).str.contains('Factura A', case=False, na=False).any()
        ).reset_index()
        
        has_invoice_a['Tiene_Factura_A'] = has_invoice_a['Payment_Method'].apply(
            lambda x: 'Sí' if x else 'No'
        )
        
        return has_invoice_a[['Customer Email', 'Tiene_Factura_A']]
    
    def _merge_all_data(
        self,
        customers: pd.DataFrame,
        df_rfm: pd.DataFrame,
        df_kpis: pd.DataFrame,
        df_prefs: pd.DataFrame
    ) -> pd.DataFrame:
        """Merge all calculated data into final DataFrame.
        
        Args:
            customers: Cleaned customer data
            df_rfm: RFM metrics
            df_kpis: Additional KPIs
            df_prefs: Preference data
            
        Returns:
            Merged DataFrame
        """
        logger.debug("merging_all_data")
        
        # Start with RFM metrics
        df_final = df_rfm.copy()
        
        # Merge KPIs
        df_final = df_final.merge(df_kpis, on='Customer Email', how='left')
        
        # Merge preferences
        df_final = df_final.merge(df_prefs, on='Customer Email', how='left')
        
        # Merge customer info
        customer_cols = [
            'email', 'Name', 'ID', 'Phone', 'Postal_Code',
            'Es_Bahia_Blanca', 'Tax_VAT_Number', 'VAT_Number', 'created_at'
        ]
        df_final = customers[customer_cols].merge(
            df_final,
            left_on='email',
            right_on='Customer Email',
            how='inner'
        ).drop(columns=['email'])
        
        logger.debug("data_merged", final_rows=len(df_final))
        return df_final
    
    def _format_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format the final output DataFrame.
        
        Args:
            df: Merged data DataFrame
            
        Returns:
            Formatted DataFrame with proper column names and types
        """
        logger.debug("formatting_output")
        
        # Format dates
        df['Recencia_Fecha'] = df['Recencia_Fecha'].apply(format_date_to_dmy)
        df['Primera_Compra_Fecha'] = df['Primera_Compra_Fecha'].apply(format_date_to_dmy)
        df['Cliente_Desde'] = df['created_at'].apply(format_date_to_dmy)
        df.drop(columns=['created_at'], inplace=True)
        
        # Format currency columns
        numeric_cols = [
            'LTV_Gasto_Total', 'Gasto_Promedio_Compra', 
            'Gasto_Maximo_Compra', 'Gasto_Minimo_Compra',
            'Ticket_Promedio_Mensual'
        ]
        for col in numeric_cols:
            df[col] = df[col].fillna(0).astype(float).apply(format_to_comma_decimal)
        
        # Rename columns to Spanish
        df.rename(columns={
            'Phone': 'Telefono',
            'Postal_Code': 'Codigo_Postal',
            'Tax VAT Number': 'Tax_VAT_Number',
            'VAT Number': 'VAT_Number'
        }, inplace=True)
        
        # Ensure Name column exists
        if 'Name' not in df.columns:
            df['Name'] = 'Sin Nombre'
        
        # Define final column order
        final_cols = [
            'Name', 'Customer Email', 'ID', 'Cliente_Desde', 
            'Telefono', 'Codigo_Postal', 'Es_Bahia_Blanca', 
            'Tax_VAT_Number', 'VAT_Number', 'Tiene_Factura_A',
            'LTV_Gasto_Total', 'Ticket_Promedio_Mensual', 
            'Gasto_Promedio_Compra', 'Gasto_Maximo_Compra', 'Gasto_Minimo_Compra',
            'Frecuencia', 'Recencia_Fecha', 'Recencia_Dias', 
            'Tiempo_Promedio_Entre_Compras',
            'Primera_Compra_Fecha', 'Dias_Como_Cliente',
            'Ultimo_Trimestre_Compra', 'Dia_Semana_Max_Frec', 
            'Categoria_Preferida', 'Lista_Categorias_Compradas',
            'Marca_Preferida', 'Lista_Marcas_Compradas', 
            'Total_Productos_Unicos',
            'Producto_Favorito_SKU', 'Producto_Favorito_Nombre', 'Producto_Favorito_Qty',
            'Historial_Ordenes_Mapeo'
        ]
        
        # Add missing columns with 'N/A'
        for col in final_cols:
            if col not in df.columns:
                df[col] = 'N/A'
        
        # Reorder columns
        df = df[final_cols]
        
        logger.debug("output_formatted")
        return df
    
    def sort_by(
        self, 
        df: pd.DataFrame, 
        sort_col: str, 
        ascending: bool = False
    ) -> pd.DataFrame:
        """Sort the RFM DataFrame by a specific column.
        
        Args:
            df: RFM DataFrame
            sort_col: Column name to sort by
            ascending: Sort direction
            
        Returns:
            Sorted DataFrame
        """
        if sort_col in df.columns:
            return df.sort_values(by=sort_col, ascending=ascending)
        logger.warning("sort_column_not_found", column=sort_col)
        return df
