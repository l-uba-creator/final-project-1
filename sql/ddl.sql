-- =============================================================
-- DDL: схема хранения чеков торговой сети (товары для дома)
-- Схема: retail
-- =============================================================

CREATE SCHEMA IF NOT EXISTS retail;

-- Справочник магазинов
CREATE TABLE IF NOT EXISTS retail.shops (
    shop_id     SERIAL PRIMARY KEY,
    shop_num    INTEGER NOT NULL UNIQUE,
    shop_name   VARCHAR(100) NOT NULL,
    city        VARCHAR(100)
);

-- Справочник касс (у одного магазина может быть несколько касс)
CREATE TABLE IF NOT EXISTS retail.cash_registers (
    cash_reg_id SERIAL PRIMARY KEY,
    shop_id     INTEGER NOT NULL REFERENCES retail.shops (shop_id),
    cash_num    INTEGER NOT NULL,
    UNIQUE (shop_id, cash_num)
);

-- Справочник категорий товара
CREATE TABLE IF NOT EXISTS retail.categories (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

-- Справочник товаров
CREATE TABLE IF NOT EXISTS retail.products (
    product_id   SERIAL PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    category_id  INTEGER NOT NULL REFERENCES retail.categories (category_id),
    UNIQUE (product_name, category_id)
);

-- Чеки (шапка чека)
CREATE TABLE IF NOT EXISTS retail.receipts (
    receipt_id   BIGSERIAL PRIMARY KEY,
    doc_id       VARCHAR(50) NOT NULL,
    shop_id      INTEGER NOT NULL REFERENCES retail.shops (shop_id),
    cash_reg_id  INTEGER NOT NULL REFERENCES retail.cash_registers (cash_reg_id),
    sale_date    DATE NOT NULL,
    loaded_at    TIMESTAMP NOT NULL DEFAULT now(),
    -- один и тот же doc_id может повторяться в разные дни / на разных кассах,
    -- уникальность обеспечиваем в рамках магазина+кассы+даты
    UNIQUE (shop_id, cash_reg_id, sale_date, doc_id)
);

-- Позиции чека (строки)
CREATE TABLE IF NOT EXISTS retail.receipt_items (
    receipt_item_id BIGSERIAL PRIMARY KEY,
    receipt_id      BIGINT NOT NULL REFERENCES retail.receipts (receipt_id) ON DELETE CASCADE,
    product_id      INTEGER NOT NULL REFERENCES retail.products (product_id),
    amount          NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    price           NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    discount        NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
    line_total      NUMERIC(12, 2) GENERATED ALWAYS AS (amount * price - discount) STORED
);

-- Журнал загруженных файлов — обеспечивает идемпотентность ETL
-- (повторный запуск загрузчика не задублирует уже загруженный файл)
CREATE TABLE IF NOT EXISTS retail.processed_files (
    file_name    VARCHAR(255) NOT NULL,
    file_hash    VARCHAR(64) NOT NULL,
    shop_id      INTEGER REFERENCES retail.shops (shop_id),
    cash_reg_id  INTEGER REFERENCES retail.cash_registers (cash_reg_id),
    row_count    INTEGER NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (file_name, file_hash)
);

-- Индексы для типичных аналитических запросов
CREATE INDEX IF NOT EXISTS idx_receipts_sale_date ON retail.receipts (sale_date);
CREATE INDEX IF NOT EXISTS idx_receipts_shop ON retail.receipts (shop_id);
CREATE INDEX IF NOT EXISTS idx_receipt_items_receipt ON retail.receipt_items (receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_items_product ON retail.receipt_items (product_id);
