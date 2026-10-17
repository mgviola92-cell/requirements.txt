import copy
import random
import unittest
from games import checkers as g


class CheckersRulesTests(unittest.TestCase):
    def playing(self):
        return g.action(g.new(-1,10,'Red',0),20,'join',None,1,'White')

    def empty(self):
        s=self.playing();s['board']=[0]*64;s['history']=[]
        return s

    def move(self,s,src,dst,now=2):
        uid=s['players'][0 if s['turn']==1 else 1]
        if s['selected']!=src:s=g.action(s,uid,'square',src,now)
        return g.action(s,uid,'square',dst,now)

    def test_initial_board_and_forward_moves(self):
        s=self.playing()
        self.assertEqual(s['board'].count(1),12)
        self.assertEqual(s['board'].count(-1),12)
        self.assertEqual(len(g.legal(s)),7)
        moved=self.move(s,40,33)
        self.assertEqual(moved['board'][33],1)
        self.assertEqual(moved['turn'],-1)
        self.assertEqual(s['board'][40],1)

    def test_join_target_self_and_duplicate_rejected(self):
        s=g.new(-1,10,'R',0,target=20)
        for uid in (10,30):
            with self.assertRaises(ValueError):g.action(s,uid,'join',None,1)
        s=g.action(s,20,'join',None,1)
        with self.assertRaises(ValueError):g.action(s,30,'join',None,2)

    def test_wrong_turn_and_spectator(self):
        s=self.playing()
        for uid in (20,30):
            with self.assertRaises(ValueError):g.action(s,uid,'square',40,2)

    def test_capture_is_mandatory(self):
        s=self.empty();s['board'][42]=s['board'][46]=1;s['board'][33]=-1;s['board'][1]=-1
        self.assertEqual(g.legal(s),[(42,24,33)])
        with self.assertRaises(ValueError):self.move(s,46,37)
        s=self.move(s,42,24)
        self.assertEqual(s['board'][33],0)

    def test_multiple_jump_cannot_switch_piece_or_extend_clock(self):
        s=self.empty();s['board'][42]=s['board'][46]=1
        for i in (33,17,1):s['board'][i]=-1
        deadline=s['deadline'];s=self.move(s,42,24)
        self.assertEqual(s['turn'],1);self.assertEqual(s['chain'],24)
        self.assertEqual(s['deadline'],deadline)
        with self.assertRaises(ValueError):g.action(s,10,'square',46,3)
        s=self.move(s,24,10,3)
        self.assertEqual(s['turn'],-1)

    def test_crowning_ends_turn(self):
        s=self.empty();s['board'][17]=1;s['board'][10]=s['board'][12]=-1
        s=self.move(s,17,3)
        self.assertEqual(s['board'][3],2);self.assertEqual(s['turn'],-1)
        self.assertIsNone(s['chain'])

    def test_kings_move_backwards_but_not_flying(self):
        s=self.empty();s['board'][26]=2;s['board'][1]=-2
        self.assertIn((26,35,None),g.legal(s))
        with self.assertRaises(ValueError):self.move(s,26,44)

    def test_last_piece_capture_wins(self):
        s=self.empty();s['board'][42]=1;s['board'][33]=-1
        s=self.move(s,42,24)
        self.assertEqual((s['phase'],s['winner']),('finished',1))

    def test_immobilized_player_loses(self):
        s=self.empty();s['board'][42]=1;s['board'][56]=-1
        s=self.move(s,42,33)
        self.assertEqual(s['winner'],1)

    def test_selection_does_not_reset_timeout(self):
        s=self.playing();deadline=s['deadline']
        s=g.action(s,10,'square',40,deadline-1)
        self.assertEqual(s['deadline'],deadline)
        self.assertTrue(g.expire(s,deadline));self.assertEqual(s['winner'],-1)

    def test_resign_confirmation_and_admin_cancel(self):
        s=g.action(self.playing(),10,'cancel',None,2)
        with self.assertRaises(ValueError):g.action(s,20,'yes',None,3)
        s=g.action(s,10,'yes',None,3)
        self.assertEqual((s['reason'],s['winner']),('resign',-1))
        s=g.action(self.playing(),30,'cancel',None,2,admin=True)
        s=g.action(s,30,'yes',None,3,admin=True)
        self.assertEqual(s['reason'],'cancelled')

    def test_draw_requires_other_player(self):
        s=g.action(self.playing(),10,'draw',None,2)
        with self.assertRaises(ValueError):g.action(s,10,'accept',None,3)
        with self.assertRaises(ValueError):g.action(s,30,'accept',None,3)
        s=g.action(s,20,'accept',None,3)
        self.assertEqual(s['reason'],'draw')

    def test_quiet_draw_and_repetition(self):
        s=self.empty();s['board'][42]=2;s['board'][7]=-2;s['quiet']=79
        self.assertEqual(self.move(s,42,33)['reason'],'draw')
        s=self.empty();s['board'][42]=2;s['board'][7]=-2
        future=self.move(s,42,33);key=g.position(future)
        s['history']=[key,key]
        self.assertEqual(self.move(s,42,33)['reason'],'draw')

    def test_random_play_invariants(self):
        rng=random.Random(831)
        for _ in range(30):
            s=self.playing()
            for turn in range(250):
                if s['phase']=='finished':break
                moves=g.legal(s);self.assertTrue(moves)
                src,dst,_=rng.choice(moves);before=sum(bool(p) for p in s['board'])
                s=self.move(s,src,dst,turn+2)
                self.assertLessEqual(sum(bool(p) for p in s['board']),before)
                self.assertTrue(all(not p or sum(divmod(i,8))%2 for i,p in enumerate(s['board'])))

    def test_ui_payload_and_restore(self):
        import json
        from features import checkers as f
        from unittest.mock import patch
        s=self.playing()
        s=json.loads(json.dumps(s))
        with patch.object(f,'text',side_effect=lambda key,**kw:f.MESSAGES[key].format(**kw)):
            keyboard=f.keyboard(s).to_dict()
            self.assertEqual(len(keyboard['inline_keyboard'][0]),8)
            self.assertTrue(all(len(b['callback_data'].encode())<=64 for row in keyboard['inline_keyboard'] for b in row))
            self.assertIn('Red',f.body(s))


