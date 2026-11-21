import { useEffect, useState, type FormEvent } from 'react'
import { api } from '@/lib/api'
import { RecipeTabs, type RecipeTabKey } from '@/components/RecipeTabs'
import { RecipesPage } from '@/pages/RecipesPage'
import { RecipePage } from '@/pages/RecipePage'
import { CreateRecipePage } from '@/pages/CreateRecipePage'
import { ShoppingListPage } from '@/pages/ShoppingListPage'
import { ProductCatalogPage } from '@/pages/ProductCatalogPage'
import { Button } from '@/components/ui/button'

type DetailView =
  | { name: 'list' }
  | { name: 'recipe'; id: number }
  | { name: 'edit'; id: number }
  | { name: 'shopping'; id: number }

function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(sessionStorage.getItem('culinary_auth')))
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [activeTab, setActiveTab] = useState<RecipeTabKey>('recipes')
  const [detail, setDetail] = useState<DetailView>({ name: 'list' })
  // Форма создания рецепта монтируется один раз при первом открытии вкладки
  // и остаётся в дереве, чтобы введённые данные не терялись при переключении.
  const [isCreateMounted, setIsCreateMounted] = useState(false)
  const [isCatalogMounted, setIsCatalogMounted] = useState(false)
  // Смена ключа пересоздаёт форму (очищает её) после сохранения или отмены.
  const [createFormKey, setCreateFormKey] = useState(0)

  useEffect(() => {
    if (!sessionStorage.getItem('culinary_auth')) return
    api.checkAuth().then(() => setAuthenticated(true)).catch(() => {
      sessionStorage.removeItem('culinary_auth')
      setAuthenticated(false)
    })
  }, [])

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const raw = new TextEncoder().encode(`${username}:${password}`)
    const token = btoa(String.fromCharCode(...raw))
    sessionStorage.setItem('culinary_auth', token)
    try {
      await api.checkAuth()
      setAuthenticated(true)
      setLoginError('')
      setPassword('')
    } catch {
      sessionStorage.removeItem('culinary_auth')
      setLoginError('Неверный логин или пароль, либо сервер не настроен')
    }
  }

  const handleTabChange = (tab: RecipeTabKey) => {
    setActiveTab(tab)
    if (tab === 'create') {
      setIsCreateMounted(true)
      return
    }
    if (tab === 'catalog') {
      setIsCatalogMounted(true)
      return
    }
    // Возврат на вкладку «Мои рецепты» всегда показывает список рецептов.
    setDetail({ name: 'list' })
  }

  const resetCreateForm = () => setCreateFormKey((key) => key + 1)

  const handleRecipeCreated = (id: number) => {
    resetCreateForm()
    setActiveTab('recipes')
    setDetail({ name: 'recipe', id })
  }

  const handleCreateCancel = () => {
    resetCreateForm()
    setActiveTab('recipes')
    setDetail({ name: 'list' })
  }

  if (!authenticated) {
    return (
      <main className="min-h-screen bg-background flex items-center justify-center p-4">
        <form onSubmit={handleLogin} className="w-full max-w-sm space-y-4 rounded-xl border bg-card p-6">
          <h1 className="text-2xl font-bold">Culinary App</h1>
          <p className="text-sm text-muted-foreground">Войдите, чтобы продолжить</p>
          <label className="block space-y-1 text-sm">Логин<input required autoComplete="username" className="w-full rounded-md border bg-background px-3 py-2" value={username} onChange={e => setUsername(e.target.value)} /></label>
          <label className="block space-y-1 text-sm">Пароль<input required type="password" autoComplete="current-password" className="w-full rounded-md border bg-background px-3 py-2" value={password} onChange={e => setPassword(e.target.value)} /></label>
          {loginError && <p role="alert" className="text-sm text-red-500">{loginError}</p>}
          <Button type="submit" className="w-full">Войти</Button>
        </form>
      </main>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <RecipeTabs activeTab={activeTab} onChange={handleTabChange} />

      <div
        role="tabpanel"
        id="panel-recipes"
        aria-labelledby="tab-recipes"
        className={activeTab === 'recipes' ? undefined : 'hidden'}
      >
        {detail.name === 'edit' ? (
          <CreateRecipePage
            key={`edit-${detail.id}`}
            recipeId={detail.id}
            onCreated={(id) => setDetail({ name: 'recipe', id })}
            onCancel={() => setDetail({ name: 'recipe', id: detail.id })}
          />
        ) : detail.name === 'recipe' ? (
          <div className="max-w-3xl mx-auto p-4">
            <Button variant="ghost" onClick={() => setDetail({ name: 'list' })} className="mb-4">
              ← Назад к рецептам
            </Button>
            <RecipePage recipeId={detail.id} onEdit={(id) => setDetail({ name: 'edit', id })} />
          </div>
        ) : detail.name === 'shopping' ? (
          <div className="max-w-3xl mx-auto p-4">
            <Button variant="ghost" onClick={() => setDetail({ name: 'list' })} className="mb-4">
              ← Назад к рецептам
            </Button>
            <ShoppingListPage listId={detail.id} />
          </div>
        ) : (
          <RecipesPage
            onSelect={(id) => setDetail({ name: 'recipe', id })}
            onCreate={() => handleTabChange('create')}
          />
        )}
      </div>

      {isCreateMounted && (
        <div
          role="tabpanel"
          id="panel-create"
          aria-labelledby="tab-create"
          className={activeTab === 'create' ? undefined : 'hidden'}
        >
          <CreateRecipePage
            key={createFormKey}
            onCreated={handleRecipeCreated}
            onCancel={handleCreateCancel}
          />
        </div>
      )}

      {isCatalogMounted && (
        <div
          role="tabpanel"
          id="panel-catalog"
          aria-labelledby="tab-catalog"
          className={activeTab === 'catalog' ? undefined : 'hidden'}
        >
          <ProductCatalogPage />
        </div>
      )}
    </div>
  )
}

export default App
