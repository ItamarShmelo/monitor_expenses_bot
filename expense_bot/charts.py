"""Chart generation for expense visualization.

This module provides functions to generate pie charts showing expense
distribution by category using matplotlib.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from .constants import CATEGORY_NAMES


# Color palette for categories
CATEGORY_COLORS: dict[str, str] = {
    "home": "#FF6B6B",       # Red
    "transport": "#4ECDC4",  # Teal
    "groceries": "#45B7D1",  # Blue
    "dining": "#96CEB4",     # Green
    "other": "#FFEAA7",      # Yellow
}


def generate_expense_chart(
    expenses_by_category: dict[str, float],
    year: int,
    month: int,
) -> Path:
    """Generate a pie chart of expenses by category.

    Args:
        expenses_by_category: Dict mapping category keys to total amounts.
        year: The year of the data.
        month: The month of the data.

    Returns:
        Path to the generated PNG image.
    """
    # Prepare data
    categories = []
    amounts = []
    colors = []

    for category, amount in sorted(
        expenses_by_category.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        category_name = CATEGORY_NAMES.get(category, category.title())
        categories.append(f"{category_name}\n${amount:.2f}")
        amounts.append(amount)
        colors.append(CATEGORY_COLORS.get(category, "#CCCCCC"))

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))

    # Create pie chart
    wedges, texts, autotexts = ax.pie(
        amounts,
        labels=None,  # We'll use legend instead
        autopct=lambda pct: f"{pct:.1f}%" if pct > 5 else "",
        colors=colors,
        startangle=90,
        explode=[0.02] * len(amounts),  # Slight separation
    )

    # Style the percentage text
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")
        autotext.set_fontsize(10)

    # Add legend
    legend_labels = [
        f"{CATEGORY_NAMES.get(cat, cat.title())}: ${amt:.2f}"
        for cat, amt in sorted(
            expenses_by_category.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]
    ax.legend(
        wedges,
        legend_labels,
        title="Categories",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
        fontsize=10,
    )

    # Title
    month_name = datetime(year, month, 1).strftime("%B")
    total = sum(amounts)
    ax.set_title(
        f"Expenses for {month_name} {year}\n"
        f"Total: ${total:.2f}",
        fontsize=14,
        fontweight="bold",
    )

    # Add generation date as subtitle
    generated_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5,
        0.02,
        f"Generated on {generated_date}",
        ha="center",
        fontsize=8,
        style="italic",
        color="gray",
    )

    # Adjust layout
    plt.tight_layout()

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        prefix=f"expenses_{year}_{month:02d}_",
    )
    chart_path = Path(temp_file.name)
    temp_file.close()

    fig.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return chart_path
