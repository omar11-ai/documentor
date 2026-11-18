# DocuMentor

**Documentation that knows *why*, not just what.**

Most documentation tools extract signatures and describe types. DocuMentor reads
the code, the git history, and the existing docs, then writes the narrative a
senior engineer would have written — including the architectural decisions and
gotchas that only surface from reading the implementation.

[Live demo →](https://spider-coaching-casa-acoustic.trycloudflare.com) · [MIT licensed](LICENSE)

---

## Why it exists

Under-documented codebases are expensive. They slow onboarding, cause bugs from
misunderstood APIs, and duplicate work that was already solved once.

Generic doc generators fail here because they only read the *current* state of
the code. The context that makes documentation useful — *why* a function
exists, *what broke before*, *which modules churn* — lives in git history and
in the existing docs. DocuMentor reads all three.

## What it does

| Capability | Detail |
|---|---|
| Multi-language AST | Python (libcst), JavaScript, TypeScript, Go, Rust (tree-sitter) |
| Git-history mining | Bug-fix commits, reverts, and churn hotspots become documented gotchas |
| Knowledge graph | Modules, entities, and call relationships persisted as you work |
| Incremental regeneration | Only re-documents what changed |
| Hosted doc browser | Searchable web UI over generated docs |
| CI integration | GitHub Action comments on PRs with fresh docs |
| Fully offline | Runs against a local model — your code never leaves your machine |

## Install

```bash
pip install documentor
```

Or from source:

```bash
git clone https://github.com/omar11-ai/documentor.git
cd documentor
pip install -e ".[dev]"
```

## Use

```bash
documentor init          # create config in any git repo
documentor analyze       # parse code -> knowledge graph
documentor generate      # write contextual Markdown docs
documentor serve         # browse docs in your browser
documentor watch --once  # regenerate changed files only (CI friendly)
```

### Use a local model (optional, recommended for privacy)

```bash
ollama pull qwen2.5-coder:7b
```

DocuMentor talks to Ollama on `localhost:11434`. No API key, no code leaves
your machine. A deterministic offline fallback is built in, so the pipeline
always produces output.

## Architecture

```
documentor/
  analysis/     AST parsers per language, normalised into one model
  core/         config, logging, exceptions, knowledge-graph models
  generation/   doc writers, templates, offline fallback generator
  cli/          Typer + Rich command-line interface
```

Each language parser produces the same intermediate representation, so the
generation layer is language-agnostic. Adding a language means adding a
parser, not touching the writers.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [LICENSE](LICENSE).

---

Built by [Omar Wael](https://github.com/omar11-ai) in Malaysia.
