#!/usr/bin/env python
"""Загрузчик CSV-выгрузок касс из папки data/ в PostgreSQL.

Правила:
  * обрабатываются только файлы вида {shop_num}_{cash_num}.csv, всё остальное
    в папке (сторонние файлы) игнорируется;
  * повторный запуск не задваивает уже загруженные файлы — идемпотентность
    обеспечивается таблицей retail.processed_files по паре (имя файла, hash
    содержимого);
  * дата продажи (sale_date) — дата запуска загрузчика: кассовое ПО каждый
    день перезаписывает файл выгрузки за текущие сутки.
"""

import argparse
import csv
import hashlib
import logging
import re
from datetime import date
from pathlib import Path

from catalog import SHOP_NAME_TEMPLATE, CITIES
from db import get_connection
from settings import DATA_DIR, LOG_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "load_to_db.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("load_to_db")

FILENAME_RE = re.compile(r"^(\d+)_(\d+)\.csv$")
REQUIRED_COLUMNS = {"doc_id", "item", "category", "amount", "price", "discount"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_or_create_shop(cur, shop_num: int) -> int:
    cur.execute("SELECT shop_id FROM retail.shops WHERE shop_num = %s", (shop_num,))
    row = cur.fetchone()
    if row:
        return row[0]

    city = CITIES[shop_num % len(CITIES)]
    cur.execute(
        """
        INSERT INTO retail.shops (shop_num, shop_name, city)
        VALUES (%s, %s, %s)
        ON CONFLICT (shop_num) DO NOTHING
        RETURNING shop_id
        """,
        (shop_num, SHOP_NAME_TEMPLATE.format(shop_num=shop_num), city),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("SELECT shop_id FROM retail.shops WHERE shop_num = %s", (shop_num,))
    return cur.fetchone()[0]


def get_or_create_cash_register(cur, shop_id: int, cash_num: int) -> int:
    cur.execute(
        "SELECT cash_reg_id FROM retail.cash_registers WHERE shop_id = %s AND cash_num = %s",
        (shop_id, cash_num),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO retail.cash_registers (shop_id, cash_num)
        VALUES (%s, %s)
        ON CONFLICT (shop_id, cash_num) DO NOTHING
        RETURNING cash_reg_id
        """,
        (shop_id, cash_num),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "SELECT cash_reg_id FROM retail.cash_registers WHERE shop_id = %s AND cash_num = %s",
        (shop_id, cash_num),
    )
    return cur.fetchone()[0]


def get_or_create_category(cur, cache: dict, category_name: str) -> int:
    if category_name in cache:
        return cache[category_name]

    cur.execute(
        """
        INSERT INTO retail.categories (category_name)
        VALUES (%s)
        ON CONFLICT (category_name) DO NOTHING
        RETURNING category_id
        """,
        (category_name,),
    )
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT category_id FROM retail.categories WHERE category_name = %s", (category_name,))
        row = cur.fetchone()

    cache[category_name] = row[0]
    return row[0]


def get_or_create_product(cur, cache: dict, product_name: str, category_id: int) -> int:
    key = (product_name, category_id)
    if key in cache:
        return cache[key]

    cur.execute(
        """
        INSERT INTO retail.products (product_name, category_id)
        VALUES (%s, %s)
        ON CONFLICT (product_name, category_id) DO NOTHING
        RETURNING product_id
        """,
        (product_name, category_id),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            "SELECT product_id FROM retail.products WHERE product_name = %s AND category_id = %s",
            (product_name, category_id),
        )
        row = cur.fetchone()

    cache[key] = row[0]
    return row[0]


def load_file(cur, path: Path, shop_num: int, cash_num: int, sale_date: date,
              category_cache: dict, product_cache: dict) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
            raise ValueError(f"файл {path.name} не содержит нужных колонок: {REQUIRED_COLUMNS}")
        rows = list(reader)

    if not rows:
        logger.warning("Файл %s пуст, пропускаем", path.name)
        return 0

    shop_id = get_or_create_shop(cur, shop_num)
    cash_reg_id = get_or_create_cash_register(cur, shop_id, cash_num)

    # группируем строки по doc_id, сохраняя порядок появления в файле
    receipts: dict[str, list[dict]] = {}
    for row in rows:
        receipts.setdefault(row["doc_id"], []).append(row)

    inserted_rows = 0
    for doc_id, items in receipts.items():
        cur.execute(
            """
            INSERT INTO retail.receipts (doc_id, shop_id, cash_reg_id, sale_date)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (shop_id, cash_reg_id, sale_date, doc_id) DO NOTHING
            RETURNING receipt_id
            """,
            (doc_id, shop_id, cash_reg_id, sale_date),
        )
        row = cur.fetchone()
        if not row:
            logger.warning(
                "Чек doc_id=%s уже был загружен ранее (магазин %s, касса %s, дата %s) — пропускаем позиции",
                doc_id, shop_num, cash_num, sale_date,
            )
            continue
        receipt_id = row[0]

        for item in items:
            category_id = get_or_create_category(cur, category_cache, item["category"])
            product_id = get_or_create_product(cur, product_cache, item["item"], category_id)
            cur.execute(
                """
                INSERT INTO retail.receipt_items (receipt_id, product_id, amount, price, discount)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (receipt_id, product_id, item["amount"], item["price"], item["discount"]),
            )
            inserted_rows += 1

    cur.execute(
        """
        INSERT INTO retail.processed_files (file_name, file_hash, shop_id, cash_reg_id, row_count)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (path.name, file_hash(path), shop_id, cash_reg_id, len(rows)),
    )

    return inserted_rows


def discover_files(data_dir: Path) -> list[tuple[Path, int, int]]:
    matched = []
    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        m = FILENAME_RE.match(path.name)
        if not m:
            logger.info("Игнорируем файл, не подходящий под маску {shop}_{cash}.csv: %s", path.name)
            continue
        matched.append((path, int(m.group(1)), int(m.group(2))))
    return matched


def main():
    parser = argparse.ArgumentParser(description="Загрузка выгрузок касс из data/ в PostgreSQL")
    parser.add_argument("--date", type=str, default=None, help="Дата продажи в формате YYYY-MM-DD (по умолчанию — сегодня)")
    args = parser.parse_args()
    sale_date = date.fromisoformat(args.date) if args.date else date.today()

    files = discover_files(DATA_DIR)
    if not files:
        logger.info("В папке %s нет файлов, подходящих под маску {shop}_{cash}.csv", DATA_DIR)
        return

    conn = get_connection()
    conn.autocommit = False
    category_cache: dict = {}
    product_cache: dict = {}

    loaded_files = 0
    skipped_files = 0
    total_rows = 0

    try:
        for path, shop_num, cash_num in files:
            h = file_hash(path)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM retail.processed_files WHERE file_name = %s AND file_hash = %s",
                    (path.name, h),
                )
                already_loaded = cur.fetchone() is not None

            if already_loaded:
                logger.info("Файл %s уже был загружен ранее (содержимое не изменилось) — пропускаем", path.name)
                skipped_files += 1
                continue

            try:
                with conn.cursor() as cur:
                    rows = load_file(cur, path, shop_num, cash_num, sale_date, category_cache, product_cache)
                conn.commit()
                loaded_files += 1
                total_rows += rows
                logger.info("Загружен файл %s: %s строк чеков", path.name, rows)
            except Exception:
                conn.rollback()
                logger.exception("Ошибка при загрузке файла %s, откат транзакции", path.name)
    finally:
        conn.close()

    logger.info(
        "Готово: загружено файлов %s, пропущено (уже загружены) %s, всего строк %s",
        loaded_files, skipped_files, total_rows,
    )


if __name__ == "__main__":
    main()
