"""Google Sheets Connector.

This module provides the GoogleSheetsUploader class for uploading
DataFrames to Google Sheets with proper error handling and batching.
"""

from typing import Optional, Dict, List

import pandas as pd
import gspread
from gspread.worksheet import Worksheet
from google.oauth2.service_account import Credentials
import structlog

from ..config.settings import Settings, get_settings
from ..core.exceptions import AuthenticationError, APIError, DataProcessingError

logger = structlog.get_logger(__name__)


class GoogleSheetsUploader:
    """Upload data to Google Sheets.
    
    This class handles authentication, worksheet management, and data upload
    to Google Sheets with proper error handling.
    
    Example:
        >>> uploader = GoogleSheetsUploader()
        >>> uploader.connect()
        >>> uploader.upload_rfm_data(df_rfm)
        >>> uploader.upload_cart_data(df_carts)
    """
    
    # Google API scopes required
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    def __init__(
        self, 
        settings: Optional[Settings] = None,
        spreadsheet_name: Optional[str] = None
    ) -> None:
        """Initialize the uploader.
        
        Args:
            settings: Settings instance (uses global if not provided)
            spreadsheet_name: Name of the spreadsheet (uses settings default if not provided)
        """
        self.settings = settings or get_settings()
        self.spreadsheet_name = spreadsheet_name or self.settings.spreadsheet_name
        self.credentials_path = self.settings.google_credentials_path
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None
        
        logger.debug(
            "sheets_uploader_initialized",
            spreadsheet=self.spreadsheet_name
        )
    
    def connect(self) -> None:
        """Establish connection to Google Sheets API.
        
        Raises:
            AuthenticationError: If credentials are invalid
            APIError: If connection fails
        """
        try:
            logger.info("connecting_to_google_sheets")
            
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open(self.spreadsheet_name)
            
            logger.info(
                "connected_to_spreadsheet",
                spreadsheet=self.spreadsheet_name
            )
            
        except FileNotFoundError:
            raise AuthenticationError(
                f"Credentials file not found: {self.credentials_path}",
                service="Google Sheets"
            )
        except Exception as e:
            raise APIError(
                f"Failed to connect to Google Sheets: {e}",
                endpoint="sheets.open"
            )
    
    def _get_or_create_worksheet(
        self, 
        title: str, 
        rows: int = 2000, 
        cols: int = 40
    ) -> Worksheet:
        """Get existing worksheet or create new one.
        
        Args:
            title: Worksheet title
            rows: Number of rows for new worksheet
            cols: Number of columns for new worksheet
            
        Returns:
            Worksheet object
        """
        if not self.spreadsheet:
            raise APIError(
                "Not connected to spreadsheet. Call connect() first.",
                endpoint="worksheet"
            )
        
        try:
            # Try to get existing worksheet
            worksheet = self.spreadsheet.worksheet(title)
            logger.debug("worksheet_found", title=title)
            return worksheet
        except gspread.WorksheetNotFound:
            # Create new worksheet
            logger.info("creating_worksheet", title=title)
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
    
    def upload_dataframe(
        self,
        worksheet: Worksheet,
        df: pd.DataFrame,
        clear_first: bool = True
    ) -> None:
        """Upload DataFrame to a worksheet.
        
        Args:
            worksheet: Target worksheet
            df: DataFrame to upload
            clear_first: If True, clear worksheet before uploading
            
        Raises:
            DataProcessingError: If upload fails
        """
        try:
            if clear_first:
                worksheet.clear()
                logger.debug("worksheet_cleared", title=worksheet.title)
            
            # Prepare data (handle NaN and convert to string)
            data = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
            
            # Upload in batch
            worksheet.update(data)
            
            logger.info(
                "worksheet_updated",
                title=worksheet.title,
                rows=len(df),
                columns=len(df.columns)
            )
            
        except Exception as e:
            logger.error(
                "worksheet_upload_failed",
                title=worksheet.title,
                error=str(e)
            )
            raise DataProcessingError(
                f"Failed to upload to worksheet {worksheet.title}: {e}",
                operation="upload_dataframe"
            )
    
    def _generate_documentation_df(self) -> pd.DataFrame:
        """Generate documentation DataFrame.
        
        Returns:
            DataFrame with column documentation
        """
        docs = [
            # --- RFM CLIENTES ---
            ["RFM Clientes", "Name", "Nombre completo registrado en Magento."],
            ["RFM Clientes", "Customer Email", "Correo electronico del cliente (ID principal)."],
            ["RFM Clientes", "ID", "ID interno de la base de datos de clientes."],
            ["RFM Clientes", "Cliente_Desde", "Fecha de creacion de la cuenta del cliente."],
            ["RFM Clientes", "Telefono", "Numero de telefono registrado."],
            ["RFM Clientes", "Codigo_Postal", "Codigo postal de la direccion del cliente."],
            ["RFM Clientes", "Es_Bahia_Blanca", "Indica si el cliente es de Bahia Blanca."],
            ["RFM Clientes", "Tax_VAT_Number", "DNI, CUIT o CUIL registrado en el campo Tax."],
            ["RFM Clientes", "VAT_Number", "Numero de identificacion fiscal secundario."],
            ["RFM Clientes", "Tiene_Factura_A", "Indica si el cliente tiene al menos una orden con Factura A."],
            ["RFM Clientes", "LTV_Gasto_Total", "Life Time Value: Suma de todas las compras finalizadas."],
            ["RFM Clientes", "Ticket_Promedio_Mensual", "Gasto estimado del cliente por cada mes de antiguedad."],
            ["RFM Clientes", "Gasto_Promedio_Compra", "Valor promedio de cada orden realizada."],
            ["RFM Clientes", "Gasto_Maximo_Compra", "Monto de la compra mas alta registrada."],
            ["RFM Clientes", "Gasto_Minimo_Compra", "Monto de la compra mas baja registrada."],
            ["RFM Clientes", "Frecuencia", "Cantidad total de ordenes aprobadas."],
            ["RFM Clientes", "Recencia_Fecha", "Fecha de la ultima compra realizada."],
            ["RFM Clientes", "Recencia_Dias", "Dias desde la ultima compra (menor = mas activo)."],
            ["RFM Clientes", "Tiempo_Promedio_Entre_Compras", "Dias promedio entre pedidos."],
            ["RFM Clientes", "Primera_Compra_Fecha", "Fecha de la primera orden registrada."],
            ["RFM Clientes", "Dias_Como_Cliente", "Antiguedad total en dias desde la primera compra."],
            ["RFM Clientes", "Ultimo_Trimestre_Compra", "Trimestre de actividad mas reciente."],
            ["RFM Clientes", "Dia_Semana_Max_Frec", "Dia de la semana con mayor frecuencia de compra."],
            ["RFM Clientes", "Categoria_Preferida", "Categoria donde el cliente tiene mas gasto."],
            ["RFM Clientes", "Lista_Categorias_Compradas", "Todas las categorias que el cliente ha probado."],
            ["RFM Clientes", "Marca_Preferida", "Marca que el cliente elige con mayor frecuencia."],
            ["RFM Clientes", "Lista_Marcas_Compradas", "Listado de todas las marcas adquiridas."],
            ["RFM Clientes", "Total_Productos_Unicos", "Cantidad de SKUs diferentes comprados."],
            ["RFM Clientes", "Producto_Favorito_SKU", "SKU del producto mas comprado."],
            ["RFM Clientes", "Producto_Favorito_Nombre", "Nombre del producto mas comprado."],
            ["RFM Clientes", "Producto_Favorito_Qty", "Unidades totales del producto favorito."],
            ["RFM Clientes", "Historial_Ordenes_Mapeo", "Detalle: ID Orden | Monto | Estado."],
            
            # --- CARRITOS ---
            ["Carritos", "Email", "Email del cliente que abandono el carrito."],
            ["Carritos", "Subtotal", "Monto de los productos olvidados en el carrito."],
            ["Carritos", "Es_Bahia_Blanca", "Indica si el cliente es de Bahia Blanca."],
            ["Carritos", "Tiene_Factura_A", "Indica si el cliente ha usado Factura A anteriormente."],
            ["Carritos", "Score_Intencion", "Puntaje 0-100 de valor de recuperacion."],
            ["Carritos", "Segmento", "Prioridad: Alta, Media o Baja."],
            ["Carritos", "Tipo_Cliente", "Clasificacion: VIP, Recurrente, Nuevo."],
            ["Carritos", "Accion_Sugerida", "Sugerencia de contacto (WhatsApp, Email, etc.)."],
            
            # --- LOGICA VIP ---
            ["LOGICA: Clientes", "VIP", "Gasto Total > $1.000.000 O Frecuencia >= 5 O Tiene Factura A = Si."],
            ["LOGICA: Clientes", "Recurrente", "Mas de 1 compra realizada."],
            ["LOGICA: Clientes", "Nuevo", "0 o 1 compra realizada en total."],
            
            # --- LOGICA SCORING ---
            ["LOGICA: Scoring", "Score Total", "Suma de: LTV (30) + Frecuencia (30) + Recencia (20) + Carrito (20)."],
            ["LOGICA: Scoring", "Puntos LTV", "> 1M: 30 pts | > 300k: 20 pts | > 0: 10 pts."],
            ["LOGICA: Scoring", "Puntos Frecuencia", ">= 5: 30 pts | >= 3: 20 pts | >= 1: 10 pts."],
            ["LOGICA: Scoring", "Puntos Recencia", "< 7 dias: 20 pts | < 30 dias: 10 pts."],
            ["LOGICA: Scoring", "Puntos Carrito", "> 300k: 20 pts | > 100k: 10 pts."],
        ]
        
        return pd.DataFrame(
            docs, 
            columns=["Hoja / Categoria", "Columna / Concepto", "Descripcion / Regla"]
        )
    
    def upload_rfm_data(
        self, 
        df_rfm: pd.DataFrame,
        df_carts: Optional[pd.DataFrame] = None
    ) -> None:
        """Upload RFM and cart data to Google Sheets.
        
        This uploads multiple worksheets:
        - Documentacion
        - RFM Clientes
        - Carritos Abandonados
        - Carritos segmentados (Nuevos, Recurrentes, VIP)
        
        Args:
            df_rfm: RFM analysis DataFrame
            df_carts: Optional cart abandonment DataFrame
        """
        if not self.spreadsheet:
            raise APIError(
                "Not connected to spreadsheet. Call connect() first.",
                endpoint="upload"
            )
        
        logger.info("uploading_rfm_data", rfm_rows=len(df_rfm))
        
        # Prepare data for upload
        data_to_upload: Dict[str, pd.DataFrame] = {
            "Documentacion": self._generate_documentation_df(),
            "RFM Clientes": df_rfm,
        }
        
        # Add cart data if provided
        if df_carts is not None and not df_carts.empty:
            logger.info("uploading_cart_data", cart_rows=len(df_carts))
            
            data_to_upload["Carritos Abandonados"] = df_carts
            
            # Create segmented cart sheets
            for customer_type in ["Nuevo", "Recurrente", "VIP"]:
                df_segment = df_carts[df_carts.get("Tipo_Cliente") == customer_type]
                if not df_segment.empty:
                    data_to_upload[f"Carritos - {customer_type}s"] = df_segment
        
        # Get existing worksheets
        existing_worksheets = {ws.title: ws for ws in self.spreadsheet.worksheets()}
        
        # Upload all data
        for title, df in data_to_upload.items():
            try:
                worksheet = self._get_or_create_worksheet(title)
                self.upload_dataframe(worksheet, df, clear_first=True)
                
            except Exception as e:
                logger.error(
                    "upload_failed",
                    worksheet=title,
                    error=str(e)
                )
                raise
        
        # Clean up obsolete worksheets
        for old_title, ws in existing_worksheets.items():
            if old_title not in data_to_upload:
                try:
                    self.spreadsheet.del_worksheet(ws)
                    logger.info("deleted_obsolete_worksheet", title=old_title)
                except Exception as e:
                    logger.warning(
                        "failed_to_delete_worksheet",
                        title=old_title,
                        error=str(e)
                    )
        
        logger.info("upload_complete")
    
    def upload_simple(
        self, 
        worksheet_name: str, 
        df: pd.DataFrame,
        clear_first: bool = True
    ) -> None:
        """Simple upload to a single worksheet.
        
        Args:
            worksheet_name: Name of the worksheet
            df: DataFrame to upload
            clear_first: If True, clear worksheet before uploading
        """
        if not self.spreadsheet:
            raise APIError(
                "Not connected to spreadsheet. Call connect() first.",
                endpoint="upload_simple"
            )
        
        worksheet = self._get_or_create_worksheet(worksheet_name)
        self.upload_dataframe(worksheet, df, clear_first=clear_first)
        
        logger.info("simple_upload_complete", worksheet=worksheet_name, rows=len(df))
