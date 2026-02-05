"""Google Merchant Center Feed Generator.

This module provides the GoogleMerchantFeed class for generating
TSV feeds compatible with Google Merchant Center.
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime

import pandas as pd
import structlog

from ..utils.helpers import get_custom_attribute
from ..core.exceptions import DataProcessingError, FileNotFoundError

logger = structlog.get_logger(__name__)


class GoogleMerchantFeed:
    """Generate Google Merchant Center product feeds.
    
    This class handles the conversion of Magento product data to
    Google Merchant Center TSV format.
    
    Example:
        >>> feed = GoogleMerchantFeed(
        ...     categories_file_path="input/google_categories.txt",
        ...     output_path="output/"
        ... )
        >>> feed.generate(products_df)
    """
    
    # Default values for required fields
    DEFAULT_DESCRIPTION = "Para mas informacion, visite nuestro sitio web"
    DEFAULT_CONDITION = "new"
    DEFAULT_AVAILABILITY = "in_stock"
    DEFAULT_CURRENCY = "ARS"
    DEFAULT_BRAND = "Generico"
    DEFAULT_CATEGORY = "Hardware > Building Materials"
    
    # URL configuration
    BASE_URL = "https://giliycia.com.ar"
    MEDIA_BASE_URL = "https://giliycia.com.ar/media/catalog/product"
    
    # Required columns in output
    REQUIRED_COLUMNS = [
        'id', 'title', 'description', 'link', 'image_link',
        'availability', 'price', 'brand', 'google_product_category',
        'product_type', 'condition'
    ]
    
    def __init__(
        self,
        categories_file_path: str,
        output_path: str,
        base_url: Optional[str] = None,
        media_base_url: Optional[str] = None
    ) -> None:
        """Initialize the merchant feed generator.
        
        Args:
            categories_file_path: Path to Google categories taxonomy file
            output_path: Directory path for output TSV file
            base_url: Base URL for product links (default: giliycia.com.ar)
            media_base_url: Base URL for product images
        """
        self.categories_file_path = categories_file_path
        self.output_path = output_path
        self.base_url = base_url or self.BASE_URL
        self.media_base_url = media_base_url or self.MEDIA_BASE_URL
        
        logger.debug(
            "merchant_feed_initialized",
            categories_file=categories_file_path,
            output_path=output_path
        )
    
    def load_google_categories(self) -> List[str]:
        """Load Google product categories taxonomy.
        
        Returns:
            List of category strings
            
        Raises:
            FileNotFoundError: If categories file not found
        """
        if not os.path.exists(self.categories_file_path):
            logger.warning(
                "categories_file_not_found",
                path=self.categories_file_path
            )
            return []
        
        try:
            categories = []
            with open(self.categories_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(' - ', 1)
                    if len(parts) > 1:
                        categories.append(parts[1])
                    else:
                        categories.append(line.strip())
            
            logger.debug(
                "categories_loaded",
                count=len(categories)
            )
            return categories
            
        except Exception as e:
            logger.error(
                "failed_to_load_categories",
                error=str(e)
            )
            return []
    
    def _extract_product_data(self, row: pd.Series) -> Dict[str, Any]:
        """Extract and format product data from DataFrame row.
        
        Args:
            row: Product DataFrame row
            
        Returns:
            Dictionary with formatted product data
        """
        # Basic product info
        sku = row.get('sku', '')
        name = row.get('name', '')
        brand = row.get('brand', self.DEFAULT_BRAND)
        
        # Handle empty brand
        if not brand or brand == 'Sin Marca':
            brand = self.DEFAULT_BRAND
        
        # Price formatting
        price_val = row.get('price', 0)
        price_str = f"{price_val:.2f} {self.DEFAULT_CURRENCY}".replace('.', ',')
        
        # Product URL
        url_key = row.get('url_key')
        if url_key:
            link = f"{self.base_url}/{url_key}.html"
        else:
            product_id = row.get('id', '')
            link = f"{self.base_url}/catalog/product/view/id/{product_id}"
        
        # Image URL
        image_path = row.get('image', '')
        image_link = f"{self.media_base_url}{image_path}" if image_path else ""
        
        # Category - currently using fixed category for performance
        # TODO: Implement smart category matching if needed
        google_category = self.DEFAULT_CATEGORY
        product_type = row.get('categories', '')
        
        return {
            'id': sku,
            'title': name,
            'description': self.DEFAULT_DESCRIPTION,
            'link': link,
            'image_link': image_link,
            'availability': self.DEFAULT_AVAILABILITY,
            'price': price_str,
            'brand': brand,
            'google_product_category': google_category,
            'product_type': product_type,
            'condition': self.DEFAULT_CONDITION
        }
    
    def generate(self, products_df: pd.DataFrame) -> str:
        """Generate Google Merchant Center TSV file.
        
        Args:
            products_df: DataFrame with product data from Magento
            
        Returns:
            Path to generated TSV file
            
        Raises:
            DataProcessingError: If generation fails
            FileNotFoundError: If output directory doesn't exist
        """
        if products_df.empty:
            logger.warning("empty_product_dataframe")
            raise DataProcessingError(
                "Cannot generate feed: empty product DataFrame",
                operation="generate"
            )
        
        # Check output directory exists
        if not os.path.exists(self.output_path):
            logger.error(
                "output_directory_not_found",
                path=self.output_path
            )
            raise FileNotFoundError(
                self.output_path,
                file_type="output directory"
            )
        
        logger.info(
            "generating_merchant_feed",
            product_count=len(products_df)
        )
        
        # Load categories (for logging purposes)
        google_categories = self.load_google_categories()
        if google_categories:
            logger.info(
                "google_categories_loaded",
                count=len(google_categories)
            )
        
        # Process products
        merchant_rows = []
        total = len(products_df)
        
        for index, row in products_df.iterrows():
            try:
                product_data = self._extract_product_data(row)
                merchant_rows.append(product_data)
                
                # Log progress every 500 items
                if (index + 1) % 500 == 0:
                    logger.info(
                        "processing_progress",
                        processed=index + 1,
                        total=total,
                        percentage=f"{(index + 1) / total * 100:.1f}%"
                    )
                    
            except Exception as e:
                logger.error(
                    "failed_to_process_product",
                    index=index,
                    sku=row.get('sku', 'unknown'),
                    error=str(e)
                )
                continue
        
        # Create DataFrame
        df_merchant = pd.DataFrame(merchant_rows)
        
        if df_merchant.empty:
            raise DataProcessingError(
                "No products could be processed",
                operation="generate"
            )
        
        # Ensure all required columns exist
        for col in self.REQUIRED_COLUMNS:
            if col not in df_merchant.columns:
                df_merchant[col] = ''
        
        # Reorder columns
        df_merchant = df_merchant[self.REQUIRED_COLUMNS]
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"merchant_feed_{timestamp}.tsv"
        full_path = os.path.join(self.output_path, filename)
        
        # Save to TSV
        try:
            df_merchant.to_csv(
                full_path,
                sep='\t',
                index=False,
                encoding='utf-8'
            )
            
            logger.info(
                "merchant_feed_generated",
                path=full_path,
                product_count=len(df_merchant)
            )
            
            return full_path
            
        except Exception as e:
            logger.error(
                "failed_to_save_feed",
                path=full_path,
                error=str(e)
            )
            raise DataProcessingError(
                f"Failed to save merchant feed: {e}",
                operation="generate"
            )
    
    def validate_feed(self, file_path: str) -> bool:
        """Validate generated feed file.
        
        Args:
            file_path: Path to TSV file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            df = pd.read_csv(file_path, sep='\t')
            
            # Check required columns
            missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
            if missing_cols:
                logger.error(
                    "missing_required_columns",
                    columns=list(missing_cols)
                )
                return False
            
            # Check for empty required fields
            empty_counts = {}
            for col in ['id', 'title', 'price']:
                empty_count = df[col].isna().sum() + (df[col] == '').sum()
                if empty_count > 0:
                    empty_counts[col] = empty_count
            
            if empty_counts:
                logger.warning(
                    "empty_required_fields",
                    counts=empty_counts
                )
            
            logger.info(
                "feed_validation_complete",
                file=file_path,
                rows=len(df),
                valid=True
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "feed_validation_failed",
                file=file_path,
                error=str(e)
            )
            return False
