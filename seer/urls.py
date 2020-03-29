from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.Home, name='home'),
    path('search', views.Query, name='search'),
    path('doc/id/<document_id>/', views.Document, name='document'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
