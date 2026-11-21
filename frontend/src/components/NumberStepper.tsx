import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface NumberStepperProps {
  value: string
  onChange: (val: string) => void
  step?: number
  min?: number
}

export function NumberStepper({ value, onChange, step = 50, min = 1 }: NumberStepperProps) {
  const handleIncrement = () => {
    const current = Number(value) || 0
    onChange(String(current + step))
  }

  const handleDecrement = () => {
    const current = Number(value) || 0
    const next = current - step
    onChange(String(next < min ? min : next))
  }

  return (
    <div className="flex items-center gap-1">
      <Button 
        type="button" 
        variant="outline" 
        size="icon" 
        className="h-10 w-10 shrink-0" 
        onClick={handleDecrement}
      >
        -
      </Button>
      
      <Input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-16 text-center h-10 shrink-0 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
      />
      
      <Button 
        type="button" 
        variant="outline" 
        size="icon" 
        className="h-10 w-10 shrink-0" 
        onClick={handleIncrement}
      >
        +
      </Button>
    </div>
  )
}
