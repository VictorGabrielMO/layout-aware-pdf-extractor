from openai import OpenAI
from typing import Dict, Any, List
import json

class LLMProcessor():
	
	@staticmethod
	def build_prompt(cleaned_blocks: List[Dict[str, Any]], label: str, schema: Dict[str, str]) -> str:
		"""
		Constrói o prompt completo para o LLM, incluindo regex.
		"""
		blocks_text = "\n".join(
			f"{i+1}. \"{b['text']}\"" for i, b in enumerate(cleaned_blocks)
		)
		schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

		prompt = f"""
Você é um extrator de informações estruturadas em documentos.

Você receberá os blocos enumerados de um documento e o rótulo do tipo desse documento.
Receberá também um schema que indica as informações a serem extraídas.

Para cada campo do schema, retorne:
- "valor": o valor extraído deste PDF.
- "regex": uma expressão regular genérica capaz de capturar esse tipo de valor
  em documentos semelhantes, **não apenas este valor específico**.
- "bloco": indica o número do bloco em que o valor foi extraído.

A regex deve:
- Ser genérica o suficiente para capturar valores similares em diferentes documentos.
- Ser escrita em formato Python re (com `(?m)` se necessário).

Responda em JSON no formato:
{{
  "campo": {{
    "valor": "...",
    "regex": "...", // Apenas adicione "regex" caso "extrair_regex" for verdadeiro para o campo
    "bloco": "..."
  }}
}}

Label:
{label}

Obs: Os blocos estão ordenados pela ordem usual de leitura.
Blocos:
{blocks_text}

Schema:
{schema_json}
"""
		return prompt.strip()

	@staticmethod
	def call_llm(prompt: str, openai_client: OpenAI) -> Dict[str, Any]:
		"""
		Chama o modelo LLM para gerar os valores e regexes (ou apenas valores).
		"""
		response = openai_client.chat.completions.create(
			model="gpt-5-mini",
			messages=[{"role": "user", "content": prompt}],
			response_format={"type": "json_object"}
		)
		try:
			return json.loads(response.choices[0].message.content)
		except Exception:
			return {"error": "LLM response parse error", "raw": response.choices[0].message.content}
