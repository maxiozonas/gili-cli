# ⚙️ Sistema de Automatización y Análisis de Datos Magento 2.0

Este sistema es una herramienta ETL (Extracción, Transformación y Carga) diseñada para potenciar la gestión de clientes y la eficiencia operativa de la plataforma Magento, integrándose con sistemas externos como Flexxus y Google Sheets.

---

## 📋 Comandos Disponibles

### 1. `rfm` - Análisis RFM de Clientes

Genera una Base Maestra de Clientes con análisis RFM (Recencia, Frecuencia, Valor Monetario) y sube los resultados a Google Sheets.

```bash
python main.py rfm --year 2025
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--year`, `-y` | Requerido | Año mínimo para análisis de órdenes | - |
| `--sort`, `-s` | Opcional | Criterio de ordenamiento: `ltv`, `frequency`, `recency`, `ticket` | `ltv` |
| `--upload/--no-upload` | Opcional | Subir resultados a Google Sheets | `True` |

**Ejemplo:**
```bash
# Análisis RFM 2024, ordenar por LTV, subir a Sheets
python main.py rfm -y 2024 -s ltv --upload

# Análisis RFM 2025 sin subir a Sheets
python main.py rfm -y 2025 --no-upload
```

**Salida:** Archivo CSV en `output/` y datos subidos a Google Sheets (si `--upload`).

---

### 2. `sync` - Sincronización de Stock y Precios

Sincroniza stock y precios desde archivos Flexxus hacia Magento.

```bash
python main.py sync
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--apply-overrides` | Opcional | Aplicar overrides de stock definidos en configuración | `False` |

**Ejemplo:**
```bash
# Preview (no aplica cambios)
python main.py sync

# Aplicar overrides de stock
python main.py sync --apply-overrides
```

**Requisito:** Archivos CSV de Flexxus en la carpeta configurada en `.env`.

---

### 3. `merchant` - Generar Feed Google Merchant Center

Genera un archivo TSV compatible con Google Merchant Center para feeds de productos.

```bash
python main.py merchant
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--output`, `-o` | Opcional | Directorio de salida para el archivo TSV | Directorio actual |

**Ejemplo:**
```bash
# Feed en directorio actual
python main.py merchant

# Feed en carpeta específica
python main.py merchant --output C:/feeds
```

**Requisito:** Archivo `input/google_categories.txt` con la taxonomía de Google.

**Salida:** Archivo `feed_merchant_center_YYYYMMDD_HHMMSS.tsv`.

---

### 4. `qr` - Exportar Productos de Categoría

Exporta productos de una categoría específica a CSV (útil para generación de códigos QR).

```bash
python main.py qr 164
```

**Argumentos:**

| Argumento | Descripción |
|-----------|-------------|
| `CATEGORY_ID` | ID de la categoría de productos (requerido) |

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--output`, `-o` | Opcional | Directorio de salida | `qrs` |

**Ejemplo:**
```bash
# Exportar categoría 164
python main.py qr 164

# Exportar y guardar en carpeta específica
python main.py qr 737 --output C:/productos
```

**Salida:** Archivo CSV con columnas: `sku`, `articulo`, `marca`, `habilitado`, `url-key`.

---

### 5. `manual-update` - Actualización Masiva de Descripciones

Inyecta HTML en productos sin descripción corta de una categoría específica.

```bash
python main.py manual-update --apply
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--category`, `-c` | Opcional | ID de categoría | `737` (Pisos y revestimientos) |
| `--html`, `-h` | Opcional | Path a archivo con HTML personalizado | HTML por defecto |
| `--dry-run` | Opcional | Solo previsualizar, no aplicar cambios | `True` |
| `--apply` | Opcional | Aplicar cambios | `False` |

**Ejemplo:**
```bash
# Preview de productos a actualizar
python main.py manual-update

# Aplicar cambios
python main.py manual-update --apply

# Con HTML personalizado
python main.py manual-update -c 170 -h C:/mi_html.txt --apply
```

**Salida:** Preview o actualización real de descripciones cortas en Magento.

---

### 6. `monthly-report` - Reporte Mensual de Productos

Genera un reporte Excel con productos cargados en un mes específico, agrupados por marca con estadísticas de crossselling/upselling.

```bash
python main.py monthly-report -y 2025 -m 1
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--year`, `-y` | Requerido | Año del reporte (ej: 2025) | - |
| `--month`, `-m` | Requerido | Mes del reporte (1-12) | - |
| `--output`, `-o` | Opcional | Path de salida para archivo Excel | Auto-generado |

**Ejemplo:**
```bash
# Reporte Enero 2025
python main.py monthly-report -y 2025 -m 1

