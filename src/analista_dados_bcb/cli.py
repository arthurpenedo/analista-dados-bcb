"""Linha de comando: coletar, perguntar, benchmark."""

from __future__ import annotations

import argparse
import sys
import time

from . import db, llm


def _coletar(args) -> int:
    from . import coleta

    con = db.conectar(args.banco)
    t = time.time()
    contagens = coleta.coletar_tudo(con)
    for tabela, n in contagens.items():
        print(f"{tabela}: {n} linhas")
    print(f"coleta em {time.time() - t:.1f}s -> {args.banco}")
    return 0


def _perguntar(args) -> int:
    from .responder import formatar, perguntar

    r = perguntar(args.banco, " ".join(args.pergunta), args.motor, args.modelo)
    print(formatar(r))
    return 0 if r.ok else 1


def _benchmark(args) -> int:
    from . import benchmark

    if args.motor == "ollama" and not llm.ollama_disponivel():
        print("Ollama não está rodando em localhost:11434 (instale em ollama.com e rode `ollama pull "
              f"{args.modelo}`).")
        return 2
    itens = benchmark.rodar(args.banco, args.motor, args.modelo)
    texto = benchmark.resumo(itens)
    print(texto)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(f"# Benchmark ({args.motor}" + (f", {args.modelo}" if args.motor == "ollama" else "") + ")\n\n")
            f.write("```\n" + texto + "\n```\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="analista-dados-bcb", description=__doc__)
    p.add_argument("--banco", default="bcb.duckdb", help="arquivo DuckDB (padrão: bcb.duckdb)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coletar", help="baixa SGS e Olinda do BCB para o DuckDB").set_defaults(fn=_coletar)

    def com_motor(sp):
        sp.add_argument("--motor", choices=["regras", "ollama", "auto"], default="regras")
        sp.add_argument("--modelo", default=llm.MODELO_PADRAO, help="modelo do Ollama")

    pp = sub.add_parser("perguntar", help="responde uma pergunta em português")
    pp.add_argument("pergunta", nargs="+")
    com_motor(pp)
    pp.set_defaults(fn=_perguntar)
    pb = sub.add_parser("benchmark", help="mede o acerto nas perguntas de referência")
    pb.add_argument("--saida", help="grava o resultado num .md")
    com_motor(pb)
    pb.set_defaults(fn=_benchmark)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
