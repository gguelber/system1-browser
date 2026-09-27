# Contributing to eikos-browser

We are excited that you want to contribute to **`eikos-browser`**! Our mission is to make **agentic browser navigation fast, affordable, and accessible to everyone** by replacing expensive cloud token bleed with lightweight, local System-1 decisions.

---

## How You Can Contribute

1. **New Decision Backends:**
   - Add CPU-friendly backends (ONNX Runtime, Laya/ModernBERT, SetFit).
   - Add support for Apple Silicon (CoreML) and AMD ROCm.
2. **Browser Support:**
   - Expand CDP support to Firefox and Safari (WebDriver BiDi).
   - Improve headless containerized browser support (Docker, Playwright bridge).
3. **DOM Pruner Enhancements:**
   - Improve detection of Shadow DOM, iframes, and dynamic canvas buttons.
   - Optimize JS execution speed (currently <3ms).
4. **Benchmarks & Datasets:**
   - Contribute test cases and benchmarks on WebArena, Mind2Web, or real-world enterprise portals (LinkedIn, Government tenders, CRM forms).

---

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/gguelber/eikos-browser.git
cd eikos-browser

# 2. Install editable package with dev dependencies
pip install -e ".[dev]"

# 3. Run unit tests
python -m unittest discover tests
```

---

## Pull Request Guidelines

1. **Fork and Branch:** Create a feature branch with a descriptive name (`feat/onnx-backend`, `fix/shadow-dom-pruner`).
2. **Tests:** Ensure all unit tests pass before submitting.
3. **Commit Messages:** Follow conventional commits (`feat: ...`, `fix: ...`, `docs: ...`).
4. **No Secrets:** Ensure no personal cookies, tokens, or credentials are included in test fixtures.

Thank you for helping democratize AI agent navigation!
