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
    TelegramReplyKeyboardMessage,
)

from .constants import (
    CATEGORIES,
    CATEGORIES_NO_HELP,
    CATEGORY_HELP,
    CATEGORY_NAMES,
    VALID_CATEGORIES,
)
from .expense_manager import Expense, ExpenseManager
from .charts import generate_expense_chart


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
# KEYBOARD HELPERS
# =============================================================================


def get_main_keyboard_message(
    text: str = "What would you like to do?",
) -> TelegramReplyKeyboardMessage:
    """Return main keyboard message with Add and More buttons.

    Args:
        text: The message text to display with the keyboard.

    Returns:
        TelegramReplyKeyboardMessage with main menu options.
    """
    return TelegramReplyKeyboardMessage(
        text=text,
        keyboard=[["Add", "More"]],
    )


def get_more_keyboard_message() -> TelegramReplyKeyboardMessage:
    """Return More menu keyboard message with secondary options.

    Returns:
        TelegramReplyKeyboardMessage with secondary menu options.
    """
    return TelegramReplyKeyboardMessage(
        text="More options:",
        keyboard=[
            ["Remove", "Modify"],
            ["Recent", "Export"],
            ["Chart", "Info"],
            ["Back"],
        ],
    )


def get_info_text() -> str:
    """Return the bot info/help text.

    Returns:
        HTML-formatted info text.
    """
    return (
        "<b>Expense Monitoring Bot</b>\n\n"
        "Track your group expenses with ease!\n\n"
        "<b>Options:</b>\n"
        "Add - Add a new expense\n"
        "More - Show more options\n\n"
        "<b>More Options:</b>\n"
        "Remove - Remove an expense\n"
        "Modify - Modify an existing expense\n"
        "Recent - Show recent expenses\n"
        "Export - Export expenses as CSV\n"
        "Chart - Generate expense pie chart\n"
        "Info - Show this help\n"
        "Back - Return to main menu"
    )


# =============================================================================
# ADD EXPENSE FLOW
# =============================================================================


def _is_valid_category(result: Any) -> bool:
    """Check if result is a valid category (not 'help' or cancelled).
    
    Args:
        result: The result to validate.
        
    Returns:
        True if valid category or cancelled, False otherwise.
    """
    if is_cancelled(result):
        return True  # Exit loop on cancel
    return result in VALID_CATEGORIES


async def _on_add_complete(result: DialogResult) -> None:
    """Handle completion of add expense dialog.
    
    Args:
        result: The dialog result containing expense data.
    """
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
        f"Price: ₪{expense.price:.2f}\n"
        f"Date: {expense.timestamp.strftime('%d/%m/%Y %H:%M')}"
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
            f"₪{expense.price:.2f} ({expense.timestamp.strftime('%d/%m')})"
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
    """Handle completion of remove expense dialog.
    
    Args:
        result: The dialog result containing expense selection.
    """
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

    Flow: Month selection -> Expense selection -> Confirmation -> Removal.
    Allows selecting expenses from the current month or a different month.
    After selecting an expense, prompts for confirmation before removal.
    """

    def __init__(self) -> None:
        """Initialize the remove expense dialog."""
        super().__init__()

    async def _run_dialog(self) -> DialogResult:
        """Run the remove expense flow.

        Prompts user to select a month, then an expense from that month,
        then confirms the removal action.

        Returns:
            Dict with "expense" key containing the selected expense callback data,
            or cancellation result if user cancels at any step.
        """
        now = datetime.now()

        # First, ask which month
        month_choice = ChoiceDialog(
            prompt="Select expenses from:",
            choices=[
                ("Current Month", "current"),
                ("Different Month", "different"),
            ],
            include_cancel=True,
        )

        month_result = await month_choice.start(self.context)

        if is_cancelled(month_result):
            self._value = month_result
            return month_result

        # Determine year and month
        if month_result == "current":
            year, month = now.year, now.month
        elif month_result == "different":
            date_dialog = UserInputDialog(
                "Enter month (MM/YYYY):",
                validator=validate_date_format("%m/%Y", "MM/YYYY"),
                include_cancel=True,
            )
            date_result = await date_dialog.start(self.context)
            if is_cancelled(date_result):
                self._value = date_result
                return date_result
            if not isinstance(date_result, str):
                await get_app().send_messages("Invalid date format.")
                self._value = None
                return None
            try:
                parsed = datetime.strptime(date_result, "%m/%Y")
                year, month = parsed.year, parsed.month
            except (ValueError, TypeError):
                await get_app().send_messages("Invalid date format.")
                self._value = None
                return None
        else:
            year, month = now.year, now.month

        # Loop for expense selection and confirmation
        # If user clicks "No" on confirmation, return to expense selection
        while True:
            # Show expense selection
            expense_dialog = _create_expense_selection_dialog(year, month)
            expense_result = await expense_dialog.start(self.context)

            if is_cancelled(expense_result):
                self._value = expense_result
                return expense_result

            # Confirm deletion after expense is selected
            confirm_dialog = ConfirmDialog("Remove this expense?", include_cancel=True)
            confirm_result = await confirm_dialog.start(self.context)

            if is_cancelled(confirm_result):
                self._value = confirm_result
                return confirm_result

            # If user confirmed, proceed with removal
            if confirm_result is True:
                self._value = {"expense": expense_result}
                return self._value

            # If user declined (False), loop back to expense selection

    def build_result(self) -> DialogResult:
        """Return the dialog result."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Handle callback - child dialogs handle their own callbacks."""
        pass

    def handle_text_input(self, text: str) -> None:
        """Handle text input - child dialogs handle their own text input."""
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
    """Handle completion of modify expense dialog.
    
    Args:
        result: The dialog result containing modified expense data.
    """
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
            f"Price: ₪{modified.price:.2f}"
        )
    else:
        await get_app().send_messages("Expense not found.")


