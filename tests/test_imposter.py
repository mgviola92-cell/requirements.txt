import unittest
from data.imposter_words import WORDS
from features.imposter import _start_clues, _start_final, _decide, _keyboard, _view

class ImposterOfflineTests(unittest.TestCase):
    def state(self):
        return {"id":"abc123","phase":"join","deadline":0,"players":[
            {"id":i+10,"name":"ကစားသူ "+str(i+1),"afk":0,"removed":False}
            for i in range(4)],"imposter":11,"word":"စာအုပ်","round":0,"turn":0,
            "warned":False,"decisions":{},"votes":{},"message_id":123}
    def test_burmese_word_bank_unique(self):
        self.assertGreaterEqual(len(WORDS),250)
        self.assertEqual(len(WORDS),len(set(WORDS)))
        self.assertTrue(all(isinstance(w,str) and w for w in WORDS))
    def test_no_public_secret_in_group_view(self):
        s=self.state()
        for stage in ("join","clue","decision","tie","final"):
            s["phase"]=stage
            rendered=_view(s)
            self.assertNotIn("စာအုပ်",rendered)
            self.assertNotIn("11",rendered)
    def test_clue_round_and_decision(self):
        s=self.state()
        _start_clues(s)
        self.assertEqual(s["phase"],"clue")
        self.assertEqual(s["round"],1)
        _decide(s,"more")
        self.assertEqual(s["round"],2)
        _decide(s,"guess")
        self.assertEqual(s["phase"],"final")
    def test_max_round_falls_through_to_final(self):
        s=self.state()
        s["round"]=5
        _decide(s,"more")
        self.assertEqual(s["phase"],"final")
    def test_vote_pagination(self):
        s=self.state()
        s["phase"]="final"
        s["players"]=[{"id":i,"name":str(i)} for i in range(21)]
        kb=_keyboard(s,page=1)
        payload=[b.callback_data for row in kb.keyboard for b in row]
        self.assertIn("imp:abc123:vote:8",payload)
        self.assertIn("imp:abc123:page:2",payload)
