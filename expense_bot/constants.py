"""Constants for the expense bot.

This module defines expense categories and help text used throughout the bot.
"""

# Category choices for ChoiceDialog: (display_label, callback_data)
CATEGORIES: list[tuple[str, str]] = [
    ("Home", "home"),
    ("Transportation", "transport"),
    ("Groceries", "groceries"),
    ("Dining Out", "dining"),
    ("Other", "other"),
    ("Help", "help"),  # Special button that shows help text
]

# Category choices without the Help option (for internal use)
CATEGORIES_NO_HELP: list[tuple[str, str]] = [
    ("Home", "home"),
    ("Transportation", "transport"),
    ("Groceries", "groceries"),
    ("Dining Out", "dining"),
    ("Other", "other"),
]

# Mapping from callback_data to display name
CATEGORY_NAMES: dict[str, str] = {
    "home": "Home",
    "transport": "Transportation",
    "groceries": "Groceries",
    "dining": "Dining Out",
    "other": "Other",
}

# Help text explaining each category (HTML formatted for Telegram)
CATEGORY_HELP: str = """<b>Expense Categories</b>

<b>Home</b>: Rent, Utilities (electricity, water, gas), Internet, Maintenance, Repairs

<b>Transportation</b>: Car payments, Gas, Public Transport, Parking, Car wash, Repairs

<b>Groceries</b>: Supermarket, Food supplies, Farmers market, Household items

<b>Dining Out</b>: Restaurants, Cafes, Takeout, Delivery, Fast food

<b>Other</b>: Everything that doesn't fit above - Gifts, Entertainment, Shopping, etc."""

# Valid category keys (for validation)
VALID_CATEGORIES: set[str] = {"home", "transport", "groceries", "dining", "other"}
