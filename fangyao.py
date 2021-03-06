#!/usr/bin/env python
# -*- encoding: utf-8 -*-
# vim: set et sw=4 ts=4 sts=4 ff=unix fenc=utf8:
# Author: Binux<i@binux.me>
#         http://binux.me
# Created on 2013-09-19 01:29:31

import sys
import time
import config
from bot import Bot
from ma import HeaderError

class FangYaoBot(Bot):
    AP_LIMIT = 0

    def choose_area(self, area_id=None):
        areas = self.ma.area()
        _area = None
        for area in areas.xpath('//area_info'):
            if area.area_type == 1:
                area_id = area.id
                _area = area
                break
        self.area_id = area_id

        floors = self.ma.floor(area_id).xpath('//floor_info') 
        _, floor = min([(x.cost, x) for x in floors if not x.boss_id])
        self._print('choose area:%s-%s cost:%s' % (_area.name, floor.id, floor.cost))
        self.floor_id = floor.id
        self.floor_cost = floor.cost

    def rewards(self):
        ret = self.ma.rewardbox()
        ids = []
        for each in ret.xpath('//rewardbox'):
            #if each.type != 4:
                ids.append(each.id)
        while ids:
            ret = self.ma.get_rewards(ids[:20])
            self._print('get reward')
            ids = ids[20:]
            time.sleep(self.OPERATION_TIME)

    def check_cards(self):
        cards = []
        for card in self.ma.cards.itervalues():
            if card.master_card_id in self.NOT_SOLD_CARDS or card.rarity >= 5:
                cards.append(card)
        cards = sorted(cards, key=lambda x: (x.rarity, x.name, -x.lv))
        for card in cards:
            print u'%s-%d lv%d/%d' % (card.name, card.rarity, card.lv, card.lv_max)

class JueXingBot(Bot):
    def _print(self, msg):
        print '--->', msg

    def _fairy(self, friend_user_id):
        for fairy_event in self.ma.fairy_select().xpath('//fairy_event'):
            if fairy_event.put_down != 1: # killed
                continue
            if fairy_event.user.id == self.ma.user_id:
                if u'觉醒的' in unicode(fairy_event.fairy.name):
                    print 'rare_fairy waiting...'
                    time.sleep(30)
                    return True
                else:
                    self._print('my fairy found, break')
                    return False
            if fairy_event.user.id not in (friend_user_id, self.ma.user_id):
                continue

            fairy_event.fairy.discoverer_id = fairy_event.user.id
            fairy = self.ma.fairy_floor(fairy_event.fairy.serial_id, fairy_event.user.id).xpath('//explore/fairy')[0]
            #fairy.rare_flg
            if fairy.hp <= 0: # killed
                continue

            if fairy.lv <= 2:
                ret = self.build_roundtable('fairy_lv2')
            elif fairy.lv <= 4:
                ret = self.build_roundtable('fairy_lv4')
            elif fairy.lv <= 7:
                ret = self.build_roundtable('fairy_lv7')
            else:
                ret = self.build_roundtable('fairy_lv15')

            if ret:
                self._print('touch fairy: %slv%s by %s' % (fairy.name, fairy.lv, fairy_event.user.name))
                ret = self.battle(fairy.serial_id, fairy.discoverer_id)
                if ret is False:
                    self._print('battle loss')
                    return False
                elif hasattr(ret.explore, 'rare_fairy'): #juexing
                    rare_fairy = ret.explore.rare_fairy
                    fairy = self.ma.fairy_floor(rare_fairy.serial_id, self.ma.user_id).xpath('//explore/fairy')[0]
                    self._print('!!touch fairy: %slv%s by %s' % (fairy.name, fairy.lv, fairy_event.user.name))
                    self.AP_LIMIT = 0
                    self.my_fairy = None
                    self.choose_area()
                    self.explore(next_area=False)
                    ret = self.build_roundtable('high_damage') or self.build_roundtable('low_cost')
                    if ret:
                        self.battle(fairy.serial_id, fairy.discoverer_id)
                        return True
                    else:
                        raise Exception("build round table error")
                elif ret.battle_result.winner:
                    return True
                else:
                    self._print(ret)
                    return False
            else:
                raise Exception("build round table error")
        self._print('fairy not found')

if __name__ == '__main__':
    main_bot = JueXingBot()
    main_bot.login(config.loginId, config.password)
    for line in open('account.list'):
        if line.startswith('#'):
            continue
        login_id, password = line.split()
        print '-------------------------- %s ---------------------------' % login_id
        main_bot.report()

        bot = FangYaoBot()
        bot.AP_LIMIT = 0
        bot.OPERATION_TIME = 0.5
        bot.NOT_SOLD_CARDS = (66, 390, 391, 392, 404, 124, 8, 260, 143, 124, 49)
        bot.login(login_id, password)
        bot.sell_cards(2)
        bot.fairy_rewards()
        bot.rewards()
        bot.gacha(friend=True, auto_build=0)
        bot.check_cards()
        bot.friends(bot.ma.friend_max-1)
        bot.report()

        friendlist = bot.ma.friendlist()
        is_friend = False
        for user in friendlist.xpath('//user'):
            #print unicode(user.name), user.id, main_bot.ma.user_id
            if user.id == main_bot.ma.user_id:
                is_friend = True

        if not is_friend and bot.ma.friends >= bot.ma.friend_max:
            bot.ma.remove_friend(friendlist.xpath('//user')[0].id)
            print "max friends, removed one, use this account tomorrow"
            continue

        if not is_friend:
            try:
                bot.ma.remove_friend(10000)
            except Exception, e:
                print e
                continue
            bot.ma.add_friend(main_bot.ma.user_id)
            main_bot.ma.approve_friend(bot.ma.user_id)
            main_bot.free_point('bc')
            friendlist = bot.ma.friendlist()
            is_friend = False
            for user in friendlist.xpath('//user'):
                if user.id == main_bot.ma.user_id:
                    is_friend = True
            if not is_friend:
                print 'not friend!'
                continue
        else:
            print 'already friend.'
        bot.choose_area()
        bot.free_point('ap')
        while True:
            try:
                bot.fairy()
                bot.sell_cards(2)
                bot.explore(next_floor=False, next_area=False)
                bot.report()
            except HeaderError, e:
                print e
                continue
            if len(main_bot.ma.cards) >= 200:
                main_bot.sell_cards(3)
            if not main_bot._fairy(bot.ma.user_id):
                bot.ma.remove_friend(main_bot.ma.user_id)
                print "friend removed."
                break
            main_bot.report()
            if bot.ma.ap < bot.floor_cost:
                bot.ma.remove_friend(main_bot.ma.user_id)
                print "friend removed."
                break
        main_bot.fairy()
