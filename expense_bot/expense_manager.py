"""Expense manager for CSV-based expense tracking.

This module provides the ExpenseManager class for CRUD operations on expenses
stored in monthly CSV files under data/{year}/{month}.csv.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Expense:
    """Represents a single expense entry.

    Attributes:
        id: Unique identifier within the month's CSV.
        timestamp: When the expense was recorded.
        category: Category key (e.g., 'home', 'groceries').
        description: Brief description of the expense.
        price: Amount in dollars.
        year: Year of the expense (for tracking source file).
        month: Month of the expense (for tracking source file).
    """

    id: int
    timestamp: datetime
    category: str
    description: str
    price: float
    year: int
    month: int

    def to_row(self) -> list[str]:
        """Convert expense to CSV row format.

        Returns:
            List of string values for CSV writing.
        """
        return [
            str(self.id),
            self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.category.capitalize(),
            self.description,
            f"{self.price:.2f}",
        ]

    @classmethod
    def from_row(cls, row: list[str], year: int, month: int) -> "Expense":
        """Create an Expense from a CSV row.

        Args:
            row: List of string values from CSV.
            year: Year of the source file.
            month: Month of the source file.

        Returns:
            Expense instance.
        """
        return cls(
            id=int(row[0]),
            timestamp=datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S"),
            category=row[2],
            description=row[3],
            price=float(row[4]),
            year=year,
            month=month,
        )


class ExpenseManager:
    """Manages expense data stored in monthly CSV files.

    CSV files are organized as data/{year}/{month}.csv with columns:
    id, timestamp, category, description, price

    Attributes:
        data_dir: Path to the data directory.
    """

    CSV_HEADER = ["id", "timestamp", "category", "description", "price"]

    def __init__(self, data_dir: Path | str = "data") -> None:
        """Initialize the expense manager.

        Args:
            data_dir: Path to the data directory (default: 'data').
        """
        self.data_dir = Path(data_dir)

    def get_csv_path(self, year: int, month: int) -> Path:
        """Get the path to a month's CSV file.

        Args:
            year: The year (e.g., 2026).
            month: The month (1-12).

        Returns:
            Path to the CSV file (e.g., data/2026/01.csv).
        """
        return self.data_dir / str(year) / f"{month:02d}.csv"

    def _ensure_csv_exists(self, year: int, month: int) -> Path:
        """Ensure the CSV file and its directory exist.

        Args:
            year: The year.
            month: The month.

        Returns:
            Path to the CSV file.
        """
        csv_path = self.get_csv_path(year, month)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not csv_path.exists():
            with csv_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADER)
        return csv_path

    def get_expenses(self, year: int, month: int) -> list[Expense]:
        """Get all expenses for a specific month.

        Args:
            year: The year.
            month: The month (1-12).

        Returns:
            List of Expense objects, sorted by timestamp.
        """
        csv_path = self.get_csv_path(year, month)
        if not csv_path.exists():
            return []

        expenses = []
        with csv_path.open("r", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) >= 5:
                    expenses.append(Expense.from_row(row, year, month))

        return sorted(expenses, key=lambda e: e.timestamp)

    def get_recent(
        self,
        count: int = 5,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> list[Expense]:
        """Get the most recent expenses.

        Args:
            count: Maximum number of expenses to return.
            year: If provided with month, only search that month.
            month: If provided with year, only search that month.

        Returns:
            List of most recent Expense objects, newest first.
        """
        if year is not None and month is not None:
            expenses = self.get_expenses(year, month)
            return sorted(expenses, key=lambda e: e.timestamp, reverse=True)[:count]

        # Get current month and search backwards
        now = datetime.now()
        all_expenses: list[Expense] = []
        current_year = now.year
        current_month = now.month

        # Search up to 12 months back
        for _ in range(12):
            expenses = self.get_expenses(current_year, current_month)
            all_expenses.extend(expenses)
            if len(all_expenses) >= count:
                break
            # Move to previous month
            current_month -= 1
            if current_month < 1:
                current_month = 12
                current_year -= 1

        return sorted(all_expenses, key=lambda e: e.timestamp, reverse=True)[:count]

    def _get_next_id(self, year: int, month: int) -> int:
        """Get the next available ID for a month.

        Args:
            year: The year.
            month: The month.

        Returns:
            Next available ID (max existing ID + 1, or 1 if empty).
        """
        expenses = self.get_expenses(year, month)
        if not expenses:
            return 1
        return max(e.id for e in expenses) + 1

    def add_expense(
        self,
        category: str,
        description: str,
        price: float,
        year: Optional[int] = None,
        month: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> Expense:
        """Add a new expense.

        Args:
            category: Category key (e.g., 'home', 'groceries').
            description: Brief description.
            price: Amount in dollars.
            year: Year to add to (default: current year).
            month: Month to add to (default: current month).
            timestamp: When the expense occurred (default: now).

        Returns:
            The created Expense object.
        """
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        if timestamp is None:
            timestamp = now

        csv_path = self._ensure_csv_exists(year, month)
        expense_id = self._get_next_id(year, month)

        expense = Expense(
            id=expense_id,
            timestamp=timestamp,
            category=category,
            description=description,
            price=price,
            year=year,
            month=month,
        )

        with csv_path.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(expense.to_row())

        return expense

    def remove_expense(self, expense_id: int, year: int, month: int) -> bool:
        """Remove an expense by ID.

        Args:
            expense_id: The ID of the expense to remove.
            year: The year of the expense.
            month: The month of the expense.

        Returns:
            True if the expense was removed, False if not found.
        """
        csv_path = self.get_csv_path(year, month)
        if not csv_path.exists():
            return False

        expenses = self.get_expenses(year, month)
        original_count = len(expenses)
        expenses = [e for e in expenses if e.id != expense_id]

        if len(expenses) == original_count:
            return False  # Not found

        # Rewrite the file
        with csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.CSV_HEADER)
            for expense in expenses:
                writer.writerow(expense.to_row())

        return True

    def modify_expense(
        self,
        expense_id: int,
        year: int,
        month: int,
        category: str,
        description: str,
        price: float,
    ) -> Optional[Expense]:
        """Modify an existing expense, preserving its position.

        Args:
            expense_id: The ID of the expense to modify.
            year: The year of the expense.
            month: The month of the expense.
            category: New category.
            description: New description.
            price: New price.

        Returns:
            The modified Expense if found, None otherwise.
        """
        csv_path = self.get_csv_path(year, month)
        if not csv_path.exists():
            return None

        expenses = self.get_expenses(year, month)
        modified_expense: Optional[Expense] = None

        for i, expense in enumerate(expenses):
            if expense.id == expense_id:
                # Preserve id and timestamp, update other fields
                expenses[i] = Expense(
                    id=expense.id,
                    timestamp=expense.timestamp,
                    category=category,
                    description=description,
                    price=price,
                    year=year,
                    month=month,
                )
                modified_expense = expenses[i]
                break

        if modified_expense is None:
            return None

        # Rewrite the file
        with csv_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.CSV_HEADER)
            for expense in expenses:
                writer.writerow(expense.to_row())

        return modified_expense

    def get_expenses_by_category(
        self,
        year: int,
        month: int,
    ) -> dict[str, float]:
        """Get total expenses grouped by category.

        Args:
            year: The year.
            month: The month.

        Returns:
            Dict mapping category to total amount.
        """
        expenses = self.get_expenses(year, month)
        totals: dict[str, float] = {}
        for expense in expenses:
            totals[expense.category] = totals.get(expense.category, 0) + expense.price
        return totals

    def get_month_total(self, year: int, month: int) -> float:
        """Get total expenses for a month.

        Args:
            year: The year.
            month: The month.

        Returns:
            Total amount for the month.
        """
        expenses = self.get_expenses(year, month)
        return sum(e.price for e in expenses)
