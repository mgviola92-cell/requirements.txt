import copy
import json
import random
import unittest
from unittest.mock import MagicMock,patch
from types import SimpleNamespace as NS

from games import nan_yate as g
from features import nan_yate as ui
from core import customization as c


def ready(n=12,seed=1,**rules):
    s=g.create('abcdef123456',-909,1,rules,100)
    for uid in range(1,n+1):g.join(s,uid,'လူ '+str(uid))
    g.begin(s,200,random.Random(seed));s['events']=[]
    return s


def set_role(p,r):
    p.update(role=r,side=g.ROLES[r]['side'],uses=g.ROLES[r]['uses'],copied=None,last_protect=None,armor=int(r=='soldier'))


class NanYateRulesTests(unittest.TestCase):
    def test_catalog_is_32_distinct_roles(self):
        self.assertEqual(len(g.ROLES),32)
        self.assertEqual(len({d['name'] for d in g.ROLES.values()}),32)
        for k,v in ui.MESSAGES.items():
            self.assertIn('msg.features.nan_yate.'+k,c.CATALOG)
        for key,entry in c.CATALOG.items():
            if 'nan_yate' in key:c.validate(key,entry['default'])

    def test_all_player_counts_and_seeds_have_valid_balanced_packs(self):
        seen=set()
        for n in range(8,41):
            for seed in range(60):
                roles=g.role_pack(n,random.Random(seed),g.DEFAULTS)
                seen.update(roles);self.assertEqual(len(roles),n)
                self.assertEqual(roles.count('seer'),1)
                self.assertIn('doctor',roles);self.assertIn('detective',roles)
                self.assertEqual(sum(g.ROLES[r]['side']=='plot' for r in roles),max(2,n//4))
                if 'poisoner' in roles:self.assertIn('healer',roles)
                self.assertLessEqual(roles.count('poisoner'),1)
                if 'curser' in roles:self.assertIn('cleanser',roles)
        self.assertEqual(seen,set(g.ROLES))

    def test_disabled_optional_roles_and_dependencies(self):
        cfg=copy.deepcopy(g.DEFAULTS)
        cfg['role_enabled']['healer']=False
        cfg['role_enabled']['curser']=False
        for seed in range(50):
            roles=g.role_pack(40,random.Random(seed),cfg)
            self.assertNotIn('poisoner',roles);self.assertNotIn('curser',roles)
        cfg['role_enabled']={r:r in ('noble','seer','doctor','detective','leader','blade') for r in g.ROLES}
        self.assertEqual(len(g.role_pack(40,random.Random(1),cfg)),40)
        with self.assertRaises(ValueError):c.validate('cfg.features.nan_yate.role_enabled',{r:False for r in g.ROLES})
        with self.assertRaises(ValueError):c.validate('cfg.features.nan_yate.role_uses',{r:-1 for r in g.DEFAULTS['role_uses']})

    def test_lobby_limits_duplicate_join_and_start(self):
        s=g.create('x',-1,1,{},0)
        g.join(s,1,'a');g.join(s,1,'b');self.assertEqual(len(s['players']),1)
        with self.assertRaises(ValueError):g.begin(s,2,random.Random(0))
        for uid in range(2,41):g.join(s,uid,str(uid))
        with self.assertRaises(ValueError):g.join(s,41,'x')
        g.begin(s,2,random.Random(0))
        with self.assertRaises(ValueError):g.join(s,42,'x')
        with self.assertRaises(ValueError):g.begin(s,2,random.Random(0))

    def test_action_changes_replace_previous_not_stack(self):
        s=ready();p=s['players'][0];set_role(p,'seer')
        g.act(s,p['id'],'loc','2');g.act(s,p['id'],'ability',s['players'][1]['id'])
        self.assertEqual(len(s['actions']),1);self.assertEqual(s['actions'][p['id']]['action'],'seer')
        g.act(s,p['id'],'skip','0');self.assertIsNone(s['actions'][p['id']]['loc'])
        with self.assertRaises(ValueError):g.act(s,p['id'],'loc','99')

    def test_guard_and_protect_absorb_single_family_attack(self):
        for mode in ('protect','guard','armor','none'):
            s=ready();a,b,target=s['players'][:3]
            for p in s['players']:set_role(p,'noble')
            set_role(a,'leader');set_role(b,'blade')
            target['armor']=int(mode=='armor')
            if mode in ('protect','guard'):
                defender=s['players'][3];set_role(defender,'doctor' if mode=='protect' else 'guard')
                g.act(s,defender['id'],'ability',target['id'])
            for p in (a,b):g.act(s,p['id'],'attack',target['id'])
            g.resolve_night(s,random.Random(1))
            self.assertEqual(sum(not p['alive'] for p in s['players']),int(mode in ('guard','none')))
            self.assertEqual(target['alive'],mode!='none')

    def test_blocked_executor_cancels_attack(self):
        s=ready();a,b,t,block=s['players'][:4]
        for p in s['players']:set_role(p,'noble')
        set_role(a,'leader');set_role(b,'blade');set_role(block,'blocker')
        g.act(s,block['id'],'ability',b['id']);g.act(s,a['id'],'attack',t['id'])
        g.resolve_night(s,random.Random(1));self.assertTrue(t['alive'])

    def test_mutual_blocks_are_order_independent(self):
        states=[]
        for reverse in (False,True):
            s=ready();a,b=s['players'][:2];set_role(a,'blocker');set_role(b,'blocker')
            pairs=[(a,b),(b,a)]
            for p,q in reversed(pairs) if reverse else pairs:g.act(s,p['id'],'ability',q['id'])
            g.resolve_night(s,random.Random(1));states.append([e['code'] for e in s['events'] if e['kind']=='notice'])
            self.assertEqual(a['uses'],2);self.assertEqual(b['uses'],2)
        self.assertEqual(states[0],states[1])

    def test_poison_grace_and_cure_doctor_is_not_cure(self):
        for cure in (True,False):
            s=ready();poison,target,heal=s['players'][:3]
            set_role(poison,'poisoner');set_role(target,'noble');set_role(heal,'healer' if cure else 'doctor')
            g.act(s,poison['id'],'ability',target['id']);g.resolve_night(s,random.Random(1))
            self.assertTrue(target['alive']);self.assertEqual(target['poison'],2)
            g.night(s,400,random.Random(1));g.act(s,heal['id'],'ability',target['id'])
            g.resolve_night(s,random.Random(1));self.assertEqual(target['alive'],cure)

    def test_mask_spoofs_seer_for_one_night_only(self):
        s=ready();a,b=s['players'][:2];set_role(a,'seer');set_role(b,'mask')
        g.act(s,a['id'],'ability',b['id']);g.act(s,b['id'],'ability',b['id'])
        g.resolve_night(s,random.Random(1))
        self.assertEqual(next(e['side'] for e in s['events'] if e.get('code')=='side'),'court')
        s['events']=[];g.night(s,400,random.Random(1));g.act(s,a['id'],'ability',b['id']);g.resolve_night(s,random.Random(1))
        self.assertEqual(next(e['side'] for e in s['events'] if e.get('code')=='side'),'plot')

    def test_forge_verify_and_publish_integrity(self):
        s=ready();forger,detective,t=s['players'][:3];set_role(forger,'forger');set_role(detective,'detective')
        g.act(s,forger['id'],'ability',t['id']);g.resolve_night(s,random.Random(1))
        fake=next(e for e in s['evidence'] if e['fake']);detective['bag']=[fake['id']]
        s['events']=[];g.night(s,400,random.Random(1));g.act(s,detective['id'],'ability',fake['id']);g.resolve_night(s,random.Random(1))
        self.assertTrue(next(e['fake'] for e in s['events'] if e.get('code')=='verified'))
        s['phase']='day';g.act(s,detective['id'],'publish',fake['id'])
        with self.assertRaises(ValueError):g.act(s,detective['id'],'publish',fake['id'])
        with self.assertRaises(ValueError):g.act(s,t['id'],'publish',fake['id'])

    def test_hidden_trace_not_reported_as_innocent(self):
        s=ready();a,b,t=s['players'][:3];set_role(a,'tracker');set_role(b,'hider');set_role(t,'blade')
        g.act(s,a['id'],'ability',t['id']);g.act(s,b['id'],'ability',t['id']);g.act(s,t['id'],'loc','2')
        g.resolve_night(s,random.Random(1))
        self.assertIsNone(next(e['loc'] for e in s['events'] if e.get('code')=='location'))
        self.assertFalse(any(e['subject']==t['id'] for e in s['evidence']))

    def test_curse_and_cleanse(self):
        for cleanse in (True,False):
            s=ready();a,b,t=s['players'][:3];set_role(a,'curser');set_role(b,'cleanser')
            g.act(s,a['id'],'ability',t['id'])
            if cleanse:g.act(s,b['id'],'ability',t['id'])
            g.resolve_night(s,random.Random(1));self.assertEqual(t['cursed'],not cleanse)

    def test_quest_currency_and_shop_stock_are_idempotent(self):
        s=ready();p=s['players'][0]
        g.act(s,p['id'],'quest',sum(p['quest']));self.assertEqual(p['coins'],1)
        with self.assertRaises(ValueError):g.act(s,p['id'],'quest',sum(p['quest']))
        s['phase']='day';p['armor']=0;p['coins']=8
        g.act(s,p['id'],'buy','armor');self.assertEqual(p['coins'],4);self.assertEqual(s['armor_stock'],0)
        with self.assertRaises(ValueError):g.act(s,p['id'],'buy','armor')
        q=s['players'][1];q['coins']=8;q['armor']=0
        with self.assertRaises(ValueError):g.act(s,q['id'],'buy','armor')

    def test_dead_action_resolves_without_public_role(self):
        s=ready();seer,a,b=s['players'][:3]
        for p in s['players']:set_role(p,'noble')
        set_role(seer,'seer');set_role(a,'leader');set_role(b,'blade')
        g.act(s,seer['id'],'ability',b['id']);g.act(s,a['id'],'attack',seer['id'])
        g.resolve_night(s,random.Random(1));self.assertFalse(seer['alive'])
        self.assertTrue(any(e.get('code')=='side' and e['dest']==seer['id'] for e in s['events']))
        self.assertFalse(any('role' in e for e in s['events'] if e['kind']=='death'))

    def test_ghosts_have_no_free_text_relay_or_vote(self):
        s=ready();p=s['players'][0];g.die(s,p,'attack')
        with self.assertRaises(ValueError):g.act(s,p['id'],'vote',s['players'][1]['id'])
        g.act(s,p['id'],'ghost','2');self.assertEqual(s['ghost_votes'][p['id']],'2')
        g.resolve_night(s,random.Random(1))
        self.assertFalse(any(e.get('kind')=='evidence' and next(v for v in s['evidence'] if v['id']==e['eid'])['fake'] for e in s['events']))

    def test_vote_change_skip_tie_and_runoff(self):
        s=ready();s['phase']='vote';s['deadline']=0
        a,b,x,y=s['players'][:4]
        for p in s['players']:set_role(p,'noble');p['active']=True
        set_role(s['players'][-1],'leader')
        g.act(s,a['id'],'vote',x['id']);g.act(s,a['id'],'vote',y['id'])
        self.assertEqual(len(s['votes']),1)
        g.act(s,b['id'],'vote',x['id'])
        g.advance(s,500,random.Random(1));self.assertEqual(s['phase'],'runoff')
        with self.assertRaises(ValueError):g.act(s,a['id'],'vote',s['players'][5]['id'])
        g.act(s,a['id'],'vote','skip');g.act(s,b['id'],'vote',x['id'])
        s['deadline']=0;g.advance(s,600,random.Random(1));self.assertTrue(x['alive']);self.assertTrue(y['alive'])
        self.assertEqual(s['phase'],'night')

    def test_judge_and_pardon_work_without_extra_vote_weight(self):
        s=ready();s['phase']='day';judge,minister,a,b,v1,v2=s['players'][:6]
        for p in s['players']:set_role(p,'noble');p['active']=True
        set_role(s['players'][-1],'leader');set_role(judge,'judge');set_role(minister,'minister')
        g.act(s,judge['id'],'judge',a['id']);g.act(s,minister['id'],'pardon',a['id'])
        s['phase']='runoff';s['runoff']=[a['id'],b['id']];s['deadline']=0
        g.act(s,v1['id'],'vote',a['id']);g.act(s,v2['id'],'vote',b['id'])
        g.advance(s,500,random.Random(1));self.assertTrue(a['alive'])
        self.assertEqual(judge['uses'],0);self.assertEqual(minister['uses'],0)

    def test_merchant_gift_requires_distinct_players(self):
        s=ready();p=s['players'][0];set_role(p,'merchant');q=s['players'][1]
        g.act(s,p['id'],'ability',q['id']);g.resolve_night(s,random.Random(1));self.assertEqual(q['coins'],2)
        g.night(s,400,random.Random(1))
        with self.assertRaises(ValueError):g.act(s,p['id'],'ability',q['id'])

    def test_mimic_only_safe_actions_and_single_use(self):
        s=ready();p,dead=s['players'][:2];set_role(p,'mimic');set_role(dead,'seer');dead['alive']=False
        with self.assertRaises(ValueError):g.act(s,p['id'],'ability',dead['id'])
        set_role(dead,'tracker');g.act(s,p['id'],'ability',dead['id']);g.resolve_night(s,random.Random(1))
        self.assertEqual(p['copied'],'track');self.assertEqual(p['uses'],1)
        g.night(s,400,random.Random(1));g.act(s,p['id'],'ability',s['players'][2]['id']);g.resolve_night(s,random.Random(1))
        self.assertIsNone(p['copied']);self.assertEqual(p['uses'],0)

    def test_traitor_only_offered_noble_second_night_and_delayed_allies(self):
        s=ready(40,traitor=True);g.night(s,400,random.Random(4));uid=s['traitor_offer'];self.assertIsNotNone(uid)
        p=g.player(s,uid);self.assertEqual(p['role'],'noble')
        g.act(s,uid,'traitor','yes');self.assertEqual(p['side'],'plot');self.assertTrue(p['turned'])
        with self.assertRaises(ValueError):g.act(s,uid,'traitor','yes')
        body,_=ui.private_panel(s,int(uid));self.assertNotIn(ui.text('allies',names='').split('\n')[0],body)
        g.resolve_night(s,random.Random(2));self.assertFalse(p['turned'])

    def test_afk_two_cycles_forfeits_rewards(self):
        s=ready();p=s['players'][0]
        for day in (1,2):
            s['phase']='vote';s['deadline']=0;s['day']=day
            for q in s['players'][1:]:q['active']=True
            g.advance(s,500+day,random.Random(3))
        self.assertFalse(p['alive']);self.assertTrue(p['forfeit'])
        s['winner']='draw';g.finish(s)
        self.assertFalse(any(a['uid']==p['id'] for a in s['awardees']))

    def test_win_draw_and_rewards_only_once(self):
        s=ready()
        for p in s['players']:p['participated']=True
        for p in s['players']:
            if p['side']=='plot':p['alive']=False
        self.assertTrue(g.check_win(s));self.assertEqual(s['winner'],'court')
        count=len(s['awardees']);g.finish(s);self.assertEqual(len(s['awardees']),count)
        s=ready()
        for p in s['players']:p['alive']=False
        g.check_win(s);self.assertEqual(s['winner'],'draw')

    def test_finish_neutral_targets_and_escape(self):
        s=ready();p,q=s['players'][:2];set_role(p,'hunter');p['objective']=q['id']
        g.die(s,q,'vote');self.assertTrue(p['wins'])
        set_role(p,'treasure');p['relics']=[0,1,2];s['phase']='day';g.act(s,p['id'],'escape',0)
        self.assertFalse(p['alive']);self.assertTrue(p['departed']);self.assertTrue(p['wins'])

    def test_every_night_role_action_executes_and_renders(self):
        for role,d in g.ROLES.items():
            if d['action'] in ('search','pardon','judge'):continue
            s=ready(16);p,t,dead=s['players'][:3];set_role(p,role);set_role(t,'blade');set_role(dead,'tracker');dead['alive']=False
            e=g.evidence(s,0,t['id'],True);p['bag']=[e['id']];dead['bag']=[e['id']]
            targets=g.available_targets(s,p,d['action']);self.assertTrue(targets,role)
            g.act(s,p['id'],'ability',targets[0]);g.resolve_night(s,random.Random(4))
            for event in s['events']:ui.render_event(MagicMock(),s,event)
            json.loads(json.dumps(s))

    def test_menu_pagination_and_callbacks_fit_telegram_limit(self):
        s=ready(40);s['phase']='vote';p=s['players'][0];seen=[]
        for page in range(5):
            _,k=ui.menu(s,int(p['id']),'vote',page)
            for row in k.keyboard:
                for b in row:
                    self.assertLessEqual(len(b.callback_data.encode()),64)
                    parts=b.callback_data.split(':')
                    if parts[3]=='vote' and parts[4]!='skip':seen.append(parts[4])
        self.assertEqual(len(set(seen)),39)

    def test_anonymous_group_card_does_not_reveal_player_names(self):
        s=ready(8,anonymous=True)
        body,_=ui.render_event(MagicMock(),s,dict(kind='phase'))
        for p in s['players']:self.assertNotIn(p['name'],body)

    def test_serialized_restart_retains_secrets_choices_and_deadline(self):
        s=ready();g.act(s,s['players'][0]['id'],'loc','2')
        restored=json.loads(json.dumps(s,ensure_ascii=False))
        self.assertEqual(restored,s);self.assertEqual(restored['actions'],s['actions'])
        epoch=s['epoch'];g.advance(restored,restored['deadline'],random.Random(1))
        self.assertGreater(restored['epoch'],epoch)

    def test_phase_settings_snapshot_does_not_mutate_active_game(self):
        s=ready(night_seconds=60);self.assertEqual(s['deadline'],260)
        with patch.object(ui,'setting_value',return_value=180):
            self.assertEqual(s['rules']['night_seconds'],60)

    def test_cancel_no_rewards_and_no_restart(self):
        s=ready();g.cancel(s);self.assertEqual(s['phase'],'cancelled');self.assertEqual(s['awardees'],[])
        self.assertFalse(g.advance(s,999999,random.Random(1)))

    def test_transactional_reward_sql_marker_and_points_same_cursor(self):
        s=ready();s['awardees']=[dict(uid='1',points=15)];s['events']=[]
        cur=MagicMock();cur.fetchone.return_value=(1,)
        ui.persist(cur,s,700)
        statements=[c.args[0] for c in cur.execute.call_args_list]
        self.assertTrue(any('ON CONFLICT DO NOTHING RETURNING' in x for x in statements))
        self.assertTrue(any('INSERT INTO player_stats' in x for x in statements))
        self.assertTrue(any('INSERT INTO reward_transactions' in x for x in statements))
        cur.reset_mock();cur.fetchone.return_value=None;ui.persist(cur,s,800)
        self.assertFalse(any('INSERT INTO player_stats' in call.args[0] for call in cur.execute.call_args_list))

    def test_randomized_full_games_all_counts_modes_bounded(self):
        completed=0
        for seed in range(3000):
            n=8+seed%33;rng=random.Random(seed)
            s=ready(n,seed,traitor=bool(seed%2),anonymous=bool(seed%3==0))
            for step in range(40):
                if s['phase'] in ('finished','cancelled'):break
                if s['phase']=='night':
                    for p in s['players']:
                        if not p['alive']:
                            if not p['departed']:g.act(s,p['id'],'ghost',str(rng.randrange(6)))
                            continue
                        if seed%11==0 and p['number']%4==0:continue
                        g.act(s,p['id'],'loc',str(rng.randrange(6)))
                        action=g.role_action(p);targets=g.available_targets(s,p,action)
                        if action not in g.DAY_ACTIONS and action!='search' and p['uses'] and targets and rng.random()<.8:
                            g.act(s,p['id'],'ability',rng.choice(targets))
                        if p['side']=='plot':
                            ts=[q for q in g.alive(s) if q['side']!='plot']
                            if ts:g.act(s,p['id'],'attack',rng.choice(ts)['id'])
                        if s['traitor_offer']==p['id']:g.act(s,p['id'],'traitor','yes' if rng.random()<.5 else 'no')
                        if not p['quest_done']:g.act(s,p['id'],'quest',sum(p['quest']))
                elif s['phase']=='day':
                    for p in g.alive(s)[:]:
                        if p['bag']:g.act(s,p['id'],'publish',p['bag'][-1])
                        if g.role_action(p) in g.DAY_ACTIONS and p['uses']:
                            targets=g.available_targets(s,p,g.role_action(p))
                            if targets:g.act(s,p['id'],g.role_action(p),rng.choice(targets))
                        if p['role']=='treasure' and len(p['relics'])>=3:g.act(s,p['id'],'escape','0')
                else:
                    for p in g.alive(s):
                        ts=[q['id'] for q in g.alive(s) if q is not p and (s['phase']!='runoff' or q['id'] in s['runoff'])]+['skip']
                        g.act(s,p['id'],'vote',rng.choice(ts))
                now=s['deadline']+1;g.advance(s,now,rng)
                self.assertEqual(len({p['id'] for p in s['players']}),n)
                self.assertTrue(all(0<=p['coins']<=8 for p in s['players']))
                self.assertLessEqual(len(s['awardees']),n)
                if seed<25:
                    for e in s['events']:
                        body,k=ui.render_event(NS(get_me=lambda:NS(username='testbot')),s,e)
                        self.assertNotRegex(body,r'\{[a-z][a-z_]*\}')
                s['events']=[]
            self.assertEqual(s['phase'],'finished',(seed,s['phase'],s['day']))
            completed+=1
        self.assertEqual(completed,3000)


if __name__=='__main__':unittest.main()


class NanYateTelegramTests(unittest.TestCase):
    def setUp(self):
        from contextlib import contextmanager
        self.bot=MagicMock();self.handlers={}
        for method in ('message_handler','callback_query_handler'):
            def factory(*args,**kwargs):
                def bind(fn):self.handlers[fn.__name__]=fn;return fn
                return bind
            getattr(self.bot,method).side_effect=factory
        self.state=ready();self.cur=MagicMock();self.cur.fetchone.return_value=None
        @contextmanager
        def tx(**kwargs):
            if kwargs.get('gid') and kwargs['gid']!=self.state['id']:raise ValueError('closed')
            yield self.cur,self.state,self.state['chat_id']
        self.patches=[patch.object(ui,'init_db'),patch.object(ui,'get_db_connection'),
                      patch.object(ui,'WORKER_STARTED',True),patch.object(ui,'transaction',tx),
                      patch.object(ui,'persist'),patch.object(ui,'invalidate_rewards'),
                      patch.object(ui,'admin',return_value=True),patch.object(ui,'end_session')]
        self.mocks=[p.start() for p in self.patches]
        ui.register(self.bot)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
    def q(self,kind,value='0',uid=1,epoch=None,private=True):
        return NS(id='cb',data=f"ny:{self.state['id']}:{self.state['epoch'] if epoch is None else epoch}:{kind}:{value}",
                  from_user=NS(id=uid,first_name='မေ'),message=NS(chat=NS(id=uid if private else self.state['chat_id'],type='private' if private else 'supergroup')))
    def invoke(self,q):
        with patch.object(ui.time,'time',return_value=210):self.handlers['callback_handler'](q)
    def test_stale_phase_cannot_apply_action(self):
        self.invoke(self.q('loc','2',epoch=self.state['epoch']-1));self.assertEqual(self.state['actions'],{})
        self.bot.answer_callback_query.assert_called_with('cb',ui.text('closed'),show_alert=True)
    def test_wrong_private_recipient_cannot_use_another_person_panel(self):
        q=self.q('loc','2');q.message.chat.id=999
        self.invoke(q);self.assertEqual(self.state['actions'],{})
    def test_public_group_cannot_expose_secret_action_menu(self):
        self.invoke(self.q('menu','ability.0',private=False))
        self.bot.send_message.assert_not_called();self.bot.answer_callback_query.assert_called()
    def test_nonparticipant_cannot_use_action(self):
        self.invoke(self.q('loc','2',uid=999));self.assertEqual(self.state['actions'],{})
    def test_late_action_rejected(self):
        self.state['deadline']=200;self.invoke(self.q('loc','2'));self.assertEqual(self.state['actions'],{})
    def test_accepted_action_uses_durable_panel_outbox(self):
        self.invoke(self.q('loc','2'));self.assertEqual(self.state['actions']['1']['loc'],2)
        self.bot.send_message.assert_not_called()
        self.assertTrue(any(e['kind']=='panel' and e['dest']=='1' for e in self.state['events']))
        self.mocks[4].assert_called()
    def test_duplicate_quest_does_not_duplicate_coin(self):
        q=self.q('quest',str(sum(self.state['players'][0]['quest'])))
        self.invoke(q);self.invoke(q);self.assertEqual(self.state['players'][0]['coins'],1)
    def test_unauthorized_admin_stop(self):
        self.mocks[6].return_value=False
        self.invoke(self.q('stopconfirmed',private=False));self.assertEqual(self.state['phase'],'night')
    def test_stop_requires_confirmation(self):
        self.invoke(self.q('stop',private=False));self.assertEqual(self.state['phase'],'night')
        self.invoke(self.q('stopconfirmed',private=False));self.assertEqual(self.state['phase'],'cancelled')
    def test_lobby_private_join_and_withdraw(self):
        self.state=g.create('abcdef123456',-909,1,{},100)
        self.bot.get_chat_member.return_value.status='member'
        self.invoke(self.q('join',uid=55));self.assertEqual(len(self.state['players']),1)
        self.invoke(self.q('join',uid=55));self.assertEqual(len(self.state['players']),1)
        self.invoke(self.q('withdraw',uid=55));self.assertEqual(self.state['players'],[])
    def test_group_outsider_cannot_join_via_private_link(self):
        self.state=g.create('abcdef123456',-909,1,{},100)
        self.bot.get_chat_member.return_value.status='left'
        self.invoke(self.q('join',uid=55));self.assertEqual(self.state['players'],[])
    def test_dead_player_cannot_relay_role_secrets(self):
        self.state['players'][0]['alive']=False
        msg=NS(chat=NS(type='private'),from_user=NS(id=1),text='/nychat abcdef123456 role leak')
        self.handlers['chat_command'](msg)
        self.assertFalse(any(e['kind']=='relay' for e in self.state['events']))


class NanYateDeliveryTests(unittest.TestCase):
    def connection(self,rows):
        con=MagicMock();con.__enter__.return_value=con
        cur=con.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect=rows
        return con,cur
    def test_worker_skips_stale_private_panel(self):
        s=ready();e=dict(kind='panel',epoch=s['epoch']-1,dest='1')
        con,cur=self.connection([(1,s['id'],1,e,0),(1,),(s,),None])
        bot=MagicMock()
        with patch.object(ui,'get_db_connection',return_value=con):ui.drain(bot)
        bot.send_message.assert_not_called();bot.edit_message_text.assert_not_called()
    def test_private_panel_edits_previous_message_and_coalesces(self):
        s=ready();s['players'][0]['panel_id']=123
        e=dict(kind='panel',epoch=s['epoch'],dest='1')
        con,cur=self.connection([(1,s['id'],1,e,0),(7,),(s,),None]);bot=MagicMock()
        with patch.object(ui,'get_db_connection',return_value=con):ui.drain(bot)
        self.assertEqual(bot.edit_message_text.call_args.args[1:3],(1,123))
        self.assertTrue(any('id<=%s' in call.args[0] for call in cur.execute.call_args_list))
        bot.send_message.assert_not_called()
    def test_group_telegram_pacing_defers_without_loss(self):
        s=ready();s['group_delivery_at']=1000;e=dict(kind='phase',epoch=s['epoch'],dest=str(s['chat_id']))
        con,cur=self.connection([(1,s['id'],s['chat_id'],e,0),(1,),(s,),None]);bot=MagicMock()
        with patch.object(ui,'get_db_connection',return_value=con),patch.object(ui.time,'time',return_value=1001):ui.drain(bot)
        bot.send_message.assert_not_called()
        self.assertTrue(any('next_try=NOW()' in call.args[0] for call in cur.execute.call_args_list))
    def test_result_updates_main_card_and_removes_game_buttons(self):
        s=ready();s['card']=123;s['winner']='court';g.finish(s)
        e=dict(kind='result',epoch=s['epoch'],dest=str(s['chat_id']))
        con,cur=self.connection([(1,s['id'],s['chat_id'],e,0),(1,),(s,),None]);bot=MagicMock()
        with patch.object(ui,'get_db_connection',return_value=con):ui.drain(bot)
        self.assertEqual(bot.edit_message_text.call_args.args[1:3],(s['chat_id'],123))
        self.assertIsNone(bot.edit_message_text.call_args.kwargs['reply_markup'])
    def test_restart_extends_expired_phase_and_preserves_selections(self):
        from contextlib import contextmanager
        s=ready();s['updated']=100;s['deadline']=150;g.act(s,'1','loc','2');old=copy.deepcopy(s['actions'])
        @contextmanager
        def tx(**kwargs):yield MagicMock(),s,s['chat_id']
        con,cur=self.connection([]);cur.fetchall.return_value=[(s['chat_id'],)]
        with patch.object(ui,'transaction',tx),patch.object(ui,'get_db_connection',return_value=con),patch.object(ui,'start_session'),patch.object(ui,'persist'),patch.object(ui,'drain'),patch.object(ui.time,'time',return_value=300):ui.tick(MagicMock())
        self.assertEqual(s['deadline'],330);self.assertEqual(s['actions'],old);self.assertEqual(s['phase'],'night')
    def test_session_concurrent_reservation_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from core import sessions
        cid=-876432
        sessions.end_session(cid,'nan_yate');sessions.end_session(cid,'imposter')
        with patch('features.owner_operations.feature_allowed',return_value=True),patch('features.owner_operations.usage'):
            with ThreadPoolExecutor(max_workers=10) as pool:
                outcomes=list(pool.map(lambda i:sessions.start_session(cid,'nan_yate' if i%2 else 'imposter')[0],range(10)))
        self.assertEqual(sum(outcomes),1)
        sessions.end_session(cid,'nan_yate');sessions.end_session(cid,'imposter')
