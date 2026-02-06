# ✅ Campo attribute_set_id Agregado

## 🎯 Campos Finales del Comando `product`

```json
{
  "id": 20203,
  "sku": "100553",
  "name": "Puerta Corrediza de Embutir Cedro C/15 80x200cm Plac Corr",
  "attribute_set_id": 111,
  "custom_attributes": [...],
  "categories": "Corrediza de embutir",
  "category_names": ["Corrediza de embutir"]
}
```

---

## 📋 Lista Completa de Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **id** | Integer | ID del producto en Magento |
| **sku** | String | Código SKU del producto |
| **name** | String | Nombre del producto |
| **attribute_set_id** | Integer | ID del set de atributos |
| **custom_attributes** | Array | Lista de atributos custom con labels |
| **categories** | String | Categorías como string |
| **category_names** | Array | Categorías como array |

---

## 📊 Estadísticas Finales

| Métrica | Valor |
|---------|-------|
| **Campos principales** | 7 |
| **Atributos custom** | 14 (filtrados de 29) |
| **Atributos con labels** | 11 de 14 |
| **Tamaño del JSON** | ~40 líneas |
| **Reducción total** | 60% más compacto |

---

## 🚀 Ejemplo de Uso

```bash
# Ver producto con todos los campos
python main.py product 100553

# Guardar a archivo
python main.py product 100553 --output producto.json

# JSON compacto
python main.py product 100553 --compact

# Extraer attribute_set_id con jq
python main.py product 100553 --compact | jq '.attribute_set_id'
```

---

**¡Implementación completada con attribute_set_id! 🎉**
