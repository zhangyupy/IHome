import json
import random
import re

from django import http
import logging
from django.views.generic.base import View
from django_redis import get_redis_connection
from redis import StrictRedis

from IHome.libs.captcha.captcha import captcha
from IHome.libs.yuntongxun.ccp_sms import CCP
from IHome.utils import constants
from IHome.utils.response_code import RET, error_map
from users.models import User

logger = logging.getLogger('django')


class ImageCodeView(View):
    def get(self, request):
        """
        1. 获取传入的验证码编号，并判断编号是否有值
        2. 生成图片验证码
        3. 保存编号和其对应的图片验证码内容到redis
        4. 返回验证码图片
        :return: image
        """
        # 1.获取传入的验证码编号，并判断编号是否有值
        cur = request.GET.get('cur')  # 当前图片验证码UUID
        pre = request.GET.get("pre")  # 前一个图片验证码UUID
        # 如果当前图片验证码UUID为None,直接返回参数有误响应
        if cur is None:
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': error_map[RET.PARAMERR]})

        # 2.生成图片验证码
        text, image = captcha.generate_captcha()
        logger.info(text)

        # 3.保存编号和其对应的图片验证码内容到redis
        redis_con = get_redis_connection('verify_code')  # type: StrictRedis
        if pre:
            # 3.1删除之前存储的验证码图片
            redis_con.delete("ImageCode_" + pre)
        redis_con.setex("ImageCode_" + cur, constants.IMAGE_CODE_REDIS_EXPIRES, text)

        # 4. 返回验证码图片
        return http.HttpResponse(image, content_type='image/jpg')


class SMSCodeView(View):
    """短信验证码"""

    def post(self, request):
        '''
        1. 接收参数并校验参数
        2. 校验手机号是正确
        3. 通过传入的图片验证码UUID去redis中查询真实的图片验证码内容
        4. 进行验证码内容的比对
        5. 生成发送短信的内容并发送短信
        6. redis中保存短信验证码内容
        7. 返回发送成功的响应
        :param request:
        :return:
        '''
        # 1. 接收参数并校验参数
        data_dict = json.loads(request.body.decode())
        mobile = data_dict.get("mobile")  # 手机号
        image_code = data_dict.get("image_code")  # 图片验证码
        image_code_id = data_dict.get("image_code_id")  # 图片验证码UUID

        if not all([mobile, image_code_id, image_code]):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': '参数不全'})

        # 2. 校验手机号是正确
        if not re.match("^1[3578][0-9]{9}$", mobile):
            return http.JsonResponse({'errno': RET.PARAMERR, 'errmsg': "手机号格式不正确"})

        # 3. 通过传入的图片验证码UUID去redis中查询真实的图片验证码内容
        redis_con = get_redis_connection('verify_code')  # type: StrictRedis
        try:
            real_image_code = redis_con.get("ImageCode_" + image_code_id)
            # 如果能够取出来值，删除redis中缓存的内容
            if real_image_code:
                redis_con.delete("ImageCode_" + image_code_id)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "获取图片验证码失败"})
        # 3.1 判断验证码是否存在，已过期
        if not real_image_code:
            return http.JsonResponse({'errno': RET.NODATA, 'errmsg': "验证码已过期"})

        # 4. 进行验证码内容的比对
        if image_code.lower() != real_image_code.decode().lower():
            return http.JsonResponse({'errno': RET.DATAERR, 'errmsg': "验证码输入错误"})

        # 4.1 校验该手机是否已经注册
        try:
            user = User.objects.get(mobile=mobile)
        except Exception as e:
            user = None  # 如果查询时出现错误，也需要给user初始化，如果不初始化，会报未定义的异常
            logger.error(e)
        if user:
            return http.JsonResponse({'errno': RET.DATAEXIST, 'errmsg': "该手机已被注册"})

        # 5. 生成发送短信的内容并发送短信
        result = random.randint(0, 999999)
        sms_code = "%06d" % result
        logger.info("短信验证码的内容：%s" % sms_code)
        # result = CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], "1")
        # if result != 1:
        #     return http.JsonResponse({'errno': RET.THIRDERR, 'errmsg': "THIRDERR"})

        # 6. redis中保存短信验证码内容
        try:
            redis_con.set("SMS_" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
        except Exception as e:
            logger.error(e)
            return http.JsonResponse({'errno': RET.DBERR, 'errmsg': "保存短信验证码失败"})

        # 7. 返回发送成功的响应
        return http.JsonResponse({'errno': RET.OK, 'errmsg': "发送成功"})



