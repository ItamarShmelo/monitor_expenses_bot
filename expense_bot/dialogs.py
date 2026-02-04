"""Dialog flows for the expense bot.

This module defines all interactive dialog flows for expense management:
- Add expense flow
- Remove expense flow
- Modify expense flow
- Export CSV flow
- Chart generation flow
"""

from datetime import datetime
from typing import Any, Optional

from my_bot_framework import (
    ChoiceDialog,
    ChoiceBranchDialog,
    ConfirmDialog,
    Dialog,
    DialogHandler,
    DialogResult,
    PaginatedChoiceDialog,
    SequenceDialog,
    UserInputDialog,
    get_app,
    is_cancelled,
    validate_date_format,
    validate_positive_float,
    format_numbered_list,
    TelegramDocumentMessage,
    TelegramImageMessage,
)

from .constants import CATEGORIES, CATEGORY_HELP, CATEGORY_NAMES, VALID_CATEGORIES
from .expense_manager import Expense, ExpenseManager


# Global expense manager instance (set in main.py)
_expense_manager: Optional[ExpenseManager] = None


def set_expense_manager(manager: ExpenseManager) -> None:
    """Set the global expense manager instance.

    Args:
        manager: The ExpenseManager to use for all operations.
    """
    global _expense_manager
    _expense_manager = manager


def get_expense_manager() -> ExpenseManager:
    """Get the global expense manager instance.

    Returns:
        The ExpenseManager instance.

    Raises:
        RuntimeError: If set_expense_manager() hasn't been called.
    """
    if _expense_manager is None:
        raise RuntimeError("ExpenseManager not set. Call set_expense_manager() first.")
    return _expense_manager


# =============================================================================
# ADD EXPENSE FLOW
# =============================================================================


def _is_valid_category(result: Any) -> bool:
    """Check if result is a valid category (not 'help' or cancelled)."""
    if is_cancelled(result):
        return True  # Exit loop on cancel
    return result in VALID_CATEGORIES


async def _on_add_complete(result: DialogResult) -> None:
    """Handle completion of add expense dialog."""
    if is_cancelled(result):
        await get_app().send_messages("Expense entry cancelled.")
        return

    if not isinstance(result, dict):
        await get_app().send_messages("Unexpected error. Please try again.")
        return

    category_raw = result.get("category")
    description = result.get("description", "")
    price_str = result.get("price", "0")

    # The category might be nested from LoopDialog
    category: str | None = None
    if isinstance(category_raw, dict):
        # Extract from loop result
        for v in category_raw.values():
            if isinstance(v, str) and v in VALID_CATEGORIES:
                category = v
                break
    elif isinstance(category_raw, str):
        category = category_raw

    if not category or category not in VALID_CATEGORIES:
        await get_app().send_messages("Invalid category. Please try again.")
        return

    try:
        price = float(price_str)
    except (ValueError, TypeError):
        await get_app().send_messages("Invalid price. Please try again.")
        return

    manager = get_expense_manager()
    expense = manager.add_expense(
        category=category,
        description=description.strip(),
        price=price,
    )

    category_name = CATEGORY_NAMES.get(category, category)
    await get_app().send_messages(
        f"Expense added:\n"
        f"Category: {category_name}\n"
        f"Description: {expense.description}\n"
        f"Price: ${expense.price:.2f}\n"
        f"Date: {expense.timestamp.strftime('%Y-%m-%d %H:%M')}"
    )


