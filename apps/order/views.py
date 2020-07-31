import datetime
import json

from django.db.models import Q
from django.views.generic import View
# Create your views here.
from IHome.utils.response_code import RET
from IHome.utils.views import LoginRequiredJSONMixin
from django import http
import logging

from house.models import House
from order.models import Order

logger = logging.getLogger('django')


class HouseOrder(LoginRequiredJSONMixin, View):
    '''房屋订单'''

    def get(self, request):
        """
        1. 去订单的表中查询当前登录用户下的订单
        2. 返回数据
        """
        user = request.user
        # 取当前角色的标识：房客：custom,房东：landlord
        role = request.GET.get("role")
        if role is None:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 判断 role 是否是指定的值
        if role not in ("custom", "landlord"):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        try:
            if "custom" == role:  # 房客订单查询
                orders = Order.objects.filter(user=user).order_by('-create_time')
            elif "landlord" == role:  # 房东订单查询
                # 1. 先查出当前登录用户的所有的房屋, House
                houses = House.objects.filter(user=user)
                # 2. 取到所有的房屋id
                houses_ids = [house.id for house in houses]
                # 3. 从订单表中查询出房屋id在第2步取出来的列表中的房屋
                orders = Order.objects.filter(house_id__in=houses_ids).order_by('-create_time')
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "数据查询错误"})

        orders_dict_li = []

        for order in orders:
            orders_dict_li.append({
                "order_id": order.id,
                "title": order.house.title,
                "img_url": order.house.index_image_url if order.house.index_image_url else "",
                "start_date": order.begin_date.strftime("%Y-%m-%d"),
                "end_date": order.end_date.strftime("%Y-%m-%d"),
                "ctime": order.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "days": order.days,
                "amount": order.amount,
                "status": order.status,
                "comment": order.comment if order.comment else ""
            })
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': {"orders": orders_dict_li}})

    def post(self, request):
        """
           下单
           1. 获取参数
           2. 校验参数
           3. 查询指定房屋是否存在
           4. 判断当前房屋的房主是否是登录用户
           5. 查询当前预订时间是否存在冲突
           6. 生成订单模型，进行下单
           7. 返回下单结果
        """
        # 获取到当前用户
        user = request.user
        # 1. 获取到传入的参数
        params = json.loads(request.body.decode())
        house_id = params.get('house_id')
        start_date_str = params.get('start_date')
        end_date_str = params.get('end_date')

        # 2. 校验参数
        if not all([house_id, start_date_str, end_date_str]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数错误'})

        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            assert start_date < end_date, Exception("开始日期大于结束日期")
            # 计算入住天数
            days = (end_date - start_date).days
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 3. 查询指定房屋是否存在
        try:
            house = House.objects.get(id=house_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': "房屋不存在"})

        # 4. 判断当前房屋的房主是否是当前用户，如果当前用户是房东，不能预订
        if house.user_id == user.id:
            return http.JsonResponse({'errno': RET.ROLEERR, 'errmsg': "不能预订自已的房屋"})

        # 5. 查询该房屋是否有冲突的订单
        count = Order.objects.filter(house_id=house_id, begin_date__lt=end_date, end_date__gt=start_date).count()

        if count > 0:
            return http.JsonResponse({'errno': RET.DATAERR, 'errmsg': "该房屋已被预订"})

        try:
            # 6. 生成订单模型，进行下单
            order = Order.objects.create(user=user, house=house, begin_date=start_date, end_date=end_date,
                                         days=days, house_price=house.price, amount=days * house.price)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "生成订单失败"})

        # 7. 返回下单结果
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': {"order_id": order.id}})

    def put(self, request):
        '''接单拒单
            1. 接受参数：order_id
            2. 通过order_id找到指定的订单，(条件：status="待接单")
            3. 修改订单状态
            4. 保存到数据库
            5. 返回
        '''

        user = request.user
        data_json = json.loads(request.body.decode())
        # 取到订单号
        order_id = data_json.get("order_id")
        action = data_json.get("action")

        if not all([order_id, action]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # accept / reject
        if action not in ("accept", "reject"):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 2. 查询订单
        try:
            order = Order.objects.get(id=order_id, status='WAIT_ACCEPT')
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': "未查询到订单"})

        # 查询当前订单的房东是否是当前登录用户，如果不是，不允许操作
        if user != order.house.user:
            return http.JsonResponse({'errno': RET.ROLEERR, 'errmsg': "不允许操作"})

        # 3 更改订单的状态
        if "accept" == action:
            # 接单
            order.status = "WAIT_COMMENT"
        elif "reject" == action:
            order.status = "REJECTED"
            # 取出原因
            reason = data_json.get("reason")
            if not reason:
                return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "请填写拒单原因"})
            # 保存拒单原因
            order.comment = reason

        # 提交数据库
        try:
            order.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存数据失败"})

        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK"})


class HouseOrderComment(LoginRequiredJSONMixin, View):
    '''订单评论'''

    def put(self, request):
        """
        订单评价
        1. 获取参数
        2. 校验参数
        3. 修改模型
        """

        # 1. 获取参数
        data_json = json.loads(request.body.decode())
        order_id = data_json.get("order_id")
        comment = data_json.get("comment")

        # 2. 2. 校验参数
        if not all([order_id, comment]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        try:
            order = Order.objects.get(id=order_id, status="WAIT_COMMENT")
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "该订单不存在"})

        # 3. 修改模型并且保存到数据库
        order.comment = comment
        order.status = "COMPLETE"

        try:
            order.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存数据失败"})

        # 4. 返回结果
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "ok"})
