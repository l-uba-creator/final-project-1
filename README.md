# Автоматизация обработки чеков торговой сети (товары для дома)

Финальный проект курса «Аналитика и инженерия данных». Эмулирует ежедневную выгрузку
чеков из кассового ПО сети магазинов товаров для дома (бытовая химия, текстиль,
посуда, хозтовары и т.д.) и автоматическую загрузку этих выгрузок в базу данных.

## Что делает проект

1. **`scripts/generate_data.py`** — эмулирует кассовое ПО: генерирует по одному
   CSV-файлу на каждую кассу каждого магазина в папку `data/`. Имя файла —
   `{shop_num}_{cash_num}.csv` (например, `11_2.csv` — магазин 11, касса 2).
2. **`scripts/load_to_db.py`** — читает файлы из `data/`, подходящие под маску
   `{shop}_{cash}.csv` (все остальные файлы в папке игнорируются), и загружает их
   в PostgreSQL. Повторный запуск не задваивает уже загруженные данные.
3. Оба скрипта автоматизированы через **Планировщик заданий Windows**:
   генерация — каждый день, кроме воскресенья; загрузка — каждый день.

## Структура репозитория

```
├── config/
│   └── config.yaml            # параметры генерации (число магазинов, касс и т.д.)
├── data/                      # пример сгенерированной выгрузки (CSV)
├── img/                       # скриншоты автоматизации и БД
├── scripts/
│   ├── catalog.py             # справочник категорий/товаров
│   ├── settings.py            # загрузка конфигурации (.env + config.yaml)
│   ├── db.py                  # подключение к PostgreSQL
│   ├── generate_data.py       # генератор выгрузок
│   ├── load_to_db.py          # загрузчик выгрузок в БД
│   ├── run_generate.ps1       # обёртка для Планировщика заданий
│   ├── run_load.ps1           # обёртка для Планировщика заданий
│   └── register_scheduled_tasks.ps1  # регистрация задач в Планировщике
├── sql/
│   └── ddl.sql                # DDL создания таблиц БД
├── docker-compose.yml         # PostgreSQL + pgAdmin
├── .env.example                # пример файла с параметрами подключения к БД
├── requirements.txt
└── README.md
```

## Формат выгрузки

Столбцы CSV: `doc_id, item, category, amount, price, discount`.
- `doc_id` — численно-буквенный идентификатор чека (несколько строк с одним
  `doc_id` образуют один чек с несколькими позициями);
- `item` — название товара;
- `category` — категория товара;
- `amount` — количество товара в позиции;
- `price` — цена одной позиции без учёта скидки;
- `discount` — сумма скидки на позицию (может быть 0).

## Модель данных

Схема `retail` в PostgreSQL (см. [`sql/ddl.sql`](sql/ddl.sql)):

- `shops`, `cash_registers` — справочники магазинов и касс;
- `categories`, `products` — справочники категорий и товаров;
- `receipts` — шапки чеков (уникальность в рамках магазин+касса+дата+doc_id);
- `receipt_items` — позиции чеков (сумма строки считается автоматически:
  `amount * price - discount`);
- `processed_files` — журнал загруженных файлов (обеспечивает идемпотентность ETL).

## Запуск проекта на новой машине

### 0. Предварительные требования

- Python 3.11+
- Windows с доступным Планировщиком заданий (для автоматизации)
- СУБД PostgreSQL — один из двух вариантов:
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (самый быстрый способ, требует рабочий WSL2/Hyper-V);
  - либо [нативная установка PostgreSQL для Windows](https://www.postgresql.org/download/windows/) — используйте,
    если Docker Desktop не запускается (например, из-за проблем с WSL2 на машине).

### 1. Клонировать репозиторий

```powershell
git clone <URL-репозитория>
cd final-project-1st
```

### 2. Настроить окружение Python

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

При необходимости отредактируйте `.env` (по умолчанию подходит для локального
`docker-compose.yml` без изменений).

### 3. Поднять базу данных

**Вариант А — Docker (рекомендуется, если Docker Desktop у вас работает):**

```powershell
docker compose up -d
```

Таблицы создаются автоматически при первом запуске контейнера — `sql/ddl.sql`
подключён как init-скрипт PostgreSQL (`docker-entrypoint-initdb.d`).
pgAdmin доступен на [http://localhost:5050](http://localhost:5050)
(логин `admin@example.com` / пароль `admin`).

**Вариант Б — нативный PostgreSQL (если Docker недоступен, например из-за WSL2):**

```powershell
winget install --id PostgreSQL.PostgreSQL.16 -e --source winget
```

После установки создайте пользователя и БД (значения соответствуют `.env.example`)
и накатите схему из `sql/ddl.sql`:

```powershell
$env:PGBIN = "C:\Program Files\PostgreSQL\16\bin"
& "$env:PGBIN\psql.exe" -U postgres -h localhost -c "CREATE ROLE retail_user LOGIN PASSWORD 'retail_pass';"
& "$env:PGBIN\psql.exe" -U postgres -h localhost -c "CREATE DATABASE retail OWNER retail_user;"
& "$env:PGBIN\psql.exe" -U retail_user -h localhost -d retail -f sql\ddl.sql
```

Для просмотра таблиц удобно использовать [DBeaver](https://dbeaver.io/) или pgAdmin
(идёт в комплекте с установщиком PostgreSQL) — подключение: `localhost:5432`,
база `retail`, пользователь/пароль из `.env`.

### 4. Сгенерировать тестовую выгрузку вручную

```powershell
.\.venv\Scripts\python scripts\generate_data.py
```

Файлы появятся в `data/`. Количество магазинов и другие параметры генерации
задаются в `config/config.yaml` или флагом `--shops N`.

### 5. Загрузить выгрузку в БД

```powershell
.\.venv\Scripts\python scripts\load_to_db.py
```

Скрипт игнорирует в `data/` любые файлы, не подходящие под маску
`{shop_num}_{cash_num}.csv`.

### 6. Настроить автоматический ежедневный запуск

```powershell
.\scripts\register_scheduled_tasks.ps1
```

Скрипт регистрирует в Планировщике заданий Windows две задачи:

| Задача | Расписание | Действие |
|---|---|---|
| `RetailDataGenerate` | каждый день, кроме воскресенья, в 08:00 | `scripts/run_generate.ps1` |
| `RetailDataLoad` | каждый день в 08:30 | `scripts/run_load.ps1` |

Проверить задачи можно в приложении «Планировщик заданий» (`taskschd.msc`) —
см. скриншот в [`img/`](img/). Логи выполнения пишутся в `logs/`.

> На Linux/macOS вместо Планировщика заданий используйте `cron`, например:
> `0 8 * * 1-6 /path/to/.venv/bin/python /path/to/scripts/generate_data.py`
> `30 8 * * * /path/to/.venv/bin/python /path/to/scripts/load_to_db.py`

## Скриншоты

В папке [`img/`](img/):
- [`task_scheduler.jpg`](img/task_scheduler.jpg) — задачи `RetailDataGenerate` и `RetailDataLoad`
  в Планировщике заданий Windows; у `RetailDataGenerate` виден триггер «по понедельник,
  вторник, среда, четверг, пятница, суббота» (то есть каждый день, кроме воскресенья);
- [`db_schema.jpg`](img/db_schema.jpg) — ER-диаграмма всех 7 таблиц схемы `retail` в DBeaver;
- [`db_data_sample.jpg`](img/db_data_sample.jpg) — результат запроса
  `SELECT * FROM retail.receipt_items LIMIT 20`, подтверждающий, что данные реально загружены.

## Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