def _get_expense_by_id(
    year: int,
    month: int,
    expense_id: int,
) -> Optional[Expense]:
    """Get a specific expense by ID from a given year and month.

    Args:
        year: The year to search in.
        month: The month to search in.
        expense_id: The unique ID of the expense to find.

    Returns:
        The Expense object if found, None otherwise.
    """
    manager = get_expense_manager()
    expenses = manager.get_expenses(year, month)
    for expense in expenses:
        if expense.id == expense_id:
            return expense
    return None


class ModifyExpenseDialog(Dialog):
    """Dialog for modifying an expense.

    Flow: Month selection -> Expense selection -> Edit values -> Confirmation.
    Shows current values as defaults with option to keep them.
    Clicking "No" on confirmation returns to the start of the dialog.
    """

    def __init__(self) -> None:
        """Initialize the modify expense dialog."""
        super().__init__()

    async def _run_dialog(self) -> DialogResult:
        """Run the modify expense flow.

        Returns:
            Dict with expense data and new values,
            or cancellation result if user cancels.
        """
        # Main loop - "No" on confirmation returns here
        while True:
            result = await self._collect_modification()
            if result is None:
                # User declined confirmation, restart
                continue
            # Either cancelled or confirmed
            self._value = result
            return result

    async def _collect_modification(self) -> DialogResult:
        """Collect expense selection and new values.

        Returns:
            Dict with modification data if confirmed,
            None if user clicked "No" on confirmation,
            or cancellation result if cancelled.
        """
        now = datetime.now()

        # First, ask which month
        month_choice = ChoiceDialog(
            prompt="Select expenses from:",
            choices=[
                ("Current Month", "current"),
                ("Different Month", "different"),
            ],
            include_cancel=True,
        )

        month_result = await month_choice.start(self.context)

        if is_cancelled(month_result):
            return month_result

        # Determine year and month
        if month_result == "current":
            year, month = now.year, now.month
        elif month_result == "different":
            date_dialog = UserInputDialog(
                "Enter month (MM/YYYY):",
                validator=validate_date_format("%m/%Y", "MM/YYYY"),
                include_cancel=True,
            )
            date_result = await date_dialog.start(self.context)
            if is_cancelled(date_result):
                return date_result
            if not isinstance(date_result, str):
                await get_app().send_messages("Invalid date format.")
                return None
            try:
                parsed = datetime.strptime(date_result, "%m/%Y")
                year, month = parsed.year, parsed.month
            except (ValueError, TypeError):
                await get_app().send_messages("Invalid date format.")
                return None
        else:
            year, month = now.year, now.month

        # Show expense selection
        expense_dialog = _create_expense_selection_dialog(year, month)
        expense_result = await expense_dialog.start(self.context)

        if is_cancelled(expense_result):
            return expense_result

        # Get the original expense to show current values
        if not isinstance(expense_result, str) or ":" not in expense_result:
            await get_app().send_messages("Invalid expense selection.")
            return None

        exp_year, exp_month, expense_id = _parse_expense_callback(expense_result)
        original_expense = _get_expense_by_id(exp_year, exp_month, expense_id)

        if original_expense is None:
            await get_app().send_messages("Expense not found.")
            return None

        # Get old values for display
        old_category = original_expense.category
        old_category_name = CATEGORY_NAMES.get(old_category, old_category)
        old_description = original_expense.description
        old_price = original_expense.price
        old_date: str = original_expense.timestamp.strftime("%d/%m")

        # Collect new values with current values as defaults
        expense_summary: str = (
            f"[{old_category_name}] {old_description} - "
            f"₪{old_price:.2f} ({old_date})"
        )
        await get_app().send_messages(
            f"Modifying expense: {expense_summary}\n\n"
            f"Current values:\n"
            f"Category: {old_category_name}\n"
            f"Description: {old_description}\n"
            f"Price: ₪{old_price:.2f}\n\n"
            f"Select new values or keep current:"
        )

        # Category selection with "Keep Current" option
        # Order: categories, Keep Current, Help (Cancel added by dialog)
        category_choices = CATEGORIES_NO_HELP + [("Keep Current", "keep"), ("Help", "help")]
        category_dialog = ChoiceDialog(
            prompt=f"Category (current: {old_category_name}):",
            choices=category_choices,
            include_cancel=True,
        )
        category_result = await category_dialog.start(self.context)

        if is_cancelled(category_result):
            return category_result

        # Handle "help" selection for category
        while category_result == "help":
            await get_app().send_messages(CATEGORY_HELP)
            category_result = await category_dialog.start(self.context)
            if is_cancelled(category_result):
                return category_result

        new_category = old_category if category_result == "keep" else category_result

        # Description with "Keep Current" option at the end
        desc_choice = ChoiceDialog(
            prompt=f"Description (current: {old_description}):",
            choices=[
                ("Enter New", "new"),
                ("Keep Current", "keep"),
            ],
            include_cancel=True,
        )
        desc_choice_result = await desc_choice.start(self.context)

        if is_cancelled(desc_choice_result):
            return desc_choice_result

        if desc_choice_result == "new":
            desc_dialog = UserInputDialog("Enter new description:")
            desc_result = await desc_dialog.start(self.context)
            if is_cancelled(desc_result):
                return desc_result
            new_description = desc_result if isinstance(desc_result, str) else old_description
        else:
            new_description = old_description

        # Price with "Keep Current" option at the end
        price_choice = ChoiceDialog(
            prompt=f"Price (current: ₪{old_price:.2f}):",
            choices=[
                ("Enter New", "new"),
                ("Keep Current", "keep"),
            ],
            include_cancel=True,
        )
        price_choice_result = await price_choice.start(self.context)

        if is_cancelled(price_choice_result):
            return price_choice_result

        if price_choice_result == "new":
            price_dialog = UserInputDialog(
                "Enter new price:",
                validator=validate_positive_float,
            )
            price_result = await price_dialog.start(self.context)
            if is_cancelled(price_result):
                return price_result
            try:
                new_price = float(price_result) if isinstance(price_result, str) else old_price
            except (ValueError, TypeError):
                new_price = old_price
        else:
            new_price = old_price

        # Build confirmation message showing old vs new
        new_category_name = CATEGORY_NAMES.get(str(new_category), str(new_category))
        changes: list[str] = []

        if new_category != old_category:
            changes.append(f"Category: {old_category_name} → {new_category_name}")
        if new_description != old_description:
            changes.append(f"Description: {old_description} → {new_description}")
        if new_price != old_price:
            changes.append(f"Price: ₪{old_price:.2f} → ₪{new_price:.2f}")

        if not changes:
            await get_app().send_messages("No changes made.")
            return None

        confirm_message = "Confirm changes?\n\n" + "\n".join(changes)

        # Confirm modification
        confirm_dialog = ConfirmDialog(confirm_message, include_cancel=True)
        confirm_result = await confirm_dialog.start(self.context)

        if is_cancelled(confirm_result):
            return confirm_result

        # If user declined, return None to trigger restart
        if confirm_result is False:
            return None

        return {
            "original_expense": expense_result,
            "category": new_category,
            "description": new_description,
            "price": str(new_price),
        }

    def build_result(self) -> DialogResult:
        """Return the dialog result."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Handle callback - child dialogs handle their own callbacks."""
        pass

    def handle_text_input(self, text: str) -> None:
        """Handle text input - child dialogs handle their own text input."""
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
    """Handle completion of export dialog.
    
    Args:
        result: The dialog result containing month selection.
    """
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


