import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'

import { toast } from 'sonner'

export function RecipesPage({ onSelect }: { onSelect: (id: number) => void; onCreate: () => void }) {
  const qc = useQueryClient()
  const [recipeToDelete, setRecipeToDelete] = useState<{ id: number; title: string } | null>(null)

  const { data: recipes, isLoading, error } = useQuery<any[]>({
    queryKey: ['recipes'],
    queryFn: () => api.getRecipes(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteRecipe(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recipes'] })
      setRecipeToDelete(null)
    },
    onError: (err: any) => {
      toast.error('Ошибка удаления: ' + err.message)
      setRecipeToDelete(null)
    }
  })

  if (isLoading) return <div className="p-8 text-center">Загрузка рецептов...</div>
  if (error) return <div className="p-8 text-center text-red-500">Ошибка: {(error as Error).message}</div>

  return (
    <div className="max-w-6xl mx-auto p-8">

      <div className="mb-8">
        <h1 className="text-3xl font-bold">Мои рецепты</h1>
      </div>

      {(!recipes || recipes.length === 0) ? (
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            У вас пока нет рецептов. Перейдите во вкладку «Добавить рецепт», чтобы создать первый.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {recipes.map((r) => (
            <Card
              key={r.id}
              className="flex flex-col cursor-pointer hover:shadow-md transition-shadow group relative"
              onClick={() => onSelect(r.id)}
            >
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button variant="destructive" size="icon" className="h-8 w-8" onClick={(e) => {
                  e.stopPropagation()
                  setRecipeToDelete({ id: r.id, title: r.title })
                }}>
                  ✕
                </Button>
              </div>

              <CardHeader className="pr-12">
                <CardTitle className="text-xl">{r.title}</CardTitle>
              </CardHeader>
              <CardContent className="flex-1">
                <p className="text-sm text-muted-foreground mb-4">
                  Ингредиентов: {r.ingredients?.length || 0}
                </p>
                <div className="flex flex-wrap gap-1">
                  {r.ingredients?.slice(0, 4).map((ing: any, i: number) => (
                    <Badge key={i} variant="secondary" className="text-xs font-normal">
                      {ing.product_name}
                    </Badge>
                  ))}
                  {r.ingredients?.length > 4 && (
                    <Badge variant="outline" className="text-xs">+{r.ingredients.length - 4}</Badge>
                  )}
                </div>
              </CardContent>
              <CardFooter className="pt-2">
                <Button variant="outline" className="w-full">Открыть рецепт</Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!recipeToDelete} onOpenChange={(open) => !open && setRecipeToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Удалить рецепт?</DialogTitle>
            <DialogDescription>
              Вы уверены, что хотите удалить рецепт «{recipeToDelete?.title}»? Это действие нельзя отменить.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRecipeToDelete(null)}>Отмена</Button>
            <Button variant="destructive" onClick={() => recipeToDelete && deleteMutation.mutate(recipeToDelete.id)} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
