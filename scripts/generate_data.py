#!/usr/bin/env python
"""Генератор ежедневных CSV-выгрузок кассового ПО.

Эмулирует выгрузку чеков из касс сети магазинов товаров для дома:
для каждой кассы каждого магазина создаётся файл {shop_num}_{cash_num}.csv
в папке data/ со столбцами doc_id, item, category, amount, price, discount.

Запуск планируется через Windows Task Scheduler каждый день, кроме воскресенья
(см. scripts/register_scheduled_tasks.ps1).
"""

import argparse
import csv
import logging
import random
import string
from datetime import date
from pathlib import Path

from catalog import CATALOG
from settings import DATA_DIR, GENERATION, LOG_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "generate_data.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("generate_data")

ALL_PRODUCTS = [
    (name, price, category)
    for category, items in CATALOG.items()
    for name, price in items
]

FIELDNAMES = ["doc_id", "item", "category", "amount", "price", "discount"]


def make_doc_id(rng: random.Random) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(rng.choices(alphabet, k=10))


def generate_receipt_rows(rng: random.Random, gen_cfg: dict) -> list[dict]:
    n_items = rng.randint(*gen_cfg["items_per_receipt"])
    doc_id = make_doc_id(rng)
    products = rng.sample(ALL_PRODUCTS, k=min(n_items, len(ALL_PRODUCTS)))

    rows = []
    for name, base_price, category in products:
        amount = rng.randint(1, 5)
        jitter_pct = gen_cfg["price_jitter_pct"]
        price = round(base_price * (1 + rng.uniform(-jitter_pct, jitter_pct)), 2)

        discount = 0.0
        if rng.random() < gen_cfg["discount_probability"]:
            pct = rng.uniform(0, gen_cfg["discount_max_pct"])
            discount = round(amount * price * pct, 2)

        rows.append(
            {
                "doc_id": doc_id,
                "item": name,
                "category": category,
                "amount": amount,
                "price": price,
                "discount": discount,
            }
        )
    return rows


def generate_cash_register_file(shop_num: int, cash_num: int, gen_cfg: dict, rng: random.Random) -> tuple[Path, int]:
    n_receipts = rng.randint(*gen_cfg["receipts_per_cash_per_day"])
    file_path = DATA_DIR / f"{shop_num}_{cash_num}.csv"

    rows_written = 0
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for _ in range(n_receipts):
            for row in generate_receipt_rows(rng, gen_cfg):
                writer.writerow(row)
                rows_written += 1

    return file_path, rows_written


def main():
    parser = argparse.ArgumentParser(description="Генерация ежедневных выгрузок касс в data/")
    parser.add_argument("--shops", type=int, default=None, help="Количество магазинов (по умолчанию — из config.yaml)")
    parser.add_argument("--seed", type=int, default=None, help="Seed для воспроизводимой генерации")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    gen_cfg = GENERATION
    n_shops = args.shops or gen_cfg["shops"]

    logger.info("Запуск генерации выгрузок: %s магазинов, дата %s", n_shops, date.today().isoformat())

    total_files = 0
    total_rows = 0
    for shop_num in range(1, n_shops + 1):
        n_cash = rng.randint(*gen_cfg["cash_registers_per_shop"])
        for cash_num in range(1, n_cash + 1):
            file_path, n_rows = generate_cash_register_file(shop_num, cash_num, gen_cfg, rng)
            total_files += 1
            total_rows += n_rows
            logger.info("Сгенерирован файл %s (%s строк)", file_path.name, n_rows)

    logger.info("Готово: %s файлов, %s строк в %s", total_files, total_rows, DATA_DIR)


if __name__ == "__main__":
    main()
