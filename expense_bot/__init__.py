"""Expense monitoring bot package.

This package provides a Telegram bot for tracking group expenses with CSV storage,
interactive dialogs for CRUD operations, and pie chart visualization.
"""

from .expense_manager import Expense, ExpenseManager
from .constants import (
    CATEGORIES,
    CATEGORIES_NO_HELP,
    CATEGORY_HELP,
    CATEGORY_NAMES,
    VALID_CATEGORIES,
)

__all__ = [
    "Expense",
    "ExpenseManager",
    "CATEGORIES",
    "CATEGORIES_NO_HELP",
    "CATEGORY_HELP",
    "CATEGORY_NAMES",
    "VALID_CATEGORIES",
]
