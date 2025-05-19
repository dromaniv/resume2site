from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_CSS_PATH = Path(__file__).parent / "static" / "style.css"
env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                  autoescape=True)

def json_to_html(data: dict, inline: bool = False) -> str:
    """Render résumé → HTML.  If inline=True, embed CSS in a <style> tag."""
    css_inline = _CSS_PATH.read_text() if inline else ""
    return env.get_template("base.html").render(r=data, inline_css=css_inline)