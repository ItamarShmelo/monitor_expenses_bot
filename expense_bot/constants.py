"""Constants for the expense bot.

This module defines expense categories and help text used throughout the bot.
"""

# Single source of truth for category labels, stored keys, and help text.
_CATEGORY_DEFINITIONS: list[tuple[str, str, str]] = [
    (
        "Home",
        "home",
        "Rent, Utilities (electricity, water, gas), Internet, Maintenance, Repairs",
    ),
    (
        "Transportation",
        "transport",
        "Car payments, Gas, Public Transport, Parking, Car wash, Repairs",
    ),
    (
        "Groceries",
        "groceries",
        "Supermarket, Food supplies, Farmers market, Household items",
    ),
    (
        "Dining Out",
        "dining",
        "Restaurants, Takeout, Delivery, Fast food, sit-down meals",
    ),
    (
        "Coffee",
        "coffee",
        "Coffee shops, cafe drinks, beans, pods, tea, quick cafe snacks",
    ),
    (
        "Shopping",
        "shopping",
        "Clothes, electronics, home goods, online orders, personal items",
    ),
    (
        "Other",
        "other",
        "Everything that doesn't fit above - Gifts, Entertainment, subscriptions, etc.",
    ),
]
_HELP_CHOICE: tuple[str, str] = ("Help", "help")

# Category choices for ReplyKeyboardChoiceDialog: (display_label, callback_data)
CATEGORIES_NO_HELP: list[tuple[str, str]] = [
    (label, key) for label, key, _ in _CATEGORY_DEFINITIONS
]
CATEGORIES: list[tuple[str, str]] = [*CATEGORIES_NO_HELP, _HELP_CHOICE]

# Mapping from callback_data to display name
CATEGORY_NAMES: dict[str, str] = {
    key: label for label, key, _ in _CATEGORY_DEFINITIONS
}

# Help text explaining each category (HTML formatted for Telegram)
CATEGORY_HELP: str = "<b>Expense Categories</b>\n\n" + "\n\n".join(
    f"<b>{label}</b>: {description}"
    for label, _, description in _CATEGORY_DEFINITIONS
)

# Valid category keys (for validation)
VALID_CATEGORIES: set[str] = {key for _, key, _ in _CATEGORY_DEFINITIONS}
