from django.conf.urls import url
from house import views

urlpatterns = [
    # 处理页面请求
    url(r'^(?P<file_name>.*?\.html)$', views.get_html_file),
    url(r'^$', views.index),
    # 发布房源信息
    url(r'^api/v1.0/houses/$', views.HouseRelease.as_view()),
    # 上传房源图片
    url(r'^api/v1.0/houses/(?P<house_id>\d+)/images/$', views.HouseImageUpload.as_view()),
    # 房屋详情信息
    url(r'^api/v1.0/houses/(?P<house_id>\d+)/$', views.HouseDetail.as_view()),
    # 首页房屋推荐展示
    url(r'^api/v1.0/houses/index/$', views.HouseIndex.as_view()),
    # 首页房屋搜索
    url(r'^api/v1.0/houses/search/$', views.HouseSearch.as_view())
]
