# -*- coding: utf8 -*-
from aiohttp import FormData
import ujson as json
import vk_api
import asyncio
import sqlite3
import time
import config_cover as config
import re
import io
import traceback
import sys
import base64
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

def logs(strings=''):
     with open('logs_error.txt', 'a') as f:
        if strings:
            f.write(f'{time.ctime()} --> {strings}')
            f.write('\n> > > ')
        else:
            f.write(f'{time.ctime()} ERROR--> ')
            a = sys.exc_info()
            traceback.print_exception(*a)
            traceback.print_exception(*a, file=f)
            f.write('\n> > > ')

class until:
    social_tmp = {}
    loop_tasks = []
    cover = {}

    @staticmethod
    def start_task(coro):
        until.loop_tasks.append(asyncio.create_task(coro))

class req:
    session = None

    @staticmethod
    async def get(url, params=None, data=None, headers=None, timeout=30, proxy=None):
        async with await req.session.get(url, params=params, data=data, headers=headers, timeout=timeout,
                                         proxy=proxy) as res:
            res = await res.read()
            return res

    @staticmethod
    async def post(url, params=None, data=None, headers=None, timeout=30, proxy=None):
        async with await req.session.post(url, params=params, data=data, headers=headers, timeout=timeout,
                                        proxy=proxy) as res:
            res = await res.read()
            return res

class sqlbd:
    __slots__ = 'tabs', 'path'

    def __init__(self, tabs='userdata'):
        self.tabs = tabs
        if sys.platform == "linux" or sys.platform == "linux2":
            self.path = '/home/vurdolag/bd/vkbot.db'
        else:
            self.path = 'db/vkbot.db'


    def get_between(self, key='', val1='', val2=''):
        connection = sqlite3.connect(self.path)
        crsr = connection.cursor()
        t = f'where {key} between {val1} and {val2}'
        crsr.execute(f'SELECT * FROM {self.tabs} {t};')
        ans = crsr.fetchall()
        connection.close()
        return ans


    def delete(self, command):
        connection = sqlite3.connect(self.path)
        crsr = connection.cursor()
        command = f'DELETE FROM {self.tabs} WHERE {command};'
        crsr.execute(command)
        connection.commit()
        connection.close()
        ans = crsr.rowcount
        return ans


    def put(self, *args):
        x = '('
        for i in args:
            if isinstance(i, str):
                x += '"' + re.sub('"', "'", i) + '", '
            else:
                x += str(i) + ', '
        x = x[:-2] + ')'

        sql_command = f"INSERT INTO {self.tabs} VALUES {x};"
        try:
            connection = sqlite3.connect(self.path)
            crsr = connection.cursor()
            crsr.execute(sql_command)
            connection.commit()
            connection.close()
            return True

        except Exception as ex:
            print(ex)
            return False

def get_user_token():
    vk_session = vk_api.VkApi(config.user_login, config.user_pass, app_id=config.user_app_id)
    vk_session.auth()
    token = vk_session.token['access_token']
    return token

