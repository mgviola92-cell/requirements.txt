"""Keep public help synchronized with actual handlers and safe to download."""
import ast
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from flask import Flask
from features import command_help as help

class CommandHelpTests(unittest.TestCase):
    def test_every_registered_alias_exactly_once(self):
        registered=set()
        for path in [help.ROOT/'bot.py',*(help.ROOT/'features').glob('*.py')]:
            for n in ast.walk(ast.parse(path.read_text())):
                if not isinstance(n,ast.Call):continue
                if isinstance(n.func,ast.Attribute) and n.func.attr=='message_handler':
                    for k in n.keywords:
                        if k.arg=='commands':
                            registered.update(ast.literal_eval(k.value))
        registered.update({'secret','ဖြေမယ်'})
        listed=[a for e in help.REFERENCE['entries'] for a in e['aliases']]
        self.assertEqual(registered,set(listed))
        self.assertEqual(len(listed),len(set(listed)))

    def test_all_pages_reach_every_alias_and_fit_telegram(self):
        for category in ['all',*help.REFERENCE['categories']]:
            chunks=help.pages(category)
            for i in range(len(chunks)):
                body,keyboard=help.view(category,i)
                self.assertLess(len(body.encode('utf-16-le'))//2,4096)
                self.assertTrue(keyboard.keyboard)
            combined='\n'.join(chunks)
            for e in help.REFERENCE['entries']:
                if category=='all' or category==e['category']:
                    for alias in e['aliases']:self.assertIn('/'+alias,combined)

    def test_guide_complete_offline_links(self):
        source=help.GUIDE.read_text()
        for e in help.REFERENCE['entries']:
            self.assertIn('id="'+e['id']+'"',source)
            for alias in e['aliases']:self.assertIn('/'+alias,source)
        ids=set(re.findall(r'id="([^"]+)"',source))
        for target in re.findall(r'href="#([^"]+)"',source):self.assertIn(target,ids)
        self.assertIn('data:font/ttf;base64,',source)
        self.assertNotIn('<script src=',source)

    def test_download_route_and_telegram_delivery(self):
        app=Flask(__name__);bot=MagicMock();help.register(app,bot)
        with app.test_client() as client:
            response=client.get('/guide')
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response.headers['Content-Disposition'])
            self.assertEqual(response.data,help.GUIDE.read_bytes())
            response.close()
        help.download(bot,-123)
        bot.send_document.assert_called_once()
        self.assertEqual(bot.send_document.call_args.args[0],-123)
        self.assertEqual(bot.send_document.call_args.kwargs['visible_file_name'],'bot_user_guide.html')

    def test_hidden_secret_alias_reserved_from_custom_override(self):
        from features import group_studio as studio
        from telebot import TeleBot
        bot=TeleBot('123:test');bot._studio_custom_handler=lambda m:None
        studio.register_custom_handler(bot)
        self.assertTrue({'secret','ဖြေမယ်'}<=studio.BUILTINS)

    def test_failed_document_delivery_is_reported(self):
        bot=MagicMock();bot.send_document.side_effect=RuntimeError('test delivery failure')
        with patch.object(help,'text',return_value='Retry /guide'):
            help.download(bot,123)
        bot.send_message.assert_called_once_with(123,'Retry /guide',parse_mode=None)

if __name__=='__main__':unittest.main()
