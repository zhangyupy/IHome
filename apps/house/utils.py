from IHome.utils import constants
from order.models import Order


def house_to_dict(house):
    """将详细信息转换为字典数据"""
    house_dict = {
        "hid": house.id,
        "user_id": house.user.id,
        "user_name": house.user.username,
        "user_avatar": house.user.avatar_url if house.user.avatar_url else "",
        "title": house.title,
        "price": house.price,
        "address": house.address,
        "room_count": house.room_count,
        "acreage": house.acreage,
        "unit": house.unit,
        "capacity": house.capacity,
        "beds": house.beds,
        "deposit": house.deposit,
        "min_days": house.min_days,
        "max_days": house.max_days,
    }

    # 房屋图片
    img_urls = []
    for image in house.houseimage_set.all():
        img_urls.append(image.url)
    house_dict["img_urls"] = img_urls

    # 房屋设施
    facilities = []
    for facility in house.facilities.all():
        facilities.append(facility.id)
    house_dict["facilities"] = facilities

    # # 评论信息
    comments = []
    orders = Order.objects.filter(house=house, status="COMPLETE").order_by('-update_time')
    if orders.count() > constants.HOUSE_DETAIL_COMMENT_DISPLAY_COUNTS:
        orders = orders[:constants.HOUSE_DETAIL_COMMENT_DISPLAY_COUNTS]
    for order in orders:
        comment = {
            "comment": order.comment,  # 评论的内容
            "user_name": order.user.username if order.user.username != order.user.mobile else "匿名用户",  # 发表评论的用户
            "ctime": order.update_time.strftime("%Y-%m-%d %H:%M:%S")  # 评价的时间
        }
        comments.append(comment)
    house_dict["comments"] = comments
    return house_dict
