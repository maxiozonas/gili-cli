"""Manual Update Operation - Actualización masiva de descripciones cortas."""

import time
from typing import List, Dict, Optional
from tqdm import tqdm
import structlog

from ..core.client import MagentoAPIClient
from ..config.settings import Settings

logger = structlog.get_logger(__name__)

DEFAULT_HTML = '''<p><a title="Recomendaciones para la colocación de pisos" href="https://drive.google.com/file/d/1u6OW9ErzEI5On8F_KigUj0wRYSZhBsar/view" target="_blank" rel="noopener"> <span style="color: #de0b0b;"> <strong> Hacé clic y accedé a nuestro manual de recomendaciones </strong> <img src="https://giliycia.com.ar/media/wysiwyg/Servicios/pdf_icon.png" alt="" /> </span> </a></p>'''


def get_short_description(product: Dict) -> str:
    """Extract short description from product custom attributes."""
    for attr in product.get("custom_attributes", []):
        if attr.get("attribute_code") == "short_description":
            return attr.get("value", "").strip() or ""
    return ""


def has_category(product: Dict, category_id: int) -> bool:
    """Check if product has specific category."""
    for attr in product.get("custom_attributes", []):
        if attr.get("attribute_code") == "category_ids":
            category_ids = attr.get("value", [])
            if isinstance(category_ids, list):
                return str(category_id) in [str(c) for c in category_ids]
            elif isinstance(category_ids, str):
                return str(category_id) in category_ids.split(",")
    return False


def run_manual_update(
    settings: Settings,
    category_id: int = 737,
    html_content: Optional[str] = None,
    dry_run: bool = True
) -> Dict:
    """Execute manual update operation for products without short description.
    
    Args:
        settings: Application settings
        category_id: Category ID to process (default: 737 - Pisos y revestimientos)
        html_content: HTML content to inject (uses default if None)
        dry_run: If True, only preview without applying changes
        
    Returns:
        Dictionary with operation results
    """
    logger.info("manual_update_started", category_id=category_id, dry_run=dry_run)
    
    html_content = html_content or DEFAULT_HTML
    
    client = MagentoAPIClient(settings)
    client.authenticate()
    
    store_views = client.get_store_views()
    if not store_views:
        store_views = [{"code": "default", "name": "Default Store View"}]
    
    logger.info("store_views_found", count=len(store_views))
    
    products = list(client.get_products_by_category(category_id))
    logger.info("products_in_category", count=len(products))
    
    products_to_update = []
    for product in products:
        if not has_category(product, category_id):
            continue
        
        sku = product.get("sku")
        name = product.get("name")
        short_desc = get_short_description(product)
        
        if not short_desc:
            products_to_update.append({
                "sku": sku,
                "name": name
            })
    
    logger.info("products_without_short_description", count=len(products_to_update))
    
    if dry_run:
        logger.info("dry_run_mode", products_would_update=len(products_to_update))
        return {
            "success": True,
            "dry_run": True,
            "total_products_in_category": len(products),
            "products_to_update": len(products_to_update),
            "products_preview": products_to_update[:10]
        }
    
    if not products_to_update:
        logger.info("no_products_to_update")
        return {
            "success": True,
            "message": "Todos los productos ya tienen descripción corta"
        }
    
    stores_to_update = ["all"]
    stores_to_update.extend([s["code"] for s in store_views])
    
    logger.info("updating_stores", stores=stores_to_update)
    
    success_count = 0
    error_count = 0
    errors_detail = []
    
    for product in tqdm(products_to_update, desc="Actualizando productos"):
        sku = product["sku"]
        product_success = True
        failed_stores = []
        
        for store_code in stores_to_update:
            if not client.update_product_short_description(sku, html_content, store_code):
                product_success = False
                failed_stores.append(store_code)
            time.sleep(0.05)
        
        if product_success:
            success_count += 1
        else:
            error_count += 1
            errors_detail.append({
                "sku": sku,
                "name": product["name"],
                "failed_stores": failed_stores
            })
        
        time.sleep(0.1)
    
    result = {
        "success": error_count == 0,
        "dry_run": False,
        "total_products_in_category": len(products),
        "products_updated": success_count,
        "products_failed": error_count,
        "errors": errors_detail[:5]
    }
    
    logger.info("manual_update_completed", **result)
    return result
