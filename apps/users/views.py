import json

from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import render
from django.views.generic import View
from django import http
from fdfs_client.client import Fdfs_client
from redis import StrictRedis
from IHome.utils.response_code import RET
from django_redis import get_redis_connection
import logging

from IHome.utils.views import LoginRequiredJSONMixin
from house.models import House
from users.models import User

logger = logging.getLogger('django')


class Register(View):
    '''用户注册'''

    def post(self, request):
        """
        用户注册
        1. 获取参数并进行参数校验
        2. 从redis中获取指定手机号对应的短信验证码的
        3. 校验验证码
        4. 初始化 user 模型，并设置数据并添加到数据库
        5. 保存当前用户的状态
        6. 返回注册的结果
        :return:
        """
        # 1. 获取参数并进行参数校验
        data_dict = json.loads(request.body.decode())
        mobile = data_dict.get("mobile")  # 获取手机号
        phonecode = data_dict.get("phonecode")  # 获取短信验证码
        password = data_dict.get("password")  # 密码
        password2 = data_dict.get('password2')  # 密码2

        # 判断参数是否完整
        if not all([mobile, phonecode, password, password2]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数不全"})

        # 判断密码是否一致
        if password != password2:
            return http.JsonResponse({'errno': RET.PWDERR, 'errmsg': "密码不一致"})

        # 2. 从redis中获取指定手机号对应的短信验证码的
        redis_conn = get_redis_connection('verify_code')  # type: StrictRedis
        try:
            sms_code = redis_conn.get("SMS_" + mobile)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "获取本地验证码失败"})

        if not sms_code:
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': "短信验证码过期"})

        # 3. 校验验证码
        if phonecode != sms_code.decode():
            return http.JsonResponse({'errno': RET.DATAERR, 'errmsg': "短信验证码错误"})

        # 4. 初始化 user 模型，并设置数据并添加到数据库
        try:
            user = User.objects.create_user(username=mobile, mobile=mobile, password=password)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DATAERR, 'errmsg': "用户创建失败"})

        # 状态保持
        login(request, user)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "注册成功"})


class Session(View):
    '''用户状态查询'''

    def get(self, request):
        """
        检测用户是否登录，如果登录，则返回用户的名和用户id
        """
        user = request.user
        if user.is_authenticated:
            data = {'user_id': user.id, 'name': user.username}
            return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': data})
        else:
            return http.JsonResponse({'errno': RET.SESSIONERR, 'errmsg': '用户未登录'})


class Logout(LoginRequiredJSONMixin,View):
    '''用户退出'''

    def delete(self, request):
        """
        1. 清除session中的对应登录之后保存的信息
        """
        # 清楚session
        logout(request)
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "用户已退出"})


class Login(View):
    '''登录'''

    def post(self, request):
        """
        用户登录
        1. 获取参数并对参数进行校验
        2. 从数据库查询出指定的用户
        3. 校验密码
        4. 保存用户登录状态
        5. 返回结果
        """
        # 1. 获取参数和判断是否有值
        data_dict = json.loads(request.body.decode())

        mobile = data_dict.get("mobile")
        password = data_dict.get("password")

        if not all([mobile, password]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数不全"})

        # 2. 从数据库查询出指定的用户
        try:
            user = User.objects.get(mobile=mobile)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "用户不存在"})

        # 3. 校验密码
        if not user.check_password(password):
            return http.JsonResponse({'errno': RET.PWDERR, 'errmsg': "密码错误"})

        # 4. 保存用户登录状态
        login(request, user)

        # 5. 返回结果
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "登录成功"})


class UserAvatar(LoginRequiredJSONMixin, View):
    '''
            {
            "data": {
                "avatar_url": "http://oyucyko3w.bkt.clouddn.com/FmWZRObXNX6TdC8D688AjmDAoVrS"
            },
            "errno": "0",
            "errmsg": "OK"
        }
    '''

    def post(self, request):
        """
            1. 获取到上传的文件
            2. 再将文件上传到FastDFs
            3. 将头像信息保存到用户模型
            4. 返回上传的结果<avatar_url>
            :return:
            """

        # 1. 获取到上传的文件
        content = request.FILES.get('avatar')
        if content is None:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数错误"})

        # 2. 再将文件上传到FastDFs
        # 创建客户端对象
        # 调用上传函数
        try:
            client = Fdfs_client(settings.FDFS_CLIENT_CONF)
            result = client.upload_by_buffer(content.read())
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.THIRDERR, 'errmsg': "上传图片错误"})

        # 上传成功：返回file_id,拼接图片访问URL
        file_id = result.get('Remote file_id')
        url = settings.FDFS_URL + file_id

        # 3. 将头像信息保存到用户模型
        user = request.user
        user.avatar_url = url
        user.save()

        # 4. 返回上传的结果<avatar_url>
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': {"avatar_url": url}})


class UserProfile(LoginRequiredJSONMixin, View):
    '''用户信息获取修改'''

    def get(self, request):
        '''获取用户信息
        1.获取当前登录用户
        2.返回用户信息
        '''

        # 1.获取当前登录用户
        user = request.user
        # 2.返回用户信息
        data = {
            "name": user.username,
            "avatar_url": user.avatar_url,
            "mobile": user.mobile
        }
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': data})

    def post(self, request):
        """
        1. 获取到传入参数
        2. 将用户名信息更新到当前用户的模型中
        3. 返回结果
        """

        # 1. 获取到传入参数
        data_dict = json.loads(request.body.decode())
        name = data_dict.get("name")
        if name is None:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "参数不完整"})

        # 2. 获取当前登录用户/更新用户名
        user = request.user
        try:

            user.username = name
            user.save()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存数据失败"})

        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK"})


class AuthProfile(LoginRequiredJSONMixin, View):
    '''用户真实信息获取和设置'''

    def get(self, request):
        """
        1. 取到当前登录用户
        2. 获取当前用户的认证信息
        3. 返回信息
        """
        # 1. 取到当前登录用户
        user = request.user

        # 2. 获取当前用户的认证信息
        auth_dict = {
            "real_name": user.real_name,
            "id_card": user.id_card
        }
        # 3. 返回信息
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': auth_dict})

    def post(self, request):
        """
        1. 取到当前登录用户
        2. 取到传过来的认证的信息
        3. 更新用户的认证信息
        4. 返回结果
        """

        # 1. 取到当前登录用户
        user = request.user

        # 2. 取到传过来的认证的信息
        data_dict = json.loads(request.body.decode())
        real_name = data_dict.get("real_name")
        id_card = data_dict.get("id_card")

        # 3. 更新用户的认证信息
        user.real_name = real_name
        user.id_card = id_card
        try:
            user.save()
        except Exception as e:
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存数据失败"})

        # 4. 返回结果
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK"})


class UserHouse(LoginRequiredJSONMixin, View):
    '''用户房屋信息'''

    def get(self, request):
        """
        获取用户房屋列表
        1. 获取当前登录用户
        2. 查询房屋数据返回数据
        """
        user = request.user
        try:
            houses = user.house_set.all()
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "查询数据失败"})

        houses_dict = []
        for house in houses:
            houses_dict.append({
                "house_id": house.id,
                "title": house.title,
                "price": house.price,
                "area_name": house.area.name,
                "img_url": house.index_image_url,
                "room_count": house.room_count,
                "order_count": house.order_count,
                "address": house.address,
                "user_avatar": house.user.avatar_url,
                "ctime": house.create_time.strftime("%Y-%m-%d")
            })
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "OK", 'data': houses_dict})
