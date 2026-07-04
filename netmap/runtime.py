"""Configuração de runtime: localizar o binário ``dot`` do Graphviz.

A biblioteca ``diagrams`` invoca o executável ``dot``; quando a aplicação é
empacotada, o Graphviz pode ser distribuído junto (``<recursos>/graphviz/bin``,
preenchido no build via ``GRAPHVIZ_HOME``). Caso contrário usa-se o caminho
configurado em ``config.ini`` ou o ``dot`` do sistema.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .paths import resource_dir


def configure_graphviz(dot_path: str | None = None) -> str | None:
    """Garante que o executável ``dot`` fica acessível no PATH.

    Ordem de resolução: caminho configurado → Graphviz empacotado →
    ``dot`` já presente no PATH do sistema. Devolve o caminho resolvido do
    ``dot`` ou ``None`` se não existir (o mapa fica indisponível, a aplicação
    continua a funcionar).
    """
    exe = "dot.exe" if os.name == "nt" else "dot"
    candidates: list[Path] = []
    if dot_path:
        p = Path(dot_path)
        candidates.append(p if p.name.startswith("dot") else p / exe)
    candidates.append(resource_dir() / "graphviz" / "bin" / exe)
    for candidate in candidates:
        if candidate.is_file():
            os.environ["PATH"] = (
                str(candidate.parent) + os.pathsep + os.environ.get("PATH", "")
            )
            return str(candidate)
    return shutil.which("dot")
