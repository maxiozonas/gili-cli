"""Magento Automation System - CLI Entry Point.

This module provides the main CLI interface for the Magento Automation System
using Typer for modern, user-friendly command-line interactions.

Commands:
    rfm: RFM analysis with customer scoring
    sync: Stock and price synchronization with Flexxus
    merchant: Generate Google Merchant Center feed
    qr: Generate QR codes for products
    product: Search product by SKU and return attributes in JSON

Example:
    $ python main.py rfm --year 2024
    $ python main.py sync
    $ python main.py merchant
    $ python main.py qr --category-id 737
    $ python main.py product 00042
"""

import sys
from os.path import exists
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent))

import json

import pandas as pd
import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from src.config import Settings
from src.connectors import FlexxusSync, GoogleMerchantFeed, GoogleSheetsUploader
from src.core import MagentoAPIClient
from src.operations import run_export_category, run_manual_update, run_monthly_report
from src.processors import MarketingScorer, RFMProcessor
from src.utils import get_logger, parse_comma_decimal, setup_file_logging

# Initialize Typer app
app = typer.Typer(
    name="magento-automation",
    help="Sistema de automatizacion y analisis de datos Magento",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Initialize console for rich output
console = Console()


def get_settings() -> Settings:
    """Get validated settings."""
    return Settings()


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose file logging"),
) -> None:
    """Magento Automation System CLI.
    
    Herramienta ETL para gestion de clientes y operaciones de Magento.
    Los logs tecnicos se guardan en logs/app.log
    """
    log_level = "DEBUG" if verbose else "INFO"
    log_file = setup_file_logging(level=log_level)
    # Logs tecnicos van al archivo, mensajes de usuario via console.print()


