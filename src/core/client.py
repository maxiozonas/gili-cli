"""Unified Magento API Client.

This module provides a centralized client for all Magento API interactions,
eliminating code duplication across the application and providing consistent
error handling, retry logic, and authentication.
"""

from typing import Any, Dict, Iterator, Optional, Union

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import structlog
from tqdm import tqdm

from ..config.settings import Settings, get_settings
from ..config.constants import USER_AGENT, OrderStatus
from ..core.exceptions import APIError, AuthenticationError, ValidationError

logger = structlog.get_logger(__name__)


class MagentoAPIClient:
    """Unified client for Magento REST API.
    
    This client handles authentication, request retries, pagination,
    and provides a clean interface for all Magento API operations.
    
    Attributes:
        settings: Application settings instance
        session: Configured requests session with retry logic
        token: Authentication token (obtained automatically)
        base_url: Base URL for Magento API
        
    Example:
        >>> client = MagentoAPIClient()
        >>> client.authenticate()
        >>> orders = client.fetch_orders(min_year=2024)
        >>> customers = client.fetch_customers()
    """
    
    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize the API client.
        
        Args:
            settings: Settings instance (uses global if not provided)
        """
        self.settings = settings or get_settings()
        self.token: Optional[str] = None
        self.base_url = f"{self.settings.magento_url}/rest/V1"
        
        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.settings.api_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.debug("api_client_initialized", base_url=self.base_url)
    
    def authenticate(self) -> str:
        """Authenticate with Magento API and obtain token.
        
        Returns:
            Authentication token string
            
        Raises:
            AuthenticationError: If authentication fails
            APIError: If there's a connection or API error
        """
        if self.token:
            return self.token
        
        auth_url = f"{self.settings.magento_url}/rest/V1/integration/admin/token"
        payload = {
            "username": self.settings.magento_user,
            "password": self.settings.magento_password
        }
        
        logger.info("authenticating", username=self.settings.magento_user)
        
        try:
            response = self.session.post(
                auth_url,
                json=payload,
                timeout=self.settings.api_timeout,
                headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            
            self.token = response.json()
            logger.info("authentication_successful")
            return self.token
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise AuthenticationError(
                    "Invalid credentials",
                    service="Magento"
                )
            raise APIError(
                f"Authentication failed: {e}",
                status_code=response.status_code,
                endpoint="/integration/admin/token"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(
                f"Connection error during authentication: {e}",
                endpoint="/integration/admin/token"
            )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication.
        
        Returns:
            Dictionary of HTTP headers
            
        Raises:
            AuthenticationError: If not authenticated
        """
        if not self.token:
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                service="Magento"
            )
        
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            json_data: JSON payload for POST/PUT
            
        Returns:
            Parsed JSON response
            
        Raises:
            APIError: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        logger.debug(
            "api_request",
            method=method,
            endpoint=endpoint,
            params=params
        )
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=self.settings.api_timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            raise APIError(
                f"API request failed: {e}",
                status_code=response.status_code,
                endpoint=endpoint
            )
        except requests.exceptions.RequestException as e:
            raise APIError(
                f"Connection error: {e}",
                endpoint=endpoint
            )
    
    def _paginate(
        self,
        endpoint: str,
        page_size: Optional[int] = None,
        params: Optional[Dict] = None,
        desc: str = "Descargando"
    ) -> Iterator[Dict[str, Any]]:
        """Iterate through paginated API results with progress bar.
        
        Args:
            endpoint: API endpoint path
            page_size: Items per page (uses settings default if not specified)
            params: Additional query parameters
            desc: Description for progress bar
            
        Yields:
            Individual items from all pages
        """
        page_size = page_size or self.settings.page_size
        current_page = 1
        
        request_params = {
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[currentPage]": current_page
        }
        if params:
            request_params.update(params)
        
        # First request to get total count
        logger.info("fetching_paginated", endpoint=endpoint, page_size=page_size)
        first_response = self._make_request("GET", endpoint, params=request_params)
        first_items = first_response.get("items", [])
        total_count = first_response.get("total_count", len(first_items))
        
        if not first_items:
            logger.info("pagination_complete", endpoint=endpoint, total_items=0)
            return
        
        # Yield first page items
        for item in first_items:
            yield item
        
        # If only one page, we're done
        if len(first_items) < page_size or len(first_items) >= total_count:
            logger.info("pagination_complete", endpoint=endpoint, total_items=len(first_items))
            return
        
        # Continue with remaining pages using progress bar
        current_page = 2
        pbar = tqdm(total=total_count, initial=len(first_items), desc=desc, unit=" items")
        
        try:
            while True:
                request_params["searchCriteria[currentPage]"] = current_page
                
                response = self._make_request("GET", endpoint, params=request_params)
                items = response.get("items", [])
                
                if not items:
                    break
                
                for item in items:
                    yield item
                    pbar.update(1)
                
                # Check if we've fetched all items
                if len(items) < page_size:
                    break
                
                current_page += 1
        finally:
            pbar.close()
        
        logger.info("pagination_complete", endpoint=endpoint, total_items=total_count)
    
    def _extract_payment_title(self, order: Dict[str, Any]) -> str:
        """Extract payment method title from order, including Factura A detection.
        
        Args:
            order: Order data from API
            
        Returns:
            Payment method title string
        """
        # Get default payment method
        payment_method = order.get("payment", {}).get("method", "N/A")
        
        # Look in extension_attributes -> payment_additional_info
        ext_attrs = order.get("extension_attributes", {})
        if ext_attrs:
            pay_add_info = ext_attrs.get("payment_additional_info")
            if isinstance(pay_add_info, list):
                for info in pay_add_info:
                    if isinstance(info, dict) and info.get("key") == "method_title":
                        title_val = info.get("value")
                        if title_val:
                            return title_val
        
        return payment_method
    
    def _process_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single order and extract relevant fields.
        
        Args:
            order: Raw order data from API
            
        Returns:
            Processed order dictionary with mapped column names
        """
        order_id = order.get("increment_id")
        email = order.get("customer_email")
        payment_method = self._extract_payment_title(order)
        
        return {
            "entity_id": order.get("entity_id"),
            "ID": str(order_id),
            "Customer Email": email,
            "customer_email": email,  # Keep both for compatibility
            "Purchase Date": order.get("created_at"),
            "Grand Total (Purchased)": order.get("grand_total"),
            "Status": order.get("status"),
            "Payment_Method": payment_method
        }
    
    def _process_order_items(self, order: Dict[str, Any]) -> list:
        """Process items from a single order.
        
        Args:
            order: Order data from API
            
        Returns:
            List of processed item dictionaries
        """
        order_id = order.get("increment_id")
        email = order.get("customer_email")
        items = []
        
        for item in order.get("items", []):
            # Skip configurable products without parent (duplicates)
            if item.get("product_type") == "configurable" and item.get("parent_item_id") is None:
                continue
            
            items.append({
                "order_id": str(order_id),
                "customer_email": email,
                "sku": item.get("sku"),
                "qty_ordered": item.get("qty_invoiced", item.get("qty_ordered", 0)),
                "row_total": item.get("row_total_incl_tax")
            })
        
        return items
    
    def fetch_orders(
        self,
        min_year: int,
        status: OrderStatus = OrderStatus.PROCESSING
    ) -> pd.DataFrame:
        """Fetch orders from Magento API with field mapping.
        
        Args:
            min_year: Minimum order year to fetch
            status: Order status filter (default: processing)
            
        Returns:
            DataFrame with mapped order data
        """
        min_date = f"{min_year}-01-01 00:00:00"
        
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "created_at",
            "searchCriteria[filterGroups][0][filters][0][value]": min_date,
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "gteq",
            "searchCriteria[filterGroups][1][filters][0][field]": "status",
            "searchCriteria[filterGroups][1][filters][0][value]": status,
            "searchCriteria[filterGroups][1][filters][0][conditionType]": "eq"
        }
        
        logger.info("fetching_orders", min_year=min_year, status=status)
        
        # Fetch and process orders
        orders_raw = list(self._paginate("/orders", params=params, desc="Descargando ordenes"))
        orders_processed = [self._process_order(order) for order in tqdm(orders_raw, desc="Procesando ordenes", unit=" ordenes")]
        df = pd.DataFrame(orders_processed)
        
        logger.info("orders_fetched", count=len(df))
        return df
    
    def fetch_order_items(self, min_year: int) -> pd.DataFrame:
        """Fetch order items from Magento API with field mapping.
        
        This fetches orders with their items in a single call to ensure
        customer_email is available in the items.
        
        Args:
            min_year: Minimum order year
            
        Returns:
            DataFrame with processed order item data including customer_email
        """
        min_date = f"{min_year}-01-01 00:00:00"
        
        params = {
            "searchCriteria[filterGroups][0][filters][0][field]": "created_at",
            "searchCriteria[filterGroups][0][filters][0][value]": min_date,
            "searchCriteria[filterGroups][0][filters][0][conditionType]": "gteq",
            "searchCriteria[filterGroups][1][filters][0][field]": "status",
            "searchCriteria[filterGroups][1][filters][0][value]": OrderStatus.PROCESSING,
            "searchCriteria[filterGroups][1][filters][0][conditionType]": "eq"
        }
        
        logger.info("fetching_order_items", min_year=min_year)
        
        # Fetch orders with full item details
        orders_raw = list(self._paginate("/orders", params=params, desc="Descargando ordenes con items"))
        
        items_data = []
        for order in tqdm(orders_raw, desc="Procesando items", unit=" ordenes"):
            items_data.extend(self._process_order_items(order))
        
        df = pd.DataFrame(items_data)
        logger.info("order_items_fetched", count=len(df))
        return df
    
    def fetch_customers(self) -> pd.DataFrame:
        """Fetch all customers from Magento API.
        
        Returns:
            DataFrame with customer data
        """
        logger.info("fetching_customers")
        
        customers = list(self._paginate("/customers/search", desc="Descargando clientes"))
        df = pd.DataFrame(customers)
        
        logger.info("customers_fetched", count=len(df))
        return df
    
    def _fetch_categories_map(self) -> Dict[str, str]:
        """Fetch category ID to name mapping.
        
        Returns:
            Dictionary mapping category ID to category name
        """
        try:
            response = self._make_request("GET", "/categories")
            categories = response.get("children_data", [])
            cat_map = {}
            
            def extract_categories(cats):
                for cat in cats:
                    cat_id = str(cat.get("id"))
                    cat_name = cat.get("name", cat_id)
                    cat_map[cat_id] = cat_name
                    if "children_data" in cat and cat["children_data"]:
                        extract_categories(cat["children_data"])
            
            extract_categories(categories)
            logger.debug("categories_map_fetched", count=len(cat_map))
            return cat_map
        except Exception as e:
            logger.warning("failed_to_fetch_categories", error=str(e))
            return {}
    
    def _fetch_attribute_options(self, attribute_code: str) -> Dict[str, str]:
        """Fetch attribute options (like brand) mapping.
        
        Args:
            attribute_code: Attribute code to fetch options for
            
        Returns:
            Dictionary mapping option value to label
        """
        try:
            response = self._make_request("GET", f"/products/attributes/{attribute_code}")
            options = response.get("options", [])
            return {opt.get("value", "").strip(): opt.get("label", "") for opt in options}
        except Exception as e:
            logger.warning("failed_to_fetch_attribute", attribute=attribute_code, error=str(e))
            return {}
    
    def _process_product(self, item: Dict[str, Any], cat_map: Dict[str, str], brand_map: Dict[str, str]) -> Dict[str, Any]:
        """Process a single product and extract relevant fields.
        
        Args:
            item: Raw product data from API
            cat_map: Category ID to name mapping
            brand_map: Brand value to label mapping
            
        Returns:
            Processed product dictionary
        """
        cat_string = "Sin Categoria"
        brand_name = "Sin Marca"
        url_key = ""
        image = ""
        
        # Extract from custom_attributes
        for attr in item.get("custom_attributes", []):
            attr_code = attr.get("attribute_code")
            attr_value = attr.get("value")
            
            if attr_code == "category_ids":
                if isinstance(attr_value, list):
                    cat_names = [cat_map.get(str(i), str(i)) for i in attr_value]
                elif isinstance(attr_value, str):
                    cat_names = [cat_map.get(str(i), str(i)) for i in attr_value.split(",")]
                else:
                    cat_names = []
                cat_string = ", ".join(cat_names) if cat_names else "Sin Categoria"
                
            elif attr_code == "brand":
                if attr_value:
                    brand_value_str = str(attr_value).strip()
                    brand_name = brand_map.get(brand_value_str, f"Sin Marca (ID: {brand_value_str})")
            
            elif attr_code == "url_key":
                url_key = attr_value or ""
            elif attr_code == "image":
                image = attr_value or ""
        
        return {
            "id": item.get("id"),
            "sku": item.get("sku"),
            "name": item.get("name"),
            "product_name": item.get("name"),
            "price": item.get("price", 0),
            "categories": cat_string,
            "brand": brand_name,
            "url_key": url_key,
            "image": image
        }
    
    def fetch_catalog(self) -> pd.DataFrame:
        """Fetch product catalog from Magento API.
        
        Processes products to extract categories, brand, and product_name
        from custom_attributes.
        
        Returns:
            DataFrame with processed product data
        """
        logger.info("fetching_catalog")
        
        # Fetch mappings first
        cat_map = self._fetch_categories_map()
        brand_map = self._fetch_attribute_options("brand")
        
        # Fetch and process products
        products_raw = list(self._paginate("/products", desc="Descargando productos"))
        products_processed = [
            self._process_product(item, cat_map, brand_map) 
            for item in tqdm(products_raw, desc="Procesando productos", unit=" items")
        ]
        
        df = pd.DataFrame(products_processed)
        
        logger.info("catalog_fetched", count=len(df))
        return df
    
    def fetch_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Fetch a single product by SKU.
        
        Args:
            sku: Product SKU
            
        Returns:
            Product data dictionary or None if not found
        """
        try:
            endpoint = f"/products/{sku}"
            return self._make_request("GET", endpoint)
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    def update_product_stock(self, sku: str, stock_qty: int) -> bool:
        """Update product stock quantity.
        
        Args:
            sku: Product SKU
            stock_qty: New stock quantity
            
        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"/products/{sku}/stockItems/1"
            data = {"qty": stock_qty, "is_in_stock": stock_qty > 0}
            
            self._make_request("PUT", endpoint, json_data=data)
            logger.info("stock_updated", sku=sku, qty=stock_qty)
            return True
            
        except APIError as e:
            logger.error("stock_update_failed", sku=sku, error=str(e))
            return False
    
    def update_product_price(self, sku: str, price: float) -> bool:
        """Update product price.
        
        Args:
            sku: Product SKU
            price: New price
            
        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"/products/{sku}"
            data = {"product": {"price": price}}
            
            self._make_request("PUT", endpoint, json_data=data)
            logger.info("price_updated", sku=sku, price=price)
            return True
            
        except APIError as e:
            logger.error("price_update_failed", sku=sku, error=str(e))
            return False
    
    # =========================================================================
    # Helper methods for operations module
    # =========================================================================
    
    def get_store_views(self) -> List[Dict]:
        """Get all active store views excluding admin.
        
        Returns:
            List of store view dictionaries
        """
        try:
            endpoint = "/store/storeViews"
            response = self._make_request("GET", endpoint)
            stores = response if isinstance(response, list) else response.get("items", [])
            
            # Filter active stores excluding admin
            active_stores = [
                s for s in stores
                if s.get("is_active") == 1 and s.get("code") != "admin"
            ]
            
            logger.info("store_views_fetched", count=len(active_stores))
            return active_stores
            
        except APIError as e:
            logger.error("failed_to_fetch_store_views", error=str(e))
            return []
    
    def update_product_short_description(
        self,
        sku: str,
        description: str,
        store_view: str = "all"
    ) -> bool:
        """Update product short description for a specific store view.
        
        Args:
            sku: Product SKU
            description: HTML content for short description
            store_view: Store view code (default: "all")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use store-specific endpoint
            base_url = self.settings.magento_url
            endpoint = f"/rest/{store_view}/V1/products/{sku}"
            url = f"{base_url}{endpoint}"
            
            data = {
                "product": {
                    "sku": sku,
                    "custom_attributes": [
                        {
                            "attribute_code": "short_description",
                            "value": description
                        }
                    ]
                }
            }
            
            headers = self._get_headers()
            response = self.session.put(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            logger.debug("short_description_updated", sku=sku, store=store_view)
            return True
            
        except Exception as e:
            logger.debug("short_description_update_failed", sku=sku, store=store_view, error=str(e))
            return False
    
    def get_brand_map(self) -> Dict[str, str]:
        """Get mapping of brand IDs to brand names.
        
        Returns:
            Dictionary mapping brand_id -> brand_name
        """
        try:
            endpoint = "/products/attributes/brand/options"
            response = self._make_request("GET", endpoint)
            options = response if isinstance(response, list) else response.get("items", [])
            
            brand_map = {}
            for opt in options:
                if opt.get("value") and opt.get("label"):
                    brand_map[str(opt["value"])] = opt["label"]
            
            logger.info("brand_map_fetched", count=len(brand_map))
            return brand_map
            
        except APIError as e:
            logger.error("failed_to_fetch_brand_map", error=str(e))
            return {}
    
    def _paginate_request(
        self,
        endpoint: str,
        page_size: Optional[int] = None,
        params: Optional[Dict] = None,
        desc: str = "Procesando"
    ) -> Iterator[Dict[str, Any]]:
        """Make paginated request and yield items.
        
        Args:
            endpoint: API endpoint path
            page_size: Items per page
            params: Additional query parameters
            desc: Description for progress bar
            
        Yields:
            Individual items from all pages
        """
        page_size = page_size or self.settings.page_size
        current_page = 1
        
        request_params = {
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[currentPage]": current_page
        }
        if params:
            request_params.update(params)
        
        first_response = self._make_request("GET", endpoint, params=request_params)
        first_items = first_response.get("items", [])
        total_count = first_response.get("total_count", len(first_items))
        
        if not first_items:
            return
        
        for item in first_items:
            yield item
        
        if len(first_items) < page_size or len(first_items) >= total_count:
            return
        
        current_page = 2
        pbar = tqdm(total=total_count, initial=len(first_items), desc=desc, unit=" items")
        
        try:
            while True:
                request_params["searchCriteria[currentPage]"] = current_page
                response = self._make_request("GET", endpoint, params=request_params)
                items = response.get("items", [])
                
                if not items:
                    break
                
                for item in items:
                    yield item
                    pbar.update(1)
                
                if len(items) < page_size:
                    break
                
                current_page += 1
        finally:
            pbar.close()
    
    def get_products_by_date_range(
        self,
        start_date: str,
        end_date: str,
        page_size: Optional[int] = None
    ) -> Iterator[Dict]:
        """Get all products created within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD HH:MM:SS)
            end_date: End date (YYYY-MM-DD HH:MM:SS)
            page_size: Items per page
            
        Yields:
            Product dictionaries
        """
        page_size = page_size or self.settings.page_size
        
        params = {
            "searchCriteria[filter_groups][0][filters][0][field]": "created_at",
            "searchCriteria[filter_groups][0][filters][0][value]": start_date,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "gteq",
            "searchCriteria[filter_groups][1][filters][0][field]": "created_at",
            "searchCriteria[filter_groups][1][filters][0][value]": end_date,
            "searchCriteria[filter_groups][1][filters][0][condition_type]": "lteq",
        }
        
        logger.info("fetching_products_by_date_range", start=start_date, end=end_date)
        
        yield from self._paginate_request(
            "/products",
            page_size=page_size,
            params=params,
            desc="Obteniendo productos"
        )
    
    def get_products_by_category(
        self,
        category_id: int,
        page_size: Optional[int] = None
    ) -> Iterator[Dict]:
        """Get all products from a specific category.
        
        Args:
            category_id: Category ID
            page_size: Items per page
            
        Yields:
            Product dictionaries
        """
        page_size = page_size or self.settings.page_size
        
        params = {
            "searchCriteria[filter_groups][0][filters][0][field]": "category_id",
            "searchCriteria[filter_groups][0][filters][0][value]": category_id,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
        }
        
        logger.info("fetching_products_by_category", category_id=category_id)
        
        yield from self._paginate_request(
            "/products",
            page_size=page_size,
            params=params,
            desc=f"Categoría {category_id}"
        )
