import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function ShoppingListPage({ listId }: { listId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['shopping-list', listId],
    queryFn: () => api.getShoppingList(listId),
  })

  if (isLoading) return <div className="p-8 text-center">Загрузка списка...</div>
  if (error) return <div className="p-8 text-center text-red-500">Ошибка: {(error as Error).message}</div>
  if (!data) return null

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-2">{data.title}</h1>
      <p className="text-muted-foreground mb-8">Список покупок</p>

      <Card>
        <CardHeader>
          <CardTitle>Что купить</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-4">
            {data.items?.map((item: any) => (
              <li key={item.id} className="flex items-center justify-between border-b pb-4 last:border-0 last:pb-0">
                <div className="flex items-center gap-3">
                  <input type="checkbox" className="w-5 h-5 rounded border-gray-300" />
                  <span className="text-lg">{item.product_name}</span>
                </div>
                <Badge variant="secondary" className="text-sm">
                  {item.amount} {item.unit}
                </Badge>
              </li>
            ))}
          </ul>
          
          <div className="mt-8 pt-4 border-t flex justify-between items-center">
            <span className="font-semibold">Примерная стоимость:</span>
            <span className="text-2xl font-bold">
              {data.total_cost === null ? 'Нет подтверждённых цен' : `${data.total_cost} ₽`}
            </span>
          </div>
          {data.missing_prices?.length > 0 && (
            <p className="mt-2 text-sm text-muted-foreground">
              Частичная стоимость: цена известна для {data.known_prices} из {data.item_count} позиций.
              Без цены: {data.missing_prices.join(', ')}.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
