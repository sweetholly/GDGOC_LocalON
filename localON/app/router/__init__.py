from .areas import router as areas_router
from .insights import router as insights_router
from .mainpage import router as mainpage_router
from .search import router as search_router

__all__ = ["mainpage_router", "areas_router", "search_router", "insights_router"]
