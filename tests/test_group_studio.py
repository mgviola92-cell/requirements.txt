import hashlib,hmac,io,json,random,time,unittest
from datetime import datetime,timezone
from types import SimpleNamespace as NS
from urllib.parse import urlencode
from unittest.mock import MagicMock,patch
from flask import Flask
from PIL import Image
from core import group_content as content,customization as custom
from features import group_studio as studio,draw_guess as draw,owner_dashboard as owner
from games import draw_guess as game


def signed(uid,token='123:test',stamp=1000,**extra):
    data={'auth_date':str(stamp),'user':json.dumps({'id':uid}),**extra}
    key=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    data['hash']=hmac.new(key,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(data)
def ready(n=3):
    s=game.create('abc123',-100,1,{},100)
    for i in range(1,n+1):game.join(s,i,str(i))
    game.begin(s,200,random.Random(1));s['events']=[];return s


class ContentTests(unittest.TestCase):
    def test_preserve_voice_photo_text_without_forward_reference(self):
        for kind in ('voice','photo','text'):
            m=NS(content_type=kind,text='hello',html_text='<b>hello</b>',caption=None,html_caption=None)
            setattr(m,kind,[NS(file_id='photo')] if kind=='photo' else NS(file_id='voice'))
            p=content.capture(m);self.assertEqual(p['kind'],kind);self.assertNotIn('source_chat',p)
    def test_html_and_arbitrary_actions_rejected(self):
        for p in ({'kind':'exec','text':'rm'}, {'kind':'text','text':'<script>bad</script>'},{'kind':'text','text':'<b>unclosed'},{'kind':'voice','file_id':'x','url':'https://evil.test'}):
            with self.assertRaises(ValueError):content.validate(p)
    def test_templates_escape_user_input_and_do_not_execute(self):
        p=content.substitute({'kind':'text','text':'Hello {name} {args}'},{'name':'<script>x</script>','args':'{__import__(os)}'})
        self.assertIn('&lt;script&gt;',p['text']);self.assertIn('{__import__(os)}',p['text'])
    def test_voice_delivery_uses_send_voice(self):
        bot=MagicMock();content.deliver(bot,-1,{'kind':'voice','file_id':'ABC','caption':'hey'})
        bot.send_voice.assert_called_once_with(-1,'ABC',caption='hey',parse_mode='HTML')
    def test_capsule_myanmar_date_is_utc_and_no_past_or_far_future(self):
        dt=studio.when('2026-10-12 20:00',now=datetime(2026,10,12,tzinfo=timezone.utc).timestamp())
        self.assertEqual(dt.astimezone(timezone.utc).hour,13);self.assertEqual(dt.astimezone(timezone.utc).minute,30)
        for bad in ('tomorrow','2020-01-01 00:00','2030-01-01 00:00'):
            with self.assertRaises(ValueError):studio.when(bad,now=1700000000)
    def test_name_restrictions(self):
        self.assertEqual(studio.name('Hello_2'),'hello_2')
        for bad in ('a','../x','eval()','bad name','x'*33):
            with self.assertRaises(ValueError):studio.name(bad)
    def test_group_scope_precedence_query(self):
        cur=MagicMock();cur.fetchone.return_value=([{'kind':'text','text':'x'}],)
        studio.asset(cur,-100,'command','hi');self.assertIn('ORDER BY scope ASC',cur.execute.call_args.args[0])
    def test_reserved_commands_cannot_be_shadowed(self):
        with patch.object(studio,'BUILTINS',{'draw','owner','nanyate'}):
            with self.assertRaises(ValueError):studio.asset_save(MagicMock(),-1,'command','owner',[{'kind':'text','text':'x'}],1)
    def test_command_append_is_limited_and_transactional(self):
        cur=MagicMock();cur.fetchone.return_value=([{'kind':'text','text':'x'}]*5,)
        with self.assertRaises(ValueError):studio.asset_save(cur,-1,'command','hello',[{'kind':'text','text':'x'}],1,append=True)
        self.assertFalse(any('INSERT INTO group_studio_assets' in c.args[0] for c in cur.execute.call_args_list))
    def test_owner_forms_plain_steps_support_existing_media(self):
        data=studio.form_payloads({'kind0':'text','body0':'Hi {name}','kind1':'voice','file1':'ABC','body1':''},'command')
        self.assertEqual(len(data),2);self.assertEqual(data[1]['file_id'],'ABC')
        for p in data:content.validate(p)
        html=studio.asset_form(-100,'command','hello',data,'token');self.assertNotIn('steps JSON',html);self.assertIn('body0',html)
    def test_book_never_executes_user_html_and_has_original_ids(self):
        rows=[(12,'<script>x</script>',{'kind':'text','text':'<b>hello</b>'},datetime.now(timezone.utc))]
        html=studio.book(rows,'book').decode();self.assertNotIn('<script>',html);self.assertIn('/memory 12',html);self.assertIn('hello',html)
    def test_job_idempotency_and_retry_data_persist(self):
        cur=MagicMock();cur.fetchone.return_value=(77,)
        self.assertEqual(studio.enqueue(cur,'req',-1,1,{'kind':'text','text':'Hi'}),77)
        self.assertIn('ON CONFLICT(request_key) DO NOTHING',cur.execute.call_args.args[0])
    def test_credit_requires_new_unique_reward_marker(self):
        cur=MagicMock();cur.fetchone.return_value=None;studio.credit(cur,'key',-100,1,10)
        self.assertEqual(cur.execute.call_count,1)
    def test_custom_dispatch_before_legacy_filters_but_reserved_commands_excluded(self):
        bot=NS(message_handlers=[{'filters':{'commands':['owner','draw']}},{'filters':{'func':lambda m:True}}],_studio_custom_handler=lambda m:None)
        def decorator(**kwargs):
            def bind(fn):bot.message_handlers.append({'filters':kwargs,'function':fn});return fn
            return bind
        bot.message_handler=decorator
        with patch.object(studio,'BUILTINS',set()):
            studio.register_custom_handler(bot);self.assertEqual(bot.message_handlers[0]['function'],bot._studio_custom_handler)
            self.assertIn('owner',studio.BUILTINS)


class DrawTests(unittest.TestCase):
    def test_hmac_valid_invalid_old_duplicate_fields(self):
        self.assertEqual(draw.authenticate(signed(42),'123:test',now=1100),42)
        for raw in (signed(42)+'&user=x',signed(42).replace('auth_date=1000','auth_date=1001'),signed(42,stamp=1)):
            with self.assertRaises(ValueError):draw.authenticate(raw,'123:test',now=5000)
    def test_hmac_includes_telegram_signature_field(self):
        self.assertEqual(draw.authenticate(signed(42,signature='abc'),'123:test',now=1100),42)
    def test_png_size_and_format_validation(self):
        import base64
        im=Image.new('RGB',(760,500),'white');out=io.BytesIO();im.save(out,'PNG')
        raw='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode();self.assertTrue(draw.png(raw))
        for value in ('data:image/jpeg;base64,x','data:image/png;base64,notbase64'):
            with self.assertRaises(ValueError):draw.png(value)
        im=Image.new('RGB',(1,1));out=io.BytesIO();im.save(out,'PNG')
        with self.assertRaises(ValueError):draw.png('data:image/png;base64,'+base64.b64encode(out.getvalue()).decode())
    def test_lobby_duplicate_join_capacity_and_minimum(self):
        s=game.create('a',-1,1,{},0);game.join(s,1,'a');game.join(s,1,'a');self.assertEqual(len(s['players']),1)
        with self.assertRaises(ValueError):game.begin(s,1,random.Random(1))
        for i in range(2,13):game.join(s,i,str(i))
        with self.assertRaises(ValueError):game.join(s,13,'x')
    def test_only_drawer_can_submit_and_expired_round_rejects(self):
        s=ready();other=next(p['id'] for p in s['players'] if p['id']!=s['drawer'])
        with self.assertRaises(ValueError):game.submit(s,other,210)
        with self.assertRaises(ValueError):game.submit(s,s['drawer'],999999)
        game.submit(s,s['drawer'],210);self.assertEqual(s['phase'],'guess');self.assertEqual(s['deadline'],300)
    def test_first_guess_only_awards_once_and_drawer_cannot_guess(self):
        s=ready();game.submit(s,s['drawer'],210);word=s['word'];drawer=s['drawer']
        self.assertFalse(game.guess(s,drawer,word,220,random.Random(1)))
        other=next(p['id'] for p in s['players'] if p['id']!=drawer)
        self.assertTrue(game.guess(s,other,word,220,random.Random(1)))
        self.assertEqual(len(s['awards']),2);self.assertFalse(game.guess(s,other,word,221,random.Random(1)))
        self.assertEqual(len(s['awards']),2)
    def test_burmese_normalization_and_alias(self):
        self.assertEqual(game.normalize(' ကြောင်\u200b '),game.normalize('ကြောင်'))
        s=ready();s['word']='ကြောင်';s['aliases']=['ကြောင်လေး'];game.submit(s,s['drawer'],210)
        other=next(p['id'] for p in s['players'] if p['id']!=s['drawer'])
        self.assertTrue(game.guess(s,other,'ကြောင်လေး',220,random.Random(1)))
    def test_all_players_get_turn_and_words_do_not_repeat(self):
        s=ready(12);seen=[];words=[]
        while s['phase']!='finished':
            seen.append(s['drawer']);words.append(s['word']);game.advance(s,s['deadline']+1,random.Random(s['round']))
        self.assertEqual(len(set(seen)),12);self.assertEqual(len(set(words)),12)
    def test_serialization_and_restart_preserves_round_ticket(self):
        s=ready();s['ticket']='secret';self.assertEqual(json.loads(json.dumps(s)),s)
        game.next_round(s,400,random.Random(1));self.assertIsNone(s['ticket'])
    def test_draw_word_owner_validation(self):
        for words in (['a','a'],['\u200b'],['x'*41]):
            with self.assertRaises(ValueError):custom.validate('cfg.features.draw_guess.words',words)
    def test_many_full_games_terminate_for_every_player_count(self):
        for seed in range(1000):
            s=ready(2+seed%11);rng=random.Random(seed)
            for _ in range(30):
                if s['phase']=='finished':break
                if seed%2:
                    game.submit(s,s['drawer'],s['deadline']-1)
                    p=next(p for p in s['players'] if p['id']!=s['drawer'])
                    game.guess(s,p['id'],s['word'],s['deadline']-1,rng)
                else:game.advance(s,s['deadline']+1,rng)
            self.assertEqual(s['phase'],'finished')


class StudioWebTests(unittest.TestCase):
    def setUp(self):
        self.bot=MagicMock();self.bot.message_handler.side_effect=lambda *a,**kw:lambda fn:fn
        self.app=Flask(__name__);self.app.secret_key='secret'
        self.conn=MagicMock();self.conn.__enter__.return_value=self.conn
        self.cur=self.conn.cursor.return_value.__enter__.return_value;self.cur.fetchall.return_value=[];self.cur.fetchone.return_value=None
        self.patches=[patch.object(studio,'initialize'),patch.object(studio,'get_db_connection',return_value=self.conn),patch.object(studio,'STARTED',True),patch.object(owner,'_ready',return_value=True)]
        for p in self.patches:p.start()
        self.app.register_blueprint(owner.dashboard)
        studio.register(self.app,self.bot);self.client=self.app.test_client()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
    def login(self):
        with self.client.session_transaction() as s:s['owner']=True;s['csrf']='right'
    def test_owner_auth_required(self):self.assertEqual(self.client.get('/owner/studio/').status_code,302)
    def test_csrf_failure_does_not_mutate(self):
        self.login();self.cur.reset_mock()
        r=self.client.post('/owner/studio/',data={'csrf':'wrong','scope':'0','kind':'command','name':'hello','body0':'Hi'})
        self.assertEqual(r.status_code,403);self.assertFalse(any('INSERT' in c.args[0] or 'DELETE' in c.args[0] for c in self.cur.execute.call_args_list))
    def test_web_command_creation_plain_text_steps(self):
        self.login();r=self.client.post('/owner/studio/',data={'csrf':'right','scope':'0','kind':'command','name':'hello','body0':'Hi {name}','action':'save'})
        self.assertEqual(r.status_code,200)
        self.assertTrue(any('INSERT INTO group_studio_assets' in c.args[0] for c in self.cur.execute.call_args_list))
    def test_script_payload_rolls_back_before_save(self):
        self.login();r=self.client.post('/owner/studio/',data={'csrf':'right','scope':'0','kind':'command','name':'hello','body0':'<script>bad</script>','action':'save'})
        self.assertEqual(r.status_code,200)
        self.assertFalse(any('INSERT INTO group_studio_assets' in c.args[0] for c in self.cur.execute.call_args_list))


class DrawApiTests(unittest.TestCase):
    def setUp(self):
        from contextlib import contextmanager
        self.s=ready();self.s['ticket']='private-ticket';self.s['deadline']=1200
        self.cur=MagicMock();self.bot=MagicMock()
        for method in ('message_handler','callback_query_handler'):getattr(self.bot,method).side_effect=lambda *a,**kw:lambda fn:fn
        @contextmanager
        def tx(**kwargs):
            if kwargs.get('gid')!=self.s['id']:raise ValueError('closed')
            yield self.cur,self.s,self.s['chat_id']
        self.patches=[patch.object(draw,'init_db'),patch.object(draw,'STARTED',True),patch.object(draw,'tx',tx),patch.object(draw,'persist'),patch.dict('os.environ',{'BOT_TOKEN':'123:test'}),patch.object(draw.time,'time',return_value=1100)]
        for p in self.patches:p.start()
        self.app=Flask(__name__);draw.register(self.app,self.bot);self.client=self.app.test_client()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
    def data(self,uid=None):return {'game':self.s['id'],'ticket':'private-ticket','init_data':signed(int(self.s['drawer']) if uid is None else uid),'action':'state'}
    def test_authorized_drawer_only_sees_word(self):
        r=self.client.post('/draw/api',json=self.data());self.assertEqual(r.status_code,200);self.assertEqual(r.json['word'],self.s['word'])
        r=self.client.post('/draw/api',json=self.data(999));self.assertEqual(r.status_code,403);self.assertNotIn('word',r.json)
    def test_wrong_ticket_cannot_get_secret(self):
        d=self.data();d['ticket']='forged';r=self.client.post('/draw/api',json=d);self.assertEqual(r.status_code,403)
    def test_missing_or_forged_telegram_identity_cannot_submit(self):
        d=self.data();d['init_data']='';d['action']='image';r=self.client.post('/draw/api',json=d)
        self.assertEqual(r.status_code,403);self.assertIsNone(self.s['image'])
    def test_valid_canvas_submission_persists_and_queues_group_image(self):
        import base64
        raw=io.BytesIO();Image.new('RGB',(760,500),'white').save(raw,'PNG')
        d=self.data();d.update(action='image',image='data:image/png;base64,'+base64.b64encode(raw.getvalue()).decode())
        r=self.client.post('/draw/api',json=d);self.assertEqual(r.status_code,200);self.assertEqual(self.s['phase'],'guess')
        self.assertTrue(any(e['kind']=='image' for e in self.s['events']))
        r=self.client.post('/draw/api',json=d);self.assertEqual(r.status_code,400);self.assertEqual(len(self.s['events']),1)
    def test_canvas_source_has_no_embedded_secret(self):
        r=self.client.get('/draw/play?game=abc&ticket=secret');self.assertEqual(r.status_code,200)
        self.assertNotIn(self.s['word'],r.text);self.assertEqual(r.headers['Referrer-Policy'],'no-referrer')


class StudioJobTests(unittest.TestCase):
    def con(self,rows):
        con=MagicMock();con.__enter__.return_value=con;cur=con.cursor.return_value.__enter__.return_value;cur.fetchone.side_effect=rows;return con,cur
    def test_capsule_sends_stored_file_not_deleted_source_message(self):
        con,cur=self.con([(1,-100,{'kind':'voice','file_id':'VOICE'},'capsule',0),None]);bot=MagicMock()
        with patch.object(studio,'get_db_connection',return_value=con):studio.run_jobs(bot)
        bot.send_voice.assert_called_once();bot.forward_message.assert_not_called()
        self.assertTrue(any("status='sent'" in c.args[0] for c in cur.execute.call_args_list))
    def test_chain_waits_for_previous_step(self):
        con,cur=self.con([(2,-100,{'chain':'x','content':{'kind':'text','text':'Hi'}},'chain',0),('pending',),None]);bot=MagicMock()
        with patch.object(studio,'get_db_connection',return_value=con):studio.run_jobs(bot)
        bot.send_message.assert_not_called()
    def test_chain_cancels_after_failed_step(self):
        con,cur=self.con([(2,-100,{'chain':'x','content':{'kind':'text','text':'Hi'}},'chain',0),('failed',),None]);bot=MagicMock()
        with patch.object(studio,'get_db_connection',return_value=con):studio.run_jobs(bot)
        self.assertTrue(any("status='cancelled'" in c.args[0] for c in cur.execute.call_args_list));bot.send_message.assert_not_called()
    def test_failed_send_retries_from_database(self):
        con,cur=self.con([(1,-100,{'kind':'text','text':'Hi'},'send',0),None]);bot=MagicMock();bot.send_message.side_effect=RuntimeError('offline')
        with patch.object(studio,'get_db_connection',return_value=con):studio.run_jobs(bot)
        calls=[c for c in cur.execute.call_args_list if 'attempts=attempts+1' in c.args[0]]
        self.assertEqual(calls[0].args[1][0],'pending')
