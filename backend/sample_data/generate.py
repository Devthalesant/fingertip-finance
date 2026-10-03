"""Gera os arquivos sintéticos: uv run python -m sample_data.generate [pasta]

Determinístico: rodar de novo gera os mesmos bytes. A pasta padrão (sample_data/out/)
é ignorada pelo Git; os testes geram numa pasta temporária.
"""

import sys
from pathlib import Path

from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows

DEFAULT_OUT = Path(__file__).parent / "out"


def generate(out_dir: Path = DEFAULT_OUT) -> list[Path]:
    return [write_movement_statement(movement_rows(), out_dir / "movimentacao-demo.xlsx")]


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    for path in generate(out):
        print(path)
