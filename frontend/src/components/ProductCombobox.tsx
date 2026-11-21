import { useState } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface ProductComboboxProps {
  value: string
  onChange: (value: string) => void
  items: { value: string; label: string; searchText?: string }[]
  placeholder: string
  disabled?: boolean
  disabledValues?: string[] // Новое свойство: какие значения скрыть
}

export function ProductCombobox({ value, onChange, items, placeholder, disabled, disabledValues = [] }: ProductComboboxProps) {
  const [open, setOpen] = useState(false)

  // Фильтруем список, убирая те элементы, которые уже выбраны в других строках
  const availableItems = items.filter(item => !disabledValues.includes(item.value));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className="w-full justify-between font-normal text-left overflow-hidden"
        >
          <span className="truncate">
            {value
              ? items.find((item) => item.value === value)?.label
              : placeholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>} />
      <PopoverContent className="w-[300px] p-0" align="start">
        <Command>
          <CommandInput placeholder="Поиск..." />
          <CommandEmpty>Ничего не найдено.</CommandEmpty>
          <CommandGroup className="max-h-[300px] overflow-y-auto">
            {availableItems.map((item) => (
              <CommandItem
                key={item.value}
                value={item.searchText || item.label}
                onSelect={() => {
                  onChange(item.value)
                  setOpen(false)
                }}
              >
                <Check
                  className={cn(
                    'mr-2 h-4 w-4',
                    value === item.value ? 'opacity-100' : 'opacity-0'
                  )}
                />
                {item.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
