# Proposed Data Structure for Culinary App - Phase 7 Expansion

## 1. Product Catalog Structure (products.json)
Products must be stored with detailed, verifiable characteristics.

Example Structure for a Product:
{
  "id": "unique_product_id",
  "name": "Картофель",
  "category_id": "...",
  "variants": [
    {
      "name": "Картошка",
      "synonyms": ["картофель"],
      "characteristics": {
        "moisture_content": "15%",
        "type": "Starchy Root",
        "state": "Fresh"
      },
      "nutritional_info": {
        "calories_per_100g": 77,
        "protein_g_per_100g": 2.0,
        "carbs_g_per_100g": 17.5
      }
    },
    {
      "name": "Картошка (средняя)",
      "synonyms": ["картофель"],
      "characteristics": {
        "moisture_content": "18%",
        "type": "Starchy Root",
        "state": "Fresh"
      },
      "nutritional_info": {
        "calories_per_100g": 85,
        "protein_g_per_100g": 2.2,
        "carbs_g_per_100g": 20.0
      }
    }
  ],
  "synonyms": {
    "картофель": ["картошка"],
    "баклажан": ["синенький"]
  }
}

## 2. Synonym Management (synonyms.json)
Stores relationships between names, ensuring normalization.

{
  "products": {
    "картофель": {
      "synonyms": ["картошка"]
    },
    "баклажан": {
      "synonyms": ["синенький"]
    }
  }
}

## 3. Nutritional Data Tracking (nutrition_log.json)
For tracking verification and moderation.

{
  "product_id": "unique_product_id",
  "check_date": "YYYY-MM-DD",
  "status": "Pending Review" | "Verified" | "Rejected",
  "reason": "Reason for status change or rejection",
  "source": "API_X" | "Manual_Entry",
  "values_checked": {
    "calories_per_100g": 77,
    "protein_g_per_100g": 2.0,
    "carbs_g_per_100g": 17.5
  },
  "moderation_notes": "Manual review required for this entry."
}