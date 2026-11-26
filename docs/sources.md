# Изученные источники

Проверено 26 ноября 2026 года. Исходники зависимостей изучались отдельно; их переводы не переносились в проект. В fixture сохранены только девять используемых английских строк.

| Источник | Что подтверждено |
| --- | --- |
| [Foundry: Module Development](https://foundryvtt.com/article/module-development/) | Поля манифеста `relationships`, `languages`, `esmodules`, URL обновлений; модульная папка совпадает с ID |
| [Foundry: Localization](https://foundryvtt.com/article/localization/) | Словарь модулей дополняет и переопределяет базовые строки |
| [API v13: Localization](https://foundryvtt.com/api/v13/classes/foundry.helpers.Localization.html) | Публичные `translations`, асинхронный `setLanguage`, `localize` и `format` |
| [API v13: i18nInit](https://foundryvtt.com/api/v13/functions/hookEvents.i18nInit.html) | Событие после загрузки языка, между `init` и `setup` |
| [API v13: mergeObject](https://foundryvtt.com/api/v13/functions/foundry.utils.mergeObject.html) | Слияние вложенных словарей, явный `overwrite`, сохранение остальных ключей |
| [libWrapper README](https://github.com/ruipin/fvtt-lib-wrapper/blob/master/README.md) и [манифест](https://github.com/ruipin/fvtt-lib-wrapper/blob/master/module.json) | ID `lib-wrapper`; `register` на `init`, тип `WRAPPER`, вызов обёрнутого метода |
| [Phenomen v13: манифест](https://github.com/phenomen/foundry-vtt-ru/blob/e852da0227652286fc8b8b6763f4edf55cce3f90/public/module.json) | ID `ru-ru`, язык `ru`, версия 13.351.54, `coreTranslation`, адрес `release-v13` |
| [Phenomen v13: инициализация](https://github.com/phenomen/foundry-vtt-ru/blob/e852da0227652286fc8b8b6763f4edf55cce3f90/src/index.js) | Языковые файлы подключены манифестом; PF1-скрипта с поздним изменением словаря в изученной ветке нет |
| [PF1 11.11: манифест](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/public/system.json) | ID `pf1`, версия 11.11, совместимость с Foundry 13 |
| [PF1 11.11: английский словарь](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/lang/en.json) | Восемь реальных ключей и `{save}` |
| [PF1 11.11: pf1.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/v11.11/pf1.mjs) | Однократная локализация `pf1.config` в обработчике `i18nInit` |
| [Babele: актуальная документация](https://gitlab.com/riccisi/foundryvtt-babele/-/wikis/Docs) | Каталог переводов, `entries`, регистрация источников, частичные переводы |
| [Babele 2.7.3: манифест](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.3/module/module.json) | ID `babele`, Foundry 13, обязательная зависимость `lib-wrapper` |
| [Babele 2.7.3: исходник](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.3/module/script/babele.js) и [тег 2.7.9](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.9/module/script/babele.js) | `babele.init` передаёт экземпляр; `register({module, lang, dir})`; загрузка пакетов на `ready`; слияние `entries` по ключам |
| [Babele 2.7.3: английский словарь](https://gitlab.com/riccisi/foundryvtt-babele/-/blob/2.7.3/module/lang/en.json) | `BABELE.CompendiumTranslations` |
| [Pathfinder Family: характеристики](https://pathfinder.family/ability) | Шесть характеристик, термин «испытание», написание «класс брони» |

Актуальная документация Babele содержит также новые возможности более поздних веток. Здесь используются только API, дополнительно проверенные в исходниках 2.7.x: `babele.init`, `register`, единственный `dir`. Новые `dirs`, меню приоритетов и глобальные маппинги не используются. В исходном `module.json` тега Babele 2.7.9 указана версия 2.7.7: воспроизводимый манифест зависимости закреплён на согласованном теге 2.7.3.

Порядок **внутри модулей** при стандартном объединении `languages` не принят за гарантию. Зависимость обеспечивает наличие Phenomen, а обёртка `setLanguage` задаёт наложение после завершения его штатной загрузки. В публичной документации API нет исходника вызова `setLanguage` из `initialize`: фактический порядок в установленной сборке v13 остаётся пунктом ручной проверки, как и совместимость с другими обёртками. Тесты проекта моделируют этот контракт и не являются запуском ядра Foundry.
