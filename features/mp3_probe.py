"""Temporary owner-private, one-at-a-time direct YouTube MP3 experiment."""
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

LOG=logging.getLogger(__name__)
LOCK=threading.Lock()
START=time.monotonic()
WAITING=False
ATTEMPTS=0


def failure_kind(output):
    value=output.lower()
    if 'confirm' in value and 'bot' in value:return 'youtube_bot_check'
    if '403' in value:return 'youtube_403'
    if '429' in value:return 'youtube_rate_limit'
    if 'javascript' in value or 'js runtime' in value:return 'javascript_runtime'
    if 'ffmpeg' in value or 'ffprobe' in value:return 'audio_conversion'
    return 'download_failed'


def download(query,directory):
    import imageio_ffmpeg
    binary=Path(directory)/'ffmpeg'
    binary.symlink_to(imageio_ffmpeg.get_ffmpeg_exe())
    args=[sys.executable,'-m','yt_dlp','--ignore-config','--no-playlist',
          '--no-progress','--no-warnings','--socket-timeout','12','--retries','0',
          '--extractor-retries','0','--fragment-retries','0','--max-filesize','20M',
          '--match-filter','duration <= 600 & !is_live',
          '-f','bestaudio/best','-x','--audio-format','mp3','--audio-quality','128K',
          '--ffmpeg-location',str(binary),'-o',str(Path(directory)/'song.%(ext)s'),
          '--','ytsearch1:'+query]
    proc=subprocess.run(args,capture_output=True,text=True,timeout=150)
    audio=Path(directory)/'song.mp3'
    if proc.returncode or not audio.is_file():
        raise RuntimeError(failure_kind(proc.stderr+'\n'+proc.stdout))
    if audio.stat().st_size>15*1024*1024:raise RuntimeError('file_too_large')
    return audio


def register(bot):
    def owner(m):
        return bool(m.chat.type=='private' and m.from_user and str(m.from_user.id)==os.getenv('OWNER_TELEGRAM_ID','').strip())

    def run(m,query):
        global ATTEMPTS,WAITING
        if time.monotonic()-START>1800 or ATTEMPTS>=3:
            bot.reply_to(m,'ယာယီ MP3 စမ်းသပ်မှု ပြီးဆုံးပြီ။');return
        if not query.strip() or len(query)>150:
            bot.reply_to(m,'သီချင်းနာမည်တိုတို ပို့ပါ။');return
        if not LOCK.acquire(blocking=False):
            bot.reply_to(m,'တစ်ပုဒ် စမ်းနေဆဲပါ။');return
        ATTEMPTS+=1;WAITING=False
        try:bot.reply_to(m,'🎵 Railway ကနေ YouTube တိုက်ရိုက် MP3 စမ်းနေသည်။ အများဆုံး ၂–၃ မိနစ်ခန့်။')
        except Exception:
            LOCK.release()
            raise
        def worker():
            stage='download'
            try:
                with tempfile.TemporaryDirectory(prefix='mp3-probe-') as folder:
                    audio=download(query,folder);stage='telegram_upload'
                    with audio.open('rb') as source:
                        bot.send_audio(m.chat.id,source,title=query[:100],caption='🧪 Railway → YouTube → MP3 ယာယီစမ်းသပ်မှု',timeout=60)
                LOG.info('MP3_PROBE_RESULT success')
                bot.send_message(m.chat.id,'✅ MP3 ပို့နိုင်ပြီ။ စမ်းသပ်မှုသာဖြစ်၍ ဒီ function ကို ပြန်ဖြုတ်မည်။')
            except subprocess.TimeoutExpired:
                LOG.info('MP3_PROBE_RESULT timeout')
                bot.send_message(m.chat.id,'❌ စမ်းသပ်ချိန်ကုန်သွားပြီ (timeout)။')
            except Exception as exc:
                code=str(exc) if isinstance(exc,RuntimeError) else stage+'_error'
                if code not in ('youtube_bot_check','youtube_403','youtube_rate_limit','javascript_runtime','audio_conversion','download_failed','file_too_large'):
                    code=stage+'_error'
                LOG.info('MP3_PROBE_RESULT %s',code)
                bot.send_message(m.chat.id,'❌ MP3 မရပါ။ အကြောင်းရင်း: '+code+'\nဒီစမ်းသပ်မှုကို ပြန်ဖြုတ်မည်။')
            finally:LOCK.release()
        threading.Thread(target=worker,name='temporary-mp3-probe',daemon=True).start()

    @bot.message_handler(commands=['mp3test'],func=owner)
    def command(m):
        global WAITING
        query=m.text.split(maxsplit=1)
        if len(query)>1:run(m,query[1])
        elif time.monotonic()-START<=1800 and ATTEMPTS<3:
            WAITING=True;bot.reply_to(m,'🧪 စမ်းဖို့ သီချင်းနာမည်တစ်ခု ပို့ပါ။ /mp3testcancel ဖြင့် ပယ်ဖျက်နိုင်သည်။')
        else:bot.reply_to(m,'ယာယီ MP3 စမ်းသပ်ချိန်ပြီးဆုံးပြီ။')

    @bot.message_handler(commands=['mp3testcancel'],func=owner)
    def cancel(m):
        global WAITING
        WAITING=False;bot.reply_to(m,'နာမည်စောင့်နေမှု ပယ်ဖျက်ပြီးပြီ။')

    @bot.message_handler(func=lambda m:owner(m) and WAITING and not (m.text or '').startswith('/'),content_types=['text'])
    def capture(m):run(m,m.text)
