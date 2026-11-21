
import { detectUnit } from '@/lib/units'

export interface ParsedRecipeIngredient {
  name: string
  amount: string
  unit: string
  note: string
}

export interface ParsedRecipe {
  title: string
  servings: number | null
  cookingTime: string
  temperature: string
  description: string
  instructions: string
  ingredients: ParsedRecipeIngredient[]
}

const UNIT_PATTERNS: Array<[RegExp, string]> = [
  [/^(?:г|гр|грамм(?:а|ов)?)\.?(?:\s+|$)/i, 'g'],
  [/^(?:кг|килограмм(?:а|ов)?)\.?(?:\s+|$)/i, 'kg'],
  [/^(?:мл|миллилитр(?:а|ов)?)\.?(?:\s+|$)/i, 'ml'],
  [/^(?:л|литр(?:а|ов)?)\.?(?:\s+|$)/i, 'l'],
  [/^(?:шт\.?|штук(?:а|и)?)\s*(?=\S|$)/i, 'pcs'],
  [/^(?:стакан(?:а|ов)?)\s*(?=\S|$)/i, 'cup'],
  [/^(?:зубчик(?:а|ов)?)\s*(?=\S|$)/i, 'clove'],
  [/^(?:пучок|пучка|пучков)\s*(?=\S|$)/i, 'bunch'],
  [/^(?:веточ(?:ка|ки|ек))\s*(?=\S|$)/i, 'bunch'],
  [/^(?:ст\.?\s*(?:л\.?|ложк(?:а|и))|столов(?:ая|ые)\s+ложк(?:а|и))\s*(?=\S|$)/i, 'tbsp'],
  [/^(?:ч\.?\s*(?:л\.?|ложк(?:а|и))|чайная\s+ложк(?:а|и))\s*(?=\S|$)/i, 'tsp'],
  [/^(?:щепотк(?:а|и))\s*(?=\S|$)/i, 'pinch'],
]

const QUANTITY_PATTERN =
  /^\d+(?:[.,]\d+)?(?:\s*\/\s*\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?(?:\s*\/\s*\d+)?)?/

function cleanLine(value: string): string {
  return value
    .replace(/^\s*(?:[-*•▪●]|\d+[.)])\s*/, '')
    .replace(/^#{1,6}\s*/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizeAmount(value: string): string {
  return value
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/[–—]/g, '–')
}

function isPhotoCaption(value: string): boolean {
  return /^(?:фото\s+(?:к\s+рецепту|приготовления\s+рецепта)|пошаговый\s+фото\s+рецепт)/i.test(
    value,
  )
}

function extractNote(value: string): { value: string; note: string } {
  const match = value.match(/^(.*?)\s*\(([^()]*)\)\s*$/)

  if (!match || !match[1].trim()) {
    return { value: value.trim(), note: '' }
  }

  return {
    value: match[1].trim(),
    note: match[2].trim(),
  }
}


function parseQuantityAndUnit(
  value: string,
): { amount: string; unit: string; name: string; note: string } | null {
  const quantityMatch = value.match(QUANTITY_PATTERN)

  if (!quantityMatch) return null

  const amount = normalizeAmount(quantityMatch[0])
  let remainder = value.slice(quantityMatch[0].length).trim()
  let unit = ''

  for (const [pattern, code] of UNIT_PATTERNS) {
    const match = remainder.match(pattern)

    if (match) {
      unit = code
      remainder = remainder.slice(match[0].length).trim()
      break
    }
  }

  const extracted = extractNote(remainder)
  const name = extracted.value.replace(/^[,;:–—-]\s*/, '').trim()

  // Для формата «500 г» название продукта может быть перед количеством.
  // Поэтому пустое название здесь допустимо.
  return {
    amount,
    unit: unit || (name ? detectUnit(name) : ''),
    name,
    note: extracted.note,
  }
}


function parseIngredientLine(line: string): ParsedRecipeIngredient | null {
  let value = cleanLine(line)
  if (!value) return null

  value = value.replace(/^[,;]\s*/, '')

  if (
    /^(?:ингредиенты|состав|продукты|что понадобится|необходимые продукты|приготовление|способ приготовления|инструкция|инструкции|шаги)\s*:?\s*$/i.test(
      value,
    )
  ) {
    return null
  }

  // Формат: "Соль по вкусу" или "Соль - по вкусу".
  const tasteMatch = value.match(
    /^(.*?)\s*(?:[-–—:]\s*)?по вкусу\s*$/i,
  )

  if (tasteMatch && tasteMatch[1].trim()) {
    const extracted = extractNote(tasteMatch[1].trim())

    return {
      name: extracted.value,
      amount: 'по вкусу',
      unit: 'to_taste',
      note: extracted.note,
    }
  }

  // Формат: "500 г говядины".
  const leading = parseQuantityAndUnit(value)

  if (leading) {
    return {
      name: leading.name,
      amount: leading.amount,
      unit: leading.unit,
      note: leading.note,
    }
  }

  // Формат: "Говядина - 500 г".
  const separatorMatch = value.match(/^(.+?)\s+[-–—:]\s*(.+)$/)

  if (separatorMatch) {
    const rawName = separatorMatch[1].trim()
    const parsedQuantity = parseQuantityAndUnit(separatorMatch[2].trim())

    if (parsedQuantity) {
      const extractedName = extractNote(rawName)
      const notes = [
        extractedName.note,
        parsedQuantity.note,
      ].filter(Boolean)

      return {
        name: extractedName.value,
        amount: parsedQuantity.amount,
        unit: parsedQuantity.unit || detectUnit(extractedName.value),
        note: notes.join('; '),
      }
    }

    // Например: "Соль - по вкусу".
    if (/^по вкусу$/i.test(separatorMatch[2].trim())) {
      const extractedName = extractNote(rawName)

      return {
        name: extractedName.value,
        amount: 'по вкусу',
        unit: 'to_taste',
        note: extractedName.note,
      }
    }
  }

  // Количество не указано — сохраняем название без выдуманных значений.
  const extracted = extractNote(value)
  const name = extracted.value.replace(/^[,;:–—-]\s*/, '').trim()

  if (!name) return null

  return {
    name,
    amount: '',
    unit: detectUnit(name),
    note: extracted.note,
  }
}

