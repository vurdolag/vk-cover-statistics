# -*- coding: utf8 -*-

async def main():
    from aiohttp import ClientSession
    req.session = ClientSession()

    for group_id in token:
        social = VkClass(group_id)
        until.social_tmp[group_id] = social
        until.start_task(social.get_event_from_group(''))
        until.cover[group_id] = CoverCreator(group_id, social)
        until.start_task(until.cover[group_id].mainapp())
        await sleep(5)

    await gather(*until.loop_tasks)


if __name__ == '__main__':
    from untils import until, VkClass, req
    from Cover import CoverCreator
    from config_cover import *
    from asyncio import run, gather, sleep

    run(main())