@app.command()
def rfm(
    year: int = typer.Option(
        ...,
        "--year", "-y",
        help="Año minimo para analisis de ordenes",
        min=2020,
        max=2030,
    ),
    sort_by: str = typer.Option(
        "ltv",
        "--sort", "-s",
        help="Criterio de ordenamiento: ltv, frequency, recency, ticket"
    ),
    upload: bool = typer.Option(
        True,
        "--upload/--no-upload",
        help="Subir resultados a Google Sheets"
    ),
) -> None:
    """[bold green]Analisis RFM de clientes[/bold green].
    
    Genera analisis RFM (Recencia, Frecuencia, Valor Monetario) y sube a Google Sheets.
    """
    logger = get_logger(__name__)
    logger.info("rfm_command_started", year=year, sort_by=sort_by)

    try:
        # Initialize settings and client
        settings = get_settings()
        client = MagentoAPIClient(settings)

        # Authenticate
        console.print("[bold blue]Autenticando con Magento...[/bold blue]")
        client.authenticate()
        console.print("[green]Autenticacion exitosa[/green]")

        # Fetch data
        console.print(f"[bold blue]Obteniendo datos desde {year}...[/bold blue]")
        df_customers = client.fetch_customers()
        df_orders = client.fetch_orders(min_year=year)
        df_catalog = client.fetch_catalog()
        df_items = client.fetch_order_items(min_year=year)

        console.print("[green]Datos obtenidos:[/green]")
        console.print(f"  - Clientes: {len(df_customers)}")
        console.print(f"  - Ordenes: {len(df_orders)}")
        console.print(f"  - Productos: {len(df_catalog)}")
        console.print(f"  - Items: {len(df_items)}")

        # Process RFM
        console.print("[bold blue]Procesando analisis RFM...[/bold blue]")
        console.print("  - Extrayendo campos de clientes...")
        processor = RFMProcessor(min_year=year)
        df_rfm = processor.process(df_customers, df_orders, df_catalog, df_items)
        console.print("  - Calculando metricas RFM...")

        # Apply sorting
        sort_mapping = {
            "ltv": "LTV_Gasto_Total",
            "frequency": "Frecuencia",
            "recency": "Recencia_Dias",
            "ticket": "Ticket_Promedio_Mensual",
        }
        sort_col = sort_mapping.get(sort_by, "LTV_Gasto_Total")
        sort_asc = sort_by == "recency"  # Lower recency is better
        df_rfm = processor.sort_by(df_rfm, sort_col, ascending=sort_asc)

        console.print(f"[green]RFM procesado: {len(df_rfm)} clientes[/green]")

        # Initialize scorer for cart processing
        scorer = MarketingScorer()

        # Load and process abandoned carts
        console.print("[bold blue]Procesando carritos abandonados...[/bold blue]")
                # Load and process abandoned carts
        carts_path = settings.abandoned_carts_path

        if not carts_path or not exists(carts_path):
            logger.warning("abandoned_carts_file_not_found", path=carts_path)
            df_carts_rfm = pd.DataFrame()
        else:
            df_carts = pd.read_csv(carts_path)
            df_carts['Email'] = df_carts['Email'].str.lower()
            df_carts['Created'] = pd.to_datetime(df_carts['Created'], errors='coerce')
            df_carts['Updated'] = pd.to_datetime(df_carts['Updated'], errors='coerce')
            df_carts['Subtotal'] = (
                df_carts['Subtotal']
                .astype(str)
                .str.replace('$', '', regex=False)
                .str.replace(',', '', regex=False)
            )
            df_carts['Subtotal'] = pd.to_numeric(df_carts['Subtotal'], errors='coerce')
            df_carts = df_carts.sort_values('Updated', ascending=False)

            # Merge with RFM data and score
            console.print("[bold blue]Procesando carritos abandonados...[/bold blue]")
            df_carts_rfm = df_carts.merge(
                df_rfm,
                left_on='Email',
                right_on='Customer Email',
                how='left'
            )

            # Convert numeric columns
            for col in ['LTV_Gasto_Total', 'Ticket_Promedio_Mensual']:
                if col in df_carts_rfm.columns:
                    df_carts_rfm[col] = df_carts_rfm[col].apply(parse_comma_decimal)

            for col in ['Frecuencia', 'Recencia_Dias']:
                if col in df_carts_rfm.columns:
                    df_carts_rfm[col] = pd.to_numeric(df_carts_rfm[col], errors='coerce')
                    df_carts_rfm[col] = df_carts_rfm[col].fillna(0)

            # Ensure required columns exist
            if 'Tiene_Factura_A' not in df_carts_rfm.columns:
                df_carts_rfm['Tiene_Factura_A'] = 'No'
            if 'Es_Bahia_Blanca' not in df_carts_rfm.columns:
                df_carts_rfm['Es_Bahia_Blanca'] = 'No'

            # Score carts
            df_carts_rfm = scorer.process(df_carts_rfm)

            # Select final columns
            columnas = [
                'Email', 'Products', 'Quantity', 'Subtotal',
                'Created', 'Updated',
                'LTV_Gasto_Total', 'Frecuencia', 'Recencia_Dias',
                'Ticket_Promedio_Mensual', 'Categoria_Preferida',
                'Es_Bahia_Blanca',
                'Tiene_Factura_A',
                'Score_Intencion', 'Segmento', 'Tipo_Cliente', 'Accion_Sugerida'
            ]

            for c in columnas:
                if c not in df_carts_rfm.columns:
                    df_carts_rfm[c] = ""

            df_carts_rfm = df_carts_rfm[columnas].sort_values(
                by=['Updated', 'Score_Intencion'],
                ascending=[False, False]
            )

            console.print(f"[green]Carritos procesados: {len(df_carts_rfm)}[/green]")

        # Upload to Google Sheets
        if upload:
            console.print("[bold blue]Subiendo a Google Sheets...[/bold blue]")
            uploader = GoogleSheetsUploader(settings)
            uploader.connect()
            uploader.upload_rfm_data(df_rfm, df_carts_rfm)
            console.print("[green]Datos subidos exitosamente[/green]")

        # Show summary
        console.print("\n[bold green]Resumen del analisis:[/bold green]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metrica", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Total Clientes", str(len(df_rfm)))
        table.add_row("Carritos Abandonados", str(len(df_carts_rfm)))

        console.print(table)

        logger.info("rfm_command_completed")

    except Exception as e:
        logger.error("rfm_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def sync(
    apply_overrides: bool = typer.Option(
        True,
        "--apply-overrides/--no-overrides",
        help="Aplicar sobreescrituras de stock fijo"
    ),
) -> None:
    """[bold blue]Sincronizacion de Stock y Precios[/bold blue].
    
    Sincroniza stock y precios desde archivos Flexxus hacia Magento.
    """
    logger = get_logger(__name__)
    logger.info("sync_command_started")

    try:
        # Initialize settings and client
        settings = get_settings()
        client = MagentoAPIClient(settings)

        # Authenticate
        console.print("[bold blue]Autenticando con Magento...[/bold blue]")
        client.authenticate()
        console.print("[green]Autenticacion exitosa[/green]")

        # Get all Magento SKUs
        console.print("[bold blue]Obteniendo SKUs de Magento...[/bold blue]")
        df_catalog = client.fetch_catalog()
        magento_skus = set(df_catalog['sku'].apply(lambda x: str(x).strip().replace(' ', '').zfill(5)))
        console.print(f"[green]SKUs en Magento: {len(magento_skus)}[/green]")

        # Synchronize with Flexxus
        console.print("[bold blue]Sincronizando con Flexxus...[/bold blue]")
        sync_connector = FlexxusSync(settings)
        output_path = sync_connector.synchronize(magento_skus, apply_overrides=apply_overrides)

        console.print("[bold green]Sincronizacion completada![/bold green]")
        console.print(f"Archivo exportado: {output_path}")

        # Show statistics
        stats = sync_connector.get_statistics(pd.read_csv(output_path, sep=';'))

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metrica", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Total SKUs", str(stats['total_skus']))
        table.add_row("Cantidad Total", str(stats['total_qty']))
        table.add_row("Stock Overrides", str(stats['stock_overrides_applied']))
        table.add_row("Precio Promedio", f"${stats['avg_price']:.2f}")

        console.print(table)

        logger.info("sync_command_completed", output_path=output_path)

    except Exception as e:
        logger.error("sync_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def merchant(
    output_dir: str = typer.Option(
        ".",
        "--output", "-o",
        help="Directorio de salida para el archivo TSV"
    ),
) -> None:
    """[bold yellow]Generar feed para Google Merchant[/bold yellow].
    
    Genera archivo TSV compatible con Google Merchant Center.
    """
    logger = get_logger(__name__)
    logger.info("merchant_command_started", output_dir=output_dir)

    try:
        # Initialize settings and client
        settings = get_settings()
        client = MagentoAPIClient(settings)

        # Authenticate
        console.print("[bold blue]Autenticando con Magento...[/bold blue]")
        client.authenticate()
        console.print("[green]Autenticacion exitosa[/green]")

        # Fetch catalog
        console.print("[bold blue]Obteniendo catalogo de productos...[/bold blue]")
        df_catalog = client.fetch_catalog()
        console.print(f"[green]Productos obtenidos: {len(df_catalog)}[/green]")

        # Generate feed
        console.print("[bold blue]Generando feed de Google Merchant...[/bold blue]")
        feed = GoogleMerchantFeed(
            categories_file_path=settings.google_categories_path,
            output_path=output_dir
        )
        output_file = feed.generate(df_catalog)

        console.print("[bold green]Feed generado exitosamente![/bold green]")
        console.print(f"Archivo: {output_file}")

        # Validate feed
        if feed.validate_feed(output_file):
            console.print("[green]Validacion: OK[/green]")
        else:
            console.print("[yellow]Validacion: Se encontraron advertencias[/yellow]")

        logger.info("merchant_command_completed", output_file=output_file)

    except Exception as e:
        logger.error("merchant_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def qr(
    category_id: str = typer.Argument(
        ...,
        help="ID de categoria de productos"
    ),
    output_dir: str = typer.Option(
        "qrs",
        "--output", "-o",
        help="Directorio de salida para los codigos QR"
    ),
) -> None:
    """[bold magenta]Generar codigos QR para productos[/bold magenta].
    
    Genera codigos QR para todos los productos de una categoria.
    """
    logger = get_logger(__name__)
    logger.info("qr_command_started", category_id=category_id, output_dir=output_dir)

    try:
        console.print(f"[bold blue]Exportando productos de categoria {category_id}...[/bold blue]")

        settings = get_settings()
        result = run_export_category(settings, int(category_id))

        if result["success"]:
            console.print("[bold green]Exportacion completada![/bold green]")
            console.print(f"Productos exportados: {result['products_count']}")
            console.print(f"Archivo: {result['output_path']}")

            if result.get("csv_data"):
                console.print("\n[bold]Vista previa (primeros 10):[/bold]")
                for item in result["csv_data"][:10]:
                    console.print(f"  - {item['sku']}: {item['articulo']}")
        else:
            console.print(f"[bold yellow]{result.get('message', 'Error')}[/bold yellow]")

        logger.info("qr_command_completed", **result)

    except Exception as e:
        logger.error("qr_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def manual_update(
    category_id: int = typer.Option(
        737,
        "--category", "-c",
        help="ID de categoria (default: 737 - Pisos y revestimientos)"
    ),
    html_file: str = typer.Option(
        None,
        "--html", "-h",
        help="Path a archivo con HTML a inyectar (opcional)"
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Solo previsualizar sin aplicar cambios"
    ),
) -> None:
    """[bold red]Actualizacion masiva de descripciones cortas[/bold red].
    
    Inyecta HTML en productos sin descripcion corta de una categoria.
    Requiere confirmacion si --apply (no dry-run).
    """
    logger = get_logger(__name__)
    logger.info("manual_update_command_started", category_id=category_id, dry_run=dry_run)

    try:
        settings = get_settings()

        html_content = None
        if html_file and exists(html_file):
            with open(html_file, encoding="utf-8") as f:
                html_content = f.read()
            console.print(f"[blue]HTML cargado desde: {html_file}[/blue]")

        result = run_manual_update(
            settings,
            category_id=category_id,
            html_content=html_content,
            dry_run=dry_run
        )

        if result["dry_run"]:
            console.print("\n[bold yellow]MODO PREVIEW - No se aplicaran cambios[/bold yellow]")
            console.print(f"Total productos en categoria: {result['total_products_in_category']}")
            console.print(f"Productos sin descripcion: {result['products_to_update']}")

            if result.get("products_preview"):
                console.print("\n[bold]Primeros 10 productos que se actualizaran:[/bold]")
                for item in result["products_preview"]:
                    console.print(f"  - {item['sku']}: {item['name']}")

            console.print("\n[bold]Para aplicar cambios, ejecutar:[/bold]")
            console.print(f"  python main.py manual-update --category {category_id} --apply")
        else:
            if result["success"]:
                console.print("[bold green]Actualizacion completada![/bold green]")
                console.print(f"Productos actualizados: {result['products_updated']}")
                if result.get("products_failed", 0) > 0:
                    console.print(f"[bold yellow]Productos con errores: {result['products_failed']}[/bold yellow]")
            else:
                console.print(f"[bold yellow]{result.get('message', 'Completado con errores')}[/bold yellow]")

        logger.info("manual_update_command_completed", **result)

    except Exception as e:
        logger.error("manual_update_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def monthly_report(
    year: int = typer.Option(
        ...,
        "--year", "-y",
        help="Año del reporte (ej: 2025)"
    ),
    month: int = typer.Option(
        ...,
        "--month", "-m",
        help="Mes del reporte (1-12)"
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Path de salida para el archivo Excel"
    ),
) -> None:
    """[bold green]Reporte mensual de productos cargados[/bold green].
    
    Genera reporte Excel con productos creados en un mes especifico,
    agrupados por marca con estadisticas de crossselling/upselling.
    """
    logger = get_logger(__name__)
    logger.info("monthly_report_command_started", year=year, month=month)

    try:
        settings = get_settings()

        result = run_monthly_report(
            settings,
            year=year,
            month=month,
            output_path=output
        )

        if result["success"]:
            if result.get("products_count", 0) > 0:
                console.print("[bold green]Reporte generado![/bold green]")
                console.print(f"Periodo: {result['month_name']} {result['year']}")
                console.print(f"Productos cargados: {result['products_count']}")
                console.print(f"Archivo: {result['output_path']}")
            else:
                console.print(f"[bold yellow]{result['message']}[/bold yellow]")
        else:
            console.print(f"[bold red]Error: {result.get('error', 'Error desconocido')}[/bold red]")

        logger.info("monthly_report_command_completed", **result)

    except Exception as e:
        logger.error("monthly_report_command_failed", error=str(e))
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def validate(
    env_only: bool = typer.Option(
        False,
        "--env-only",
        help="Solo validar configuracion de entorno"
    ),
) -> None:
    """[bold cyan]Validar configuracion del sistema[/bold cyan].
    
    Verifica que toda la configuracion necesaria este correctamente definida.
    """
    logger = get_logger(__name__)
    logger.info("validate_command_started")

    try:
        console.print("[bold blue]Validando configuracion...[/bold blue]")

        # Validate settings
        settings = get_settings()

        console.print("[bold green]Configuracion valida![/bold green]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Configuracion", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Magento URL", settings.magento_url)
        table.add_row("Spreadsheet", settings.spreadsheet_name)
        table.add_row("Flexxus Folder", settings.flexxus_stock_folder)

        console.print(table)

        if not env_only:
            # Test connections
            console.print("\n[bold blue]Probando conexiones...[/bold blue]")

            client = MagentoAPIClient(settings)
            client.authenticate()
            console.print("[green]Conexion Magento: OK[/green]")

            # Test Google Sheets if credentials exist
            import os
            if os.path.exists(settings.google_credentials_path):
                uploader = GoogleSheetsUploader(settings)
                uploader.connect()
                console.print("[green]Conexion Google Sheets: OK[/green]")
            else:
                console.print("[yellow]Google Sheets: Credenciales no encontradas[/yellow]")

        logger.info("validate_command_completed")

    except Exception as e:
        logger.error("validate_command_failed", error=str(e))
        console.print(f"[bold red]Error de validacion: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def product(
    sku: str = typer.Argument(
        ...,
        help="SKU del producto a buscar"
    ),
    output: str | None = typer.Option(
        None,
        "--output", "-o",
        help="Guardar resultado en archivo JSON"
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Mostrar respuesta cruda de la API sin procesar"
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        help="JSON en una línea (sin formato)"
    )
) -> None:
    """[bold cyan]Buscar producto por SKU[/bold cyan].
    
    Retorna todos los atributos del producto en formato JSON.
    
    Ejemplo:
        python main.py product 00042
        python main.py product 00042 --output producto.json
        python main.py product 00042 --compact | jq .
    """
    logger = get_logger(__name__)
    logger.info("product_command_started", sku=sku)

    try:
        settings = get_settings()
        client = MagentoAPIClient(settings)

        console.print("[bold blue]Autenticando con Magento...[/bold blue]")
        client.authenticate()
        console.print("[green]Autenticacion exitosa[/green]")

        console.print(f"[bold blue]Buscando SKU: {sku}[/bold blue]")
        product_data = client.fetch_product_by_sku(sku)

        if product_data is None:
            console.print("[bold red]Producto no encontrado[/bold red]")
            console.print(f"  SKU: [cyan]{sku}[/cyan]")
            console.print("\n[yellow]Sugerencias:[/yellow]")
            console.print("  • Verifica que el SKU exista en Magento")
            console.print("  • Los SKUs pueden tener hasta 6 caracteres")
            raise typer.Exit(code=1)

        # Enrich product data with human-readable values
        console.print("[bold blue]Enriqueciendo datos del producto...[/bold blue]")
        product_data = client.enrich_product_data(product_data)

        if compact:
            json_str = json.dumps(product_data, ensure_ascii=False)
        else:
            json_str = json.dumps(
                product_data,
                ensure_ascii=False,
                indent=2
            )

        if compact:
            console.print(json_str)
        else:
            console.print("\n[bold green]Datos del producto:[/bold green]")
            json_data = JSON(json_str)
            console.print(json_data)

        if output:
            output_path = Path(output)
            output_path.write_text(
                json_str,
                encoding='utf-8'
            )
            console.print(f"\n[green]Guardado en: {output}[/green]")

        logger.info(
            "product_command_completed",
            sku=sku,
            found=True,
            output_file=output
        )

    except Exception as e:
        logger.error("product_command_failed", sku=sku, error=str(e))

        if "not found" in str(e).lower() or "404" in str(e):
            console.print("\n[bold red]❌ Producto no encontrado[/bold red]")
            console.print(f"   SKU: [cyan]{sku}[/cyan]")
            console.print("\n[yellow]💡 Verifica:[/yellow]")
            console.print("   • El SKU existe en Magento")
            console.print("   • Los SKUs pueden tener hasta 6 caracteres")
            raise typer.Exit(code=1)
        else:
            console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