class VkLoop:
    url = 'https://api.vk.com/method/'
    v_api = '5.103'
    user_token = get_user_token()
    response = {}
    task = [[] for _ in range((len(config.token)+1))]
    t1 = time.time()
    t2 = t1
    start = 1
    group_token = {k: v[1] for k, v in enumerate(config.token.items())}
    post_group_index = 0

    def create_execute_code(self, task):
        '''Генератор кода VKScript для метода execute'''
        code = 'return ['
        for i in task:
            body = re.sub(r'\\xa0', ' ', str(i[1]))
            #                 method       params            name_id
            code += '[API.' + i[0] + '(' + body + '), "' + str(i[2]) + '"], '

        return code[:-2] + '];'

    async def task_loop(self):
        '''Запуск группы задач в execute_task() после достижения
        определённого времени после получения задачи или
        количества активных задач в task'''
        time_comment = 0.4
        time_msg = 0.2
        iter = 0.05
        max_task = 24
        time_iter = iter

        try:
            while True:
                s = time.time() - self.t2
                if self.task[0] and ((len(self.task[0]) >= max_task and s > time_comment) or s > time_comment):
                        #print('???', len(self.task[0]))
                    code = self.create_execute_code(self.task[0][:max_task + 1])
                    self.task[0] = self.task[0][max_task:]
                    until.start_task(self.execute_task(code, self.user_token))
                if s > time_comment:
                    self.t2 = time.time()

                s = time.time() - self.t1
                for index in range(1, len(config.token) + 1):
                    if self.task[index] and (len(self.task[index]) >= max_task or s > time_msg):
                        time_iter = iter
                        code = self.create_execute_code(self.task[index][:max_task + 1])
                        self.task[index] = self.task[index][max_task:]
                        until.start_task(self.execute_task(code, self.group_token[index-1]))
                if s > time_msg:
                    self.t1 = time.time()

                iter_t = round(time_iter, 2) if time_iter < 1 else 1
                await asyncio.sleep(iter_t)
                time_iter += 0.0001
        except:
            logs()
            until.start_task(self.task_loop())
            return 0

    async def execute_task(self, code, token, add_params=0):
        '''Метод одновременной отправки группы задач с помощью execute'''
        method = 'execute'
        params = {'v': self.v_api,
                  'access_token': token}

        if add_params:
            params.update(add_params)

        #print(code)
        try:
            res = await req.post(self.url + method, params=params, data={'code': code})
            res = json.loads(res.decode('utf-8'))

            execute_errors = res.get('execute_errors', 0)
            errors = res.get('error', 0)
            resp = res.get('response', 0)

            if execute_errors:
                print(res)
                logs(f'execute_errors --> code ->{code}, error -> {res}')

            if errors:
                print(res)
                logs(f'errors --> code ->{code}, error -> {res}')
                await self.captcha(errors, code, token)

            if resp:
                for i in resp:
                    if i[1] == 0:
                        continue
                    else:
                        self.response[i[1]] = i[0]
                return 1

            else:
                return False

        except:
            logs()
            return False

    async def captcha(self, errors, code, token):
        if errors.get('error_msg', 0) == 'Captcha needed':
            logs(f'Captcha find')

            captcha_sid = errors['captcha_sid']
            captcha_img = errors['captcha_img']

            url = 'https://rucaptcha.com/in.php'

            data = await req.get(captcha_img)

            data = base64.b64encode(data).decode("utf-8")
            for _ in range(10):
                response = await req.post(url,
                                          params={'key': config.captcha,
                                                  'method': 'base64',
                                                  'json': 1,
                                                  'body': data})

                response = json.loads(response.decode('utf-8'))
                ids = response.get('request', 0)
                url = 'https://rucaptcha.com/res.php'
                captcha_key = ''

                for _ in range(12):
                    await asyncio.sleep(5)
                    res = await req.get(url, params={'key': config.captcha,
                                                     'action': 'get',
                                                     'id': ids,
                                                     'json': 1}, data=data)
                    res = json.loads(res.decode('utf-8'))
                    if res.get('status', -1) == 1:
                        captcha_key = res['request']
                        break

                if captcha_key:
                    add = {'captcha_sid': captcha_sid,
                        'captcha_key': captcha_key}

                    logs('Capcha ok')
                    until.start_task(self.execute_task(code, token, add))
                    break
            return True

    async def start_loop(self):
        '''Метод инициализации очереди задач'''
        if VkLoop.start:
            VkLoop.start = 0
            until.start_task(self.task_loop())
        return 1

