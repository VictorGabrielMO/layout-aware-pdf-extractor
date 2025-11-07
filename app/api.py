from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pipeline import pipeline
import json
import time

app = FastAPI(title="Document Extraction API")

@app.post("/extract")
async def extract_info(
    pdf: UploadFile = File(...),
    label: str = Form(...),
    schema_json: str = Form(...)
):
    try:
        pdf_bytes = await pdf.read()
        schema = json.loads(schema_json)
        
        start_time = time.time()
        result = pipeline(pdf_bytes, label, schema)
        duration = round(time.time() - start_time, 2)
        
        return JSONResponse(content={
            "success": True,
            "runtime_seconds": duration,
            "result": result
        })
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

# Mount static frontend files
app.mount("/", StaticFiles(directory="static", html=True), name="static")
