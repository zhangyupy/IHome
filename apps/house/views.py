import datetime
import json

from django.conf import settings
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import redirect
from django.views.generic import View
from django import http
from fdfs_client.client import Fdfs_client

from IHome.utils import constants
from IHome.utils.views import LoginRequiredJSONMixin
from address.models import Area
from house.models import House, Facility, HouseImage
# 处理页面请求
from IHome.utils.response_code import RET
import logging

from house.utils import house_to_dict
from order.models import Order
from urllib.parse import urlencode

logger = logging.getLogger('django')


def get_html_file(request, file_name):
    # 判断是否是网站的Logo，如果不是，添加前缀
    if file_name != "favicon.ico":
        file_name = "/static/html/" + file_name

    params = request.GET
    if params:
        result = urlencode(params)
        return redirect(file_name + '?{}'.format(result))

    return redirect(file_name)


def index(request):
    return redirect('/static/html/index.html')


class HouseRelease(LoginRequiredJSONMixin, View):
    def post(self, request):
        """
        发布房源
            1. 接收参数/参数校验
            2. 将参数的数据保存到新创建house模型
            3. 保存house模型到数据库
            返回给前端json数据
            {
                "title":"",
                "price":"",
                "area_id":"1",
                "address":"",
                "room_count":"",
                "acreage":"",
                "unit":"",
                "capacity":"",
                "beds":"",
                "deposit":"",
                "min_days":"",
                "max_days":"",
                "facility":["7","8"]
            }
        """

        # 1. 取到参数
        json_dict = json.loads(request.body.decode())
        title = json_dict.get('title')
        price = json_dict.get('price')
        address = json_dict.get('address')
        area_id = json_dict.get('area_id')
        room_count = json_dict.get('room_count')
        acreage = json_dict.get('acreage')
        unit = json_dict.get('unit')
        capacity = json_dict.get('capacity')
        beds = json_dict.get('beds')
        deposit = json_dict.get('deposit')
        min_days = json_dict.get('min_days')
        max_days = json_dict.get('max_days')

        # 1.1 判断是否都有值
        if not all(
                [title, price, address, area_id, room_count, acreage, unit, capacity, beds, deposit, min_days,
                 max_days]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数有误"})
        # 1.2 校验参数格式是否正确
        try:
            price = int(float(price) * 100)
            deposit = int(float(deposit) * 100)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数有误"})
        try:
            area = Area.objects.get(id=area_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数有误"})

        try:
            house = House.objects.create(user=request.user, area=area, title=title, price=price, address=address,
                                         room_count=room_count, acreage=acreage, unit=unit, capacity=capacity,
                                         beds=beds, deposit=deposit, min_days=min_days, max_days=max_days)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "数据库问题"})

        # 获取到当前房屋的设施列表数组
        facilities = json_dict.get("facility")
        facilities = Facility.objects.filter(id__in=facilities)
        house.facilities.add(*facilities)

        # 3.保存house模型到数据库

        try:
            house.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "数据保存错误"})
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "Ok", 'data': {"house_id": house.id}})


class HouseImageUpload(View):
    '''房屋图片'''

    def post(self, request, house_id):
        '''房屋图片上传
            1. 取到上传的图片
            2. 进行七牛云上传
            3. 将上传返回的图片地址存储
            4. 进行返回
        '''
        # 1. 取到上传的图片
        content = request.FILES.get('house_image')
        if content is None:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 2. 查询房屋是否存在
        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': "房屋不存在"})

        # 3. 上传到Fdfs

        try:
            client = Fdfs_client(settings.FDFS_CLIENT_CONF)
            result = client.upload_by_buffer(content.read())
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.THIRDERR, 'errmsg': "上传图片错误"})

        # 4. 初始化房屋的图片模型
        # 上传成功：返回file_id,拼接图片访问URL
        file_id = result.get('Remote file_id')
        url = settings.FDFS_URL + file_id
        try:
            house_image = HouseImage.objects.create(house=house, url=url)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存数据失败"})

        # 判断是否有首页图片
        if not house.index_image_url:
            # 保存图片地址
            house.index_image_url = url
            house.save()

        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': {"url": url}})