class VkClass(VkLoop):
    __slots__ = ('token', 'group', 'index', 'name_id')

    def __init__(self, group):
        self.group = group
        self.token = config.token.get(self.group, '')
        self.name_id = 1000
        try:
            self.index = list(config.token).index(self.group) + 1
        except:
            self.index = 0

    async def is_members(self, group, ids: list) -> dict:
        task = []
        for i in range(0, len(ids), 500):
            _id = ids[i:i + 500]
            task.append(asyncio.create_task(self.get_response('groups.isMember',
                                                              {'group_id': abs(int(group)),
                                                               'user_ids': ','.join(_id)})))
        out = []
        [out.extend(x) for x in await asyncio.gather(*task)]

        return {str(i['user_id']): i["member"] for i in out}


    async def init_long_poll(self):
        '''Получение инфо LongPoll сервера'''
        return await self.get_response('groups.getLongPollServer',
                                       {'group_id': self.group})


    async def get_event_from_group(self, event_processing):
        while True:
            try:
                await self.start_loop()
                data = await self.init_long_poll()
            except:
                logs()
                continue

            for task in until.loop_tasks:
                if task.done():
                    until.loop_tasks.remove(task)

            while True:
                try:
                    long_url = (f'{data["server"]}?act=a_'
                                f'check&key={data["key"]}&ts={data["ts"]}'
                                f'&wait=25')  # &mode=64&version=3

                    response = await req.get(long_url, timeout=120)  # <-- запрос
                    response = json.loads(response.decode('utf-8'))
                    updates = response['updates']

                    if updates:
                        for update in updates:
                            event = self.update_pars(update)
                            if event != 0:
                                until.start_task(event_processing(event))

                    data['ts'] = response['ts']

                except KeyError:
                    break
                except:
                    logs()
                    break


    async def get_user_all_info(self, user_id):
        params = {'user_ids': user_id,
                  'fields': 'sex,photo_200_orig,bdate,city,country,home_town,last_seen,online,photo_max_orig,screen_name'}
        res = await self.get_response('users.get', params)
        return res


    async def upload_cover(self, group_id, cover_img, width=1590, height=400):
        try:
            params = {"group_id": group_id,
                      "crop_x": 0,
                      "crop_y": 0,
                      "crop_x2": width,
                      "crop_y2": height
                      }
            upload_url = await self.get_response('photos.getOwnerCoverPhotoUploadServer', params)

            data = FormData()
            data.add_field('photo', io.BytesIO(cover_img), filename='photo.jpg', content_type='image/png')

            uploaded_data = await req.post(upload_url["upload_url"], data=data, timeout=60)
            uploaded_data = json.loads(uploaded_data.decode('utf-8'))

            params = {"hash": uploaded_data["hash"],
                      "photo": uploaded_data["photo"],
                      'v': '5.103', 'access_token': self.token}

            upload_result = await req.get(self.url + 'photos.saveOwnerCoverPhoto', params=params)

            return upload_result.decode('utf-8')

        except:
            logs()
            return False


    async def get_wall_user(self, user_id, count=100, offset=0, extended=0):
        params = {'owner_id': user_id, 'count': count, 'offset': offset, 'extended': extended}
        return await self.get_response('wall.get', params, True, 1)


    async def get_user_from_like_post(self, owner_id, item_id, count=1000, type_post='post',
                                      extended=0, offset=0):
        params = {'owner_id': owner_id, 'item_id': item_id, 'count': count,
                  'type': type_post, 'extended': extended, 'offset': offset}
        return await self.get_response('likes.getList', params, True, 1)


    async def get_user_from_repost_post(self, owner_id, item_id, count=1000, offset=0):
        params = {'owner_id': owner_id, 'item_id': item_id,
                  'count': count, 'offset': offset}
        return await self.get_response('wall.getReposts', params, True, 1)


    async def get_user_from_comment_post(self, owner_id, post_id, count=100, offset=0):
        params = {'owner_id': owner_id, 'post_id': post_id, 'need_likes': 1, 'extended': 1,
                  'count': count, 'offset': offset, 'thread_items_count': 10}
        return await self.get_response('wall.getComments', params, True, 1)


    async def get_response(self, method, params, user=0, timer=0.1):
        '''Ожидание ответ в self.response'''
        self.name_id += 1
        name = f'{self.group}_{self.name_id}'

        self.task[0 if user else self.index].append([method, params, name])  # <-- добавляет задачу в нужную очередь
        for _ in range(300):                                                      # с уникальным name_id
            await asyncio.sleep(timer)
            res = self.response.get(name, -1)  # Каждые 0.1 сек. пытается получить ответ.
            if res != -1:
                del self.response[name]  # если есть ответ удаляет из очереди ответов возвращает результат
                return res

        logs(f'get response error {method} | {params} | {name}')
        return {}


    def update_pars(self, update):
        until.cover[self.group].pars(update)
        return 0
















