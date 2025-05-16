from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.services.qa_helper import QAHelper
from app.config import logger
import uuid
import shutil
import os

router = APIRouter()

@router.post("/upload-audio/")
async def upload_audio(
    file: UploadFile = File(...),
    company_id: str = Form(...),
):
    # Save temp file
    call_id = os.path.splitext(file.filename)[0]
    temp_dir = f"temp/{company_id}/{call_id}"
    os.makedirs(temp_dir, exist_ok=True)

    temp_path = f"{temp_dir}/{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Instantiate QAHelper
    job_name = f"qa-{call_id}-{str(uuid.uuid4())}"
    s3_uri = f"s3://testingstt/{file.filename}"

    qa = QAHelper(
        job_name=job_name,
        s3_uri=s3_uri,
        OutputBucketName="testingstt-results",
        InputBucketName="testingstt",
        filename=file.filename,
        filepath=temp_path,
        qa_criteria_file="app/config/qa_criteria.json",
    )

    result = qa.run_pipeline(company_id=company_id, call_id=call_id)
    return JSONResponse(content={"call_id": call_id, "company_id": company_id, "result": result})
