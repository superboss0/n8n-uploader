from fastapi import APIRouter

from .processor_api import router as processor_api_router
from .xlsx_api import router as xlsx_api_router

router = APIRouter()
router.include_router(processor_api_router)
router.include_router(xlsx_api_router)
