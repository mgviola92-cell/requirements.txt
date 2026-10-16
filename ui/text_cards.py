"""Small, readable Telegram text cards. No raster assets or image uploads."""
import time
from html.parser import HTMLParser
from dataclasses import dataclass
from core.customization import message_text
from config.ranks import get_rank_data, get_rank_progress

MESSAGES = {
 'speed_pending':'⚡ SPEED TAP\n━━━━━━━━━━━━━━\n🎲 အချိန်မရွေး စတင်မယ်။\n🟢 GO ပေါ်လာတာနဲ့ အမြန်ဆုံးနှိပ်ပါ။',
 'speed_wait':'⏳ ခဏစောင့်ပါ…\nGO မပေါ်ခင် နှိပ်ရင် မနိုင်ပါ။',
 'speed_go':'👇 အောက်ကခလုတ်ကို အမြန်နှိပ်ပါ။',
 'math':'🧮 MATH BATTLE · {round}/5\n━━━━━━━━━━━━━━\n\n{question}\n\n⏳ {seconds} စက္ကန့်\n⚡ အဖြေမှန်အမြန်ဆုံး ၃ ယောက်: +10 / +5 / +3 score\n\n🏆 လက်ရှိအမှတ်\n{leaders}',
 'math_result':'🏁 MATH BATTLE · ရလဒ်\n━━━━━━━━━━━━━━\n{leaders}',
 'word':'🔤 WORD CHAIN · {mode}\n━━━━━━━━━━━━━━\n\n🔗 လက်ရှိစကားလုံး: {word}\n➡️ ဆက်ရမည့်အစ: {required}\n\n⏳ နောက်အဖြေအတွက် {seconds} စက္ကန့်\n✅ ဆက်ထားပြီး {moves} ကြိမ်\n\n🏆 ထိပ်ဆုံးကစားသမားများ\n{leaders}\n\nတစ်ယောက်တည်း နှစ်ကြိမ်ဆက်တိုက် မဖြေရပါ။',
 'word_result':'🏁 WORD CHAIN · ရလဒ်\n━━━━━━━━━━━━━━\n{reason}\n\n{leaders}',
 'profile':'👤 {name}\n━━━━━━━━━━━━━━\n{emoji} {rank}\n⭐ အမှတ် {points}\n\n🏆 နိုင် {wins} · ရှုံး {losses} · သရေ {draws}\n🎮 ကစားပြီး {games} ပွဲ\n\n{progress}',
 'rank':'🏆 GROUP RANKING\n━━━━━━━━━━━━━━\n{leaders}',
 'reason_idle':'အချိန်မီ ဆက်ဖြေသူမရှိပါ။', 'reason_limit':'ပွဲချိန်ပြည့်ပါပြီ။',
 'reason_stop':'Admin က ပွဲရပ်လိုက်ပါပြီ။', 'reason_end':'ပွဲပြီးပါပြီ။',
 'empty':'ပါဝင်သူ မရှိသေးပါ။',
 'math_row':'{rank}. {name} · {score} score{reward}',
 'word_leader':'{rank}. {name} · {words} လုံး',
 'personal_message':'မတူညီသော အဓိပ္ပါယ်ရှိသည့်စာ {n} ကြိမ် ပို့ပါ',
 'personal_play':'Group ဂိမ်းတွင် {n} ကြိမ် ပါဝင်ပါ',
 'personal_correct':'ဂိမ်းမေးခွန်း {n} ခု မှန်အောင်ဖြေပါ',
 'personal_win':'ဂိမ်း {n} ပွဲ အနိုင်ရပါ',
 'personal_math':'Math Battle အဖြေ {n} ခု မှန်အောင်ဖြေပါ',
 'personal_word':'Word Chain တွင် စကားလုံး {n} လုံး ဆက်ပါ',
 'word_row':'{rank}. {name} · {words} လုံး · {reward}',
 'rank_row':'{medal} {name}\n    ⭐ {points} · 🏆 {wins} · 🎮 {games}',
 'next_rank':'{bar} {percent}%\nနောက်တစ်ဆင့် {rank} အတွက် {remaining} မှတ်လိုသည်။',
 'max_rank':'💫 အမြင့်ဆုံး Rank ရောက်ရှိပြီးပါပြီ။',
 'daily':'🎯 DAILY CHALLENGE\n━━━━━━━━━━━━━━\n📅 {day} · {mode}{double}\n\n{missions}\n\n{claim}',
 'personal':'ကိုယ်ပိုင်မစ်ရှင်များ', 'group':'Group မစ်ရှင်များ', 'double':' · ✨ ဆုနှစ်ဆနေ့',
 'daily_mission':'{number}. {description}\n{bar} {progress}/{needed}\n🎁 {lo}–{hi} points · {status}',
 'daily_group_mission':'{number}. {description}\n{bar} {progress}/{needed}\n👥 {users}/{unique} ယောက် · ကိုယ်တိုင် {mine}/{personal}\n🎁 {lo}–{hi} points{status}',
 'claimed':'✅ ဆုယူပြီး', 'ready':'✅ ဆုယူနိုင်ပြီ', 'ongoing':'⏳ ဆက်လုပ်ရန်',
 'claim_personal':'ဆုယူရန် /dailyclaim 1–3', 'claim_group':'ဆုယူရန် /dailygroupclaim 1–3',
 'message':'အဓိပ္ပါယ်ရှိပြီး မတူညီသောစာများ ပို့ပါ', 'play':'Group ဂိမ်းများ ပါဝင်ကစားပါ',
 'correct':'ဂိမ်းမေးခွန်းများ မှန်အောင်ဖြေပါ', 'win':'Group ဂိမ်းများ အနိုင်ရပါ',
 'reward':' +{points} points', 'reward_error':'ဆုသိမ်းမရသေး',
}

