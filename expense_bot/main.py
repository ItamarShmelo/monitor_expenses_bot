"""Expense monitoring bot entry point.

This module initializes and runs the expense monitoring Telegram bot.
Uses a keyboard-based interface with "Add" and "More" buttons.
Reads credentials from .token and .chat_id files in the project root.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from telegram import Update

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from my_bot_framework import (
    BotApplication,
    Event,
    UpdatePollerMixin,
    flush_pending_updates,
    get_app,
    get_bot,
    get_logger,
    get_stop_event,
    set_next_update_id,
    TelegramCallbackAnswerMessage,
    TelegramRemoveKeyboardMessage,
)

from expense_bot.dialogs import (
    create_add_expense_dialog,
    create_remove_expense_dialog,
    create_modify_expense_dialog,
    create_export_dialog,
    create_chart_dialog,
    get_recent_expenses_message,
    set_expense_manager,
    get_main_keyboard_message,
    get_more_keyboard_message,
    get_info_text,
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


class KeyboardEvent(Event, UpdatePollerMixin):
    """Event that handles keyboard-based navigation and built-in commands.

    Listens for button presses from the reply keyboard and routes them
    to the appropriate dialogs or actions. Also handles /terminate and
    /commands built-in commands.

    Attributes:
        event_name: Unique identifier for the event.
    """

    def __init__(self, event_name: str = "keyboard") -> None:
        """Initialize the keyboard event.

        Args:
            event_name: Unique identifier for the event.
        """
        super().__init__(event_name)
        self._stop_event: Optional[asyncio.Event] = None

    def should_stop_polling(self) -> bool:
        """Return True when polling should stop.

        Returns:
            True if stop event is set, False otherwise.
        """
        return self._stop_event.is_set() if self._stop_event else True

    async def handle_callback_update(self, update: Update) -> None:
        """Handle stale callback queries.

        Args:
            update: The Telegram update containing the callback query.
        """
        logger = get_logger()
        callback_query = update.callback_query
        if callback_query is None:
            return

        logger.debug("stale_callback_received id=%s", callback_query.id)

        await get_app().send_messages(TelegramCallbackAnswerMessage(
            callback_query.id,
            text="No active session.",
        ))

        if callback_query.message:
            await get_app().send_messages(
                TelegramRemoveKeyboardMessage(callback_query.message.message_id)
            )

    async def handle_text_update(self, update: Update) -> None:
        """Handle text message updates from keyboard buttons and commands.

        Args:
            update: The Telegram update containing the text message.
        """
        if update.message is None or update.message.text is None:
            return

        text = update.message.text.strip()
        logger = get_logger()

        # Handle built-in commands
        if text == "/terminate":
            logger.info("command_matched command=/terminate")
            await get_app().send_messages("Bot terminating...")
            if self._stop_event:
                self._stop_event.set()
            return

        if text == "/commands":
            logger.info("command_matched command=/commands")
            commands_text = (
                "<b>Available Commands:</b>\n"
                "/terminate - Terminate the bot and shut down.\n"
                "/commands - List all available commands."
            )
            await get_app().send_messages(commands_text)
            return

        # Handle main menu buttons
        if text == "Add":
            logger.info("Handling Add button")
            set_next_update_id(update.update_id + 1)
            await self._handle_add()
            return

        if text == "More":
            logger.info("Handling More button")
            await self._send_more_keyboard()
            return

        # Handle More menu buttons
        if text == "Back":
            logger.info("Handling Back button")
            await self._send_main_keyboard()
            return

        if text == "Remove":
            logger.info("Handling Remove button")
            set_next_update_id(update.update_id + 1)
            await self._handle_remove()
            return

        if text == "Modify":
            logger.info("Handling Modify button")
            set_next_update_id(update.update_id + 1)
            await self._handle_modify()
            return

        if text == "Recent":
            logger.info("Handling Recent button")
            await self._handle_recent()
            return

        if text == "Export":
            logger.info("Handling Export button")
            set_next_update_id(update.update_id + 1)
            await self._handle_export()
            return

        if text == "Chart":
            logger.info("Handling Chart button")
            set_next_update_id(update.update_id + 1)
            await self._handle_chart()
            return

        if text == "Info":
            logger.info("Handling Info button")
            await self._handle_info()
            return

        # Ignore other messages
        logger.debug("Ignoring message: %s", text[:50] if len(text) > 50 else text)

    async def submit(self, stop_event: asyncio.Event) -> None:
        """Run the event loop.

        Args:
            stop_event: Event that signals when to stop.
        """
        self._stop_event = stop_event
        logger = get_logger()
        logger.info("[%s] keyboard_event_started", self.event_name)

        # Send initial main keyboard
        await self._send_main_keyboard(
            "<b>Expense Bot Started!</b>\n\nSelect an option below:"
        )

        # Start polling
        await self.poll()

        logger.info("[%s] keyboard_event_stopped", self.event_name)

    async def _send_main_keyboard(self, text: Optional[str] = None) -> None:
        """Send the main keyboard to the user.

        Args:
            text: Optional custom text. Defaults to standard prompt.
        """
        if text:
            message = get_main_keyboard_message(text)
        else:
            message = get_main_keyboard_message()
        await get_app().send_messages(message)

    async def _send_more_keyboard(self) -> None:
        """Send the More menu keyboard to the user."""
        await get_app().send_messages(get_more_keyboard_message())

    async def _handle_add(self) -> None:
        """Handle the Add button press."""
        dialog = create_add_expense_dialog()
        await dialog.start({})
        await self._send_main_keyboard()

    async def _handle_remove(self) -> None:
        """Handle the Remove button press."""
        dialog = create_remove_expense_dialog()
        await dialog.start({})
        await self._send_main_keyboard()

    async def _handle_modify(self) -> None:
        """Handle the Modify button press."""
        dialog = create_modify_expense_dialog()
        await dialog.start({})
        await self._send_main_keyboard()

    async def _handle_recent(self) -> None:
        """Handle the Recent button press."""
        message = await get_recent_expenses_message()
        await get_app().send_messages(message)
        await self._send_main_keyboard()

    async def _handle_export(self) -> None:
        """Handle the Export button press."""
        dialog = create_export_dialog()
        await dialog.start({})
        await self._send_main_keyboard()

    async def _handle_chart(self) -> None:
        """Handle the Chart button press."""
        dialog = create_chart_dialog()
        await dialog.start({})
        await self._send_main_keyboard()

    async def _handle_info(self) -> None:
        """Handle the Info button press."""
        await get_app().send_messages(get_info_text())
        await self._send_main_keyboard()


async def run_bot(logger: logging.Logger) -> None:
    """Run the bot with a single keyboard event.

    This runs the KeyboardEvent directly without using app.run() to avoid
    having multiple polling events that exhaust the connection pool.

    Args:
        logger: Logger for recording events.
    """
    # Flush pending updates
    await flush_pending_updates(get_bot())

    # Create and run the keyboard event
    stop_event = get_stop_event()
    keyboard_event = KeyboardEvent()

    logger.info("bot_started")

    await keyboard_event.submit(stop_event)

    logger.info("bot_stopped")


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

    # Initialize bot application (sets up singletons, but we don't call app.run())
    BotApplication.initialize(
        token=token,
        chat_id=chat_id,
        logger=logger,
    )

    # Run the bot with our custom run function
    asyncio.run(run_bot(logger))


if __name__ == "__main__":
    main()
