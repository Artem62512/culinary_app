
import { useState, useEffect, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Product, Recipe } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from '@/components/ui/card'
import { ProductCombobox } from '@/components/ProductCombobox'
import { detectUnit } from '@/lib/units'
import { parseRecipeText } from '@/lib/recipeParser'
import { toast } from 'sonner'

// Тип строки ингредиента в форме
interface IngredientRow {
  category: string
  base_name: string
  product_id: number | ''
  amount: string
  unit: string
  note: string
  preserveParsedValues?: boolean
}

// Результат разбора количества
interface ParsedAmount {
  amount: number
  amount_text: string
  amount_is_exact: boolean
}

// Данные ингредиента для отправки на сервер
interface ParsedIngredientPayload {
  product_id: number
  amount: number
  amount_text: string
  amount_is_exact: boolean
  unit: string
  note: string | null
}

// Разбор количества: число, дробь, диапазон или «по вкусу»
function parseAmountText(
  value: string,
  unit: string,
): ParsedAmount | null {
  const text = value.trim()

  // Специальная единица «по вкусу»
  if (unit === 'to_taste' || text.toLowerCase() === 'по вкусу') {
    return {
      amount: 0,
      amount_text: 'по вкусу',
      amount_is_exact: false,
    }
  }

  if (!text) return null

  const parseNumber = (part: string): number | null => {
    const normalized = part.trim().replace(',', '.')

    // Десятичное число
    if (/^\d+(?:\.\d+)?$/.test(normalized)) {
      const number = Number(normalized)
      return Number.isFinite(number) ? number : null
    }

    // Обыкновенная дробь: 1/2, 3/4 и т. п.
    const fraction = normalized.match(/^(\d+)\s*\/\s*(\d+)$/)

    if (fraction) {
      const numerator = Number(fraction[1])
      const denominator = Number(fraction[2])

      if (denominator === 0) return null

      const result = numerator / denominator

      return Number.isFinite(result) ? result : null
    }

    return null
  }

  // Диапазон: 0,5–1 или 2-3
  const range = text.match(/^(.+?)\s*[-–—]\s*(.+)$/)

  if (range) {
    const min = parseNumber(range[1])
    const max = parseNumber(range[2])

    if (
      min === null ||
      max === null ||
      min <= 0 ||
      max < min ||
      max > 100000
    ) {
      return null
    }

    return {
      amount: 0,
      amount_text: text,
      amount_is_exact: false,
    }
  }

  // Точное количество
  const amount = parseNumber(text)

  if (
    amount === null ||
    !Number.isFinite(amount) ||
    amount <= 0 ||
    amount > 100000
  ) {
    return null
  }

  return {
    amount,
    amount_text: text,
    amount_is_exact: true,
  }
}

