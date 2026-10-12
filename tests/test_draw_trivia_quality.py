import json,random,unittest
from pathlib import Path
from unittest.mock import patch
from games import draw_guess as draw
from core import trivia_myanmar as mm
from core.customization import validate,CATALOG

class DrawExpansionTests(unittest.TestCase):
    def test_curated_bank_and_editor_agree(self):
        self.assertGreaterEqual(len(draw.WORDS),500)
        self.assertLessEqual(len(draw.WORDS),800)
        self.assertEqual(len(draw.WORDS),len({draw.normalize(w) for w,a in draw.WORDS}))
        words=[w for w,a in draw.WORDS]
        validate('cfg.features.draw_guess.words',words)
        self.assertEqual(CATALOG['cfg.features.draw_guess.words']['default'],words)
        self.assertIn('ကြောင်လေး',dict(draw.WORDS)['ကြောင်'])

    def test_group_size_shifts_difficulty_without_selecting_mode(self):
        means=[]
        for size in (3,6,12):
            rng=random.Random(91)
            levels=[draw.word_level(draw.choose_word(draw.WORDS,size,rng)[0]) for _ in range(4000)]
            means.append(sum(levels)/len(levels))
            if size==3:self.assertNotIn(3,levels)
        self.assertLess(means[0],means[1]);self.assertLess(means[1],means[2])

    def test_custom_only_bank_stays_playable_and_no_repeat(self):
        bank=[('ကိုယ်ပိုင်ပုံတစ်',[]),('ကိုယ်ပိုင်ပုံနှစ်',[])]
        for n in (2,6,12):self.assertIn(draw.choose_word(bank,n,random.Random(n)),bank)
        s=draw.create('q',-1,1,{},0)
        for i in range(2):draw.join(s,i,str(i))
        draw.begin(s,1,random.Random(1),bank)
        first=s['word'];draw.next_round(s,100,random.Random(2),bank)
        self.assertNotEqual(s['word'],first)

class TriviaMyanmarTests(unittest.TestCase):
    def test_common_facts_do_not_need_translation_service(self):
        with patch.object(mm.urllib.request,'urlopen',side_effect=AssertionError('network')):
            out=mm.translate_question({'question':'What is the capital of Myanmar?','answers':['123','45','67','89'],'correct_index':2})
        self.assertIn('မြို့တော်',out['question']);self.assertIn('Myanmar',out['question'])
        self.assertEqual(out['correct_index'],2);self.assertEqual(out['answers'],['123','45','67','89'])

    def test_local_wording_deduplicates_only_prefixes(self):
        self.assertEqual(mm.clean('General Quiz: ကမ္ဘာက ဘယ်ပုံစံလဲ?'),mm.clean('ကမ္ဘာက ဘယ်ပုံစံလဲ?'))
        self.assertIn('ကိန်းစဉ်',mm.clean('အောက်က sequence ကိုဆက်ပါ — 1, 2, ?'))
        self.assertNotEqual(mm.clean('10 + 20 = ?'),mm.clean('20 + 10 = ?'))

    def test_numeric_answer_and_date_identity(self):
        for text in ('2010','1.50','100,000','25%','အင်္ဂါဂြိုဟ်'):
            with patch.object(mm.urllib.request,'urlopen',side_effect=AssertionError('network')):self.assertEqual(mm.translate(text),text)

    def test_uncertain_answer_translation_keeps_original(self):
        q={'question':'Unknown question text here?','answers':['Alpha','Beta','Gamma','Delta'],'correct_index':1}
        with patch.object(mm,'translate',side_effect=lambda t:'ဘာသာပြန်'):
            out=mm.translate_question(q)
        self.assertEqual(len(set(out['answers'])),4)
        self.assertIn('Beta',out['answers'][1]);self.assertEqual(out['correct_index'],1)

    def test_failed_or_number_changing_translation_falls_back(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return self.payload
        for status,translated in [(403,'သတ်မှတ်ချက်'),(200,'၂၀၂၀ ခုနှစ်မှာ မေးခွန်း')]:
            response=Response();response.payload=json.dumps({'responseStatus':status,'responseData':{'translatedText':translated}}).encode()
            with patch.object(mm.urllib.request,'urlopen',return_value=response):
                self.assertEqual(mm.translate('Unknown fact in 2010?'),'Unknown fact in 2010?')

    def test_valid_translation_is_cached(self):
        mm._CACHE.clear()
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return json.dumps({'responseStatus':200,'responseData':{'translatedText':'ဤမေးခွန်းကို ဖြေပါ'}}).encode()
        with patch.object(mm.urllib.request,'urlopen',return_value=Response()) as fetch:
            self.assertEqual(mm.translate('A novel test question?'),'ဤမေးခွန်းကို ဖြေပါ')
            self.assertEqual(mm.translate('A novel test question?'),'ဤမေးခွန်းကို ဖြေပါ')
            self.assertEqual(fetch.call_count,1)

if __name__=='__main__':unittest.main()