async def _generate_and_send_chart(year: int, month: int) -> None:
    """Generate and send a chart for the specified month.

    Args:
        year: The year.
        month: The month.
    """
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


class ChartDialog(Dialog):
    """Dialog for generating expense charts.

    Flow: Month selection -> Chart generation (no confirmation).
    Allows selecting expenses from the previous month or a custom month.
    Chart is generated and sent immediately after month selection.
    """

    def __init__(self) -> None:
        """Initialize the chart dialog."""
        super().__init__()

    async def _run_dialog(self) -> DialogResult:
        """Run the chart generation flow.

        Returns:
            Dict with month selection or cancellation result.
        """
        now = datetime.now()

        # Ask which month
        month_choice = ChoiceDialog(
            prompt="Generate chart for which month?",
            choices=[
                ("Previous Month", "previous"),
                ("Provide Month", "custom"),
            ],
            include_cancel=True,
        )

        month_result = await month_choice.start(self.context)

        if is_cancelled(month_result):
            self._value = month_result
            return month_result

        # Determine year and month
        if month_result == "previous":
            if now.month == 1:
                year, month = now.year - 1, 12
            else:
                year, month = now.year, now.month - 1
        elif month_result == "custom":
            date_dialog = UserInputDialog(
                "Enter month (MM/YYYY):",
                validator=validate_date_format("%m/%Y", "MM/YYYY"),
                include_cancel=True,
            )
            date_result = await date_dialog.start(self.context)
            if is_cancelled(date_result):
                self._value = date_result
                return date_result
            if not isinstance(date_result, str):
                await get_app().send_messages("Invalid date format.")
                self._value = None
                return None
            try:
                parsed = datetime.strptime(date_result, "%m/%Y")
                year, month = parsed.year, parsed.month
            except (ValueError, TypeError):
                await get_app().send_messages("Invalid date format.")
                self._value = None
                return None
        else:
            self._value = None
            return None

        # Generate and send chart immediately (no confirmation)
        await _generate_and_send_chart(year, month)

        self._value = {"year": year, "month": month}
        return self._value

    def build_result(self) -> DialogResult:
        """Return the dialog result."""
        return self._value

    def handle_callback(self, callback_data: str) -> None:
        """Handle callback - child dialogs handle their own callbacks."""
        pass

    def handle_text_input(self, text: str) -> None:
        """Handle text input - child dialogs handle their own text input."""
        pass


async def _on_chart_complete(result: DialogResult) -> None:
    """Handle completion of chart dialog.
    
    Args:
        result: The dialog result containing month selection.
    """
    if is_cancelled(result):
        await get_app().send_messages("Chart cancelled.")
        return

    # Chart was already generated in the dialog, nothing more to do


def create_chart_dialog() -> Dialog:
    """Create the chart generation dialog flow.

    Returns:
        Dialog for generating expense charts.
    """
    return DialogHandler(
        ChartDialog(),
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
            f"₪{expense.price:.2f} ({expense.timestamp.strftime('%d/%m/%Y')})"
        )
        lines.append(line)

    header = "<b>Recent Expenses</b>\n\n"
    return header + format_numbered_list(lines)
