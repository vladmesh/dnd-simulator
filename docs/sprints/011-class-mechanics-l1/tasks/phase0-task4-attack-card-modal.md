# Task: Attack Card Modal

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown
**Status:** `done`

## Problem

Текущий `RollBreakdown` — inline-вставка в 11px шрифтом внутри строки лога. Результаты dice рендерятся как текст `[5]`, а модификаторы — мелкий курсив. Пользователь жалуется: "не сильно поменялось", "всё ещё нет кликабельных надписей", "хочу карточку атаки". Нужна полноценная модалка с максимально подробным визуальным breakdown.

## Solution

Заменить inline `RollBreakdown` на клик → модалка `AttackCardModal` (shadcn Dialog). Модалка открывается по клику на строку атаки в логе.

### Содержимое модалки

**Header:**
- Иконка оружия + название атаки (e.g. "Longsword Attack")
- Кто → кого (attacker → target)
- Вердикт: HIT / MISS / CRIT (большой, цветной badge)

**Attack Roll секция:**
- Визуальный d20: большой кубик с числом внутри (стилизованный div, не картинка)
- Если advantage/disadvantage — два d20, один зачёркнут/затемнён, показывает какой kept/dropped
- Столбец модификаторов: каждый на отдельной строке с source label и значением
  - `+3` STR (ability)
  - `+2` Proficiency
  - `+1` Magic Weapon
- Итог: `= 21 vs AC 15` → HIT

**Damage секция (только при hit):**
- Каждый damage component отдельным блоком:
  - Dice expression (e.g. "2d6 slashing")
  - Визуальные кубики: каждый die face как стилизованный div с числом
  - Если reroll — показать original зачёркнутым, стрелку, новый результат
  - Source label (weapon, sneak attack, etc.)
- Flat бонусы отдельной строкой: `+3 STR`, `+2 Dueling`
- Итого damage (жирный, большой)

### Визуальный стиль кубиков

Стилизованные div'ы с border-radius и тенью:
- d20: крупный (40x40), скруглённые углы, число по центру
- d6/d8/d10/d12: средние (28x28), цвет по типу damage (slashing=красный, bludgeoning=оранжевый, piercing=серый)
- Reroll: original die затемнён + зачёркнут, стрелка →, новый die нормальный
- Critical: золотая рамка на d20

### Интеграция с логом

- Строки атак в `EventLog` получают `cursor-pointer` и hover-эффект
- Клик на строку атаки → открывает `AttackCardModal`
- Убрать inline expand/chevron — модалка заменяет его полностью
- Текст строки лога не меняется (краткий формат остаётся)

## Files

- `frontend/src/components/game/AttackCardModal.tsx` — новый компонент модалки
- `frontend/src/components/game/DiceVisual.tsx` — визуальные кубики (переиспользуемый)
- `frontend/src/components/game/EventLog.tsx` — убрать inline expand, добавить клик → модалка
- `frontend/src/components/game/RollBreakdown.tsx` — удалить или оставить как fallback
- `frontend/src/components/game/__tests__/AttackCardModal.test.tsx` — тесты
- `frontend/src/components/game/__tests__/DiceVisual.test.tsx` — тесты визуальных кубиков

## Tests

### Unit (vitest + testing-library)

1. **DiceVisual** — рендерит d20/d6/d8 с правильным размером и числом, reroll показывает original+arrow+new, crit имеет gold border
2. **AttackCardModal** — открывается при передаче данных, показывает attacker/target/weapon, d20 с модификаторами, damage компоненты с dice faces, advantage показывает два d20
3. **EventLog integration** — клик на attack event вызывает открытие модалки, non-attack events не кликабельны

## Acceptance Criteria

- [x] Клик на строку атаки в логе открывает модалку
- [x] Модалка показывает d20 как визуальный кубик (не текст)
- [x] Каждый modifier на отдельной строке с source
- [x] Damage dice как визуальные кубики с цветом по типу
- [x] Reroll показывает original → new визуально
- [x] Advantage/disadvantage: два d20, dropped затемнён
- [x] Critical: золотая рамка на d20
- [x] Итоговый damage жирно, крупно
- [x] Модалка закрывается по клику вне / Escape / крестик
- [x] Inline chevron/expand из лога убран

## Developer Notes

Replaced inline `RollBreakdown` expand/collapse with `AttackCardModal` (shadcn Dialog). Created reusable `DiceVisual` component for styled die faces with damage-type coloring, reroll visualization, critical gold ring, and dropped-die dimming. The `extractAttackCardData` helper lives in `AttackCardModal.tsx` and converts raw event data to the typed `AttackCardData` shape. Old `RollBreakdown.tsx` is now unused — kept for now but can be deleted. Existing tests in `RollBreakdown.test.tsx` were rewritten to test the new modal flow instead of inline expand. `attacker_name`/`target_name` fields added to test data to match modal display.
