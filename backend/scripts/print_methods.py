import sys, inspect
sys.path.insert(0, '.')
from backend.services.analytics_service import AnalyticsService

print("get_top_regions source:")
print(inspect.getsource(AnalyticsService.get_top_regions))

print("get_top_regions_bu source:")
print(inspect.getsource(AnalyticsService.get_top_regions_bu))
