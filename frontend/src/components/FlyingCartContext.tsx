
import {
  useState,
  useRef,
  useCallback,
  type ReactNode,
} from 'react'
import { motion, AnimatePresence } from 'motion/react'

type FlyingItem = {
  id: number
  startX: number
  startY: number
  endX: number
  endY: number
}

import { FlyingCartContext } from './FlyingCartContextValue'

export function FlyingCartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<FlyingItem[]>([])
  const cartTargetRef = useRef<HTMLElement | null>(null)
  const nextIdRef = useRef(0)

  const registerCartTarget = useCallback((element: HTMLElement | null) => {
    cartTargetRef.current = element
  }, [])

  const flyToCart = useCallback((startEl: HTMLElement) => {
    const endEl = cartTargetRef.current

    if (!endEl) return

    const startRect = startEl.getBoundingClientRect()
    const endRect = endEl.getBoundingClientRect()

    const id = ++nextIdRef.current

    // Координаты центра начального элемента
    const startX = startRect.left + startRect.width / 2
    const startY = startRect.top + startRect.height / 2

    // Координаты центра корзины
    const endX = endRect.left + endRect.width / 2
    const endY = endRect.top + endRect.height / 2

    setItems((prev) => [...prev, { id, startX, startY, endX, endY }])

    // Удаляем анимацию из состояния через 800 мс
    setTimeout(() => {
      setItems((prev) => prev.filter((item) => item.id !== id))
    }, 800)
  }, [])

  return (
    <FlyingCartContext.Provider value={{ flyToCart, registerCartTarget }}>
      {children}

      <AnimatePresence>
        {items.map((item) => (
          <motion.div
            key={item.id}
            initial={{
              position: 'fixed',
              left: item.startX,
              top: item.startY,
              width: 20,
              height: 20,
              borderRadius: '50%',
              backgroundColor: '#000',
              zIndex: 9999,
              opacity: 1,
              scale: 1,
            }}
            animate={{
              left: item.endX,
              top: item.endY,
              scale: 0.2,
              opacity: 0.5,
            }}
            exit={{ opacity: 0 }}
            transition={{
              duration: 0.8,
              ease: [0.32, 0.72, 0, 1],
            }}
          />
        ))}
      </AnimatePresence>
    </FlyingCartContext.Provider>
  )
}
