"""
CLI entrypoint for system1-browser.
"""
import argparse
import json
import sys
from system1_browser import BrowserCoprocessor
from system1_browser.server.mcp_server import main as run_mcp

def main():
    parser = argparse.ArgumentParser(description="system1-browser: Pluggable System-1 Browser Navigation Coprocessor")
    parser.add_argument("--backend", "-b", choices=["julia", "eikos", "auto", "mock"], default="julia", help="Motor de decisão (padrão: julia)")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ser executado")

    # Run command
    run_parser = subparsers.add_parser("run", help="Executa uma sub-meta autônoma")
    run_parser.add_argument("--goal", "-g", required=True, help="Sub-meta em linguagem natural")
    run_parser.add_argument("--max-steps", "-s", type=int, default=8, help="Máximo de passos")

    # Inspect command
    inspect_parser = subparsers.add_parser("inspect", help="Inspeciona a página ativa e retorna o DOM podado")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Inicia o servidor MCP via stdio")

    args = parser.parse_args()

    if args.command == "run":
        coprocessor = BrowserCoprocessor(backend=args.backend)
        res = coprocessor.execute_subgoal(goal=args.goal, max_steps=args.max_steps)
        print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
    elif args.command == "inspect":
        from system1_browser.server.mcp_server import system1_browser_inspect
        res = system1_browser_inspect()
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.command == "serve":
        run_mcp()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
