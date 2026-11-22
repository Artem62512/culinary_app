import type { Recipe } from '@/types'

const API_BASE = import.meta.env.DEV ? '/api' : ''

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const auth = sessionStorage.getItem('culinary_auth')
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(auth ? { Authorization: `Basic ${auth}` } : {}),
      ...(options?.headers || {}),
    },
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API ${res.status}: ${err}`)
  }
  if (res.status === 204) return true as unknown as T;
  return res.json()
}

export const api = {
  getProducts: (q?: string, categoryId?: number, limit = 100, offset = 0) => apiFetch<any[]>(`/products?${new URLSearchParams({ ...(q ? { q } : {}), ...(categoryId ? { category_id: String(categoryId) } : {}), limit: String(limit), offset: String(offset) }).toString()}`),
  matchProduct: (q: string) => apiFetch<any | null>(`/products/match?q=${encodeURIComponent(q)}`),
  getStoreProducts: (universalProductId: number) => apiFetch<any[]>(`/products/store-products?universal_product_id=${universalProductId}`),
  createStoreProduct: (body: any) => apiFetch<any>('/products/store-products', { method: 'POST', body: JSON.stringify(body) }),
  getStoreProductPrices: (id: number) => apiFetch<any[]>(`/products/store-products/${id}/prices`),
  addStoreProductPrice: (id: number, body: any) => apiFetch<any>(`/products/store-products/${id}/prices`, { method: 'POST', body: JSON.stringify(body) }),
  updateProductStatus: (id: number, status: string) => apiFetch<any>(`/products/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  getProduct: (id: number) => apiFetch<any>(`/products/${id}`),
  getCategories: () => apiFetch<string[]>('/products/categories'),
  getCatalogCategories: () => apiFetch<{ id: number; name: string; slug: string }[]>('/products/catalog/categories'),
  getCatalogQuality: () => apiFetch<any>('/products/catalog/quality'),
  createProduct: (body: any) => apiFetch<any>('/products', { method: 'POST', body: JSON.stringify(body) }),
  updateProduct: (id: number, body: any) => apiFetch<any>(`/products/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteProduct: (id: number) => apiFetch<boolean>(`/products/${id}`, { method: 'DELETE' }),
  getProductUnitPrices: (id: number) => apiFetch<any>(`/products/${id}/prices`),
  updateProductUnitPrices: (id: number, body: any) => apiFetch<any>(`/products/${id}/prices`, { method: 'PUT', body: JSON.stringify(body) }),
  refreshPyaterochkaPrices: (id: number) => apiFetch<any>(`/products/${id}/refresh-prices/pyaterochka`, { method: 'POST' }),
  refreshProductKbju: (id: number) => apiFetch<any>(`/products/${id}/refresh-kbju`, { method: 'POST' }),
  refreshMissingKbju: (limit = 20) => apiFetch<any>(`/products/catalog/refresh-kbju/missing?limit=${limit}`, { method: 'POST' }),
  getProductGroups: (category?: string, q?: string) => apiFetch<{ base_name: string; aliases: string[] }[]>(`/products/groups?${new URLSearchParams({ ...(category ? { category } : {}), ...(q ? { q } : {}) }).toString()}`),
  getProductVariations: (baseName: string) => apiFetch<any[]>(`/products/groups/variations?base_name=${encodeURIComponent(baseName)}`),
  getProductAliases: (id: number) => apiFetch<{ id: number; product_id: number; alias: string }[]>(`/products/${id}/aliases`),
  addProductAlias: (id: number, alias: string) => apiFetch<any>(`/products/${id}/aliases`, { method: 'POST', body: JSON.stringify({ alias }) }),
  deleteProductAlias: (id: number, aliasId: number) => apiFetch<boolean>(`/products/${id}/aliases/${aliasId}`, { method: 'DELETE' }),
  
  getRecipes: () => apiFetch<Recipe[]>('/recipes'),
  getRecipe: (id: number) => apiFetch<Recipe>(`/recipes/${id}`),
  getShoppingList: (id: number) => apiFetch<any>(`/shopping-lists/${id}`),
  checkAuth: () => apiFetch<{ authenticated: boolean; username: string }>('/auth/check'),
  createRecipe: (body: any) => apiFetch<any>('/recipes', { method: 'POST', body: JSON.stringify(body) }),
  updateRecipe: (id: number, body: any) => apiFetch<any>(`/recipes/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRecipe: (id: number) => apiFetch<boolean>(`/recipes/${id}`, { method: 'DELETE' }),
  calculateRecipe: (id: number, servings: number) => apiFetch<any>(`/recipes/${id}/calculate?servings=${servings}`),
  
  getCart: () => apiFetch<any>('/shopping-lists/cart/current'),
  addToCart: (product_id: number, amount: number, unit: string) => 
    apiFetch<any>(`/shopping-lists/cart/add?product_id=${product_id}&amount=${amount}&unit=${unit}`, { method: 'POST' }),
  removeFromCart: (itemId: number) => apiFetch<any>(`/shopping-lists/cart/item/${itemId}`, { method: 'DELETE' }),
  updateCartItem: (itemId: number, body: {
    amount?: number
    unit?: string
    price_override?: number | null
    package_price_override?: number | null
    package_amount_override?: number | null
    package_unit_override?: string | null
    package_amount_in_recipe_unit_override?: number | null
    price_mode?: 'basis' | 'package'
    selected_store_product_id?: number | null
  }) => apiFetch<any>(`/shopping-lists/cart/item/${itemId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  saveCartPriceToHistory: (itemId: number) => apiFetch<any>(`/shopping-lists/cart/item/${itemId}/save-price`, { method: 'POST' }),
}