class CategoryChoiceWithHelp(Dialog):
    """Custom dialog for category selection with Help button support.

    When Help is selected, shows help text and re-displays the choices.
    """

    def __init__(self) -> None:
        """Initialize the category choice dialog."""
        super().__init__()
        self._choice_dialog: Optional[ChoiceDialog] = None

    async def _run_dialog(self) -> DialogResult:
        """Run the category selection with help loop."""
        while True:
            self._choice_dialog = ChoiceDialog(
                prompt="Select expense category:",
                choices=CATEGORIES,
                include_cancel=True,
            )
            result = await self._choice_dialog.start(self.context)

            if is_cancelled(result):
                self._value = result
                return result

            if result == "help":
                # Show help and loop again
                await get_app().send_messages(CATEGORY_HELP)
                continue

            if result in VALID_CATEGORIES:
                self._value = result
                return result

    def build_result(self) -> DialogResult:
        """Return the selected category."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Delegate to inner dialog."""
        if self._choice_dialog:
            self._choice_dialog.handle_callback(callback_data)

    def handle_text_input(self, text: str) -> None:
        """Delegate to inner dialog."""
        if self._choice_dialog:
            self._choice_dialog.handle_text_input(text)


def create_add_expense_dialog() -> Dialog:
    """Create the add expense dialog flow.

    Flow: Category (with Help) -> Description -> Price -> Save

    Returns:
        Dialog for adding expenses.
    """
    return DialogHandler(
        SequenceDialog([
            ("category", CategoryChoiceWithHelp()),
            ("description", UserInputDialog("Enter a brief description:")),
            ("price", UserInputDialog(
                "Enter the price:",
                validator=validate_positive_float,
            )),
        ]),
        on_complete=_on_add_complete,
    )


# =============================================================================
# REMOVE EXPENSE FLOW
# =============================================================================


def _get_expense_choices(
    year: int,
    month: int,
) -> list[tuple[str, str]]:
    """Get expense choices for PaginatedChoiceDialog.

    Args:
        year: The year to get expenses from.
        month: The month to get expenses from.

    Returns:
        List of (label, callback_data) tuples.
    """
    manager = get_expense_manager()
    expenses = manager.get_expenses(year, month)

    choices = []
    for expense in reversed(expenses):  # Most recent first
        category_name = CATEGORY_NAMES.get(expense.category, expense.category)
        label = (
            f"[{category_name}] {expense.description} - "
            f"${expense.price:.2f} ({expense.timestamp.strftime('%m/%d')})"
        )
        # Store year, month, and id in callback data
        callback = f"{expense.year}:{expense.month}:{expense.id}"
        choices.append((label, callback))

    return choices


def _parse_expense_callback(callback: str) -> tuple[int, int, int]:
    """Parse expense callback data into year, month, id.

    Args:
        callback: Callback data in format "year:month:id".

    Returns:
        Tuple of (year, month, expense_id).
    """
    parts = callback.split(":")
    return int(parts[0]), int(parts[1]), int(parts[2])


async def _on_remove_complete(result: DialogResult) -> None:
    """Handle completion of remove expense dialog."""
    if is_cancelled(result):
        await get_app().send_messages("Remove cancelled.")
        return

    if not isinstance(result, dict):
        await get_app().send_messages("Unexpected error. Please try again.")
        return

    # Get the expense selection from the result
    expense_selection = result.get("expense")
    if isinstance(expense_selection, dict):
        # Navigate through nested dict to find the actual value
        for v in expense_selection.values():
            if isinstance(v, str) and ":" in v:
                expense_selection = v
                break

    if not isinstance(expense_selection, str) or ":" not in expense_selection:
        await get_app().send_messages("No expense selected.")
        return

    year, month, expense_id = _parse_expense_callback(expense_selection)
    manager = get_expense_manager()

    if manager.remove_expense(expense_id, year, month):
        await get_app().send_messages(f"Expense #{expense_id} removed.")
    else:
        await get_app().send_messages("Expense not found.")


def _create_expense_selection_dialog(year: int, month: int) -> Dialog:
    """Create a dialog for selecting an expense from a specific month.

    Args:
        year: The year.
        month: The month.

    Returns:
        PaginatedChoiceDialog for expense selection.
    """
    choices = _get_expense_choices(year, month)
    if not choices:
        # Return a simple dialog indicating no expenses
        return UserInputDialog(
            f"No expenses found for {month:02d}/{year}. Press Cancel to go back.",
            include_cancel=True,
        )

    return PaginatedChoiceDialog(
        prompt=f"Select expense from {month:02d}/{year}:",
        items=choices,
        page_size=5,
        include_cancel=True,
    )


