# Действия, события и видимость

Обсуждение 2026-03-20.

## Действие → что происходит

Любое действие существа в мире проходит четыре этапа:

```
1. Валидация      — можно ли? (регион, жив, оружие есть...)
                    Нет → ActionResult(success=False, error="...")
2. Резолюция      — бросок кубиков, проверки
3. Мутация стейта — HP, инвентарь, позиция...
4. Лог событий    — что произошло, для awareness других существ
```

ActionResult возвращается вызывающему (player/NPC). Если success=False —
ход не засчитывается, существо может попробовать другое действие.

## Visibility — кто видит событие

Два отдельных вопроса:
- **Visibility**: видит ли наблюдатель это событие вообще?
- **Perspective**: если видит — как именно? (уже есть: perceive_event)

Visibility определяется при резолюции действия. На Event хранится явный
список наблюдателей:

```python
@dataclass
class Event:
    ...
    observer_ids: frozenset[str] | None = None  # None = все в area видят
```

`None` = public (видят все в той же area/регионе). Явный set = только они.

### Кто определяет visibility — правила, не LLM

Типизированные действия:
- **Атака** → public (все видят)
- **Речь** → public
- **Шёпот** → observers = {speaker, listener}
- **Кража (успех)** → observers = {thief}
- **Кража (провал)** → observers = {thief, victim}
- **Кража (крит-провал)** → public

Механика: Sleight of Hand vs Passive Perception определяет кто заметил.
Чистые правила, без LLM.

### Нетипизированные действия (будущее, Мастер)

"Делаю отвлекающий манёвр", "незаметно подмигиваю союзнику" — Мастер (LLM)
решает: какой чек, какая сложность, кто видит. Но это после реализации Мастера.

### Четвёртая стена

Пример: игрок крадётся и крадёт кошелёк. Без visibility торговец читает лог
и знает кто украл. С visibility: если кража успешна — события нет в логе
торговца вообще. Если провалена — торговец видит "кто-то пытался залезть
в твой карман" (perspective фильтрует детали).

## Фильтрация awareness

При построении лога для существа:

```python
def get_perceived_log(self, observer: Character) -> list[str]:
    for event in region_log:
        if event.observer_ids is not None and observer.id not in event.observer_ids:
            continue  # это событие observer не видел
        yield perceive_event(event, observer, get_entity)
```

## Что реализуем сейчас

1. `ActionResult` — success/error + events
2. Валидация в _resolve_attack: регион, жив, оружие
3. `observer_ids` на Event (None = public для всех текущих действий)
4. Фильтрация лога по observer_ids
