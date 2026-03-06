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
    "transport": "#3498DB",  # Blue
    "groceries": "#E67E22",  # Orange
    "dining": "#27AE60",     # Emerald Green
    "coffee": "#8D6E63",     # Coffee Brown
    "shopping": "#E84393",   # Pink
    "other": "#9B59B6",      # Purple
}

# Chart configuration constants
CHART_FIGURE_WIDTH = 12
CHART_FIGURE_HEIGHT = 10
MIN_PERCENTAGE_FOR_LABEL = 5.0  # Only show percentage if >= 5%
PIE_EXPLODE_VALUE = 0.02  # Slight separation between pie slices
PERCENTAGE_TEXT_FONTSIZE = 20
LEGEND_FONTSIZE = 20
TITLE_FONTSIZE = 24
SUBTITLE_FONTSIZE = 8
CHART_DPI = 150  # Resolution for saved image (Telegram requires width+height < 10000)


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
    # Sort once and reuse the same ordering across the pie chart and summary table.
    sorted_expenses = sorted(
        expenses_by_category.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    # Prepare data
    amounts = []
    colors = []

    for category, amount in sorted_expenses:
        # Normalize category key to lowercase for color/name lookup
        category_key = category.lower()
        amounts.append(amount)
        colors.append(CATEGORY_COLORS.get(category_key, "#CCCCCC"))

    # Create figure with room for table on the right
    fig, ax = plt.subplots(figsize=(CHART_FIGURE_WIDTH, CHART_FIGURE_HEIGHT))
    fig.subplots_adjust(left=0.02, right=0.7, top=0.92, bottom=0.05)

    # Create autopct function that shows both percentage and value
    total_amount = sum(amounts)

    def make_autopct(pct: float) -> str:
        """Generate label with percentage and value for pie slices.

        Args:
            pct: Percentage value (0-100) for the pie slice.

        Returns:
            Formatted string with percentage and value if >= MIN_PERCENTAGE_FOR_LABEL,
            empty string otherwise.
        """
        if pct >= MIN_PERCENTAGE_FOR_LABEL:
            amount = pct * total_amount / 100.0
            return f"{pct:.0f}%\n₪{amount:.0f}"
        return ""

    # Create pie chart
    _, _, autotexts = ax.pie(
        amounts,
        labels=None,  # We'll use legend instead
        autopct=make_autopct,
        colors=colors,
        startangle=90,
        explode=[PIE_EXPLODE_VALUE] * len(amounts),  # Slight separation
    )

    # Style the percentage text
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")
        autotext.set_fontsize(PERCENTAGE_TEXT_FONTSIZE)
        autotext.set_horizontalalignment("center")

    # Add legend as a table on separate axes
    table_data = [
        [CATEGORY_NAMES.get(cat.lower(), cat.title()), f"₪{amt:.0f}"]
        for cat, amt in sorted_expenses
    ]

    # Create separate axes for table
    table_ax = fig.add_axes((0.68, 0.25, 0.26, 0.55))
    table_ax.axis("off")

    # Prepare colors for each row
    cell_colors = [
        [CATEGORY_COLORS.get(cat.lower(), "#CCCCCC")] * 2
        for cat, _ in sorted_expenses
    ]

    table = table_ax.table(
        cellText=table_data,
        cellColours=cell_colors,
        cellLoc="left",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(LEGEND_FONTSIZE)
    table.auto_set_column_width([0, 1])
    table.scale(1.2, 2.5)  # Increased row height for more padding

    # Style text in all cells
    for cell in table.get_celld().values():
        cell.set_text_props(color="white", fontweight="bold")

    # Title
    month_name = datetime(year, month, 1).strftime("%B")
    ax.set_title(
        f"Expenses for {month_name} {year}\n"
        f"Total: ₪{total_amount:.0f}",
        fontsize=TITLE_FONTSIZE,
        fontweight="bold",
    )

    # Add generation date as subtitle
    generated_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    fig.text(
        0.5,
        0.01,
        f"Generated on {generated_date}",
        ha="center",
        fontsize=SUBTITLE_FONTSIZE,
        style="italic",
        color="gray",
    )

    # Layout is manually adjusted via subplots_adjust

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
        prefix=f"expenses_{year}_{month:02d}_",
    )
    chart_path = Path(temp_file.name)
    temp_file.close()

    fig.savefig(chart_path, dpi=CHART_DPI, facecolor="white")
    plt.close(fig)

    return chart_path