export function parseRecipeText(source: string): ParsedRecipe {
  const lines = source
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((line) => line.trim())

  const result: ParsedRecipe = {
    title: '',
    servings: null,
    cookingTime: '',
    temperature: '',
    description: '',
    instructions: '',
    ingredients: [],
  }

  let section: 'before' | 'ingredients' | 'instructions' = 'before'

  const descriptionLines: string[] = []
  const instructionLines: string[] = []

  const ingredientHeading =
    /^(?:ингредиенты|состав|продукты|что понадобится|необходимые продукты)(?:\s*\([^)]*\))?\s*:?\s*$/i

  const instructionHeading =
    /^(?:приготовление|способ приготовления|как приготовить|инструкция|инструкции|шаги приготовления)(?:\s+.*)?\s*:?\s*$/i

  for (const originalLine of lines) {
    const line = originalLine.trim()
    if (!line) continue

    const cleaned = cleanLine(line)

    if (!cleaned) continue

    // Подписи к фотографиям не относятся к содержанию рецепта.
    if (isPhotoCaption(cleaned)) continue

    // Заголовок пошагового фото-рецепта означает начало инструкции.
    if (/^пошаговый\s+фото\s+рецепт/i.test(cleaned)) {
      section = 'instructions'
      continue
    }

    // Заголовки разделов.
    if (ingredientHeading.test(cleaned)) {
      section = 'ingredients'

      const headingServings = cleaned.match(
        /на\s+(\d+)\s*порци(?:и|й)/i,
      )

      if (headingServings) {
        result.servings = Number(headingServings[1])
      }

      continue
    }

    if (instructionHeading.test(cleaned)) {
      section = 'instructions'
      continue
    }

    // Количество порций.
    const servingsMatch = cleaned.match(
      /(?:на\s+)?(\d+)\s*(?:порци(?:и|й)|человек)/i,
    ) || cleaned.match(
      /(?:порции|количество порций|выход)\s*:\s*(\d+)/i,
    )

    if (servingsMatch) {
      result.servings = Number(servingsMatch[1])
      continue
    }

    // Время приготовления: "2 часа (ваши 30 мин)".
    const timeMatch = cleaned.match(
      /(?:время приготовления|время готовки|готовить|выпекать|варить|жарить)\s*[:—-]?\s*(.+)$/i,
    )

    const simpleTimeMatch = cleaned.match(
      /^(\d+\s*(?:час(?:а|ов)?|ч\.?|минут(?:а|ы)?|мин\.?)(?:\s+\d+\s*(?:минут(?:а|ы)?|мин\.?))?(?:\s*\([^)]*\))?)$/i,
    )

    if (timeMatch || simpleTimeMatch) {
      result.cookingTime = (timeMatch?.[1] || simpleTimeMatch?.[1] || '').trim()
      continue
    }

    // Температура приготовления.
    const temperatureMatch = cleaned.match(
      /(?:температура\s*[:=]?\s*)?(\d{2,3})\s*°?\s*(?:c|с|градус(?:ов|а)?)/i,
    )

    if (temperatureMatch) {
      result.temperature = `${temperatureMatch[1]} °C`
      continue
    }

    // Строка с автором и датой, например "Практика-П 18.04.14".
    if (
      /(?:19|20)\d{2}/.test(cleaned) ||
      /\b\d{1,2}\.\d{1,2}\.\d{2,4}\b/.test(cleaned)
    ) {
      continue
    }

    if (section === 'before') {
      if (!result.title) {
        result.title = cleaned.replace(/^["«]|["»]$/g, '').trim()
      } else {
        descriptionLines.push(cleaned)
      }

      continue
    }

    if (section === 'ingredients') {
      const ingredient = parseIngredientLine(line)

      if (ingredient) {
        result.ingredients.push(ingredient)
      }

      continue
    }

    if (section === 'instructions') {
      instructionLines.push(line)
    }
  }

  result.description = descriptionLines.join('\n')

  if (result.cookingTime || result.temperature) {
    const metadata = [
      result.cookingTime
        ? `Время приготовления: ${result.cookingTime}`
        : '',
      result.temperature
        ? `Температура: ${result.temperature}`
        : '',
    ]
      .filter(Boolean)
      .join('\n')

    result.description = [result.description, metadata]
      .filter(Boolean)
      .join('\n\n')
  }

  result.instructions = instructionLines.join('\n')

  return result
}
