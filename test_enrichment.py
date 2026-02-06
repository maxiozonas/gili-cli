#!/usr/bin/env python3
import sys
import json
from src.config import Settings
from src.core import MagentoAPIClient

settings = Settings()
client = MagentoAPIClient(settings)
client.authenticate()

product = client.fetch_product_by_sku('100553')
enriched = client.enrich_product_data(product)

custom_attrs = enriched.get('custom_attributes', [])
attrs_with_label = [attr for attr in custom_attrs if 'label' in attr]

print('=== ATRIBUTOS ENRIQUECIDOS ===')
print(f'Total de atributos: {len(custom_attrs)}')
print(f'Atributos con label: {len(attrs_with_label)}')
print()

print('Atributos con label (todos):')
for attr in attrs_with_label:
    value = str(attr.get('value', ''))[:50]
    label = str(attr.get('label', ''))[:50]
    print(f"  {attr.get('attribute_code'):30} | {value:50} -> {label}")

print()
print('Atributos SIN label (primeros 5):')
attrs_without_label = [attr for attr in custom_attrs if 'label' not in attr][:5]
for attr in attrs_without_label:
    value = str(attr.get('value', ''))[:50]
    print(f"  {attr.get('attribute_code'):30} | {value}")
