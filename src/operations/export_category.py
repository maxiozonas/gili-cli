"""Export Category Operation - Exportar productos de categoría a CSV."""

from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
import structlog

from ..core.client import MagentoAPIClient
from ..config.settings import Settings

logger = structlog.get_logger(__name__)


def get_custom_attribute(product: Dict, attribute_code: str) -> str:
    """Get value of a custom attribute from product."""
    for attr in product.get("custom_attributes", []):
        if attr.get("attribute_code") == attribute_code:
            return attr.get("value", "") or ""
    return ""


def get_brand_from_product(product: Dict, brand_map: Dict[str, str]) -> str:
    """Extract brand name from product."""
    brand_id = str(get_custom_attribute(product, "brand"))
    if brand_id:
        return brand_map.get(brand_id, "")
    return ""


def get_product_status(product: Dict) -> str:
    """Get product status (enabled/disabled)."""
    status = product.get("status", 1)
    return "true" if status == 1 else "false"


def generate_csv(products: List[Dict], brand_map: Dict[str, str]) -> pd.DataFrame:
    """Generate CSV data from products."""
    csv_data = []
    
    for product in products:
        sku = product.get("sku", "")
        name = product.get("name", "")
        brand = get_brand_from_product(product, brand_map)
        status = get_product_status(product)
        url_key = get_custom_attribute(product, "url_key")
        
        csv_data.append({
            "sku": sku,
            "articulo": name,
            "marca": brand,
            "habilitado": status,
            "url-key": url_key
        })
    
    return pd.DataFrame(csv_data)


def run_export_category(
    settings: Settings,
    category_id: int,
    output_path: Optional[str] = None
) -> Dict:
    """Execute export category operation.
    
    Args:
        settings: Application settings
        category_id: Category ID to export
        output_path: Optional output file path (auto-generated if None)
        
    Returns:
        Dictionary with operation results and CSV data
    """
    logger.info("export_category_started", category_id=category_id)
    
    client = MagentoAPIClient(settings)
    client.authenticate()
    
    brand_map = client.get_brand_map()
    logger.info("brands_fetched", count=len(brand_map))
    
    products = list(client.get_products_by_category(category_id))
    logger.info("products_fetched", count=len(products))
    
    if not products:
        return {
            "success": True,
            "message": f"No se encontraron productos en la categoría {category_id}",
            "products_count": 0
        }
    
    df = generate_csv(products, brand_map)
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"productos_categoria_{category_id}_{timestamp}.csv"
    
    output_file = Path(output_path)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    
    logger.info("csv_saved", path=str(output_file))
    
    result = {
        "success": True,
        "category_id": category_id,
        "products_count": len(products),
        "output_path": str(output_file),
        "csv_data": df.head(10).to_dict("records")
    }
    
    logger.info("export_category_completed", **result)
    return result
