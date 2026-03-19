"""Style constants matching CORPFT-010522 SDS template."""

from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

# Page setup
PAGE_WIDTH_INCHES = 8.5
PAGE_HEIGHT_INCHES = 11
MARGIN_INCHES = 1.0

# Fonts
HEADING_FONT = "Arial"
BODY_FONT = "Times New Roman"
CODE_FONT = "Courier New"

# Font sizes
HEADING1_SIZE = Pt(16)
HEADING2_SIZE = Pt(14)
HEADING3_SIZE = Pt(12)
HEADING4_SIZE = Pt(11)
HEADING5_SIZE = Pt(10)
BODY_SIZE = Pt(12)
TABLE_HEADER_SIZE = Pt(10)
TABLE_BODY_SIZE = Pt(10)
CODE_SIZE = Pt(10)

# Colors
TABLE_HEADER_FILL = "D5E8F0"  # Light blue
TBC_HIGHLIGHT_COLOR = 7  # Yellow highlight index for WdColorIndex
TABLE_BORDER_COLOR = "999999"

# Spacing
BODY_SPACE_AFTER = Pt(6)
HEADING_SPACE_BEFORE = Pt(12)
HEADING_SPACE_AFTER = Pt(6)