export function CreateRecipePage({
  onCreated,
  onCancel,
  recipeId,
}: {
  onCreated: (id: number) => void
  onCancel: () => void
  recipeId?: number
}) {
  const qc = useQueryClient()

  const [title, setTitle] = useState('')
  const [parserText, setParserText] = useState('')
  const [baseServings, setBaseServings] = useState(2)
  const [instructions, setInstructions] = useState('')
  const [description, setDescription] = useState('')

  const [ingredients, setIngredients] = useState<IngredientRow[]>([
    {
      category: '',
      base_name: '',
      product_id: '',
      amount: '50',
      unit: 'g',
      note: '',
    },
  ])

  const [loadedRecipe, setLoadedRecipe] = useState(false)

  // Загрузка рецепта для редактирования
  const {
    data: existingRecipe,
    isLoading: isRecipeLoading,
    error: recipeLoadError,
  } = useQuery<Recipe>({
    queryKey: ['recipe', recipeId],
    queryFn: () => api.getRecipe(recipeId!),
    enabled: recipeId !== undefined,
  })

  // Заполнение формы данными существующего рецепта
  useEffect(() => {
    if (!existingRecipe || loadedRecipe) return

    let cancelled = false

    const load = async () => {
      const rows: IngredientRow[] = await Promise.all(
        existingRecipe.ingredients.map(
          async (ingredient): Promise<IngredientRow> => {
            const product = ingredient.product_id
              ? await api.getProduct(ingredient.product_id)
              : null

            return {
              category:
                product?.category_name || product?.category || '',

              base_name:
                product?.base_name ||
                ingredient.product_name ||
                product?.name ||
                '',

              product_id: ingredient.product_id,

              amount:
                ingredient.amount_text ||
                String(ingredient.amount),

              unit: ingredient.unit,

              note: ingredient.note || '',
            }
          },
        ),
      )

      if (cancelled) return

      setTitle(existingRecipe.title)
      setBaseServings(existingRecipe.base_servings)
      setDescription(existingRecipe.description || '')
      setInstructions(existingRecipe.instructions || '')
      setIngredients(rows)
      setLoadedRecipe(true)
    }

    load().catch((error) => {
      toast.error(
        'Не удалось загрузить состав рецепта: ' + error.message,
      )
    })

    return () => {
      cancelled = true
    }
  }, [existingRecipe, loadedRecipe])

  // Категории продуктов
  const { data: categories } = useQuery<string[]>({
    queryKey: ['categories'],
    queryFn: () => api.getCategories(),
  })

  // Создание или обновление рецепта
  const createMutation = useMutation({
    mutationFn: (body: any) =>
      recipeId === undefined
        ? api.createRecipe(body)
        : api.updateRecipe(recipeId, body),

    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ['recipes'] })
      qc.invalidateQueries({ queryKey: ['recipe', data.id] })
      qc.invalidateQueries({ queryKey: ['calc', data.id] })
      const ingredientIds: number[] = Array.from(new Set<number>(
        (data.ingredients || []).flatMap((ingredient: any) => {
          const productId = Number(ingredient?.product_id)
          return Number.isInteger(productId) && productId > 0 ? [productId] : []
        }),
      ))
      ingredientIds.forEach((productId) => {
        api.refreshPyaterochkaPrices(productId).then(() => {
          qc.invalidateQueries({ queryKey: ['store-products', productId] })
          qc.invalidateQueries({ queryKey: ['calc', data.id] })
          qc.invalidateQueries({ queryKey: ['cart'] })
        }).catch(() => undefined)
      })

      toast.success(
        recipeId === undefined
          ? 'Рецепт создан'
          : 'Изменения сохранены',
      )

      onCreated(data.id)
    },

    onError: (err: any) => {
      toast.error('Ошибка: ' + err.message)
    },
  })

  // Обновление отдельной строки ингредиента
  const updateRow = useCallback((
    idx: number,
    patch: Partial<IngredientRow>,
  ) => {
    setIngredients((prev) =>
      prev.map((row, i) =>
        i === idx ? { ...row, ...patch } : row,
      ),
    )
  }, [])

  // Добавление строки ингредиента
  const addRow = () => {
    setIngredients((prev) => [
      ...prev,
      {
        category: '',
        base_name: '',
        product_id: '',
        amount: '50',
        unit: 'g',
        note: '',
      },
    ])
  }

  // Удаление строки ингредиента
  const removeRow = (idx: number) => {
    setIngredients((prev) =>
      prev.filter((_, i) => i !== idx),
    )
  }

  const handleParseRecipe = () => {
    if (!parserText.trim()) {
      toast.error('Вставьте текст рецепта')
      return
    }

    const parsed = parseRecipeText(parserText)

    if (
      !parsed.title &&
      !parsed.ingredients.length &&
      !parsed.instructions
    ) {
      toast.error('Не удалось распознать рецепт. Проверьте текст.')
      return
    }

    if (parsed.title) setTitle(parsed.title)
    if (parsed.servings) setBaseServings(parsed.servings)
    if (parsed.description) setDescription(parsed.description)
    if (parsed.instructions) setInstructions(parsed.instructions)

    if (parsed.ingredients.length > 0) {
      setIngredients(
        parsed.ingredients.map((item) => ({
          category: '',
          base_name: item.name,
          product_id: '',
          amount: item.amount,
          unit: item.unit,
          note: item.note,
          preserveParsedValues: true,
        })),
      )
    }

    toast.success(
      `Распознано ингредиентов: ${parsed.ingredients.length}. Проверьте заполненные поля.`,
    )
  }

  // Сохранение рецепта
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!title.trim()) {
      toast.warning('Введите название рецепта')
      return
    }

    if (!Number.isInteger(baseServings) || baseServings < 1) {
      toast.warning('Количество порций должно быть целым числом больше нуля')
      return
    }

    // Оставляем только заполненные ингредиенты
    const validRows = ingredients.filter((row) => row.product_id !== '')

    if (validRows.length !== ingredients.length) {
      const missingNames = ingredients
        .filter((row) => row.product_id === '')
        .map((row) => row.base_name.trim())
        .filter(Boolean)
      toast.warning(
        missingNames.length
          ? `Добавьте ингредиенты в каталог или выберите существующие: ${missingNames.join(', ')}`
          : 'Для каждой строки выберите продукт из каталога',
      )
      return
    }

    if (validRows.length === 0) {
      toast.warning('Добавьте хотя бы один ингредиент')
      return
    }

    const parsedIngredients: ParsedIngredientPayload[] = []

    for (const row of validRows) {
      const parsed = parseAmountText(row.amount, row.unit)

      if (!parsed) {
        toast.error(
          `Некорректное количество: "${row.amount}"`,
        )
        return
      }

      parsedIngredients.push({
        product_id: Number(row.product_id),

        amount: parsed.amount,
        amount_text: parsed.amount_text,
        amount_is_exact: parsed.amount_is_exact,

        unit: row.unit,

        note: row.note.trim() || null,
      })
    }

    createMutation.mutate({
      title: title.trim(),
      description: description.trim() || null,
      base_servings: baseServings,
      instructions,
      ingredients: parsedIngredients,
    })
  }

  // Состояние загрузки рецепта
  if (
    recipeId !== undefined &&
    (isRecipeLoading || (existingRecipe && !loadedRecipe))
  ) {
    return (
      <div className="p-8 text-center">
        Загрузка рецепта для редактирования...
      </div>
    )
  }

  // Ошибка загрузки рецепта
  if (recipeLoadError) {
    return (
      <div className="p-8 text-center text-red-500">
        Не удалось загрузить рецепт:{' '}
        {(recipeLoadError as Error).message}
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-6">
      {recipeId === undefined && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">
              Заполнение рецепта из текста
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Вставьте текст рецепта из сайта, книги или заметок.
              Парсер попробует определить название, ингредиенты и
              способ приготовления. Перед сохранением проверьте результат.
            </p>

            <textarea
              value={parserText}
              onChange={(event) => setParserText(event.target.value)}
              placeholder="Вставьте сюда текст рецепта..."
              rows={10}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
            />


            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={handleParseRecipe}
                disabled={!parserText.trim()}
              >
                Распознать рецепт
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={() => setParserText('')}
                disabled={!parserText}
              >
                Очистить
              </Button>
            </div>

          </CardContent>
        </Card>
      )}

      <Card className="shadow-sm">
        <form onSubmit={handleSubmit}>
          <CardHeader className="border-b pb-6">
            <CardTitle className="text-2xl font-semibold">
              {recipeId === undefined
                ? 'Создание рецепта'
                : 'Редактирование рецепта'}
            </CardTitle>
          </CardHeader>

          <CardContent className="space-y-8 pt-6">
            {/* Название */}
            <div className="space-y-3">
              <Label className="text-base">
                Название рецепта
              </Label>

              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Например, Блины классические"
                className="h-11 text-base"
              />
            </div>

            {/* Описание */}
            <div className="space-y-3">
              <Label className="text-base">
                Краткое описание
              </Label>

              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Кратко опишите блюдо..."
                className="flex w-full rounded-md border border-input bg-background px-3 py-3 text-sm"
              />
            </div>

            {/* Количество порций */}
            <div className="space-y-3 w-40">
              <Label className="text-base">
                Количество порций
              </Label>

              <Input
                type="number"
                min={1}
                step={1}
                value={baseServings}
                onChange={(e) =>
                  setBaseServings(Number(e.target.value))
                }
                className="h-11"
              />
            </div>

            {/* Ингредиенты */}
            <div className="space-y-4">
              <Label className="text-base font-semibold">
                Ингредиенты
              </Label>

              <div className="space-y-4">
                {ingredients.map((row, idx) => {
                  const selectedElsewhere = ingredients
                    .filter((_, i) => i !== idx)
                    .map((r) => r.base_name)
                    .filter(Boolean)

                  return (
                    <IngredientRowInput
                      key={idx}
                      row={row}
                      idx={idx}
                      categories={categories}
                      updateRow={updateRow}
                      removeRow={removeRow}
                      selectedElsewhere={selectedElsewhere}
                    />
                  )
                })}
              </div>

              <Button
                type="button"
                variant="outline"
                className="w-full border-dashed h-12"
                onClick={addRow}
              >
                + Добавить ингредиент
              </Button>
            </div>

            {/* Инструкции */}
            <div className="space-y-3">
              <Label className="text-base">
                Инструкции
              </Label>

              <textarea
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                rows={5}
                placeholder="Опишите процесс приготовления..."
                className="flex w-full rounded-md border border-input bg-background px-3 py-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
          </CardContent>

          <CardFooter className="flex gap-3 border-t pt-6 pb-6 bg-muted/20">
            <Button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6"
            >
              {createMutation.isPending
                ? 'Сохранение...'
                : recipeId === undefined
                  ? 'Создать рецепт'
                  : 'Сохранить изменения'}
            </Button>

            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              className="px-6"
            >
              Отмена
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}

