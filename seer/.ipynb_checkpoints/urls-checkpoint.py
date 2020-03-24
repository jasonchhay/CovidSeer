from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.Home, name='home'),
    path('query/', views.Query, name='query'),
    path('search/', views.Search, name='search'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
