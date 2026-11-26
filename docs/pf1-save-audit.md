# Проверка PF1.Save в Pathfinder 1e 11.11

Проверен полный исходный код тега **`v11.11`**, коммит **`418761d2e16a6037c0156bb4a241f7cea5a2986d`**. Поиск точного ключа по всему дереву (`rg -n --hidden -g '!.git' 'PF1\.Save\b' .`) нашёл **шесть** прямых употреблений. Дополнительно просмотрены употребления отдельного слова `Save` в JavaScript и шаблонах, чтобы проверить динамические обращения и команду `@Save[...]`.

| Место | Контекст |
| --- | --- |
| [damage-type-selector.mjs:127](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/damage-type-selector.mjs#L127) | Кнопка `submit`, применяющая выбор типов урона через `updateCallback` |
| [abstract-list-selector.mjs:162](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/abstract-list-selector.mjs#L162) | Кнопка `submit` базового редактора списков; `_save` обновляет документ. Наследуется `EntrySelector` и `DamageResistanceSelector` |
| [script-editor.mjs:95](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/script-editor.mjs#L95) | Кнопка `submit`, возвращающая изменённые текст и имя скрипта вызывающему коду |
| [senses-selector.mjs:98](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/senses-selector.mjs#L98) | Кнопка `submit`, сохраняющая параметры чувств/зрения актора |
| [speed-editor.mjs:73](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/speed-editor.mjs#L73) | Кнопка `submit`, сохраняющая параметры скорости документа |
| [vision-sharing.mjs:101](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/applications/vision-sharing.mjs#L101) | Кнопка `submit`, сохраняющая настройки совместного обзора |

Во всех шести местах ключ обозначает сохранение изменений. В английском [lang/en.json:1914](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/lang/en.json#L1914) определён `PF1.Save: "Save"`. Поэтому выбрано общее переопределение **`PF1.Save: "Сохранить"`** в `lang/overrides/phenomen.json`. Контекстный патч окон не нужен.

Игровые испытания используют отдельные ключи: например, `PF1.SavingThrow` в [action.hbs:342](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/public/templates/apps/item-action/action.hbs#L342) и [spell-header.hbs:27](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/public/templates/items/headers/spell-header.hbs#L27). Команда [@Save в text-enrichers.mjs:834](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/418761d2e16a6037c0156bb4a241f7cea5a2986d/module/chat/text-enrichers.mjs#L834) получает название из `pf1.config.savingThrows` и `PF1.SavingThrowButtonLabel`; `PF1.Save` она не запрашивает. Техническая команда, формулы и ключ `PF1.SavingThrow` не менялись; русский термин «Испытание» сохраняется.

Регрессионный тест загружает реальные JSON модуля поверх модели базового перевода с ошибочным `Save: "Испытание"`, проверяет результат `Save: "Сохранить"` и сохранение `SavingThrow`, `SavingThrowPlural` и `SavingThrowFort`. Пользователь подтвердил результат временного присваивания в Foundry; повторная проверка постоянного переопределения после загрузки модуля перечислена в [ручных сценариях](manual-testing.md).

Вывод относится к PF1 **11.11**. При расширении совместимости системы нужно повторить поиск употреблений ключа в новой версии.
