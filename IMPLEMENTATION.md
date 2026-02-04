# Implementation Guide

This document describes the internal architecture, design patterns, and code flow of the Expense Monitoring Bot.

## Architecture Overview

The bot is built on top of `my_bot_framework` and follows its patterns for commands, dialogs, and messaging.

```
┌──────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│              (Entry point, command registration)                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐   │
│  │   dialogs.py │    │expense_manager│    │    charts.py     │   │
│  │   (Flows)    │    │   (CRUD)      │    │ (Visualization)  │   │
│  └──────┬───────┘    └──────┬────────┘    └────────┬─────────┘   │
│         │                   │                      │             │
│         └───────────────────┼──────────────────────┘             │
│                             │                                    │
│                             ▼                                    │
│                    ┌────────────────┐                            │
│                    │   constants.py │                            │
│                    │  (Categories)  │                            │
│                    └────────────────┘                            │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                      my_bot_framework                            │
│         (BotApplication, Dialogs, Commands, Messages)            │
└──────────────────────────────────────────────────────────────────┘
```

## Module Structure

```
expense_bot/
├── __init__.py           # Package init
├── main.py               # Bot entry point and command registration
├── expense_manager.py    # CSV CRUD operations (Expense dataclass, ExpenseManager)
├── dialogs.py            # Interactive dialog flows for all commands
├── charts.py             # Pie chart generation with matplotlib
└── constants.py          # Category definitions and help text
```

### Module Dependency Graph

```mermaid
graph TD
    MAIN[main.py] --> DIALOGS[dialogs.py]
    MAIN --> EXPENSE[expense_manager.py]
    DIALOGS --> EXPENSE
    DIALOGS --> CHARTS[charts.py]
    DIALOGS --> CONSTANTS[constants.py]
    CHARTS --> CONSTANTS
```

### Dependency Table

| Module | Imports From |
|--------|--------------|
| `constants.py` | *(no internal dependencies)* |
| `expense_manager.py` | *(no internal dependencies)* |
| `charts.py` | `constants` |
| `dialogs.py` | `constants`, `expense_manager`, `charts` (lazy) |
| `main.py` | `dialogs`, `expense_manager` |

## Core Components

### 1. ExpenseManager (expense_manager.py)

The `ExpenseManager` class handles all CRUD operations for expenses stored in CSV files.

**Expense Dataclass:**

```python
@dataclass
class Expense:
    id: int           # Unique within month
    timestamp: datetime
    category: str     # Category key (home, transport, etc.)
    description: str
    price: float
    year: int         # Source file year
    month: int        # Source file month
```

**Key Methods:**

| Method | Description |
|--------|-------------|
| `get_expenses(year, month)` | Get all expenses for a month, sorted by timestamp |
| `get_recent(count)` | Get N most recent expenses across all months |
| `add_expense(...)` | Add new expense, auto-assigns ID |
| `remove_expense(id, year, month)` | Remove expense by ID |
| `modify_expense(id, year, month, ...)` | Update expense, preserves ID and timestamp |
| `get_expenses_by_category(year, month)` | Get totals grouped by category |
| `get_month_total(year, month)` | Get total expenses for a month |

**File Organization:**

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

Each CSV has columns: `id`, `timestamp`, `category`, `description`, `price`

### 2. Dialog Flows (dialogs.py)

All interactive commands use dialog flows built with the framework's dialog system.

**Global ExpenseManager Pattern:**

```python
_expense_manager: Optional[ExpenseManager] = None

def set_expense_manager(manager: ExpenseManager) -> None:
    global _expense_manager
    _expense_manager = manager

def get_expense_manager() -> ExpenseManager:
    if _expense_manager is None:
        raise RuntimeError("ExpenseManager not set")
    return _expense_manager
```

This pattern allows dialogs to access the manager without passing it through every function.

### 3. Charts (charts.py)

Generates pie charts using matplotlib with:
- Color-coded categories
- Percentage labels (>5%)
- Legend with amounts
- Title with month/year and total
- Generation timestamp footer

**Color Palette:**