def text(key, **fields):
    return message_text('msg.ui.text_cards.'+key,MESSAGES[key],fields)

def bar(ratio):
    count=max(0,min(10,int(ratio*10)))
    return '▰'*count+'▱'*(10-count)

class _Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def plain(value):
    parser=_Plain();parser.feed(str(value or ''));return ''.join(parser.parts)

@dataclass
class TextCard:
    media: str
    caption: str = None
    parse_mode: str = None

def content(card,caption=None,parse_mode=None):
    heading=plain(caption) if parse_mode else str(caption or '')
    # The complete card already contains its heading; speed captions add live status.
    body=str(card or '')
    if body and heading and body.startswith(('🧮','🏁','🔤','👤','🏆','🎯','⚡ SPEED')):return body
    return '\n\n'.join(p for p in (heading,body) if p)

def send_card(bot,chat_id,card,caption=None,**kwargs):
    mode=kwargs.pop('parse_mode',None)
    return bot.send_message(chat_id,content(card,caption,mode),parse_mode=None,**kwargs)

def edit_card(bot,media,chat_id=None,message_id=None,**kwargs):
    return bot.edit_message_text(content(media.media,media.caption,media.parse_mode),chat_id,message_id,parse_mode=None,**kwargs)

def speed_pending(**kwargs):return text('speed_pending')
def speed_wait(**kwargs):return text('speed_wait')
def speed_go(**kwargs):return text('speed_go')
def speed_result(**kwargs):return ''  # Existing editable caption contains all result fields.
def speed_timeout(**kwargs):return ''
def get_speed_tap_background():return None

def math_round(game):
    ranked=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))[:3]
    leaders='\n'.join(text('math_row',rank=i,name=str(game['names'].get(uid,'Player'))[:80],score=score,reward='') for i,(uid,score) in enumerate(ranked,1)) or text('empty')
    return text('math',round=game['round']+1,question=game['question']['question'],seconds=max(0,int(game['deadline']-time.monotonic()+.99)),leaders=leaders)

def math_result(game,rewards):
    ranked=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))[:10]
    rows=[text('math_row',rank=i,name=str(game['names'].get(uid,'Player'))[:80],score=score,reward=text('reward',points=rewards[uid]) if uid in rewards else '') for i,(uid,score) in enumerate(ranked,1)]
    return text('math_result',leaders='\n'.join(rows) or text('empty'))

