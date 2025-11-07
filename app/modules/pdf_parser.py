import fitz  # PyMuPDF
from typing import List, Dict, Any


class PDFParser:
    """
    Componente responsável por extrair texto e posições (bboxes)
    de arquivos PDF de página única.
    """

    @staticmethod
    def extract_text_blocks(pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extrai blocos de texto e coordenadas do PDF.
        Cada bloco contém:
            {
              "text": str,
              "bbox": (x0, y0, x1, y1)
            }
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            raise ValueError("PDF sem páginas")

        page = doc[0]
        blocks = page.get_text("blocks")  # retorna blocos com bounding boxes
        results = []
        for block in blocks:
            x0, y0, x1, y1, text, *_ = block
            clean_text = text.strip().replace("\n", " ")
            if clean_text:
                results.append({
                    "text": clean_text,
                    "bbox": (x0, y0, x1, y1)
                })
        return results

    @staticmethod
    def extract_lines(pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extrai linhas (dividindo os blocos) para granularidade maior.
        Cada linha contém:
            {
              "text": str,
              "bbox": (x0, y0, x1, y1)
            }
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        lines = []
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, *_ = block
            for line in text.splitlines():
                line = line.strip()
                if line:
                    lines.append({
                        "text": line,
                        "bbox": (x0, y0, x1, y1)
                    })
        return lines

    @staticmethod
    def extract_plain_text(pdf_bytes: bytes) -> str:
        """
        Retorna todo o texto concatenado do PDF.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        return page.get_text("text").strip()