// Компонент отдельной строки ингредиента
function IngredientRowInput({
  row,
  idx,
  categories,
  updateRow,
  removeRow,
  selectedElsewhere,
}: {
  row: IngredientRow
  idx: number
  categories: string[] | undefined
  updateRow: (
    idx: number,
    patch: Partial<IngredientRow>,
  ) => void
  removeRow: (idx: number) => void
  selectedElsewhere: string[]
}) {
  const qc = useQueryClient()

  // Добавление пользовательского продукта в каталог
  const addToCatalogMutation = useMutation({
    mutationFn: () =>
      api.createProduct({
        name: row.base_name.trim(),
        base_name: row.base_name.trim(),
        category: row.category || 'Другое',
      }),

    onSuccess: (product: Product) => {
      updateRow(idx, {
        category: product.category_name || product.category || '',
        base_name: product.base_name || product.name,
        product_id: product.id,
      })
      api.refreshPyaterochkaPrices(product.id).then(() => {
        qc.invalidateQueries({ queryKey: ['store-products', product.id] })
      }).catch(() => undefined)
      api.refreshProductKbju(product.id).then(() => {
        qc.invalidateQueries({ queryKey: ['catalog-products'] })
        qc.invalidateQueries({ queryKey: ['catalog-quality'] })
        qc.invalidateQueries({ queryKey: ['calc'] })
      }).catch(() => undefined)

      qc.invalidateQueries({ queryKey: ['groups'] })
      qc.invalidateQueries({
        queryKey: ['catalog-products'],
      })
      qc.invalidateQueries({
        queryKey: ['catalog-products-for-matching'],
      })

      toast.success('Ингредиент добавлен в общий каталог')
    },

    onError: (error: Error) => {
      toast.error(
        'Не удалось добавить продукт: ' + error.message,
      )
    },
  })

  // Поиск возможных совпадений по введённому названию.
  // Результаты не выбираются автоматически: пользователь подтверждает совпадение.
  const { data: matchingProducts = [] } = useQuery<Product[]>({
    queryKey: ['recipe-product-search', row.base_name],
    queryFn: () => api.getProducts(row.base_name.trim(), undefined, 20, 0),
    enabled: !!row.base_name.trim() && row.product_id === '',
  })

  // Точное однозначное совпадение связывается автоматически.
  // Частичные и неоднозначные совпадения остаются для ручного подтверждения.
  const { data: exactMatch } = useQuery<Product | null>({
    queryKey: ['recipe-product-exact-match', row.base_name],
    queryFn: () => api.matchProduct(row.base_name.trim()),
    enabled: !!row.base_name.trim() && row.product_id === '',
  })

  useEffect(() => {
    if (!exactMatch || row.product_id !== '') return
    updateRow(idx, {
      product_id: exactMatch.id,
      category: exactMatch.category_name || exactMatch.category || '',
      base_name: exactMatch.base_name || exactMatch.name,
    })
    api.refreshPyaterochkaPrices(exactMatch.id).then(() => {
      qc.invalidateQueries({ queryKey: ['store-products', exactMatch.id] })
      qc.invalidateQueries({ queryKey: ['calc'] })
      qc.invalidateQueries({ queryKey: ['cart'] })
    }).catch(() => undefined)
    api.refreshProductKbju(exactMatch.id).then(() => {
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['calc'] })
    }).catch(() => undefined)
  }, [exactMatch, row.product_id, idx, updateRow, qc])

  // Группы продуктов
  const { data: groups } = useQuery<
    { base_name: string; aliases?: string[] }[]
  >({
    queryKey: ['groups', row.category],
    queryFn: () =>
      api.getProductGroups(row.category || undefined),
  })

  // Варианты продукта
  const { data: variations } = useQuery<Product[]>({
    queryKey: ['variations', row.base_name],
    queryFn: () =>
      api.getProductVariations(row.base_name),
    enabled: !!row.base_name,
  })

  // Изменение категории
  const handleCategoryChange = (category: string) => {
    updateRow(idx, {
      category,
      product_id: '',
    })
  }

  // Изменение базового названия продукта
  const handleBaseNameChange = (base_name: string) => {
    updateRow(idx, {
      base_name,
      product_id: '',
    })
  }

  // Автоматический выбор единственного варианта продукта
  useEffect(() => {
    if (
      variations &&
      variations.length === 1 &&
      row.product_id === ''
    ) {
      const product = variations[0]

      if (row.preserveParsedValues) {
        updateRow(idx, {
          product_id: product.id,
        })
        api.refreshPyaterochkaPrices(product.id).catch(() => undefined)
      } else {
        const unit = detectUnit(product.name)
        const amount = unit === 'pcs' ? '1' : '50'

        updateRow(idx, {
          product_id: product.id,
          unit,
          amount,
        })
        api.refreshPyaterochkaPrices(product.id).catch(() => undefined)
      }
    }
  }, [
    variations,
    row.product_id,
    row.preserveParsedValues,
    idx,
    updateRow,
  ])
  // Выбор конкретного варианта продукта
  const handleVariationChange = (productIdStr: string) => {
    const productId =
      productIdStr === '' ? '' : Number(productIdStr)

    updateRow(idx, { product_id: productId })
    if (productId !== '') {
      api.refreshPyaterochkaPrices(productId).catch(() => undefined)
    }
  }

  // Изменение единицы измерения
  const handleUnitChange = (newUnit: string) => {
    updateRow(idx, { unit: newUnit })
  }

  const categoryItems =
    categories?.map((category) => ({
      value: category,
      label: category,
    })) || []

  const productItems =
    groups?.map((group) => ({
      value: group.base_name,
      label: group.base_name,
      searchText: [
        group.base_name,
        ...(group.aliases || []),
      ].join(' '),
    })) || []

  return (
    <div className="relative bg-muted/30 p-4 rounded-lg border border-border/50">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => removeRow(idx)}
        className="absolute top-3 right-3 h-7 w-7 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
      >
        ✕
      </Button>

      <div className="space-y-4">
        <div className="flex items-center justify-between pr-8">
          <span className="text-sm font-medium">
            {row.product_id !== ''
              ? 'Продукт из общего каталога'
              : 'Выберите продукт или добавьте новый'}
          </span>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pr-8">
          <div className="w-full sm:w-[200px] shrink-0">
            <ProductCombobox
              value={row.category}
              onChange={handleCategoryChange}
              items={categoryItems}
              placeholder="Категория"
            />
          </div>

          <div className="w-full sm:flex-1 min-w-0">
            <Input
              list={`recipe-product-groups-${idx}`}
              value={row.base_name}
              onChange={(event) => handleBaseNameChange(event.target.value)}
              placeholder="Поиск или название продукта..."
            />
            <datalist id={`recipe-product-groups-${idx}`}>
              {productItems
                .filter((item) => !selectedElsewhere.includes(item.value))
                .map((item) => (
                  <option key={item.value} value={item.value} label={item.searchText} />
                ))}
            </datalist>
          </div>
        </div>

        {row.product_id === '' && row.base_name.trim() && (
          <div className="space-y-2 rounded-md border border-dashed p-3">
            {matchingProducts.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">
                  Возможные совпадения в каталоге — выберите вручную:
                </p>
                <select
                  value=""
                  onChange={(event) => {
                    const product = matchingProducts.find(
                      (item) => item.id === Number(event.target.value),
                    )
                    if (product) {
                      updateRow(idx, {
                        product_id: product.id,
                        category: product.category_name || product.category || '',
                        base_name: product.base_name || product.name,
                      })
                      api.refreshPyaterochkaPrices(product.id).then(() => {
                        qc.invalidateQueries({ queryKey: ['store-products', product.id] })
                        qc.invalidateQueries({ queryKey: ['cart'] })
                        qc.invalidateQueries({ queryKey: ['calc'] })
                      }).catch(() => undefined)
                    }
                  }}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">Выбрать существующий продукт…</option>
                  {matchingProducts.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                      {product.category_name ? ` · ${product.category_name}` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Если подходящего продукта нет, его можно создать. КБЖУ останется пустым до заполнения.
              </p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={
                  addToCatalogMutation.isPending ||
                  matchingProducts.some(
                    (product) =>
                      product.name.trim().toLocaleLowerCase() ===
                      row.base_name.trim().toLocaleLowerCase(),
                  )
                }
                onClick={() => addToCatalogMutation.mutate()}
              >
                {addToCatalogMutation.isPending
                  ? 'Добавление…'
                  : `Добавить «${row.base_name.trim()}» в каталог`}
              </Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 items-center">
          {variations &&
            variations.length > 1 && (
              <div className="w-full sm:w-auto flex-1 min-w-[150px]">
                <select
                  value={row.product_id}
                  onChange={(e) =>
                    handleVariationChange(e.target.value)
                  }
                  className="flex h-10 w-[160px] min-w-[160px] shrink-0 rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">
                    Выберите вариант
                  </option>

                  {variations
                    .filter(
                      (product, index, self) =>
                        index ===
                        self.findIndex(
                          (item) =>
                            item.variation === product.variation &&
                            Math.round(item.calories || 0) ===
                            Math.round(product.calories || 0),
                        ),
                    )
                    .map((product) => (
                      <option
                        key={product.id}
                        value={product.id}
                      >
                        {product.variation || product.name}
                      </option>
                    ))}
                </select>
              </div>
            )}

          <div className="flex flex-nowrap gap-3 ml-auto shrink-0">
            {/* Количество */}
            <Input
              value={row.amount}
              onChange={(e) =>
                updateRow(idx, {
                  amount: e.target.value,
                })
              }
              placeholder="Количество"
              className="w-36"
            />

            {/* Единица измерения */}
            <div className="w-[160px] min-w-[160px] shrink-0 whitespace-nowrap">
              <select
                value={row.unit}
                onChange={(e) => handleUnitChange(e.target.value)}
                className="block h-10 w-full appearance-none rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="g">г</option>
                <option value="kg">кг</option>
                <option value="ml">мл</option>
                <option value="l">л</option>
                <option value="pcs">шт</option>
                <option value="cup">стакан</option>
                <option value="clove">зубчик</option>
                <option value="bunch">пучок</option>
                <option value="tbsp">ст. ложка</option>
                <option value="tsp">ч. ложка</option>
                <option value="pinch">щепотка</option>
                <option value="to_taste">по вкусу</option>
              </select>
            </div>
          </div>

          {/* Примечание */}
          <Input
            value={row.note}
            onChange={(e) =>
              updateRow(idx, {
                note: e.target.value,
              })
            }
            placeholder="Примечание к ингредиенту (необязательно)"
            maxLength={255}
            className="mt-3"
          />
        </div>
      </div>
    </div>
  )
}