class RemoveExpenseDialog(Dialog):
    """Dialog for removing an expense.

    Allows selecting from current month or a different month.
    """

    def __init__(self) -> None:
        """Initialize the remove expense dialog."""
        super().__init__()

    async def _run_dialog(self) -> DialogResult:
        """Run the remove expense flow."""
        now = datetime.now()

        # First, ask which month
        month_choice = ChoiceBranchDialog(
            prompt="Select expenses from:",
            branches={
                "current": ("Current Month", ConfirmDialog("Continue?", include_cancel=True)),
                "different": ("Different Month", UserInputDialog(
                    "Enter month (MM/YYYY):",
                    validator=validate_date_format("%m/%Y", "MM/YYYY"),
                    include_cancel=True,
                )),
            },
            include_cancel=True,
        )

        month_result = await month_choice.start(self.context)

        if is_cancelled(month_result):
            self._value = month_result
            return month_result

        # Determine year and month
        if isinstance(month_result, dict):
            if "current" in month_result:
                year, month = now.year, now.month
            elif "different" in month_result:
                date_str = month_result["different"]
                if is_cancelled(date_str):
                    self._value = date_str
                    return date_str
                try:
                    parsed = datetime.strptime(date_str, "%m/%Y")
                    year, month = parsed.year, parsed.month
                except (ValueError, TypeError):
                    await get_app().send_messages("Invalid date format.")
                    self._value = None
                    return None
            else:
                year, month = now.year, now.month
        else:
            year, month = now.year, now.month

        # Show expense selection
        expense_dialog = _create_expense_selection_dialog(year, month)
        expense_result = await expense_dialog.start(self.context)

        if is_cancelled(expense_result):
            self._value = expense_result
            return expense_result

        self._value = {"expense": expense_result}
        return self._value

    def build_result(self) -> DialogResult:
        """Return the dialog result."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Not used - delegates to child dialogs."""
        pass

    def handle_text_input(self, text: str) -> None:
        """Not used - delegates to child dialogs."""
        pass


def create_remove_expense_dialog() -> Dialog:
    """Create the remove expense dialog flow.

    Returns:
        Dialog for removing expenses.
    """
    return DialogHandler(
        RemoveExpenseDialog(),
        on_complete=_on_remove_complete,
    )


# =============================================================================
# MODIFY EXPENSE FLOW
# =============================================================================


async def _on_modify_complete(result: DialogResult) -> None:
    """Handle completion of modify expense dialog."""
    if is_cancelled(result):
        await get_app().send_messages("Modify cancelled.")
        return

    if not isinstance(result, dict):
        await get_app().send_messages("Unexpected error. Please try again.")
        return

    # Get the original expense selection
    expense_selection = result.get("original_expense")
    if not isinstance(expense_selection, str) or ":" not in expense_selection:
        await get_app().send_messages("No expense selected.")
        return

    year, month, expense_id = _parse_expense_callback(expense_selection)

    # Get new values
    category = result.get("category")
    description = result.get("description", "")
    price_str = result.get("price", "0")

    if category not in VALID_CATEGORIES:
        await get_app().send_messages("Invalid category. Please try again.")
        return

    try:
        price = float(price_str)
    except (ValueError, TypeError):
        await get_app().send_messages("Invalid price. Please try again.")
        return

    manager = get_expense_manager()
    modified = manager.modify_expense(
        expense_id=expense_id,
        year=year,
        month=month,
        category=category,
        description=description.strip(),
        price=price,
    )

    if modified:
        category_name = CATEGORY_NAMES.get(category, category)
        await get_app().send_messages(
            f"Expense modified:\n"
            f"Category: {category_name}\n"
            f"Description: {modified.description}\n"
            f"Price: ${modified.price:.2f}"
        )
    else:
        await get_app().send_messages("Expense not found.")