# Reporte con nombre personalizado
python main.py monthly-report -y 2025 -m 1 -o C:/reportes/mi_reporte.xlsx
```

**Salida:** Archivo Excel con dos hojas:
- `Carga de productos`: Distribución por marca
- `Resumen`: Objetivos vs. actuales

---

### 7. `validate` - Validar Configuración

Valida la configuración del sistema y prueba las conexiones.

```bash
python main.py validate
```

**Parámetros:**

| Parámetro | Opción | Descripción | Valor por defecto |
|-----------|--------|-------------|-------------------|
| `--env-only` | Opcional | Solo validar configuración de entorno | `False` |

**Ejemplo:**
```bash
# Validar solo configuración
python main.py validate --env-only

# Validar todo incluyendo conexiones
python main.py validate
```

---

## ✨ Características Principales

### Módulo de Análisis RFM (Recencia, Frecuencia, Valor Monetario)

Genera una **Base Maestra de Clientes Compradores** a partir de la API de Magento:

* **RFM Completo:** Cálculo de métricas como Recencia, Frecuencia y LTV
* **Enriquecimiento de Datos:** Categoría Preferida, Marca Preferida, Producto Favorito
* **Segmentación Avanzada:** Filtros por año y múltiples criterios de ordenamiento
* **Integración Google Sheets:** Upload directo a spreadsheet configurado

### Módulo de Sincronización Stock/Precios

Automatiza la actualización desde archivos Flexxus:

* **Detección Automática:** Lee el CSV más reciente de la carpeta configurada
* **Validación de SKUs:** Filtra productos existentes en Magento
* **Overrides de Stock:** Soporte para reglas de stock manuales

### Módulo Google Merchant Center

Genera feeds optimizados para publicidad:

* **Formato TSV:** Compatible con Google Merchant Center
* **Categorización Google:** Usa taxonomía oficial de Google
* **Validación:** Verifica integridad del feed generado

---

## 🚀 Guía de Instalación y Uso

### 1. Requisitos Previos

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
# Editar archivo .env con las credenciales de Magento y Google
```

### 2. Configuración (.env)

```env
# Magento
MAGENTO_URL=https://tu-tienda.com.ar
MAGENTO_USER=tu_usuario
MAGENTO_PASSWORD=tu_password

# Google Sheets
GOOGLE_CREDENTIALS_PATH=credentials.json
SPREADSHEET_NAME=Base de datos Marketing

# Flexxus
FLEXXUS_STOCK_FOLDER=C:/Exportacion de Precios y Stock
```

### 3. Ejecución de Comandos

```bash
# Ver ayuda general
python main.py --help

# Ver ayuda de un comando específico
python main.py rfm --help

# Ejecutar comando
python main.py rfm -y 2025
```

---

## 📁 Estructura del Proyecto

```
project-root/
├── main.py                 # Entry point CLI
├── requirements.txt        # Dependencias Python
├── .env                    # Configuración (no versionar)
├── .env.example            # Ejemplo de configuración
├── credentials.json        # Google Service Account
│
├── src/
│   ├── core/
│   │   ├── client.py       # Magento API Client
│   │   └── exceptions.py   # Custom exceptions
│   ├── connectors/
│   │   ├── google_sheets.py
│   │   ├── merchant.py
│   │   └── flexxus.py
│   ├── processors/
│   │   ├── rfm.py
│   │   └── scoring.py
│   ├── operations/
│   │   ├── manual_update.py
│   │   ├── monthly_report.py
│   │   └── export_category.py
│   └── config/
│       ├── settings.py
│       └── constants.py
│
├── input/                  # Archivos de entrada
│   └── google_categories.txt
├── output/                 # Archivos generados
├── logs/                   # Logs de aplicación
└── src/auto/               # Scripts legacy para referencia
```

---

## 📝 Notas Técnicas

### Dependencias Principales

| Paquete | Propósito |
|---------|-----------|
| `typer` | CLI moderno con Rich |
| `requests` | HTTP client para APIs |
| `pandas` | Manipulación de datos |
| `gspread` | Integración Google Sheets |
| `structlog` | Logging estructurado |
| `openpyxl` | Lectura/escritura Excel |

### Logs

Los logs técnicos se guardan en `logs/app.log`. Para ver logs en tiempo real:

```bash
python main.py -v [comando]
```

### Solución de Problemas

| Problema | Solución |
|----------|----------|
| Error de autenticación | Verificar `.env` con credenciales correctas |
| Timeout en API | Aumentar `API_TIMEOUT` en `.env` |
| Google Sheets fallando | Verificar `credentials.json` y permisos |
| Feed Merchant vacío | Verificar `input/google_categories.txt` |
