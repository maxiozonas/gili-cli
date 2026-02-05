"""Constants and enumerations for Magento Automation System."""

from enum import Enum
from typing import Dict, Tuple


class OrderStatus(str, Enum):
    """Order status values in Magento."""
    PROCESSING = "processing"
    COMPLETE = "complete"
    PENDING = "pending"
    CANCELED = "canceled"
    CLOSED = "closed"


class SortBy(str, Enum):
    """Sorting options for RFM analysis output."""
    LTV = "LTV_Gasto_Total"
    FREQUENCY = "Frecuencia"
    TICKET_PROMEDIO = "Ticket_Promedio_Mensual"
    RECENCY = "Recencia_Dias"
    TIME_BETWEEN_PURCHASES = "Tiempo_Promedio_Entre_Compras"


class CustomerSegment(str, Enum):
    """Customer segments based on RFM scoring."""
    CHAMPION = "Campeon"
    LOYAL = "Leal"
    POTENTIAL = "Potencial"
    NEW = "Nuevo"
    AT_RISK = "En Riesgo"
    LOST = "Perdido"


# Sort configuration mapping
SORT_OPTIONS: Dict[str, Tuple[str, str, bool]] = {
    "1": ("Gasto Total (LTV)", "LTV_Gasto_Total", False),
    "2": ("Cantidad de Ordenes (Frecuencia)", "Frecuencia", False),
    "3": ("Ticket Promedio Mensual", "Ticket_Promedio_Mensual", False),
    "4": ("Tiempo Promedio Entre Compras", "Tiempo_Promedio_Entre_Compras", True),
    "5": ("Ultima Fecha de Compra (Recencia)", "Recencia_Dias", True),
}

# Marketing scoring thresholds
MARKETING_THRESHOLDS = {
    "high_value": 1_000_000,  # $1,000,000 ARS
    "medium_value": 300_000,   # $300,000 ARS
    "high_frequency": 5,
    "medium_frequency": 2,
    "recent_days": 90,         # 3 months
    "medium_days": 180,        # 6 months
}

# Column definitions for Google Sheets uploads
RFM_COLUMNS = [
    "Customer ID",
    "Customer Email",
    "Nombre",
    "Apellido",
    "Telefono",
    "LTV_Gasto_Total",
    "Frecuencia",
    "Recencia_Dias",
    "Ticket_Promedio_Mensual",
    "Tiempo_Promedio_Entre_Compras",
    "Primera_Compra",
    "Ultima_Compra",
    "Categoria_Preferida",
    "Marca_Preferida",
    "Producto_Favorito",
    "Tiene_Factura_A",
    "Es_Bahia_Blanca",
]

CART_COLUMNS = [
    "Email",
    "Products",
    "Quantity",
    "Subtotal",
    "Created",
    "Updated",
    "LTV_Gasto_Total",
    "Frecuencia",
    "Recencia_Dias",
    "Ticket_Promedio_Mensual",
    "Categoria_Preferida",
    "Es_Bahia_Blanca",
    "Tiene_Factura_A",
    "Score_Intencion",
    "Segmento",
    "Tipo_Cliente",
    "Accion_Sugerida",
]

# User agent for API requests
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MagentoAutomation/2.0"

# Cache TTL in seconds (24 hours)
CACHE_TTL = 86400

# Fixed stock overrides (from original stock_sync.py)
FIXED_STOCK_OVERRIDES: Dict[str, int] = {
    "1021": 90,
    "1022": 25,
    "1023": 15,
    "1075": 20,
    "1085": 50,
    "1088": 20,
    "1104": 0,
    "1105": 0,
    "1127": 0,
    "1185": 10,
    "1329": 20,
    "1374": 25,
    "1419": 25,
    "1647": 5,
    "1649": 30,
    "1651": 50,
    "1656": 2,
    "1657": 5,
    "1664": 10,
    "1665": 15,
    "1672": 1,
    "1675": 10,
    "1678": 4,
}