def word_status(game):
    ranked=sorted(game['scores'].items(),key=lambda x:(-x[1],x[0]))[:3]
    rows=[text('word_leader',rank=i,name=str(game['names'].get(uid,'Player'))[:80],words=score) for i,(uid,score) in enumerate(ranked,1)]
    return text('word',mode='မြန်မာ' if game['mode']=='my' else 'English',word=game['word'],required=game['required'],seconds=max(0,int(min(game['idle_deadline'],game['deadline'])-time.monotonic()+.99)),moves=game['moves'],leaders='\n'.join(rows) or text('empty'))

def word_result(game,rows,reason):
    labels={'60 seconds no answer':'reason_idle','Round time limit':'reason_limit','Stopped by admin':'reason_stop','Game ended':'reason_end'}
    leaders=[text('word_row',rank=r['rank'],name=str(r['name'])[:80],words=r['words'],reward=text('reward_error') if r.get('reward_error') else text('reward',points=r['points'])) for r in rows[:10]]
    return text('word_result',reason=text(labels.get(reason,'reason_end')),leaders='\n'.join(leaders) or text('empty'))

def profile(player_name,points,wins,games,losses,draws,**kwargs):
    rank=get_rank_data(points);ratio=get_rank_progress(points)
    progress=text('next_rank',bar=bar(ratio),percent=int(ratio*100),rank=rank['next_rank'],remaining=max(0,rank['next_points']-points)) if rank.get('next_points') is not None else text('max_rank')
    return text('profile',name=str(player_name)[:80],emoji=rank['emoji'],rank=rank['title'],points=points,wins=wins,losses=losses,draws=draws,games=games,progress=progress)

def leaderboard(players,**kwargs):
    medals=['🥇','🥈','🥉']
    rows=[text('rank_row',medal=medals[i] if i<3 else str(i+1)+'.',name=str(p['name'])[:80],points=p['points'],wins=p['wins'],games=p['games']) for i,p in enumerate(players[:10])]
    return text('rank',leaders='\n\n'.join(rows) or text('empty'))

def daily(stats):
    import hashlib
    from database.daily_challenge import missions_for,game_progress,mission_state
    double=int(hashlib.sha256(f"{stats.get('chat_id')}:{stats['day']}:double".encode()).hexdigest(),16)%7==0
    multiplier=2 if double else 1;rows=[]
    if stats.get('personal'):
        for mission,progress in stats['missions']:
            i,kind,game,need,lo,hi=mission
            desc=text('personal_math' if game=='math_battle' else 'personal_word' if game=='word_chain' else 'personal_'+kind,n=need)
            status=text('claimed' if i in stats.get('claimed',set()) else 'ready' if progress>=need else 'ongoing')
            rows.append(text('daily_mission',number=i,description=desc,bar=bar(progress/max(1,need)),progress=min(progress,need),needed=need,lo=lo*multiplier,hi=hi*multiplier,status=status))
    else:
        for i,mission in enumerate(missions_for(stats['chat_id'],stats['day']),1):
            kind,need,unique,personal,(lo,hi)=mission
            total,users,_=(stats['total'],stats['users'],0) if kind=='message' else game_progress(stats['chat_id'],stats['day'],kind)
            viewer=stats.get('viewer_id');mine=0;status=''
            if viewer is not None:
                _,_,mine=mission_state(stats['chat_id'],viewer,mission,stats['day'])
                status=' · '+text('claimed' if i in stats.get('claimed',set()) else 'ready' if total>=need and users>=unique and mine>=personal else 'ongoing')
            rows.append(text('daily_group_mission',number=i,description=text(kind),bar=bar(min(total/max(1,need),users/max(1,unique))),progress=min(total,need),needed=need,users=min(users,unique),unique=unique,mine=min(mine,personal) if viewer is not None else '—',personal=personal,lo=lo*multiplier,hi=hi*multiplier,status=status))
    return text('daily',day=stats['day'],mode=text('personal' if stats.get('personal') else 'group'),double=text('double') if double else '',missions='\n\n'.join(rows),claim=text('claim_personal' if stats.get('personal') else 'claim_group'))
