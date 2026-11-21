import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { toast } from 'sonner'

type CartItem = {
  id: number
  product_id: number
  product_name: string
  amount: number
  unit: string
  cost: number | null
  price_source: string | null
  observed_at: string | null
  store_name: string | null
  store_product_name: string | null
  manufacturer: string | null
  selected_store_product_id: number | null
  offered_store_product_id: number | null
  price_override: number | null
  price_basis_unit: string | null
  catalog_price_per_basis: number | null
}

function CartItemRow({ item, onUpdate, onRemove, onSavePrice }: {
  item: CartItem
  onUpdate: (id: number, patch: { amount?: number; price_override?: number | null; selected_store_product_id?: number | null }) => void
  onRemove: (id: number) => void
  onSavePrice: (id: number) => void
}) {
  const [amount, setAmount] = useState(String(item.amount))
  const [price, setPrice] = useState(
    item.price_override !== null
      ? String(item.price_override)
      : item.catalog_price_per_basis !== null
        ? String(item.catalog_price_per_basis)
        : '',
  )
  const [priceChanged, setPriceChanged] = useState(false)
  const { data: offers = [] } = useQuery({
    queryKey: ['store-products', item.product_id],
    queryFn: () => api.getStoreProducts(item.product_id),
  })

  const basis = item.price_basis_unit || (['g', 'kg'].includes(item.unit) ? 'кг' : ['ml', 'l'].includes(item.unit) ? 'л' : 'шт')

  return (
    <li className="border-b pb-4 last:border-0 last:pb-0 space-y-3">
      <div className="flex justify-between items-start gap-3">
        <div className="min-w-0">
          <div className="font-medium text-sm leading-tight">{item.product_name}</div>
          <div className="text-xs text-muted-foreground mt-1">{item.cost === null ? 'Цена не найдена' : `${item.cost.toFixed(2)} ₽`}</div>
          {item.price_source && <div className="text-xs text-muted-foreground">{item.price_source}{item.observed_at ? ` · ${new Date(item.observed_at).toLocaleDateString()}` : ''}</div>}
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 text-muted-foreground hover:text-destructive" onClick={() => onRemove(item.id)}>
          ✕
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-muted-foreground">
          Количество ({item.unit})
          <Input
            type="number" min="0.01" step="any" value={amount}
            onChange={(event) => setAmount(event.target.value)}
            onBlur={() => {
              const next = Number(amount)
              if (Number.isFinite(next) && next > 0 && next !== item.amount) onUpdate(item.id, { amount: next })
              else setAmount(String(item.amount))
            }}
            className="mt-1 h-8"
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Цена за {basis}, ₽
          <Input
            type="number" min="0" step="any" value={price}
            placeholder="По каталогу"
            onChange={(event) => {
              setPrice(event.target.value)
              setPriceChanged(true)
            }}
            onBlur={() => {
              if (!priceChanged) return
              if (!price.trim()) {
                if (item.price_override !== null) onUpdate(item.id, { price_override: null })
                setPriceChanged(false)
                return
              }
              const next = Number(price)
              if (Number.isFinite(next) && next >= 0 && next !== item.price_override) onUpdate(item.id, { price_override: next })
              else setPrice(item.price_override === null ? '' : String(item.price_override))
              setPriceChanged(false)
            }}
            className="mt-1 h-8"
          />
        </label>
      </div>
      {offers.length > 0 && (
        <label className="block text-xs text-muted-foreground">
          Источник предложения
          <select
            className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm text-foreground"
            value={item.selected_store_product_id ?? ''}
            onChange={(event) => onUpdate(item.id, {
              selected_store_product_id: event.target.value ? Number(event.target.value) : null,
            })}
          >
            <option value="">Автоматически: {item.store_name || 'приоритетный источник'}</option>
            {offers.map((offer: any) => (
              <option key={offer.id} value={offer.id}>
                {offer.store_name} — {offer.name}{offer.manufacturer ? ` (${offer.manufacturer})` : ''}
              </option>
            ))}
          </select>
        </label>
      )}
      {item.price_override !== null && (
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs text-muted-foreground">Цена изменена только для этой корзины.</div>
          <Button
            variant="outline"
            size="sm"
            disabled={!item.offered_store_product_id}
            onClick={() => onSavePrice(item.id)}
            title={!item.offered_store_product_id ? 'Нет предложения магазина для сохранения цены' : 'Добавить цену в историю предложения'}
          >
            Сохранить в историю
          </Button>
        </div>
      )}
    </li>
  )
}

