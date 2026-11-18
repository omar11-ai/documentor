"""FastAPI web server for documentation browsing."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import markdown
import frontmatter

from documentor.core.config import get_config
from documentor.core.logging import get_logger

logger = get_logger(__name__)


def create_app(docs_dir: Path) -> FastAPI:
    """Create FastAPI application for documentation browsing."""
    app = FastAPI(
        title="DocuMentor Documentation",
        description="AI-generated contextual documentation",
        version="0.1.0",
    )

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Templates
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir)) if templates_dir.exists() else None

    # Markdown processor
    md = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "codehilite"])

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render index page with module list."""
        modules = get_modules(docs_dir)

        if templates:
            return templates.TemplateResponse(
                request,
                "index.html",
                {"request": request, "modules": modules, "title": "DocuMentor Documentation"},
            )
        else:
            # Fallback simple HTML
            return HTMLResponse(generate_index_html(modules))

    @app.get("/module/{module_name}", response_class=HTMLResponse)
    async def module_page(request: Request, module_name: str):
        """Render module documentation page."""
        module_file = docs_dir / f"{module_name}.md"
        if not module_file.exists():
            raise HTTPException(404, "Module not found")

        content = module_file.read_text(encoding="utf-8")
        html_content = md.convert(content)

        # Get entity docs for this module
        module_dir = docs_dir / module_name
        entities = []
        if module_dir.exists():
            for md_file in module_dir.glob("*.md"):
                entities.append({
                    "name": md_file.stem,
                    "path": f"/module/{module_name}/{md_file.stem}",
                })

        if templates:
            return templates.TemplateResponse(
                request,
                "module.html",
                {
                    "request": request,
                    "module_name": module_name,
                    "content": html_content,
                    "entities": entities,
                    "title": f"{module_name} - DocuMentor",
                },
            )
        else:
            return HTMLResponse(generate_module_html(module_name, html_content, entities))

    @app.get("/module/{module_name}/{entity_name}", response_class=HTMLResponse)
    async def entity_page(request: Request, module_name: str, entity_name: str):
        """Render entity documentation page."""
        entity_file = docs_dir / module_name / f"{entity_name}.md"
        if not entity_file.exists():
            raise HTTPException(404, "Entity not found")

        content = entity_file.read_text(encoding="utf-8")
        html_content = md.convert(content)

        if templates:
            return templates.TemplateResponse(
                request,
                "entity.html",
                {
                    "request": request,
                    "module_name": module_name,
                    "entity_name": entity_name,
                    "content": html_content,
                    "title": f"{entity_name} - DocuMentor",
                },
            )
        else:
            return HTMLResponse(generate_entity_html(module_name, entity_name, html_content))

    @app.get("/search")
    async def search(q: str):
        """Search documentation."""
        results = search_docs(docs_dir, q)
        return {"results": results}

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok"}

    return app


def get_modules(docs_dir: Path) -> list[dict]:
    """Get list of documented modules."""
    modules = []
    for md_file in docs_dir.glob("*.md"):
        if md_file.name == "index.md":
            continue
        try:
            post = frontmatter.load(md_file)
            modules.append({
                "name": md_file.stem,
                "title": post.metadata.get("title", md_file.stem),
                "description": post.metadata.get("description", "")[:200],
            })
        except Exception:
            modules.append({
                "name": md_file.stem,
                "title": md_file.stem,
                "description": "",
            })
    return sorted(modules, key=lambda m: m["name"])


def search_docs(docs_dir: Path, query: str) -> list[dict]:
    """Simple search across documentation files."""
    results = []
    query_lower = query.lower()

    for md_file in docs_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                # Find context around match
                idx = content.lower().index(query_lower)
                start = max(0, idx - 100)
                end = min(len(content), idx + 200)
                snippet = content[start:end].replace("\n", " ")

                rel_path = md_file.relative_to(docs_dir)
                results.append({
                    "path": str(rel_path),
                    "module": rel_path.parts[0] if len(rel_path.parts) > 1 else rel_path.stem,
                    "snippet": snippet,
                })
        except Exception:
            continue

    return results[:20]


def generate_index_html(modules: list[dict]) -> str:
    """Generate simple index HTML."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>DocuMentor Documentation</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
        h1 { color: #1a1a2e; }
        .module { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
        .module h2 { margin: 0 0 0.5rem; }
        .module a { color: #2563eb; text-decoration: none; }
        .module a:hover { text-decoration: underline; }
        .description { color: #666; font-size: 0.9rem; }
    </style>
</head>
<body>
    <h1>DocuMentor Documentation</h1>
    <p>AI-generated contextual documentation for your codebase.</p>
"""
    for module in modules:
        html += f"""
    <div class="module">
        <h2><a href="/module/{module['name']}">{module['title']}</a></h2>
        <p class="description">{module['description']}</p>
    </div>
"""
    html += "</body></html>"
    return html


def generate_module_html(module_name: str, content: str, entities: list[dict]) -> str:
    """Generate simple module HTML."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{module_name} - DocuMentor</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; }}
        h1 {{ color: #1a1a2e; }}
        .nav {{ margin-bottom: 2rem; }}
        .nav a {{ color: #2563eb; text-decoration: none; }}
        .entities {{ margin-top: 2rem; }}
        .entity {{ border-left: 3px solid #2563eb; padding-left: 1rem; margin: 0.5rem 0; }}
        .content {{ line-height: 1.6; }}
        pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        code {{ background: #f5f5f5; padding: 0.2rem 0.4rem; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="nav"><a href="/">← Index</a></div>
    <h1>{module_name}</h1>
    <div class="content">{content}</div>
"""
    if entities:
        html += '<div class="entities"><h2>Entities</h2>'
        for entity in entities:
            html += f'<div class="entity"><a href="{entity["path"]}">{entity["name"]}</a></div>'
        html += '</div>'

    html += "</body></html>"
    return html


def generate_entity_html(module_name: str, entity_name: str, content: str) -> str:
    """Generate simple entity HTML."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{entity_name} - DocuMentor</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; }}
        h1 {{ color: #1a1a2e; }}
        .nav {{ margin-bottom: 2rem; }}
        .nav a {{ color: #2563eb; text-decoration: none; }}
        .content {{ line-height: 1.6; }}
        pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        code {{ background: #f5f5f5; padding: 0.2rem 0.4rem; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="nav"><a href="/">← Index</a> / <a href="/module/{module_name}">{module_name}</a></div>
    <h1>{entity_name}</h1>
    <div class="content">{content}</div>
</body></html>
"""