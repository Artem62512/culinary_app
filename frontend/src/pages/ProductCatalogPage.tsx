/* oxlint-disable react/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from 'sonner'

type CatalogProduct = {
  id: number
  name: string
  category: string | null
  category_id: number | null
  category_name: string | null
  base_name: string | null
  variation: string | null
  calories: number | null
  proteins: number | null
  fats: number | null
  carbs: number | null
  kbju_status: 'full' | 'partial' | 'missing'
  verified: boolean
}

export function ProductCatalogPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [offset, setOffset] = useState(0)
  const pageSize = 100
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCategoryId, setNewCategoryId] = useState('')
  const [newBaseName, setNewBaseName] = useState('')
  const [newVariation, setNewVariation] = useState('')
  const [newAlias, setNewAlias] = useState('')
  const [kbjuForm, setKbjuForm] = useState({ calories: '', proteins: '', fats: '', carbs: '', verified: false })
  const [editForm, setEditForm] = useState({ name: '', categoryId: '', baseName: '', variation: '' })
  const [unitPriceForm, setUnitPriceForm] = useState({ pricePerKg: '', pricePerLiter: '', pricePerPiece: '' })
  const { data: categories = [] } = useQuery({
    queryKey: ['catalog-categories'],
    queryFn: api.getCatalogCategories,
  })
  const { data: quality } = useQuery({
    queryKey: ['catalog-quality'],
    queryFn: api.getCatalogQuality,
  })
  const { data: products = [], isLoading, error } = useQuery<CatalogProduct[]>({
    queryKey: ['catalog-products', search, categoryId, offset],
    queryFn: () => api.getProducts(search.trim() || undefined, categoryId ? Number(categoryId) : undefined, pageSize, offset),
  })
  const activeProduct = useMemo(
    () => products.find(product => product.id === selectedId) || products[0] || null,
    [products, selectedId],
  )
  const activeId = activeProduct?.id ?? null
  const { data: aliases = [] } = useQuery({
    queryKey: ['product-aliases', activeId],
    queryFn: () => api.getProductAliases(activeId!),
    enabled: activeId !== null,
  })
  const { data: unitPrices } = useQuery({
    queryKey: ['product-unit-prices', activeId],
    queryFn: () => api.getProductUnitPrices(activeId!),
    enabled: activeId !== null,
  })
  // Form fields mirror the selected server-side product.
  useEffect(() => {
    if (!activeProduct) return
    setKbjuForm({
      calories: activeProduct.calories == null ? '' : String(activeProduct.calories),
      proteins: activeProduct.proteins == null ? '' : String(activeProduct.proteins),
      fats: activeProduct.fats == null ? '' : String(activeProduct.fats),
      carbs: activeProduct.carbs == null ? '' : String(activeProduct.carbs),
      verified: activeProduct.verified,
    })
    setEditForm({
      name: activeProduct.name,
      categoryId: activeProduct.category_id == null ? '' : String(activeProduct.category_id),
      baseName: activeProduct.base_name || '',
      variation: activeProduct.variation || '',
    })
  }, [
    activeId,
    activeProduct,
    activeProduct?.name,
    activeProduct?.base_name,
    activeProduct?.category_id,
    activeProduct?.variation,
    activeProduct?.calories,
    activeProduct?.proteins,
    activeProduct?.fats,
    activeProduct?.carbs,
    activeProduct?.verified,
  ])

  useEffect(() => {
    if (!unitPrices) return
    setUnitPriceForm({
      pricePerKg: unitPrices.price_per_kg == null ? '' : String(unitPrices.price_per_kg),
      pricePerLiter: unitPrices.price_per_liter == null ? '' : String(unitPrices.price_per_liter),
      pricePerPiece: unitPrices.price_per_piece == null ? '' : String(unitPrices.price_per_piece),
    })
  }, [unitPrices])

  const createMutation = useMutation({
    mutationFn: () => api.createProduct({
      name: newName.trim(),
      category_id: newCategoryId ? Number(newCategoryId) : null,
      base_name: newBaseName.trim() || newName.trim(),
      variation: newVariation.trim() || null,
    }),
    onSuccess: (product: CatalogProduct) => {
      toast.success('Продукт добавлен в каталог')
      setNewName('')
      setNewBaseName('')
      setNewVariation('')
      setSelectedId(product.id)
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-products-for-matching'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const updateProductMutation = useMutation({
    mutationFn: () => api.updateProduct(activeId!, {
      name: editForm.name.trim(),
      category_id: editForm.categoryId ? Number(editForm.categoryId) : null,
      base_name: editForm.baseName.trim() || null,
      variation: editForm.variation.trim() || null,
    }),
    onSuccess: (product: CatalogProduct) => {
      toast.success('Продукт переименован и обновлён')
      setSelectedId(product.id)
      setEditDialogOpen(false)
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['groups'] })
      qc.invalidateQueries({ queryKey: ['recipe'] })
    },
    onError: (err: Error) => toast.error('Не удалось обновить продукт: ' + err.message),
  })

  const deleteProductMutation = useMutation({
    mutationFn: () => api.deleteProduct(activeId!),
    onSuccess: () => {
      toast.success('Продукт удалён из каталога')
      setSelectedId(null)
      setEditDialogOpen(false)
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (err: Error) => toast.error('Не удалось удалить продукт: ' + err.message),
  })

  const updateUnitPricesMutation = useMutation({
    mutationFn: () => api.updateProductUnitPrices(activeId!, {
      price_per_kg: unitPriceForm.pricePerKg === '' ? null : Number(unitPriceForm.pricePerKg),
      price_per_liter: unitPriceForm.pricePerLiter === '' ? null : Number(unitPriceForm.pricePerLiter),
      price_per_piece: unitPriceForm.pricePerPiece === '' ? null : Number(unitPriceForm.pricePerPiece),
    }),
    onSuccess: () => {
      toast.success('Цены универсального продукта сохранены')
      qc.invalidateQueries({ queryKey: ['product-unit-prices', activeId] })
      qc.invalidateQueries({ queryKey: ['cart'] })
      qc.invalidateQueries({ queryKey: ['calc'] })
    },
    onError: (err: Error) => toast.error('Не удалось сохранить цены: ' + err.message),
  })

  const updateKbjuMutation = useMutation({
    mutationFn: () => api.updateProduct(activeId!, {
      calories: kbjuForm.calories === '' ? null : Number(kbjuForm.calories),
      proteins: kbjuForm.proteins === '' ? null : Number(kbjuForm.proteins),
      fats: kbjuForm.fats === '' ? null : Number(kbjuForm.fats),
      carbs: kbjuForm.carbs === '' ? null : Number(kbjuForm.carbs),
      verified: kbjuForm.verified,
    }),
    onSuccess: () => {
      toast.success('Пищевая ценность сохранена')
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['recipe'] })
      qc.invalidateQueries({ queryKey: ['calc'] })
    },
    onError: (err: Error) => toast.error('Не удалось сохранить КБЖУ: ' + err.message),
  })

  const refreshKbjuMutation = useMutation({
    mutationFn: () => api.refreshProductKbju(activeId!),
    onSuccess: (result) => {
      toast.success(result.updated_fields > 0
        ? `КБЖУ обновлено из источника: ${result.source || 'неизвестный'}`
        : 'Подходящих данных КБЖУ не найдено')
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['recipe'] })
      qc.invalidateQueries({ queryKey: ['calc'] })
    },
    onError: (err: Error) => toast.error('Не удалось найти КБЖУ: ' + err.message),
  })

  const aliasMutation = useMutation({
    mutationFn: () => api.addProductAlias(activeId!, newAlias.trim()),
    onSuccess: () => {
      toast.success('Синоним добавлен')
      setNewAlias('')
      qc.invalidateQueries({ queryKey: ['product-aliases', activeId] })
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  const deleteAliasMutation = useMutation({
    mutationFn: (aliasId: number) => api.deleteProductAlias(activeId!, aliasId),
    onSuccess: () => {
      toast.success('Синоним удалён')
      qc.invalidateQueries({ queryKey: ['product-aliases', activeId] })
      qc.invalidateQueries({ queryKey: ['catalog-products'] })
      qc.invalidateQueries({ queryKey: ['catalog-quality'] })
      qc.invalidateQueries({ queryKey: ['groups'] })
    },
    onError: (err: Error) => toast.error(err.message),
  })

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-8">
      <header>
        <h1 className="text-2xl font-semibold">Каталог продуктов</h1>
        <p className="mt-1 text-sm text-muted-foreground">Единый справочник ингредиентов, категорий и альтернативных названий.</p>
      </header>

      {quality?.summary && <section className="space-y-3 rounded-xl border bg-card p-4">
        <div>
          <h2 className="text-lg font-semibold">Качество каталога</h2>
          <p className="text-sm text-muted-foreground">Сводка помогает находить записи, требующие ручной проверки. Автоматическое объединение и удаление не выполняется.</p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {[
            ['Всего продуктов', quality.summary.products_total],
            ['Полное КБЖУ', quality.summary.kbju_full],
            ['Частичное КБЖУ', quality.summary.kbju_partial],
            ['Без КБЖУ', quality.summary.kbju_missing],
            ['Не проверено', quality.summary.unverified],
            ['Группы одинаковых названий', quality.summary.duplicate_name_groups],
            ['Точные дубли-кандидаты', quality.summary.exact_duplicate_clusters],
          ].map(([label, value]) => <div key={label} className="rounded-lg bg-muted/40 p-3">
            <div className="text-xl font-semibold tabular-nums">{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>)}
        </div>
        {quality.exact_duplicate_groups?.length > 0 && <div className="rounded-lg border border-amber-500/40 p-3">
          <h3 className="font-medium">Кандидаты на проверку дубликатов</h3>
          {quality.exact_duplicate_groups.map((group: any) => <p key={group.name} className="mt-1 text-sm">{group.name}: ID {group.clusters.map((cluster: number[]) => cluster.join(', ')).join('; ')}</p>)}
          <p className="mt-2 text-xs text-muted-foreground">Это только совпадающие данные. Записи не объединяются, поскольку на них могут ссылаться рецепты.</p>
        </div>}
        {quality.empty_categories?.length > 0 && <p className="text-xs text-muted-foreground">Пустые категории: {quality.empty_categories.join(', ')}</p>}
      </section>}

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,380px)]">
        <div className="space-y-3 rounded-xl border bg-card p-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input value={search} onChange={event => { setSearch(event.target.value); setOffset(0) }} placeholder="Поиск по названию или синониму" />
            <select value={categoryId} onChange={event => { setCategoryId(event.target.value); setOffset(0) }} className="h-10 rounded-md border bg-background px-3 text-sm sm:w-64">
              <option value="">Все категории</option>
              {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select>
          </div>
          <div className="max-h-[560px] space-y-2 overflow-y-auto">
            {isLoading && <p className="p-4 text-sm text-muted-foreground">Загрузка каталога…</p>}
            {error && <p className="p-4 text-sm text-destructive">Не удалось загрузить продукты.</p>}
            {!isLoading && !error && products.length === 0 && <p className="p-4 text-sm text-muted-foreground">Ничего не найдено.</p>}
            {products.map(product => (
              <button
                key={product.id}
                type="button"
                onClick={() => {
                  setSelectedId(product.id)
                  setEditDialogOpen(true)
                }}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${activeId === product.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'}`}
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="font-medium">{product.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">{product.kbju_status === 'full' ? 'КБЖУ заполнено' : product.kbju_status === 'partial' ? 'КБЖУ частично' : 'Нет КБЖУ'}{!product.verified ? ' · не проверен' : ''}</span>
                </span>
                <span className="mt-1 block text-xs text-muted-foreground">{product.category_name || 'Без категории'}{product.base_name ? ` · группа: ${product.base_name}` : ''}{product.variation ? ` · ${product.variation}` : ''}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">Показаны позиции {offset + 1}–{offset + products.length}. Поиск учитывает частичное совпадение и синонимы.</p>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - pageSize))}>Назад</Button>
              <Button type="button" size="sm" variant="outline" disabled={products.length < pageSize} onClick={() => setOffset(value => value + pageSize)}>Далее</Button>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <section className="space-y-4 rounded-xl border bg-card p-4">
            <h2 className="text-lg font-semibold">Добавить продукт</h2>
            <div className="space-y-2">
              <Label htmlFor="catalog-product-name">Название</Label>
              <Input id="catalog-product-name" value={newName} onChange={event => setNewName(event.target.value)} placeholder="Например, рис басмати" maxLength={255} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="catalog-product-category">Категория</Label>
              <select id="catalog-product-category" value={newCategoryId} onChange={event => setNewCategoryId(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                <option value="">Другое / не выбрана</option>
                {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2"><Label htmlFor="catalog-base-name">Группа</Label><Input id="catalog-base-name" value={newBaseName} onChange={event => setNewBaseName(event.target.value)} placeholder="Например, Рис" maxLength={255} /></div>
              <div className="space-y-2"><Label htmlFor="catalog-variation">Вариант</Label><Input id="catalog-variation" value={newVariation} onChange={event => setNewVariation(event.target.value)} placeholder="Например, басмати" maxLength={255} /></div>
            </div>
            <Button className="w-full" disabled={!newName.trim() || createMutation.isPending} onClick={() => createMutation.mutate()}>{createMutation.isPending ? 'Добавление…' : 'Добавить в каталог'}</Button>
            <p className="text-xs text-muted-foreground">Продукт сразу становится доступен при создании и редактировании рецептов. Дубли по нормализованному названию отклоняются.</p>
          </section>

        </div>
      </section>

      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Редактирование продукта</DialogTitle>
            <DialogDescription>
              Измените название, характеристики, КБЖУ, синонимы и общие цены.
            </DialogDescription>
          </DialogHeader>

          {activeProduct && (
            <div className="space-y-5">
              <section className="space-y-3 rounded-lg border p-4">
                <h3 className="font-medium">Основные данные</h3>
                <div className="space-y-2">
                  <Label htmlFor="dialog-edit-product-name">Название</Label>
                  <Input id="dialog-edit-product-name" value={editForm.name} onChange={event => setEditForm(current => ({ ...current, name: event.target.value }))} maxLength={255} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dialog-edit-product-category">Категория</Label>
                  <select id="dialog-edit-product-category" value={editForm.categoryId} onChange={event => setEditForm(current => ({ ...current, categoryId: event.target.value }))} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                    <option value="">Без категории</option>
                    {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2"><Label htmlFor="dialog-edit-base-name">Группа</Label><Input id="dialog-edit-base-name" value={editForm.baseName} onChange={event => setEditForm(current => ({ ...current, baseName: event.target.value }))} maxLength={255} /></div>
                  <div className="space-y-2"><Label htmlFor="dialog-edit-variation">Вариант</Label><Input id="dialog-edit-variation" value={editForm.variation} onChange={event => setEditForm(current => ({ ...current, variation: event.target.value }))} maxLength={255} /></div>
                </div>
              </section>

              <section className="space-y-3 rounded-lg border p-4">
                <h3 className="font-medium">Пищевая ценность на 100 г</h3>
                <div className="grid grid-cols-2 gap-3">
                  {([
                    ['calories', 'Ккал'],
                    ['proteins', 'Белки, г'],
                    ['fats', 'Жиры, г'],
                    ['carbs', 'Углеводы, г'],
                  ] as const).map(([key, label]) => (
                    <div key={key} className="space-y-1">
                      <Label htmlFor={`dialog-kbju-${key}`}>{label}</Label>
                      <Input id={`dialog-kbju-${key}`} type="number" min="0" step="0.1" value={kbjuForm[key]} onChange={event => setKbjuForm(current => ({ ...current, [key]: event.target.value }))} placeholder="Не указано" />
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={kbjuForm.verified} onChange={event => setKbjuForm(current => ({ ...current, verified: event.target.checked }))} />
                  Данные проверены
                </label>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={refreshKbjuMutation.isPending}
                  onClick={() => refreshKbjuMutation.mutate()}
                >
                  {refreshKbjuMutation.isPending ? 'Поиск КБЖУ…' : 'Найти КБЖУ автоматически'}
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={updateKbjuMutation.isPending}
                  onClick={() => updateKbjuMutation.mutate()}
                >
                  {updateKbjuMutation.isPending ? 'Сохранение…' : 'Сохранить КБЖУ'}
                </Button>
              </section>

              <section className="space-y-3 rounded-lg border p-4">
                <h3 className="font-medium">Общие цены</h3>
                <div className="grid grid-cols-3 gap-3">
                  {([
                    ['pricePerKg', '₽ / кг'],
                    ['pricePerLiter', '₽ / л'],
                    ['pricePerPiece', '₽ / шт'],
                  ] as const).map(([key, label]) => (
                    <div key={key} className="space-y-1">
                      <Label htmlFor={`dialog-product-${key}`}>{label}</Label>
                      <Input id={`dialog-product-${key}`} type="number" min="0" step="0.01" value={unitPriceForm[key]} onChange={event => setUnitPriceForm(current => ({ ...current, [key]: event.target.value }))} placeholder="Не указано" />
                    </div>
                  ))}
                </div>
                <Button
                  variant="outline"
                  className="w-full"
                  disabled={updateUnitPricesMutation.isPending}
                  onClick={() => updateUnitPricesMutation.mutate()}
                >
                  {updateUnitPricesMutation.isPending ? 'Сохранение…' : 'Сохранить цены'}
                </Button>
              </section>

              <section className="space-y-3 rounded-lg border p-4">
                <h3 className="font-medium">Синонимы</h3>
                <div className="flex gap-2">
                  <Input value={newAlias} onChange={event => setNewAlias(event.target.value)} placeholder="Добавить синоним" maxLength={255} />
                  <Button disabled={!newAlias.trim() || aliasMutation.isPending} onClick={() => aliasMutation.mutate()}>
                    Добавить
                  </Button>
                </div>
                {aliases.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Синонимы не добавлены.</p>
                ) : (
                  <div className="space-y-2">
                    {aliases.map((alias: { id: number; alias: string }) => (
                      <div key={alias.id} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                        <span className="text-sm">{alias.alias}</span>
                        <Button variant="ghost" size="sm" disabled={deleteAliasMutation.isPending} onClick={() => deleteAliasMutation.mutate(alias.id)}>Удалить</Button>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  disabled={!editForm.name.trim() || updateProductMutation.isPending}
                  onClick={() => updateProductMutation.mutate()}
                >
                  {updateProductMutation.isPending ? 'Сохранение…' : 'Сохранить продукт'}
                </Button>
                <Button
                  variant="outline"
                  className="text-red-600 hover:text-red-700"
                  disabled={deleteProductMutation.isPending}
                  onClick={() => {
                    if (window.confirm(`Удалить «${activeProduct.name}» из каталога? Продукт удаляется только если на него нет ссылок из рецептов, корзины или магазинных товаров.`)) {
                      deleteProductMutation.mutate()
                    }
                  }}
                >
                  {deleteProductMutation.isPending ? 'Удаление…' : 'Удалить'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </main>
  )
}
