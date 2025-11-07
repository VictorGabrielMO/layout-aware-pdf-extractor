import re
from typing import Dict, Any, List
from openai import OpenAI


class Preprocessor:
    """
    Normaliza e estrutura os blocos de texto do PDF,
    preparando o contexto e o prompt para o LLM.
    Também é responsável por reduzir custo (enviar só blocos relevantes).
    """
    
    @staticmethod
    def normalize_block_text(text: str) -> str:
        """
        Limpa e padroniza o texto dos blocos.
        """
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def preprocess_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Limpa e ordena os blocos de texto por posição vertical.
        """
        cleaned = []
        for b in blocks:
            if b["text"].strip():
                cleaned.append({
                    "text": Preprocessor.normalize_block_text(b["text"]),
                    "bbox": b["bbox"]
                })
        # Ordena por posição Y (ordem de leitura)
        cleaned.sort(key=lambda x: x["bbox"][1])
        return cleaned

    from typing import List, Dict, Any

class Preprocessor:
    @staticmethod
    def normalize_block_text(text: str) -> str:
        """
        Normaliza o texto do bloco removendo espaços extras e caracteres invisíveis.
        """
        return " ".join(text.split())

    @staticmethod
    def preprocess_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Limpa e ordena os blocos de texto na ordem natural de leitura:
        - De cima para baixo (y0)
        - Da esquerda para a direita (x0) em caso de empate vertical
        - Adiciona também as coordenadas centrais (px, py) para uso posterior
        """
        cleaned = []
        for b in blocks:
            text = b.get("text", "").strip()
            if not text:
                continue

            x0, y0, x1, y1 = b["bbox"]
            px = (x0 + x1) / 2
            py = (y0 + y1) / 2

            cleaned.append({
                "text": Preprocessor.normalize_block_text(text),
                "bbox": (x0, y0, x1, y1),
                "px": px,
                "py": py
            })

        # Ordena primeiro por Y (topo -> base), depois por X (esquerda -> direita)
        cleaned.sort(key=lambda x: (round(x["bbox"][1], 3), round(x["bbox"][0], 3)))

        return cleaned