class ModifyExpenseDialog(Dialog):
    """Dialog for modifying an expense.

    First selects an expense, then collects new values.
    """

    def __init__(self) -> None:
        """Initialize the modify expense dialog."""
        super().__init__()

    async def _run_dialog(self) -> DialogResult:
        """Run the modify expense flow."""
        now = datetime.now()

        # First, ask which month
        month_choice = ChoiceBranchDialog(
            prompt="Select expenses from:",
            branches={
                "current": ("Current Month", ConfirmDialog("Continue?", include_cancel=True)),
                "different": ("Different Month", UserInputDialog(
                    "Enter month (MM/YYYY):",
                    validator=validate_date_format("%m/%Y", "MM/YYYY"),
                    include_cancel=True,
                )),
            },
            include_cancel=True,
        )

        month_result = await month_choice.start(self.context)

        if is_cancelled(month_result):
            self._value = month_result
            return month_result

        # Determine year and month
        if isinstance(month_result, dict):
            if "current" in month_result:
                year, month = now.year, now.month
            elif "different" in month_result:
                date_str = month_result["different"]
                if is_cancelled(date_str):
                    self._value = date_str
                    return date_str
                try:
                    parsed = datetime.strptime(date_str, "%m/%Y")
                    year, month = parsed.year, parsed.month
                except (ValueError, TypeError):
                    await get_app().send_messages("Invalid date format.")
                    self._value = None
                    return None
            else:
                year, month = now.year, now.month
        else:
            year, month = now.year, now.month

        # Show expense selection
        expense_dialog = _create_expense_selection_dialog(year, month)
        expense_result = await expense_dialog.start(self.context)

        if is_cancelled(expense_result):
            self._value = expense_result
            return expense_result

        # Now collect new values
        await get_app().send_messages("Now enter the new values for this expense:")

        # Category selection
        category_dialog = CategoryChoiceWithHelp()
        category_result = await category_dialog.start(self.context)

        if is_cancelled(category_result):
            self._value = category_result
            return category_result

        # Description
        desc_dialog = UserInputDialog("Enter new description:")
        desc_result = await desc_dialog.start(self.context)

        if is_cancelled(desc_result):
            self._value = desc_result
            return desc_result

        # Price
        price_dialog = UserInputDialog(
            "Enter new price:",
            validator=validate_positive_float,
        )
        price_result = await price_dialog.start(self.context)

        if is_cancelled(price_result):
            self._value = price_result
            return price_result

        self._value = {
            "original_expense": expense_result,
            "category": category_result,
            "description": desc_result,
            "price": price_result,
        }
        return self._value

    def build_result(self) -> DialogResult:
        """Return the dialog result."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Not used - delegates to child dialogs."""
        pass

    def handle_text_input(self, text: str) -> None:
        """Not used - delegates to child dialogs."""
        pass


def create_modify_expense_dialog() -> Dialog:
    """Create the modify expense dialog flow.

    Returns:
        Dialog for modifying expenses.
    """
    return DialogHandler(
        ModifyExpenseDialog(),
        on_complete=_on_modify_complete,
    )


# =============================================================================
# EXPORT CSV FLOW
# =============================================================================


async def _on_export_complete(result: DialogResult) -> None:
    """Handle completion of export dialog."""
    if is_cancelled(result):
        await get_app().send_messages("Export cancelled.")
        return

    if not isinstance(result, dict):
        await get_app().send_messages("Unexpected error. Please try again.")
        return

    now = datetime.now()

    # Determine year and month from result
    if "previous" in result:
        # Previous month
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
    elif "custom" in result:
        date_str = result["custom"]
        if is_cancelled(date_str):
            await get_app().send_messages("Export cancelled.")
            return
        try:
            parsed = datetime.strptime(date_str, "%m/%Y")
            year, month = parsed.year, parsed.month
        except (ValueError, TypeError):
            await get_app().send_messages("Invalid date format.")
            return
    else:
        await get_app().send_messages("Unexpected error.")
        return

    manager = get_expense_manager()
    csv_path = manager.get_csv_path(year, month)

    if not csv_path.exists():
        await get_app().send_messages(f"No data found for {month:02d}/{year}.")
        return

    await get_app().send_messages(
        TelegramDocumentMessage(
            csv_path,
            caption=f"Expenses for {month:02d}/{year}",
        )
    )


