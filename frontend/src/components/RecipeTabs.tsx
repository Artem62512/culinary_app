
import { useCallback } from 'react'
import { cn } from 'cn'
import { Button } from '@/components/ui/button'
import { CartSheet } from '@/components/cart/CartSheet'
import { useFlyingCart } from '@/components/useFlyingCart'

export type RecipeTabKey = 'recipes' | 'create' | 'catalog'

interface TabDefinition {
  key: RecipeTabKey
  label: string
  panelId: string
}

const TABS: TabDefinition[] = [
  { key: 'recipes', label: 'Мои рецепты', panelId: 'panel-recipes' },
  { key: 'create', label: 'Добавить рецепт', panelId: 'panel-create' },
  { key: 'catalog', label: 'Каталог продуктов', panelId: 'panel-catalog' },
]

interface RecipeTabsProps {
  activeTab: RecipeTabKey
  onChange: (tab: RecipeTabKey) => void
}

export function RecipeTabs({ activeTab, onChange }: RecipeTabsProps) {
  const { registerCartTarget } = useFlyingCart()

  const setCartTarget = useCallback(
    (element: HTMLDivElement | null) => {
      registerCartTarget(element)
    },
    [registerCartTarget]
  )

  return (
    <div className="sticky top-0 z-30 border-b border-border bg-muted/50 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-end gap-2 px-4 pt-3 sm:px-8">
        <div
          role="tablist"
          aria-label="Разделы приложения"
          className="flex min-w-0 flex-1 items-end gap-1 overflow-x-auto"
        >
          {TABS.map((tab) => {
            const isActive = tab.key === activeTab

            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                id={`tab-${tab.key}`}
                aria-selected={isActive}
                aria-controls={tab.panelId}
                tabIndex={isActive ? 0 : -1}
                onClick={() => onChange(tab.key)}
                className={cn(
                  'relative -mb-px flex h-10 items-center rounded-t-lg border px-5 text-sm font-medium whitespace-nowrap transition-colors',
                  'outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background',
                  isActive
                    ? 'border-border border-b-transparent bg-background text-foreground shadow-[0_-1px_3px_rgba(0,0,0,0.06)]'
                    : 'border-transparent bg-transparent text-muted-foreground hover:bg-background/60 hover:text-foreground'
                )}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        <div ref={setCartTarget} className="shrink-0 pb-1">
          <CartSheet
            trigger={
              <Button variant="outline" size="sm">
                Корзина
              </Button>
            }
          />
        </div>
      </div>
    </div>
  )
}
