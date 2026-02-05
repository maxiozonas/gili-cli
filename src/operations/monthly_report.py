"""Monthly Report Operation - Reporte mensual de productos cargados."""

import calendar
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import pandas as pd
import structlog

from ..core.client import MagentoAPIClient
from ..config.settings import Settings

logger = structlog.get_logger(__name__)

OBJ_PRODUCTOS = 240
OBJ_UPSELLING = 240
OBJ_CROSSSELLING = 240


def get_brand_from_product(product: Dict, brand_map: Dict[str, str]) -> str:
    """Extract brand name from product."""
    for attr in product.get("custom_attributes", []):
        if attr.get("attribute_code") == "brand":
            brand_id = str(attr.get("value", ""))
            if brand_id:
                return brand_map.get(brand_id, "Sin marca")
    return "Sin marca"


def count_product_links(product: Dict) -> tuple:
    """Count crosssell and upsell links from product."""
    product_links = product.get("product_links", [])
    crosssell = sum(1 for link in product_links if link.get("link_type") == "crosssell")
    upsell = sum(1 for link in product_links if link.get("link_type") == "upsell")
    return crosssell, upsell


def generate_report(products: List[Dict], brand_map: Dict[str, str]) -> pd.DataFrame:
    """Generate the monthly report DataFrame."""
    report_data = []
    
    for product in products:
        brand = get_brand_from_product(product, brand_map)
        crosssell, upsell = count_product_links(product)
        
        report_data.append({
            "Marca": brand,
            "Productos": 1,
            "Crossselling": crosssell,
            "Upselling": upsell
        })
    
    df = pd.DataFrame(report_data)
    
    if df.empty:
        return df
    
    df_grouped = df.groupby("Marca", as_index=False).agg({
        "Productos": "sum",
        "Crossselling": "sum",
        "Upselling": "sum"
    })
    
    df_grouped = df_grouped.sort_values("Marca")
    
    total_row = pd.DataFrame([{
        "Marca": "Total",
        "Productos": df_grouped["Productos"].sum(),
        "Crossselling": df_grouped["Crossselling"].sum(),
        "Upselling": df_grouped["Upselling"].sum()
    }])
    
    return pd.concat([df_grouped, total_row], ignore_index=True)


def generate_summary(df_report: pd.DataFrame) -> pd.DataFrame:
    """Generate summary with objectives vs actual."""
    if df_report.empty:
        return pd.DataFrame()
    
    total_productos = df_report[df_report["Marca"] == "Total"]["Productos"].values[0]
    total_upselling = df_report[df_report["Marca"] == "Total"]["Upselling"].values[0]
    total_crossselling = df_report[df_report["Marca"] == "Total"]["Crossselling"].values[0]
    total_general = total_productos + total_upselling + total_crossselling
    
    summary = pd.DataFrame([
        {
            "Categoría": "Productos",
            "Actual": total_productos,
            "Objetivo": OBJ_PRODUCTOS,
            "Porcentaje": round((total_productos / OBJ_PRODUCTOS) * 100, 2) if OBJ_PRODUCTOS > 0 else 0
        },
        {
            "Categoría": "UpSelling",
            "Actual": total_upselling,
            "Objetivo": OBJ_UPSELLING,
            "Porcentaje": round((total_upselling / OBJ_UPSELLING) * 100, 2) if OBJ_UPSELLING > 0 else 0
        },
        {
            "Categoría": "CrossSelling",
            "Actual": total_crossselling,
            "Objetivo": OBJ_CROSSSELLING,
            "Porcentaje": round((total_crossselling / OBJ_CROSSSELLING) * 100, 2) if OBJ_CROSSSELLING > 0 else 0
        },
        {
            "Categoría": "Total",
            "Actual": total_general,
            "Objetivo": OBJ_PRODUCTOS + OBJ_UPSELLING + OBJ_CROSSSELLING,
            "Porcentaje": round((total_general / (OBJ_PRODUCTOS + OBJ_UPSELLING + OBJ_CROSSSELLING)) * 100, 2)
        }
    ])
    
    return summary


def run_monthly_report(
    settings: Settings,
    year: int,
    month: int,
    output_path: Optional[str] = None
) -> Dict:
    """Execute monthly report operation.
    
    Args:
        settings: Application settings
        year: Report year
        month: Report month (1-12)
        output_path: Optional output file path (auto-generated if None)
        
    Returns:
        Dictionary with operation results and report data
    """
    month_name = calendar.month_name[month]
    logger.info("monthly_report_started", year=year, month=month, month_name=month_name)
    
    client = MagentoAPIClient(settings)
    client.authenticate()
    
    first_day = f"{year}-{month:02d}-01 00:00:00"
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = f"{year}-{month:02d}-{last_day_num} 23:59:59"
    
    logger.info("date_range", start=first_day, end=last_day)
    
    brand_map = client.get_brand_map()
    logger.info("brands_fetched", count=len(brand_map))
    
    products = list(client.get_products_by_date_range(first_day, last_day))
    logger.info("products_fetched", count=len(products))
    
    if not products:
        return {
            "success": True,
            "message": f"No se encontraron productos para {month_name} {year}",
            "products_count": 0
        }
    
    df_report = generate_report(products, brand_map)
    df_summary = generate_summary(df_report)
    
    if output_path is None:
        output_path = f"reporte_productos_{year}_{month:02d}_{month_name}.xlsx"
    
    output_file = Path(output_path)
    
    try:
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            df_report.to_excel(writer, sheet_name="Carga de productos", index=False, startrow=1)
            writer.sheets["Carga de productos"]["A1"] = "Carga de productos"
            
            df_summary.to_excel(writer, sheet_name="Resumen", index=False)
        
        logger.info("report_saved", path=str(output_file))
    except Exception as e:
        logger.error("report_save_failed", error=str(e))
        return {
            "success": False,
            "error": str(e),
            "products_count": len(products)
        }
    
    result = {
        "success": True,
        "year": year,
        "month": month,
        "month_name": month_name,
        "products_count": len(products),
        "output_path": str(output_file),
        "report_data": df_report.to_dict("records") if not df_report.empty else [],
        "summary_data": df_summary.to_dict("records") if not df_summary.empty else []
    }
    
    logger.info("monthly_report_completed", **result)
    return result
