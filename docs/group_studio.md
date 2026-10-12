# Draw & Guess နှင့် Group Studio

## Draw & Guess

Group တွင် `/draw` ပို့ပြီး Private ဂိမ်းခန်းခလုတ်ကိုနှိပ်၊ Join အတည်ပြုပါ။ အနည်းဆုံး ၂ ယောက်၊ အများဆုံး ၁၂ ယောက်။ Admin က လူပြည့်လျှင်စနိုင်သည်၊ အချိန်ပြည့်လျှင်လည်း စသည်။ ပုံဆွဲသူသာ private Canvas ခလုတ်ရမည်။ Telegram ထဲက Canvas မှာ အဖြေကိုကြည့်ပြီး ပုံဆွဲပါ။ ပထမပုံ Group ထဲရောက်မှ ခန့်မှန်းချိန်စသည်။ ဆက်ဆွဲထားမှုကို ၁၀ စက္ကန့်တိုင်းသိမ်းပို့နိုင်ပြီး Group တွင် ပုံတစ်ပုံတည်း ပြင်သုံးသည်။ ကျန်ကစားသူများ Group ထဲတွင် အဖြေစာရေးပါ။ ပထမမှန်သူနှင့်ပုံဆွဲသူ reward ရသည်။

`/drawrules` — စည်းမျဉ်း။ `/drawstop` — Admin အတည်ပြုပြီးရပ်။ “ဖျက်သိမ်းမယ်” နှိပ်လျှင် အဲ့ဒီပွဲ၏ bot ပို့ထားသော Join/ပုံ/ဂိမ်း/အတည်ပြုစာများကို ရှင်းပေးသည်။ ဖျက်သိမ်းပြီးကြောင်းစာကိုလည်း ၁၀ စက္ကန့်အကြာဖျက်သည်။ Normal group messages မဖျက်ပါ။ Cleanup ကို DB တွင်သိမ်းပြီး restart သို့မဟုတ် နောက်ပွဲစခြင်းအပြီးလည်း ဆက်လုပ်သည်။ အနည်းဆုံးလူတိုင်းတစ်လှည့်ရအောင် rounds သည် လူဦးရေထက်မနည်းပါ။

Owner Tools ဂိမ်းစာရင်းအပေါ်ဆုံးတွင် Draw & Guess ပါသည်။ Owner editor တွင် Draw & Guess ကိုရှာ၍ စာသား၊ အချိန်၊ လူဦးရေ၊ rounds၊ reward၊ စကားလုံးစာရင်း ပြင်နိုင်သည်။ ပွဲစချိန် settings နှင့်စကားလုံးစာရင်း သိမ်းထားပြီး လက်ရှိပွဲမပြောင်းပါ။ BotFather game registration သို့မဟုတ် Main Mini App configuration မလိုဘဲ private inline Web App ခလုတ်ကိုအသုံးပြုသည်။ HTTPS website ကို လက်ရှိ Render service ကပေးသည်။

## အချိန် Capsule

သိမ်းချင်သော message ကို reply လုပ်ပြီး `/capsule 2026-10-13 20:00` ပို့ပါ။ ရက်စွဲသည် မြန်မာအချိန်။ Text၊ photo၊ voice၊ audio၊ video၊ document၊ sticker စသည်ကို သိမ်းနိုင်သည်။ မူရင်း message ဖျက်သွားလည်း file ID/text ကို DB တွင်သိမ်းထားသည်။ `/capsules` ဖြင့် ကိုယ့်စာရင်း၊ `/capsulecancel ID` ဖြင့် မဖွင့်ရသေးတာ ပယ်ဖျက်ပါ။ ကိုယ့် capsule သို့မဟုတ် Admin သာ ပယ်ဖျက်နိုင်သည်။ Restart ဖြစ်ပြီးကျော်သွားသောအချိန်ကို DB worker က ပြန်ဖွင့်ပေးသည်။

## အသံစာကြည့်တိုက်

Admin က voice/audio ကို reply လုပ်၍ `/soundadd hello` သိမ်းပါ။ Member များ `/sound hello` သုံးနိုင်သည်။ `/sounds` စာရင်း၊ `/sounddel hello` ဖျက်ရန်။ Owner private chat မှသိမ်းလျှင် group အားလုံးအတွက် default ဖြစ်သည်။ Group တစ်ခု၏အမည်တူသိမ်းထားမှုက default ထက်ဦးစားပေးသည်။

