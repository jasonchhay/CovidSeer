from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.Home, name='home'),
    path('search', views.Query, name='search'),
    path('doc/id/<document_id>/', views.Document, name='document'),
    path('doc/json/id/<document_id>.json', views.DocumentJson, name='document_json'),

    # API
    path('api/search/<query>/<int:page>', views.search, name='api_search_index'),
    path('api/doc/similar_papers/<document_id>', views.get_recommendations, name='api_get_recommendations'),


] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
