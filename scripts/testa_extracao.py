"""Roda a extração contra links reais e reporta a taxa de sucesso.

Uso: python scripts/testa_extracao.py links.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from verdade_ou_fake.ingestao import extrair_noticia

def main(caminho_lista: str) -> None:
    links = Path(caminho_lista).read_text(encoding="utf-8").split()
    sucessos = 0
    for link in links:
        noticia = extrair_noticia(link)
        if noticia is None:
            print(f"FALHOU  {link}")
        else:
            sucessos += 1
            print(f"OK      {link} ({len(noticia.texto)} chars) — {noticia.titulo[:60]}")
    print(f"\nTaxa de extração: {sucessos}/{len(links)}")


if __name__ == "__main__":
    main(sys.argv[1])
