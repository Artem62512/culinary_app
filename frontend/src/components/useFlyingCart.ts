import { useContext } from 'react'
import { FlyingCartContext } from './FlyingCartContextValue'

export const useFlyingCart = () => useContext(FlyingCartContext)
