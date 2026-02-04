"""Expense monitoring bot entry point.

This module initializes and runs the expense monitoring Telegram bot.
Reads credentials from .token and .chat_id files in the project root.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from my_bot_framework import (
    BotApplication,
    DialogCommand,
    SimpleCommand,
)

from expense_bot.dialogs import (
    create_add_expense_dialog,
    create_remove_expense_dialog,
    create_modify_expense_dialog,
    create_export_dialog,
    create_chart_dialog,
    get_recent_expenses_message,
    set_expense_manager,
)
from expense_bot.expense_manager import ExpenseManager


def get_credentials() -> tuple[str, str]:
    """Read bot credentials from files.

    Reads token from .token file and chat_id from .chat_id file
    in the project root directory.

    Returns:
        Tuple of (token, chat_id).

    Raises:
        FileNotFoundError: If credential files don't exist.
        RuntimeError: If credential files are empty.
    """
    project_root = Path(__file__).resolve().parent.parent

    token_file = project_root / ".token"
    chat_id_file = project_root / ".chat_id"

    if not token_file.exists():
        raise FileNotFoundError(
            f"Token file not found: {token_file}\n"
            "Create a .token file with your Telegram bot token."
        )

    if not chat_id_file.exists():
        raise FileNotFoundError(
            f"Chat ID file not found: {chat_id_file}\n"
            "Create a .chat_id file with your Telegram chat ID."
        )

    token = token_file.read_text().strip()
    chat_id = chat_id_file.read_text().strip()

    if not token:
        raise RuntimeError("Token file is empty. Add your bot token to .token")

    if not chat_id:
        raise RuntimeError("Chat ID file is empty. Add your chat ID to .chat_id")

    return token, chat_id


def main() -> None:
    """Initialize and run the expense monitoring bot."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("expense_bot")

    # Get credentials
    try:
        token, chat_id = get_credentials()
    except (FileNotFoundError, RuntimeError) as e:
        logger.error("Credential error: %s", e)
        sys.exit(1)

    # Initialize expense manager
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    expense_manager = ExpenseManager(data_dir)
    set_expense_manager(expense_manager)

    logger.info("Data directory: %s", data_dir)

    # Initialize bot application
    app = BotApplication.initialize(
        token=token,
        chat_id=chat_id,
        logger=logger,
    )

    # Register commands
    app.register_command(DialogCommand(
        command="/add",
        description="Add a new expense",
        dialog=create_add_expense_dialog(),
    ))

    app.register_command(DialogCommand(
        command="/remove",
        description="Remove an expense",
        dialog=create_remove_expense_dialog(),
    ))

    app.register_command(DialogCommand(
        command="/modify",
        description="Modify an existing expense",
        dialog=create_modify_expense_dialog(),
    ))

    app.register_command(SimpleCommand(
        command="/recent",
        description="Show recent expenses",
        message_builder=get_recent_expenses_message,
    ))

    app.register_command(DialogCommand(
        command="/export",
        description="Export expenses as CSV file",
        dialog=create_export_dialog(),
    ))

    app.register_command(DialogCommand(
        command="/chart",
        description="Generate expense chart",
        dialog=create_chart_dialog(),
    ))

    # Info command
    info_text = (
        "<b>Expense Monitoring Bot</b>\n\n"
        "Track your group expenses with ease!\n\n"
        "<b>Commands:</b>\n"
        "/add - Add a new expense\n"
        "/remove - Remove an expense\n"
        "/modify - Modify an existing expense\n"
        "/recent - Show recent expenses\n"
        "/export - Export expenses as CSV\n"
        "/chart - Generate expense pie chart\n"
        "/commands - List all commands\n"
        "/terminate - Stop the bot"
    )
    app.register_command(SimpleCommand(
        command="/info",
        description="Show bot information",
        message_builder=lambda: info_text,
    ))

    # Run the bot
    async def send_startup_and_run() -> None:
        await app.send_messages(
            "<b>Expense Bot Started!</b>\n\n"
            "Type /info for help or /commands to see all commands."
        )
        logger.info("Expense bot started successfully")
        await app.run()

    asyncio.run(send_startup_and_run())


if __name__ == "__main__":
    main()
