export interface Product {
  id: number
  name: string
  category: string | null
  category_id?: number | null
  category_name?: string | null
  base_name?: string | null
  calories: number | null
  proteins: number | null
  fats: number | null
  carbs: number | null
  variation?: string | null
  kbju_status: 'full' | 'partial' | 'missing'
}

export interface RecipeIngredient {
  id: number
  product_id: number
  product_name: string
  amount: number
  amount_text?: string | null
  amount_is_exact?: boolean
  unit: string
  note: string | null
}

export interface Recipe {
  id: number
  title: string
  description: string | null
  base_servings: number
  instructions: string | null
  created_at: string
  ingredients: RecipeIngredient[]
}

export interface Nutrition {
  calories: number | null
  proteins: number | null
  fats: number | null
  carbs: number | null
  known_calories: number | null
  known_proteins: number | null
  known_fats: number | null
  known_carbs: number | null
  accuracy: 'exact' | 'approximate'
  coverage_percent: number
  missing_components: string[]
  missing_ingredients: string[]
}

export interface Calculation {
  recipe_id: number
  recipe_title: string
  target_servings: number
  ingredients: { product_name: string; amount: number; unit: string }[]
  total: Nutrition
  per_serving: Nutrition
  per_100g: Nutrition
  cost: {
    total_cost: number | null
    currency: string
    missing_prices: string[]
    known_ingredients: number
    ingredient_count: number
    coverage_percent: number
  }
}
