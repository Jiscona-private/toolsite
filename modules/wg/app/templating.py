from pathlib import Path

from fastapi.templating import Jinja2Templates

# A standalone module (rather than living in main.py) so both main.py and
# app/auth.py can import it without a circular import between them.
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
