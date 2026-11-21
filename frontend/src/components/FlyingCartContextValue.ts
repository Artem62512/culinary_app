import { createContext } from 'react'

export type FlyingCartContextType = {
  flyToCart: (startElement: HTMLElement) => void
  registerCartTarget: (element: HTMLElement | null) => void
}

export const FlyingCartContext = createContext<FlyingCartContextType>({
  flyToCart: () => {},
  registerCartTarget: () => {},
})