## အမှတ်တရစာအုပ်

Member က message ကို reply လုပ်ပြီး `/memorysave ပျော်ခဲ့တဲ့နေ့` သိမ်းပါ။ `/memories` စာရင်း၊ `/memory ID` မူရင်းမီဒီယာပြန်ကြည့်၊ `/memorydel ID` ကိုယ်သိမ်းထားတာဖျက်ပါ။ Admin က group အတွင်းအမှတ်တရကို ဖျက်နိုင်သည်။

`/memorybook` ဖြင့် HTML စာအုပ်၊ `/memorybook 2026-10` ဖြင့် လအလိုက်စာအုပ်ထုတ်ပါ။ စာ၊ ခေါင်းစဉ်၊ မြန်မာရက်စွဲနှင့် နောက်ဆုံးဓာတ်ပုံ ၂၀ အထိ thumbnail ထည့်ပေးသည်။ အခြားမီဒီယာကို `/memory ID` ဖြင့်ပြန်ဖွင့်နိုင်သည်။ ပုံ/ဖိုင်မသိမ်းရသေးဘဲ group message အားလုံးကို အလိုအလျောက်မစုပါ။

## ကိုယ်ပိုင် Commands

Admin က စာ သို့မဟုတ်မီဒီယာကို reply လုပ်၍ `/commandadd hello` ဖန်တီးပါ။ နောက်တစ်ဆင့်ထည့်ရန် reply ဖြင့် `/commandappend hello` သုံးပါ။ အများဆုံး ၅ ဆင့်။ `/hello` ဖြင့် အသုံးပြုပါ။ `/commands` စာရင်း၊ `/commanddel hello` ဖျက်ပါ။ Owner private မှဖန်တီးလျှင် global default ဖြစ်သည်။

စာ/Caption တွင် `{name}`, `{user}`, `{group}`, `{args}` ပါနိုင်သည်။ ဥပမာ “မင်္ဂလာပါ {name}”။ Argument သည် `/hello မောင်လှ` မှ “မောင်လှ” ဖြစ်သည်။ ရှိပြီးသား bot command များကို အစားထိုးမရ။ Code၊ shell၊ arbitrary API request မစေခိုင်းနိုင်ပါ။ စာ/မီဒီယာပို့ခြင်းသာ။

## Web နှင့် Editor

`/owner` → Group Studio Web သို့မဟုတ် `/owner/studio/` ကိုဖွင့်ပါ။ Owner login လိုသည်။ Group ရွေးပြီး command စာသား/အစဉ် ပြင်၊ အသံဖျက်၊ capsule အချိန်ပြင်/ပယ်ဖျက်၊ အမှတ်တရခေါင်းစဉ်ပြင်/ဖျက်နိုင်သည်။ Command အသစ်ကို Web မှ စာသားအဆင့်များဖြင့်ဖန်တီးနိုင်သည်။ Media အဆင့်ကို Telegram မှ reply နှင့်သိမ်းပြီး Web မှ caption/အစဉ်ကိုပြင်နိုင်သည်။ အသံဖိုင်အသစ်ကို Telegram မှ voice/audio reply ဖြင့်သိမ်းပါ။

Owner editor တွင် Group Studio ကိုရှာ၍ စာသား၊ enable/disable၊ cooldown၊ အရေအတွက်ကန့်သတ်ချက် ပြင်နိုင်သည်။ Group တစ်ခုချင်း သို့မဟုတ် global default ကိုရွေးနိုင်သည်။

## Verification

Offline tests cover media serialization, safe placeholders, HTML validation, owner permissions/CSRF, group scope, durable jobs/retries, chain order, idempotent reward markers, authenticated Mini App data, private tickets, PNG validation, round rotation, duplicate guesses and 1,000 complete simulated drawing games. Existing Nan Yate tests include 3,000 simulations. Canvas JavaScript pointer and authenticated upload logic is checked with a DOM/canvas stub. A real mobile Telegram Mini App session has not been exercised in this environment.

Telegram message delivery can be duplicated if the API succeeds but the DB acknowledgement fails; game actions and points use transactional state/unique reward keys. Sound playback and media retrieval depend on Telegram retaining the stored file IDs.
