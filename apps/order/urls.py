from django.conf.urls import url
from order import views

urlpatterns = [
    # 下订单/查询订单/接单&拒单
    url(r'^api/v1.0/orders/$', views.HouseOrder.as_view()),
    # 订单评价
    url(r'^api/v1.0/orders/comment/$', views.HouseOrderComment.as_view())
]
