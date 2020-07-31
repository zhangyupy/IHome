from django.core.cache import cache
from django.views.generic import View
from django import http
# Create your views here.
from IHome.utils.response_code import RET
from address.models import Area
import logging

logger = logging.getLogger('django')


class Areas(View):
    def get(self, request):
        """
        1. 查询出所有的城区
        2. 返回数据
        """
        # 增加：判断是否有缓存
        areas_dict = cache.get('areas_dict')
        if not areas_dict:

            # 1. 查询出所有的城区
            try:
                areas = Area.objects.all()
            except Exception as e:
                logger.error(e)
                return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "查询数据错误"})

            # 因为不能直接返回对象数组，所以定义一个列表，去中保存每一个模型所对应的字典信息
            areas_dict = []
            # 遍历进行保存
            for area in areas:
                areas_dict.append({
                    "aid": area.id,
                    "aname": area.name
                })
            # 增加：缓存省级数据
            cache.set('areas_list', areas_dict, 3600)
        # 2. 返回数据
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "ok", 'data': areas_dict})
