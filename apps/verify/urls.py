from django.conf.urls import url
from verify import views

urlpatterns = [
    # 图片验证码
    url(r'^api/v1.0/imagecode/$', views.ImageCodeView.as_view(), name='image'),
    # 短信验证码
    url(r'^api/v1.0/smscode/$', views.SMSCodeView.as_view(), name='smscode')
]
