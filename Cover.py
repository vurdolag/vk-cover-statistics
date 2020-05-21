from untils import req, sqlbd, logs, until
from collections import Counter
from asyncio import create_task, sleep, gather
from config_cover import *
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from io import BytesIO
from time import time


class CoverCreator:
    def __init__(self, group, social):
        self.groups = [group]
        self.social = social
        self.groups_wal_stat = {}
        self.post_time = {}
        self.comment_stat = {}
        self.BD = sqlbd('cover')
        self.img_temp = {}
        self.user_avatar = {}
        self.timer = time()

    def counter(self, count_list):
        a = []
        [a.extend(i) for i in count_list]
        return dict(Counter(a))

    def pars(self, update):
        print(update)
        try:
            if update['type'] == 'like_add':
                obj = update['object']
                owner_id = obj['object_owner_id']
                liker_id = obj['liker_id']
                object_id = obj['object_id']
                ban_user = str(liker_id) in BAN_USER

                if obj['object_type'] == 'post' and not ban_user:
                    _time = self.post_time.get(f"{owner_id}_{object_id}", DATE_POST)
                    if time() - _time < TIME_LIKE_1:
                        self.BD.put(owner_id, object_id, liker_id, int(time()), 0, 2)

                    elif time() - _time < TIME_LIKE_2 and not ban_user:
                        self.BD.put(owner_id, object_id, liker_id, int(time()), 0, 1)

                    # self.BD.put(owner_id, object_id, liker_id, int(time()), 0, 1)
                    if time() - _time < DATE_POST:
                        self.up_data(owner_id, liker_id, object_id, 1, 0, 0)

                    return True

                if obj['object_type'] == 'comment':
                    if self.check_my_like_on_my_comment(owner_id, object_id, liker_id):
                        self.up_data(owner_id, liker_id, object_id, 0, 0, 1)
                        self.up_like_on_my_comment(owner_id, object_id, liker_id, 1)

                    return True

            if update['type'] == 'like_remove':
                obj = update['object']
                owner_id = obj['object_owner_id']
                liker_id = obj['liker_id']
                object_id = obj['object_id']

                if obj['object_type'] == 'post':
                    _time = self.post_time.get(f"{owner_id}_{object_id}", DATE_POST)
                    self.up_data(owner_id, liker_id, object_id, -1, 0, 0)
                    command = (f"group_id = {owner_id} and "
                               f"post_id = {object_id} and "
                               f"user_id = {liker_id} and "
                               f"type_action = 0")
                    self.BD.delete(command)
                    return True

                if obj['object_type'] == 'comment':
                    if self.check_my_like_on_my_comment(owner_id, object_id, liker_id):
                        self.up_data(owner_id, liker_id, object_id, 0, 0, -1)
                        self.up_like_on_my_comment(owner_id, object_id, liker_id, -1)

            if update['type'] == 'wall_reply_delete':
                self.up_data(update['object']['owner_id'],
                             update['object']['deleter_id'],
                             update['object']['post_id'],
                             0, -1, 0)
                return True

            if update['type'] == 'wall_reply_new':
                obj = update['object']
                owner_id = obj['owner_id']
                post_id = obj['post_id']
                from_id = obj['from_id']
                object_id = obj['id']

                _time = self.post_time.get(f"{owner_id}_{post_id}", DATE_POST)
                if time() - _time < DATE_POST:
                    self.up_data(owner_id, from_id, object_id, 0, 1, 0)
                    self.comment_stat[f'{owner_id}_{object_id}'] = [str(from_id), obj.get('text', ''), 0]
                return True

            if update['type'] == 'wall_post_new':
                if update['group_id'] in self.groups:
                    create_task(self.up_data_stat_wall(str(update['object']['from_id'])))

            return True

        except:
            logs()
            return False

    def add_corners(self, im, rad):
        try:
            alpha = self.img_temp.get(im.size, 0)
            if not alpha:
                circle = Image.new("L", (rad * 4, rad * 4), 0)
                draw = ImageDraw.Draw(circle)
                draw.ellipse((2, 2, rad * 4-2, rad * 4-2), fill=255)
                del draw
                circle = circle.resize((rad * 2, rad * 2), Image.ANTIALIAS)
                alpha = Image.new("L", im.size, 255)
                draw = ImageDraw.Draw(alpha)
                w, h = im.size
                alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
                alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
                alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
                alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
                draw.rectangle([(0, 0), (alpha.size[0] - 1, alpha.size[1] - 1)], outline=0)
                del draw
                self.img_temp[im.size] = alpha

            im.putalpha(alpha)
            im = im.convert('RGBA')
            _, _, _, opacity = (0, 0, 0, 200)
            alpha = im.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(opacity / 255)

            im.putalpha(alpha)
            return im

        except:
            logs()
            return False

    def draw_outline(self, draw, x, y, finalText, shadow_color, fnt, align, spacing):

        draw.text(
            (x - 1, y), finalText, fill=shadow_color, font=fnt, align=align, spacing=spacing
        )

        draw.text(
            (x + 1, y), finalText, fill=shadow_color, font=fnt, align=align, spacing=spacing
        )

        draw.text(
            (x, y - 1), finalText, fill=shadow_color, font=fnt, align=align, spacing=spacing
        )

        draw.text(
            (x, y + 1), finalText, fill=shadow_color, font=fnt, align=align, spacing=spacing
        )

        draw.text(
            (x - 1, y - 1),
            finalText,
            fill=shadow_color,
            font=fnt,
            align=align,
            spacing=spacing,
        )

        draw.text(
            (x + 1, y - 1),
            finalText,
            fill=shadow_color,
            font=fnt,
            align=align,
            spacing=spacing,
        )

        draw.text(
            (x - 1, y + 1),
            finalText,
            fill=shadow_color,
            font=fnt,
            align=align,
            spacing=spacing,
        )

        draw.text(
            (x + 1, y + 1),
            finalText,
            fill=shadow_color,
            font=fnt,
            align=align,
            spacing=spacing,
        )

    def up_like_on_my_comment(self, owner_id, object_id, liker_id, point):
        k = f'{owner_id}_{object_id}'
        d = self.comment_stat.get(k, 0)

        if d:
            self.comment_stat[k] = [d[0], d[1], d[2] + point]

        else:
            self.comment_stat[k] = [str(liker_id), '', point]

    def check_my_like_on_my_comment(self, owner_id, object_id, liker_id):
        my = self.comment_stat.get(f'{owner_id}_{object_id}', [0])[0] == str(liker_id)
        return not MY_LIKE_ON_MY_COMMENT or not my

    def up_data(self, group_id: str, user_id: str, id_item: int, like: int, comment: int, like_on_comment: int):
        user_id = str(user_id)
        group_id = str(group_id)

        if group_id[0] != '-':
            group_id = '-' + group_id

        try:
            stat = self.groups_wal_stat[group_id].get(user_id, [0, 0, 0])
            self.groups_wal_stat[group_id][user_id] = [stat[0] + like,
                                                       stat[1] + comment,
                                                       stat[2] + like_on_comment]
            return True

        except:
            logs()
            return False

    async def avatar_and_name(self, res, user):
        avatar = self.user_avatar.get(user[0])
        if not avatar:
            avatar = BytesIO(await req.get(res.get('photo_200_orig', '')))
            self.user_avatar[user[0]] = avatar

        return [user[0], str(user[1]), res.get('first_name', ''), avatar]

    async def get_avatar_and_name(self, stat):
        task = []
        res = await self.social.get_user_all_info(','.join([user[0] for user in stat]))
        if time() - self.timer > 60*60*3:
            self.user_avatar = {}

        for j, i in enumerate(res):
            task.append(create_task(self.avatar_and_name(i, stat[j])))
        return await gather(*task)

    async def is_member(self, item, group_id):
        if IS_MEMBER and item:
            member = await self.social.is_members(group_id, item)
            out = list(filter(lambda x: member.get(x, 0), item))
            return out

        else:
            return item

    async def creator(self, stat, path, temp):
        try:
            SIZE = temp['size']
            PAD = temp['pad']
            PAD_IMG = temp['pad_img']
            RAD = temp['rad']
            XY = temp['xy']
            TXY = temp['text_xy']
            DXY = temp['digit_xy']

            try:
                original = Image.open(path)
            except:
                original = Image.open(PATH_BACK + DEFAULT_BACK)
            draw = ImageDraw.Draw(original)
            fnt = ImageFont.truetype(PATH_FONT, temp['font_size'])
            size_fnt_px = fnt.getsize("a")[0]

            im2 = Image.new("RGBA", (SIZE - PAD, SIZE - PAD), (255, 255, 255, 200))
            im2 = self.add_corners(im2, RAD)

            im = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 200))
            im = self.add_corners(im, RAD)
            im.paste(im2, (PAD // 2, PAD // 2), im2)

            for j, i in enumerate(XY):
                if len(stat) < j + 1:
                    val = ['', '???', '???', PATH_DEFAULT_USER_PHOTO]
                else:
                    val = stat[j]

                uphoto = Image.open(val[3])
                width = uphoto.size[0]  # Определяем ширину
                height = uphoto.size[1]

                if width > height:
                    z = width - height
                    pos = (z // 2, 0, width - z // 2, height)
                    uphoto = uphoto.crop(pos)
                if width < height:
                    z = height - width
                    pos = (0, z // 2, width, height - z // 2)
                    uphoto = uphoto.crop(pos)

                x, y = i

                user_photo = uphoto.resize((SIZE - PAD_IMG, SIZE - PAD_IMG), Image.ANTIALIAS)
                user_photo = self.add_corners(user_photo, RAD)

                original.paste(im, (x, y), im)

                original.paste(user_photo, (x + PAD_IMG // 2, y + PAD_IMG // 2), user_photo)

                correct = int(len(val[2]) / 2 * size_fnt_px)

                x1, y1 = x + TXY[0] - correct, y + TXY[1]

                self.draw_outline(draw, x1, y1, val[2], "#000000", fnt, "center", int(65 / 4))
                draw.text((x1, y1), val[2], fill="#ffffff", font=fnt,
                                    align="center", spacing=int(65 / 4))

                correct = int(len(val[1]) / 2 * size_fnt_px)
                x2, y2 = x + DXY[0] - correct, y + DXY[1]

                self.draw_outline(draw, x2, y2, val[1], "#000000", fnt, "center", int(65 / 4))
                draw.text((x2, y2), val[1], fill="#ffffff", font=fnt,
                                    align="center", spacing=int(65 / 4))

            #original.save('555.jpg', 'JPEG', quality=75)
            stream = BytesIO()
            original.save(stream, format="JPEG", quality=75)
            stream.seek(0)
            img = stream.read()

            return img

        except:
            logs()
            return False

    async def get_max_user_stat(self, user_stat: dict, group_id: str, count: int = 0) -> list:
        stat_group = []
        extra_point = Counter()
        point_like_on_my_comment = {}

        if LIKE_MY_COMMENT:
            for j, i in self.comment_stat.items():
                if i[2] and group_id in j:
                    point_like_on_my_comment[str(i[0])] = point_like_on_my_comment.get(str(i[0]), 0) + i[2]

        points = self.BD.get_between('time_action', int(time() - DATE_POST), int(time()))
        for x in points:
            if str(x[0]) == group_id:
                extra_point[str(x[2])] += (POINT_FOR_TIME_LIKE_1 if x[5] == 2 else POINT_FOR_TIME_LIKE_2)

        for user_id in await self.is_member(list(user_stat.keys()), group_id):
            if user_id in BAN_USER or user_id[0] == '-':
                continue
            stat = user_stat[user_id]
            point = (stat[0] * POINT_FOR_LIKE +
                     stat[1] * POINT_FOR_COMMENT +
                     stat[2] * POINT_FOR_LIKE_ON_COMMENT +
                     extra_point.get(user_id, 0) +
                     int(point_like_on_my_comment.get(user_id, 0) * POINT_FOR_LIKE_ON_MY_COMMENT))

            stat_group.append([user_id, point])

        stat = sorted(stat_group, key=lambda x: x[1], reverse=True)

        if count:
            return stat[:count]
        return stat

    async def get_like(self, group_id, id_post, type_post='post'):
        try:
            count = 1000
            offset = 0
            item = []

            while True:
                a = await self.social.get_user_from_like_post(group_id, id_post,
                                                              offset=offset,
                                                              type_post=type_post)
                offset += count
                item.extend(list(map(lambda x: str(x), a.get("items", []))))

                if a.get("count", 0) // count == 0:
                    break

            if type_post == 'comment':
                item = [x for x in item if self.check_my_like_on_my_comment(group_id, id_post, x)]
                item = await self.is_member(item, group_id)

            return item

        except:
            logs()
            return []

    async def get_comment(self, group_id, id_post):
        try:
            count = 100
            offset = 0
            items = []
            like_on_comment = []

            while True:
                a = await self.social.get_user_from_comment_post(group_id, id_post, offset=offset)
                offset += count
                d = a.get("items", [])
                for i in d:
                    if i.get('likes', 0):
                        self.comment_stat[f'{i["owner_id"]}_{i["id"]}'] = [str(i['from_id']),
                                                                           i.get('text', ''),
                                                                           i['likes']['count']]
                        if i['likes']['count'] != 0:
                            like_on_comment.append(i['id'])
                        items.append(str(i['from_id']))

                    if i.get('thread', 0) and i['thread']['count'] != 0:
                        for j in i['thread']['items']:
                            self.comment_stat[f'{j["owner_id"]}_{j["id"]}'] = [str(j['from_id']),
                                                                               j.get('text', ''),
                                                                               j['likes']['count']]
                            if j['likes']['count'] != 0:
                                like_on_comment.append(j['id'])
                            items.append(str(j['from_id']))

                if a.get("count", 0) // count == 0:
                    break

            like = []
            if like_on_comment:
                task = []
                for id_comment in like_on_comment:
                    task.append(create_task(self.get_like(group_id, id_comment, type_post='comment')))

                [like.extend(i) for i in await gather(*task)]

            return [items, like]

        except:
            logs()
            return [[], []]

    async def get_wall_stat(self, group_id, count_post=100, count=100):
        try:
            if group_id[0] != '-':
                group_id = '-' + group_id
            ids_post = []
            for offset in range(0, count_post, count):
                response = await self.social.get_wall_user(group_id, offset=offset, count=count)
                for items in response.get('items', []):
                    if time() - items.get('date', 0) <= DATE_POST:
                        ids_post.append(items['id'])
                        self.post_time[f"{group_id}_{items['id']}"] = items["date"]

                if response.get("count", 0) // count == 0:
                    break

            taskLike = []
            taskComment = []
            for id_post in ids_post:
                taskLike.append(create_task(self.get_like(group_id, id_post)))
                taskComment.append(create_task(self.get_comment(group_id, id_post)))

            comm = await gather(*taskComment)
            like = await gather(*taskLike)
            count_like_on_comment = self.counter([x[1] for x in comm])
            count_comment = self.counter([x[0] for x in comm])
            count_like = self.counter(like)

            wall_stat = {}
            for user_id in set(list(count_like.keys()) + list(count_comment.keys()) +
                               list(count_like_on_comment.keys())):
                wall_stat[user_id] = [count_like.get(user_id, 0),
                                      count_comment.get(user_id, 0),
                                      count_like_on_comment.get(user_id, 0)]

            return {group_id: wall_stat}

        except:
            logs()
            return {}

    async def up_data_stat_wall(self, group=''):
        try:
            task = []

            if group:
                task.append(create_task(self.get_wall_stat(str(group), count=1, count_post=1)))
                res = await gather(*task)
                for j, i in res[0][group].items():
                    self.groups_wal_stat[group][j] = i

            else:
                for group_id in self.groups:
                    task.append(create_task(self.get_wall_stat(str(group_id))))

                [self.groups_wal_stat.update(x) for x in await gather(*task)]

            return True

        except:
            logs()
            return False

    async def mainapp(self):
        while True:
            try:
                await self.up_data_stat_wall()
                for _ in range(TIME_GLOBAL // TIME_ITER):
                    for group_id in self.groups_wal_stat.keys():
                        stat = await self.get_max_user_stat(self.groups_wal_stat[group_id], group_id)
                        stat = await self.get_avatar_and_name(stat[:COUNT_USER_VIEW])
                        cover_img = await self.creator(stat, PATH_BACK + group_id + '.jpg', TEMPLATE[group_id])
                        if not await self.social.upload_cover(abs(int(group_id)), cover_img):
                            logs('Error upload cover')
                        print('cover ok', group_id)

                    await sleep(TIME_ITER)

            except:
                logs()
                await sleep(TIME_ITER)