class CheckersCallbackTests(unittest.TestCase):
    def setUp(self):
        from features import checkers as f
        from unittest.mock import MagicMock,patch
        from types import SimpleNamespace as NS
        self.f=f;self.patch=patch;self.NS=NS;self.bot=MagicMock();self.handlers={}
        self.bot.message_handler.side_effect=lambda **kw:lambda fn:fn
        def callback(**kw):
            def register(fn):self.handlers['callback']=fn;return fn
            return register
        self.bot.callback_query_handler.side_effect=callback
        cur=MagicMock();cur.fetchall.return_value=[]
        con=MagicMock();con.__enter__.return_value.cursor.return_value.__enter__.return_value=cur
        with patch.object(f,'get_db_connection',return_value=con),patch.object(f.threading,'Thread'):
            f.register(self.bot)
        self.s=g.action(g.new(-22,10,'Red',1000),20,'join',None,1001,'White')
        self.s['card']=88
        from contextlib import contextmanager
        @contextmanager
        def locked(cid):
            yield cur,self.s if cid==-22 else None
        self.locker=locked
        self.saved=[]
        self.bot.get_chat_member.return_value=NS(status='member')

    def invoke(self,uid,act,rev=None,cid=-22,mid=88):
        c=self.NS(id='cb',data=f"ck:{self.s['id']}:{self.s['revision'] if rev is None else rev}:{act}",
            from_user=self.NS(id=uid,is_bot=False,first_name='Name'),
            message=self.NS(chat=self.NS(id=cid,type='supergroup'),message_id=mid))
        with self.patch.object(self.f,'locked',self.locker),self.patch.object(self.f,'save',side_effect=lambda cur,s:self.saved.append(s)),self.patch.object(self.f,'text',side_effect=lambda k,**kw:self.f.MESSAGES[k].format(**kw)),self.patch.object(self.f.time,'time',return_value=1002):
            self.handlers['callback'](c)

    def test_current_move_saved_and_acknowledged(self):
        self.invoke(10,'s40')
        self.assertEqual(self.saved[-1]['selected'],40)
        self.bot.edit_message_text.assert_called_once()
        self.bot.answer_callback_query.assert_called_once()

    def test_stale_revision_cannot_move_but_repairs_board(self):
        self.invoke(10,'s40',rev=99)
        self.assertEqual(self.saved,[])
        self.bot.edit_message_text.assert_called_once()

    def test_other_group_or_card_cannot_touch_match(self):
        self.invoke(10,'s40',cid=-23)
        self.invoke(10,'s40',mid=89)
        self.assertEqual(self.saved,[])
        self.bot.edit_message_text.assert_not_called()

    def test_spectator_cannot_move(self):
        self.invoke(30,'s40')
        self.assertEqual(self.saved,[])


if __name__=='__main__':unittest.main()