export function CartSheet({ trigger }: { trigger: React.ReactNode }) {
  const qc = useQueryClient()
  const { data: cart } = useQuery({
    queryKey: ['cart'],
    queryFn: () => api.getCart(),
  })

  const refreshCart = () => qc.invalidateQueries({ queryKey: ['cart'] })
  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: { amount?: number; price_override?: number | null; selected_store_product_id?: number | null } }) =>
      api.updateCartItem(id, patch),
    onSuccess: refreshCart,
    onError: (err: Error) => toast.error('Не удалось изменить корзину: ' + err.message),
  })
  const removeMutation = useMutation({
    mutationFn: (id: number) => api.removeFromCart(id),
    onSuccess: refreshCart,
    onError: (err: Error) => toast.error('Ошибка удаления: ' + err.message),
  })
  const savePriceMutation = useMutation({
    mutationFn: (id: number) => api.saveCartPriceToHistory(id),
    onSuccess: () => {
      refreshCart()
      toast.success('Цена добавлена в историю предложения')
    },
    onError: (err: Error) => toast.error('Не удалось сохранить цену: ' + err.message),
  })

  const clearCart = () => {
    if (!cart?.items?.length || !window.confirm('Очистить корзину?')) return
    cart.items.forEach((item: CartItem) => removeMutation.mutate(item.id))
  }

  const copyToClipboard = () => {
    if (!cart?.items?.length) return
    let text = 'Список покупок:\n\n'
    cart.items.forEach((item: CartItem) => {
      text += `- ${item.product_name}: ${item.amount} ${item.unit}${item.cost === null ? ' (цена не найдена)' : ` — ${item.cost} ₽`}\n`
    })
    text += `\nИтого: ${cart.total_cost === null ? 'нет подтверждённых цен' : `${cart.total_cost} ₽`}\n`
    navigator.clipboard.writeText(text)
      .then(() => toast.success('Список покупок скопирован'))
      .catch(() => toast.error('Не удалось скопировать'))
  }

  return (
    <Sheet>
      <SheetTrigger render={trigger as ReactElement} />
      <SheetContent className="w-full sm:max-w-md flex flex-col p-0">
        <SheetHeader className="p-6 border-b">
          <SheetTitle>Корзина ({cart?.items?.length || 0})</SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-6">
          {!cart?.items?.length ? (
            <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
              <span className="text-4xl mb-4">🛒</span>
              <p>Корзина пуста</p>
              <p className="text-sm">Добавьте ингредиенты из рецептов</p>
            </div>
          ) : (
            <ul className="space-y-5">
              {cart.items.map((item: CartItem) => (
                <CartItemRow
                  key={`${item.id}-${item.amount}-${item.price_override ?? 'catalog'}`}
                  item={item}
                  onUpdate={(id, patch) => updateMutation.mutate({ id, patch })}
                  onRemove={(id) => removeMutation.mutate(id)}
                  onSavePrice={(id) => savePriceMutation.mutate(id)}
                />
              ))}
            </ul>
          )}
        </div>
        {cart?.items?.length > 0 && (
          <div className="p-6 border-t bg-muted/30">
            <div className="flex justify-between items-center">
              <span className="text-base font-semibold">Покупки:</span>
              <span className="text-2xl font-bold">{cart.total_cost === null ? '—' : `${cart.total_cost.toFixed(2)} ₽`}</span>
            </div>
            {cart.missing_prices?.length > 0 && (
              <div className="mt-2 text-xs text-muted-foreground">
                Частичная стоимость: цена известна для {cart.known_prices} из {cart.item_count} позиций. Без цены: {cart.missing_prices.join(', ')}.
              </div>
            )}
            <div className="flex gap-2 mt-4">
              <Button variant="outline" className="w-1/2" onClick={copyToClipboard}>Скопировать</Button>
              <Button variant="outline" className="w-1/2 text-red-500 hover:text-red-700 hover:bg-red-50" onClick={clearCart} disabled={removeMutation.isPending}>
                Очистить
              </Button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
