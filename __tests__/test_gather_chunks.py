import os
import bs4

os.environ.setdefault("GOOGLE_DRIVE_ROOT_FOLDER_ID", "dummy")
from src import edgar_cli as ec


def test_wrapped_table_not_duplicated():
    html = "<div><table><tr><td>A</td></tr></table></div>"
    soup = bs4.BeautifulSoup(html, "html.parser")
    chunks = ec._gather_chunks(soup)
    tables = [c for c in chunks if c.name == "table"]
    assert len(tables) == 1