class HouseDetail(View):
    def get(self, request, house_id):
        """
        房屋信息详情
        1. 通过房屋id查询出房屋模型
        2. 将数据返回
        """

        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "房屋信息查询失败"})

        house_dict = house_to_dict(house)

        # 返回数据
        return http.JsonResponse(
            {'errno': RET.OK, 'errmsg': "OK", 'data': {"user_id": request.user.id, "house": house_dict}})


class HouseIndex(View):
    '''房屋首页'''

    def get(self, request):

        # 查询房屋信息 按照房屋订单数倒叙排列
        try:
            houses = House.objects.all().order_by('-order_count')
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({})

        # 房屋数量大于最大显示房屋数量,只取五个
        if houses.count() > constants.HOME_PAGE_MAX_HOUSES:
            houses = houses[:constants.HOME_PAGE_MAX_HOUSES]

        # 拼接JSON数据返回
        houses_dict = []
        for house in houses:
            houses_dict.append({
                "house_id": house.id,
                "title": house.title,
                "price": house.price,
                "area_name": house.area.name,
                "img_url": house.index_image_url if house.index_image_url else "",
                "room_count": house.room_count,
                "order_count": house.order_count,
                "address": house.address,
                "user_avatar": house.user.avatar_url if house.user.avatar_url else "",
                "ctime": house.create_time.strftime("%Y-%m-%d")
            })

        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': houses_dict})


class HouseSearch(View):
    '''房屋首页搜索'''

    def get(self, request):
        # 获取所有的参数
        area_id = request.GET.get('aid', '')
        start_date_str = request.GET.get('sd', '')
        end_date_str = request.GET.get('ed', '')
        sort_key = request.GET.get('sk', 'new')  # booking(订单量), price-inc(低到高), price-des(高到低),
        page = request.GET.get('p', '1')

        try:
            page = int(page)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 日期转换
        try:
            start_date = None
            end_date = None
            if start_date_str:
                start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            if end_date_str:
                end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            # 如果开始时间大于或者等于结束时间，就报错
            if start_date and end_date:
                assert start_date < end_date, Exception("开始时间大于结束时间")
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        filters = {}
        # 判断是否传入城区id
        if area_id:
            filters['area_id'] = area_id

        house_query = House.objects.filter(**filters)
        # 过滤已预订的房屋
        conflict_order = None
        try:
            if start_date and end_date:
                conflict_order = Order.objects.filter(begin_date__lte=end_date, end_date__gte=start_date)
            elif start_date:
                conflict_order = Order.objects.filter(end_date__gte=start_date)
            elif end_date:
                conflict_order = Order.objects.filter(begin_date__lte=end_date)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "查询数据错误"})

        if conflict_order:
            # 取到冲突订单的房屋id
            conflict_house_id = [order.house_id for order in conflict_order]
            house_query = house_query.exclude(id__in=conflict_house_id)

        # 根据筛选条件进行排序
        if sort_key == "booking":
            # 订单量排序
            house_query = house_query.order_by('-order_count')
        elif sort_key == "price-inc":
            # 价格从低到高
            house_query = house_query.order_by('price')
        elif sort_key == "price-des":
            # 价格从高到低
            house_query = house_query.order_by('-price')
        else:
            # 创建时间排序
            house_query = house_query.order_by('create_time')

        # 获取分页器对象
        paginator = Paginator(house_query, constants.HOUSE_LIST_PAGE_CAPACITY)
        # 获取指定页房屋数据
        houses = paginator.page(page)
        # 获取列表页总页数
        total_page = paginator.num_pages

        # 将查询结果转成字符串
        houses_dict = []
        for house in houses:
            houses_dict.append({
                "house_id": house.id,
                "title": house.title,
                "price": house.price,
                "area_name": house.area.name,
                "img_url": house.index_image_url if house.index_image_url else "",
                "room_count": house.room_count,
                "order_count": house.order_count,
                "address": house.address,
                "user_avatar": request.user.avatar_url if request.user.is_authenticated else "",
                "ctime": house.create_time.strftime("%Y-%m-%d")
            })

        response_data = {"total_page": total_page, "houses": houses_dict}
        return http.JsonResponse({'errno': RET.OK, 'errmsg': '请求成功', 'data': response_data})