def create_export_dialog() -> Dialog:
    """Create the export CSV dialog flow.

    Returns:
        Dialog for exporting CSV files.
    """
    return DialogHandler(
        ChoiceBranchDialog(
            prompt="Export expenses for which month?",
            branches={
                "previous": ("Previous Month", ConfirmDialog("Export?", include_cancel=True)),
                "custom": ("Provide Month", UserInputDialog(
                    "Enter month (MM/YYYY):",
                    validator=validate_date_format("%m/%Y", "MM/YYYY"),
                    include_cancel=True,
                )),
            },
            include_cancel=True,
        ),
        on_complete=_on_export_complete,
    )


# =============================================================================
# CHART FLOW
# =============================================================================


async def _on_chart_complete(result: DialogResult) -> None:
    """Handle completion of chart dialog."""
    if is_cancelled(result):
        await get_app().send_messages("Chart cancelled.")
        return

    if not isinstance(result, dict):
        await get_app().send_messages("Unexpected error. Please try again.")
        return

    now = datetime.now()

    # Determine year and month from result
    if "previous" in result:
        # Previous month
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
    elif "custom" in result:
        date_str = result["custom"]
        if is_cancelled(date_str):
            await get_app().send_messages("Chart cancelled.")
            return
        try:
            parsed = datetime.strptime(date_str, "%m/%Y")
            year, month = parsed.year, parsed.month
        except (ValueError, TypeError):
            await get_app().send_messages("Invalid date format.")
            return
    else:
        await get_app().send_messages("Unexpected error.")
        return

    # Import charts module here to avoid circular imports
    from .charts import generate_expense_chart

    manager = get_expense_manager()
    expenses_by_category = manager.get_expenses_by_category(year, month)

    if not expenses_by_category:
        await get_app().send_messages(f"No expenses found for {month:02d}/{year}.")
        return

    chart_path = generate_expense_chart(expenses_by_category, year, month)

    await get_app().send_messages(
        TelegramImageMessage(
            chart_path,
            caption=f"Expense breakdown for {month:02d}/{year}",
        )
    )


def create_chart_dialog() -> Dialog:
    """Create the chart generation dialog flow.

    Returns:
        Dialog for generating expense charts.
    """
    return DialogHandler(
        ChoiceBranchDialog(
            prompt="Generate chart for which month?",
            branches={
                "previous": ("Previous Month", ConfirmDialog("Generate?", include_cancel=True)),
                "custom": ("Provide Month", UserInputDialog(
                    "Enter month (MM/YYYY):",
                    validator=validate_date_format("%m/%Y", "MM/YYYY"),
                    include_cancel=True,
                )),
            },
            include_cancel=True,
        ),
        on_complete=_on_chart_complete,
    )


# =============================================================================
# RECENT EXPENSES (Simple command, not a dialog)
# =============================================================================


async def get_recent_expenses_message() -> str:
    """Get a formatted message of recent expenses.

    Returns:
        Formatted string with recent expenses.
    """
    manager = get_expense_manager()
    expenses = manager.get_recent(count=10)

    if not expenses:
        return "No expenses found."

    lines = []
    for expense in expenses:
        category_name = CATEGORY_NAMES.get(expense.category, expense.category)
        line = (
            f"[{category_name}] {expense.description} - "
            f"${expense.price:.2f} ({expense.timestamp.strftime('%m/%d/%Y')})"
        )
        lines.append(line)

    header = "<b>Recent Expenses</b>\n\n"
    return header + format_numbered_list(lines)
