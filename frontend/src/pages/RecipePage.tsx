import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Calculation, Recipe } from '@/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useDebounce } from '@/hooks/useDebounce'
import { useFlyingCart } from '@/components/useFlyingCart'
import { toast } from 'sonner'

export function RecipePage({ recipeId, onEdit }: { recipeId: number; onEdit: (id: number) => void }) {
  const qc = useQueryClient()
  const [servings, setServings] = useState([2])
  const { flyToCart } = useFlyingCart()

  const debouncedServings = useDebounce(servings[0], 400)

  const { data, error } = useQuery<Calculation>({
    queryKey: ['calc', recipeId, debouncedServings],
    queryFn: () => api.calculateRecipe(recipeId, debouncedServings),
    placeholderData: (previousData) => previousData,
  })

  // Инструкция и описание приходят из карточки рецепта:
  // расчёт КБЖУ (/calculate) их не содержит.
  const { data: recipe } = useQuery<Recipe>({
    queryKey: ['recipe', recipeId],
    queryFn: () => api.getRecipe(recipeId),
  })



  const addToCartMutation = useMutation({
    mutationFn: ({ id, amount, unit }: { id: number, amount: number, unit: string }) =>
      api.addToCart(id, amount, unit),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cart'] }),
    onError: (err: any) => toast.error('Ошибка добавления: ' + err.message)
  })

  if (error) return <div className="p-8 text-center text-red-500">Ошибка: {(error as Error).message}</div>
  if (!data) return <div className="p-8 text-center">Расчёт...</div>

  const instructions = recipe?.instructions?.trim() ?? ''
  const description = recipe?.description?.trim() ?? ''

  const handleServingsSlider = (val: number | readonly number[]) => {
    const nextValue = typeof val === 'number' ? val : Number(val[0] ?? 1)
    setServings([nextValue])
  }
  const handleServingsInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value)
    if (!isNaN(val) && val > 0) setServings([val])
    else if (e.target.value === '') setServings([1])
  }

  const handleAddToCart = (
    e: React.MouseEvent<HTMLButtonElement>,
    ing: Recipe['ingredients'][number],
    amount: number,
  ) => {
    if (ing.amount_is_exact === false) {
      toast.error('Диапазон и количество «по вкусу» нельзя автоматически добавить в корзину')
      return
    }

    const productId = ing.product_id

    if (!Number.isFinite(amount) || amount <= 0 || amount > 10000) {
      toast.error('Некорректное количество ингредиента')
      return
    }

    const safeAmount = Math.round(amount * 100) / 100

    flyToCart(e.currentTarget)
    addToCartMutation.mutate({
      id: productId,
      amount: safeAmount,
      unit: ing.unit,
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold mb-2">{data.recipe_title}</h1>
          <p className="text-muted-foreground">
            Базовый рецепт
            {recipe ? ` · ${recipe.base_servings} порц.` : ''}
          </p>
          {description && (
            <p className="text-sm text-muted-foreground mt-2 max-w-xl">{description}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => onEdit(recipeId)}>
            Редактировать
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center justify-between">
            <span>Порций</span>
            <Input
              type="number" min={1} value={servings[0]}
              onChange={handleServingsInput}
              className="w-24 text-center text-lg font-bold"
            />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Slider value={servings} onValueChange={handleServingsSlider} min={1} max={12} step={1} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex justify-between items-center">
              <span>Ингредиенты</span>
              <span className="text-xs font-normal text-muted-foreground">+ добавляет кратно 50</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {(recipe?.ingredients || []).map((ing) => {
                const isExact = ing.amount_is_exact !== false

                const scaled = isExact
                  ? ing.amount * servings[0] / (recipe?.base_servings || 1)
                  : ing.amount

                const displayedAmount = isExact
                  ? `${Number(scaled.toFixed(2))} ${ing.unit}`
                  : `${ing.amount_text || 'Количество не указано'} ${ing.unit}`

                const canAddToCart = Boolean(
                  ing.product_id && isExact
                )
                return (
                  <li key={ing.id} className="border-b pb-3 last:border-0 last:pb-0 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex-1">
                        <div className="font-medium text-sm">{ing.product_name}</div>
                        <div className="text-muted-foreground text-xs">{displayedAmount}</div>
                        {ing.note && <div className="text-xs text-muted-foreground">{ing.note}</div>}
                      </div>
                      <Button size="sm" variant="outline" className="h-8 w-8 p-0 shrink-0" onClick={(e) => handleAddToCart(e, ing, scaled)} disabled={!canAddToCart || addToCartMutation.isPending} title={
                        !isExact
                          ? 'Диапазон и количество «по вкусу» нельзя добавить автоматически'
                          : !ing.product_id
                            ? 'Ингредиент должен быть связан с продуктом каталога'
                            : 'Добавить в корзину'
                      }>+</Button>
                    </div>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex justify-between">
                <span>КБЖУ</span>
                <Badge variant={data.total.accuracy === 'exact' ? 'default' : 'secondary'}>
                  {data.total.accuracy === 'exact' ? 'точно' : 'приблизительно'}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-muted-foreground mb-1">На одну порцию</div>
              <div className="text-3xl font-bold mb-4">
                {data.per_serving.calories === null ? 'Нет полных данных' : data.per_serving.calories}
                {data.per_serving.calories !== null && <span className="text-base font-normal text-muted-foreground"> ккал</span>}
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                {(['proteins', 'fats', 'carbs'] as const).map((key) => (
                  <div key={key} className="text-center p-2 bg-muted rounded-md">
                    <div className="text-muted-foreground mb-1">{({ proteins: 'Б', fats: 'Ж', carbs: 'У' })[key]}</div>
                    {data.per_serving[key] === null ? 'нет данных' : `${data.per_serving[key]} г`}
                    {data.per_serving[key] === null && data.per_serving[`known_${key}`] !== null && (
                      <div className="text-xs text-muted-foreground">известно: {data.per_serving[`known_${key}`]} г</div>
                    )}
                  </div>
                ))}
              </div>
              <div className="border-t mt-4 pt-3">
                <div className="text-sm font-medium mb-2">На 100 г исходной массы ингредиентов</div>
                <div className="grid grid-cols-4 gap-2 text-sm">
                  {(['calories', 'proteins', 'fats', 'carbs'] as const).map((key) => (
                    <div key={key} className="text-center">
                      <div className="text-xs text-muted-foreground">{({ calories: 'ккал', proteins: 'Б', fats: 'Ж', carbs: 'У' })[key]}</div>
                      {data.per_100g[key] === null ? '—' : data.per_100g[key]}
                    </div>
                  ))}
                </div>
                <div className="text-xs text-muted-foreground mt-2">Расчёт по массе ингредиентов до приготовления; изменение массы при термообработке не учитывается.</div>
              </div>
              {data.total.accuracy !== 'exact' && (
                <div className="mt-4 rounded-md bg-muted p-3 text-xs space-y-2">
                  <div>Полнота расчёта по ингредиентам: {data.total.coverage_percent}%</div>
                  <div>Не хватает данных: {data.total.missing_components.join(', ') || 'масса рецепта'}</div>
                  {data.total.missing_ingredients.length > 0 && (
                    <ul className="list-disc pl-4 space-y-1">
                      {data.total.missing_ingredients.map((item, index) => <li key={index}>{item}</li>)}
                    </ul>
                  )}
                  <div className="text-muted-foreground">«Известно» — сумма только по тем данным, которые удалось рассчитать; это не полный итог рецепта.</div>
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Стоимость рецепта</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-xs text-muted-foreground mb-1">Расход ингредиентов</div>
              <div className="text-3xl font-bold">
                {data.cost.total_cost === null ? 'Нет подтверждённых цен' : `${data.cost.total_cost} ₽`}
              </div>
              {data.cost.total_cost !== null && (
                <div className="text-sm text-muted-foreground mt-1">
                  {`${(data.cost.total_cost / servings[0]).toFixed(2)} ₽ на порцию`}
                </div>
              )}
              {data.cost.missing_prices.length > 0 && (
                <div className="mt-3 text-xs text-muted-foreground">
                  Частичная стоимость: цена известна для {data.cost.known_ingredients} из {data.cost.ingredient_count} ингредиентов.
                  Не найдена цена: {data.cost.missing_prices.join(', ')}.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Инструкция приготовления</CardTitle>
        </CardHeader>
        <CardContent>
          {instructions ? (
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
              {instructions}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Для этого рецепта инструкция не заполнена.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

