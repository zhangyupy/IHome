from django.conf.urls import url
from address import views

urlpatterns = [
    # 地区列表
    url(r'api/v1.0/areas/', views.Areas.as_view()),
]