| Category | Color |
|----------|-------|
| Home | Red (#FF6B6B) |
| Transportation | Teal (#4ECDC4) |
| Groceries | Blue (#45B7D1) |
| Dining Out | Green (#96CEB4) |
| Other | Yellow (#FFEAA7) |

### 4. Constants (constants.py)

Defines the category system:

```python
CATEGORIES = [
    ("Home", "home"),
    ("Transportation", "transport"),
    ("Groceries", "groceries"),
    ("Dining Out", "dining"),
    ("Other", "other"),
    ("Help", "help"),
]

CATEGORY_NAMES = {
    "home": "Home",
    "transport": "Transportation",
    ...
}

VALID_CATEGORIES = {"home", "transport", "groceries", "dining", "other"}
```

## Dialog Flow Details

### Add Expense Flow

```
┌─────────────────┐
│ CategoryChoice  │  Custom dialog with Help button support
│ WithHelp        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  UserInputDialog│  "Enter a brief description:"
│  (description)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  UserInputDialog│  "Enter the price:" (validate_positive_float)
│     (price)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DialogHandler  │  _on_add_complete callback
│   (save)        │  → expense_manager.add_expense()
└─────────────────┘
```

**CategoryChoiceWithHelp:**

A custom `Dialog` subclass that wraps `ChoiceDialog` and handles the "Help" button by showing category descriptions and re-displaying the choice buttons:

```python
class CategoryChoiceWithHelp(Dialog):
    async def _run_dialog(self) -> DialogResult:
        while True:
            result = await ChoiceDialog(...).start(self.context)
            if result == "help":
                await get_app().send_messages(CATEGORY_HELP)
                continue  # Show choices again
            return result
```

### Remove Expense Flow

```
┌──────────────────┐
│ChoiceBranchDialog│  "Current Month" or "Different Month"
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Current    UserInput
Month      (MM/YYYY)
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│ PaginatedChoice │  5 expenses per page, newest first
│    Dialog       │  [Category] Description - $X.XX (MM/DD)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DialogHandler  │  _on_remove_complete callback
│   (remove)      │  → expense_manager.remove_expense()
└─────────────────┘
```

**Expense Callback Data Format:**

Expenses are identified by callback data in format: `year:month:id`

```python
def _parse_expense_callback(callback: str) -> tuple[int, int, int]:
    parts = callback.split(":")
    return int(parts[0]), int(parts[1]), int(parts[2])
```

### Modify Expense Flow

```
┌─────────────────┐
│ Month Selection │  Same as Remove flow
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Expense Select  │  PaginatedChoiceDialog
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ New Category    │  CategoryChoiceWithHelp
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ New Description │  UserInputDialog
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ New Price       │  UserInputDialog (validated)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DialogHandler  │  _on_modify_complete callback
│   (modify)      │  → expense_manager.modify_expense()
└─────────────────┘
```

**Preservation of ID and Timestamp:**

When modifying, the original `id` and `timestamp` are preserved to maintain order and creation time. Only `category`, `description`, and `price` are updated.

### Export Flow

```
┌──────────────────┐
│ChoiceBranchDialog│  "Previous Month" or "Provide Month"
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Previous   UserInput
Month      (MM/YYYY)
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│  DialogHandler  │  _on_export_complete callback
│   (export)      │  → TelegramDocumentMessage(csv_path)
└─────────────────┘
```

### Chart Flow

```
┌──────────────────┐
│ChoiceBranchDialog│  "Previous Month" or "Provide Month"
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Previous   UserInput
Month      (MM/YYYY)
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│  DialogHandler  │  _on_chart_complete callback
│   (chart)       │  → generate_expense_chart()
│                 │  → TelegramImageMessage(chart_path)
└─────────────────┘
```

## Command Registration

Commands are registered in `main.py` using the framework's `DialogCommand` and `SimpleCommand`:

```python
# Dialog-based commands
app.register_command(DialogCommand(
    command="/add",
    description="Add a new expense",
    dialog=create_add_expense_dialog(),
))

# Simple commands (no dialog)
app.register_command(SimpleCommand(
    command="/recent",
    description="Show recent expenses",
    message_builder=get_recent_expenses_message,
))
```

## Data Flow

### Adding an Expense

```
1. User: /add
2. Bot: Category selection keyboard
3. User: Selects "Groceries"
4. Bot: "Enter a brief description:"
5. User: "Weekly shopping"
6. Bot: "Enter the price:"
7. User: "85.50"
8. Bot: _on_add_complete() called
   └─► expense_manager.add_expense(
         category="groceries",
         description="Weekly shopping",
         price=85.50
       )
   └─► Appends row to data/2026/02.csv
   └─► Sends confirmation message
```

### CSV File Format

```csv
id,timestamp,category,description,price
1,2026-02-01 10:30:00,groceries,Weekly shopping,85.50
2,2026-02-01 14:15:00,dining,Lunch with colleagues,32.00
3,2026-02-02 09:00:00,transport,Gas,45.00
```

### ID Generation

IDs are auto-incremented per month:

```python
def _get_next_id(self, year: int, month: int) -> int:
    expenses = self.get_expenses(year, month)
    if not expenses:
        return 1
    return max(e.id for e in expenses) + 1
```

## Error Handling

### Validation

- **Prices**: Validated with `validate_positive_float` (rejects non-numeric, negative, zero)
- **Dates**: Validated with `validate_date_format("%m/%Y", "MM/YYYY")`
- **Categories**: Checked against `VALID_CATEGORIES` set

### Dialog Cancellation

All dialogs support cancellation via the Cancel button or `/cancel` command:

```python
if is_cancelled(result):
    await get_app().send_messages("Operation cancelled.")
    return
```

### No Data Scenarios

- **No expenses for month**: Shows "No expenses found" message
- **Empty CSV file**: Returns empty list from `get_expenses()`
- **No CSV file**: Returns empty list (file created on first write)

## Startup Flow

```
1. Read credentials from .token and .chat_id files
2. Initialize ExpenseManager with data/ directory
3. Call set_expense_manager() to make it globally available
4. Initialize BotApplication with credentials
5. Register all commands (add, remove, modify, recent, export, chart, info)
6. Send startup message
7. Start polling loop
```

## Framework Integration

### Used Framework Components

| Component | Usage |
|-----------|-------|
| `BotApplication` | Singleton for bot lifecycle |
| `DialogCommand` | Multi-step interactive commands |
| `SimpleCommand` | Single-response commands (/recent, /info) |
| `ChoiceDialog` | Category selection |
| `ChoiceBranchDialog` | Month selection (current vs custom) |
| `PaginatedChoiceDialog` | Expense selection (5 per page) |
| `UserInputDialog` | Text/number input with validation |
| `ConfirmDialog` | Confirmation prompts |
| `SequenceDialog` | Chaining dialogs (add flow) |
| `DialogHandler` | Callback on completion |
| `TelegramDocumentMessage` | CSV export |
| `TelegramImageMessage` | Chart sending |
| `validate_positive_float` | Price validation |
| `validate_date_format` | Date format validation |
| `format_numbered_list` | Recent expenses formatting |
| `is_cancelled` / `CANCELLED` | Cancellation detection |

### Custom Dialog: CategoryChoiceWithHelp

The only custom dialog extends the framework's `Dialog` to add Help button support:

```python
class CategoryChoiceWithHelp(Dialog):
    """Custom dialog for category selection with Help button support."""
    
    def __init__(self) -> None:
        super().__init__()
        self._choice_dialog: Optional[ChoiceDialog] = None

    async def _run_dialog(self) -> DialogResult:
        while True:
            self._choice_dialog = ChoiceDialog(
                prompt="Select expense category:",
                choices=CATEGORIES,
                include_cancel=True,
            )
            result = await self._choice_dialog.start(self.context)

            if is_cancelled(result):
                return result

            if result == "help":
                await get_app().send_messages(CATEGORY_HELP)
                continue

            if result in VALID_CATEGORIES:
                return result
```

## Extension Points

### Adding a New Category

1. Update `CATEGORIES` in `constants.py`:
   ```python
   CATEGORIES.insert(-1, ("Health", "health"))  # Before Help
   ```

2. Update `CATEGORY_NAMES`:
   ```python
   CATEGORY_NAMES["health"] = "Health"
   ```

3. Update `VALID_CATEGORIES`:
   ```python
   VALID_CATEGORIES.add("health")
   ```

4. Update `CATEGORY_HELP` with description

5. Add color to `CATEGORY_COLORS` in `charts.py`:
   ```python
   CATEGORY_COLORS["health"] = "#E066FF"
   ```

### Adding a New Command

1. Create dialog factory function in `dialogs.py`
2. Create completion callback `_on_X_complete`
3. Register in `main.py`:
   ```python
   app.register_command(DialogCommand(
       command="/newcmd",
       description="Description",
       dialog=create_new_dialog(),
   ))
   ```

### Adding a Report Type

1. Add method to `ExpenseManager` for data aggregation
2. Create formatting function in `dialogs.py`
3. Register as `SimpleCommand` or create dialog flow
