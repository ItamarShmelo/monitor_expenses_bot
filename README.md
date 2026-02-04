# Expense Monitoring Bot

A Telegram bot for tracking group expenses with CSV storage, interactive dialogs, and pie chart visualization.

## Features

- **Add expenses** with category, description, and price through interactive dialogs
- **Remove expenses** with paginated selection from current or past months
- **Modify expenses** while preserving their timestamp and position
- **View recent expenses** showing the 10 most recent entries across all months
- **Export expenses** as CSV files for any month (current, previous, or custom)
- **Generate pie charts** showing expense breakdown by category with visualizations

## Categories

- **Home**: Rent, Utilities (electricity, water, gas), Internet, Maintenance, Repairs
- **Transportation**: Car payments, Gas, Public Transport, Parking, Car wash, Repairs
- **Groceries**: Supermarket, Food supplies, Farmers market, Household items
- **Dining Out**: Restaurants, Cafes, Takeout, Delivery, Fast food
- **Other**: Everything that doesn't fit above - Gifts, Entertainment, Shopping, etc.

## Requirements

- Python 3.12 or higher
- uv package manager (for dependency management)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd monitor_expenses_bot
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Set up credentials:
   - Create a `.token` file with your Telegram bot token
   - Create a `.chat_id` file with your target chat ID

   ```bash
   echo "YOUR_BOT_TOKEN" > .token
   echo "YOUR_CHAT_ID" > .chat_id
   ```

   **Getting your bot token:**
   - Create a bot via [@BotFather](https://t.me/botfather) on Telegram
   - Copy the token provided

   **Getting your chat ID:**
   - Start a chat with your bot
   - Send a message to your bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response (look for `"chat":{"id":...}`)

## Usage

Run the bot:

```bash
uv run python -m expense_bot.main
```

Or directly:

```bash
python expense_bot/main.py
```

The bot will send a startup message when it begins running. Type `/info` for help or `/commands` to see all available commands.

## Commands

| Command | Description |
|---------|-------------|
| `/add` | Add a new expense. Interactive flow: select category → enter description → enter price |
| `/remove` | Remove an expense. Choose from current month or enter a different month (MM/YYYY), then select from paginated list, then confirm removal |
| `/modify` | Modify an existing expense. Select expense, see current values, choose to keep or change each field, then confirm changes with old→new comparison |
| `/recent` | Show the 10 most recent expenses across all months, sorted by date |
| `/export` | Download expenses as CSV file. Choose previous month or enter custom month (MM/YYYY) |
| `/chart` | Generate a pie chart of expenses by category. Choose previous month or enter custom month (MM/YYYY) |
| `/info` | Show bot information and command list |
| `/commands` | List all available commands (built-in) |
| `/terminate` | Stop the bot gracefully (built-in) |

## Interactive Dialogs

Most commands use interactive dialogs that guide you through the process:

- **Category Selection**: When adding or modifying expenses, you'll see buttons for each category. Select "Help" to see detailed descriptions of what each category includes.

- **Month Selection**: For `/remove`, `/modify`, `/export`, and `/chart`, you can:
  - Choose "Current Month" for the current month
  - Choose "Different Month" and enter a date in `MM/YYYY` format (e.g., `02/2026`)

- **Expense Selection**: When removing or modifying, expenses are shown in a paginated list (5 per page) with:
  - Category name in brackets
  - Description
  - Price
  - Date (DD/MM format)

- **Modify Flow**: When modifying an expense:
  - After selecting an expense, you'll see its current values
  - For each field (category, description, price), you can choose "Keep Current" or provide a new value
  - After collecting all changes, you'll see a confirmation showing old→new values for each changed field
  - Clicking "Yes" confirms the changes, "No" returns to the start to select a different expense, "Cancel" exits
  - If no changes are made, the dialog exits with "No changes made"

- **Confirmation**: When removing an expense, you'll be asked to confirm before the expense is deleted.

- **Cancellation**: All dialogs support cancellation. Use the "Cancel" button or type `/cancel` to exit at any point.

- **Input Validation**: 
  - Prices must be positive numbers (e.g., `25.50`, `100`)
  - Dates must be in `MM/YYYY` format
  - Descriptions can be any text

## Data Storage

Expenses are stored in CSV files organized by year and month. The `data/` directory is automatically created if it doesn't exist, and CSV files are created on-demand when the first expense for a month is added.

Directory structure:
```
data/
├── 2025/
│   ├── 10.csv
│   ├── 11.csv
│   └── 12.csv
└── 2026/
    ├── 01.csv
    └── 02.csv
```

Each CSV file has the following columns:
- `id` - Unique identifier within the month (auto-incremented)
- `timestamp` - When the expense was recorded (format: `YYYY-MM-DD HH:MM:SS`)
- `category` - Category key (`home`, `transport`, `groceries`, `dining`, `other`)
- `description` - Brief description of the expense
- `price` - Amount in dollars (stored with 2 decimal places)

**Note:** When modifying expenses, the `id` and `timestamp` are preserved to maintain the original order and creation time. You can keep current values for any field by selecting "Keep Current" during modification.

## Project Structure

```
monitor_expenses_bot/
├── expense_bot/
│   ├── __init__.py       # Package init
│   ├── main.py           # Bot entry point
│   ├── expense_manager.py # CSV CRUD operations
│   ├── dialogs.py        # Interactive dialog flows
│   ├── charts.py         # Pie chart generation
│   └── constants.py      # Categories and help text
├── data/                 # Expense CSV files
├── my_bot_framework/     # Bot framework (submodule)
├── .token               # Bot token (git-ignored)
├── .chat_id             # Chat ID (git-ignored)
├── pyproject.toml       # Project dependencies
└── README.md            # This file
```

## Dependencies

- Python 3.12+
- python-telegram-bot (>=22.6) - Telegram Bot API wrapper
- matplotlib (>=3.8) - Chart generation
- my_bot_framework - Custom bot framework (included as git submodule)

All dependencies are managed via `pyproject.toml` and installed with `uv sync`.

## License

MIT
