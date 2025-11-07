from modules.pdf_parser import PDFParser
from modules.preprocessor import Preprocessor
from modules.layout_memory import LayoutMemory
from modules.llm_processor import LLMProcessor
from openai import OpenAI
import json
import os

def pipeline(pdf_bytes: bytes, label: str, schema: dict):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    layout_memory = LayoutMemory()
    
    # 1. Parse pdf
    pdf_blocks = PDFParser.extract_text_blocks(pdf_bytes)
    pdf_text = PDFParser.extract_plain_text(pdf_bytes)
    
    # 2. Checks if the resquest is cached
    schema_str = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    cached_result = layout_memory.get_cached_result(pdf_text, schema_str)
    if cached_result:
        return cached_result
    
    # 3. Preprocess pdf blocks
    preprocessed_blocks = Preprocessor.preprocess_blocks(pdf_blocks)
    
    # 4. Check for wich fields we can avoid a LLM fallback using layout memory heuristic
    llm_avoided_fields, llm_fallback_fields = layout_memory.layout_memory_search(label, schema, preprocessed_blocks)
    if not llm_fallback_fields:
        return llm_avoided_fields
    
    # 5. LLM fallback
    prompt = LLMProcessor.build_prompt(preprocessed_blocks, label, llm_fallback_fields)
    response = LLMProcessor.call_llm(prompt, client)

    # 6. Process LLM response
    output = llm_avoided_fields
    for field, result in response.items():
        value = result.get("valor")
        regex = result.get("regex")
        block_i = result.get("bloco")
        
        if not value:
            output[field] = None
            continue
        
        output[field] = value
        
        if not block_i:
            continue
        
        field_block = preprocessed_blocks[int(block_i) - 1]
        layout_memory.update_field(label, field, field_block["px"], field_block["py"], regex)

    # 7. Caches result
    layout_memory.set_cached_result(pdf_text, schema_str, output, label)
    return output