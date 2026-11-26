# Изученные источники

Проверено 26 ноября 2026 года. Исходники зависимостей изучались отдельно; их переводы не переносились в проект. В fixture сохранены только десять используемых английских строк.

Терминологическая политика закреплена в [AGENTS.md](../AGENTS.md). Русская книга пользователя — [«Сборник материалов по ролевой игре „Pathfinder“»](https://drive.google.com/file/d/12bDq5ppWERwsM2xOppvLzT7VosCJET3T/view) — имеет равный приоритет с Pathfinder Family. Доступ к PDF подтверждён: 608 страниц с извлекаемым русским текстом. Сведения об экземпляре и его лицензионных заявлениях проверены и дополнены 27 ноября 2026 года в [реестре источников и прав](licensing/SOURCES.md#русская-книга-правил-пользователя); неизвестные выходные данные не подменяются данными другого издания.

| Источник | Что подтверждено |
| --- | --- |
| [Foundry: Module Development](https://foundryvtt.com/article/module-development/) | Поля манифеста `relationships`, `languages`, `esmodules`, URL обновлений; модульная папка совпадает с ID |
| [GitHub: Linking to releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases) | Постоянный адрес asset `/releases/latest/download/<name>` и адреса конкретных выпусков |
| [GitHub: Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) | Разделение Save draft/Publish release, pre-release и выбор Latest |
| [Foundry: Localization](https://foundryvtt.com/article/localization/) | Словарь модулей дополняет и переопределяет базовые строки |
| [API v13: Localization](https://foundryvtt.com/api/v13/classes/foundry.helpers.Localization.html) | Публичные `translations`, асинхронный `setLanguage`, `localize` и `format` |
| [API v13: i18nInit](https://foundryvtt.com/api/v13/functions/hookEvents.i18nInit.html) | Событие после загрузки языка, между `init` и `setup` |
| [API v13: mergeObject](https://foundryvtt.com/api/v13/functions/foundry.utils.mergeObject.html) | Слияние вложенных словарей, явный `overwrite`, сохранение остальных ключей |
| [API v13: getRoute](https://foundryvtt.com/api/v13/functions/foundry.utils.getRoute.html) | Добавляет настроенный префикс маршрута; перед `fetch` итог явно приводится к пути от корня сайта |
| [libWrapper README](https://github.com/ruipin/fvtt-lib-wrapper/blob/master/README.md) и [манифест](https://github.com/ruipin/fvtt-lib-wrapper/blob/master/module.json) | ID `lib-wrapper`; `register` на `init`, тип `WRAPPER`, вызов обёрнутого метода |
| [Phenomen v13: манифест](https://github.com/phenomen/foundry-vtt-ru/blob/e852da0227652286fc8b8b6763f4edf55cce3f90/public/module.json) | ID `ru-ru`, язык `ru`, версия 13.351.54, `coreTranslation`, адрес `release-v13` |
| [Phenomen v13: инициализация](https://github.com/phenomen/foundry-vtt-ru/blob/e852da0227652286fc8b8b6763f4edf55cce3f90/src/index.js) | Языковые файлы подключены манифестом; PF1-скрипта с поздним изменением словаря в изученной ветке нет |
| [PF1 11.11: манифест](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/public/system.json) | ID `pf1`, версия 11.11, совместимость с Foundry 13 |
| [PF1 11.11: английский словарь](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/lang/en.json) | Девять реальных ключей, включая `PF1.Save`, и `{save}` |
| [Аудит PF1.Save в PF1 11.11](pf1-save-audit.md) | Шесть употреблений ключа — кнопки сохранения форм; игровых испытаний среди них нет; `PF1.SavingThrow` остаётся в базовом переводе |
| [PF1 11.11: pf1.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/pf1.mjs) | Однократная локализация `pf1.config` в обработчике `i18nInit` |
| [Babele: актуальная документация](https://gitlab.com/riccisi/foundryvtt-babele/-/wikis/Docs) | Каталог переводов, `entries`, регистрация источников, частичные переводы |
| [Babele 2.9.1: манифест](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.9.1/module/module.json) | ID `babele`, `minimum: 13`, `verified: 14`, обязательная зависимость `lib-wrapper`; допускает Foundry 13 |
| [Babele 2.9.1: фасад](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.9.1/module/script/babele.js) | `babele.init` синхронно передаёт экземпляр на `init`; `register` делегирует движку и запрещён после создания сессии; инициализация на `ready` |
| [Babele 2.9.1: реестр источников](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.9.1/module/script/translation/translation-source-registry.js) | `register({module, lang, dir})` поддерживается; каталог разрешается как `modules/<module>/<dir>`, фильтр языка сравнивает `lang` с активным языком |
| [Babele 2.9.1: английский словарь](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.9.1/module/lang/en.json) | `BABELE.CompendiumTranslations`: `Translation Export` |
| [Pathfinder Family: характеристики](https://pathfinder.family/ability) | Шесть характеристик, термин «испытание», написание «класс брони» |

Целевая версия Babele — **2.9.1**; манифест зависимости закреплён на её теге, допустимый диапазон — **2.7.3–2.9.1**. Ранее используемый контракт также проверялся по [2.7.3](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.3/module/script/babele.js) и [тегу 2.7.9](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.9/module/script/babele.js). Нужные `babele.init` и `register({module, lang, dir})` сохраняются в 2.9.1, поэтому код регистрации менять не требуется. Новые `dirs`, меню приоритетов и глобальные маппинги модуль не использует. Проверка исходников не заменяет повторный запуск в Foundry.

Проверка URL учитывает две формы `languages[].path`: исходную `lang/...` и уже подготовленную `modules/foundry-pf1-ru/lang/...`. Безусловное добавление корня модуля к второй форме дублирует его. Нормализация исключает повтор, `getRoute` сохраняет `routePrefix`, начальный `/` делает запрос независимым от браузерной базы. Регрессионные тесты воспроизводят обе формы и разрешение URL с разными базами; до исправления они падали.

Порядок **внутри модулей** при стандартном объединении `languages` не принят за гарантию. Зависимость обеспечивает наличие Phenomen, а обёртка `setLanguage` задаёт наложение после завершения его штатной загрузки. Пользователь подтвердил работу переопределений 0.1.0 в Foundry 13 / PF1 11.11 / Babele 2.9.1. Расширенная проверка кэша на `i18nInit` и совместимость с другими обёртками перечислены отдельно. Тесты проекта моделируют этот контракт и не являются запуском ядра Foundry.
