from django import http

from IHome.utils.response_code import RET


def login_required_json(view_func):
    """
    判断用户是否登陆的装饰器，并返回JSON
    :param view_func: 被装饰的视图函数
    :return: json、view_func
    """

    # 恢复view_func的名字和文档
    def wrapper(request, *args, **kwargs):
        # 如果用户未登陆，返回json数据
        if not request.user.is_authenticated():
            return http.JsonResponse({'errno': RET.SESSIONERR, 'errmsg': '用户未登录'})
        else:
            # 如果用户登陆，进入到view_func中
            return view_func(request, *args, **kwargs)

    return wrapper


class LoginRequiredJSONMixin(object):
    """验证用户是否登陆并返回json的扩展类"""

    @classmethod
    def as_view(self, **initkwargs):
        view = super().as_view(**initkwargs)
        return login_required_json(view)
