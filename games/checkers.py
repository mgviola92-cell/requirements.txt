"""Short-king, forward-capture checkers. Pure rules, no Telegram or database."""
import copy
import uuid


def new(chat_id, uid, name, now, lobby_seconds=300, turn_seconds=300, target=0):
    board = [0] * 64
    for i in range(64):
        r, c = divmod(i, 8)
        if (r + c) % 2:
            board[i] = -1 if r < 3 else 1 if r > 4 else 0
    return dict(id=uuid.uuid4().hex[:12], chat_id=chat_id, board=board,
                players=[uid, 0], names=[name, ''], target=target, phase='waiting',
                turn=1, selected=None, chain=None, revision=0, card=None,
                deadline=now+lobby_seconds, turn_seconds=turn_seconds,
                quiet=0, history=[], winner=None, reason='', confirm=None, offer=None)


def directions(piece):
    return (-1, 1) if abs(piece) == 2 else (-1,) if piece > 0 else (1,)


def candidates(board, src, capture):
    piece = board[src]
    if not piece:
        return []
    r, c = divmod(src, 8)
    out = []
    step = 2 if capture else 1
    for dr in directions(piece):
        for dc in (-1, 1):
            nr, nc = r + dr*step, c + dc*step
            if not (0 <= nr < 8 and 0 <= nc < 8):
                continue
            dst = nr*8+nc
            if board[dst]:
                continue
            mid = (r+dr)*8+c+dc
            if not capture or board[mid]*piece < 0:
                out.append((src, dst, mid if capture else None))
    return out


def legal(s):
    board = s['board']
    sources = [s['chain']] if s['chain'] is not None else [i for i,p in enumerate(board) if p*s['turn'] > 0]
    jumps = [m for i in sources for m in candidates(board, i, True)]
    return jumps or ([] if s['chain'] is not None else [m for i in sources for m in candidates(board, i, False)])


def position(s):
    return ','.join(map(str,s['board']))+':'+str(s['turn'])


def finish(s, reason, winner=None):
    s.update(phase='finished', reason=reason, winner=winner, selected=None, chain=None, confirm=None, offer=None)


def expire(s, now):
    if s['phase'] in ('waiting','playing') and now >= s['deadline']:
        finish(s, 'lobby_timeout' if s['phase']=='waiting' else 'timeout',
               None if s['phase']=='waiting' else -s['turn'])
        s['revision'] += 1
        return True
    return False


def action(original, uid, act, value, now, name='', admin=False):
    """Copy-on-write: rejected actions cannot mutate persisted state."""
    s = copy.deepcopy(original)
    if s['phase'] not in ('waiting','playing') or now >= s['deadline']:
        raise ValueError('expired')
    if act == 'join':
        if s['phase'] != 'waiting' or uid == s['players'][0] or s['target'] and uid != s['target']:
            raise ValueError('join_denied')
        s['players'][1] = uid
        s['names'][1] = name
        s.update(phase='playing', deadline=now+s['turn_seconds'])
        s['history'] = [position(s)]
    elif act in ('cancel','yes','no'):
        if uid not in s['players'] and not admin:
            raise ValueError('players_only')
        if act == 'cancel':
            s['confirm'] = uid
        elif s['confirm'] != uid:
            raise ValueError('expired')
        elif act == 'no':
            s['confirm'] = None
        else:
            if s['phase']=='playing' and uid in s['players']:
                finish(s,'resign',-1 if uid==s['players'][0] else 1)
            else:
                finish(s,'cancelled')
    elif act in ('draw','accept','decline'):
        if s['phase']!='playing' or uid not in s['players']:
            raise ValueError('players_only')
        if act=='draw':
            if s['offer'] is not None:raise ValueError('offer_pending')
            s['offer']=uid
        elif s['offer'] is None or uid==s['offer']:
            raise ValueError('opponent_only')
        elif act=='accept':finish(s,'draw')
        else:s['offer']=None
    elif act == 'square':
        if s['phase']!='playing' or uid != s['players'][0 if s['turn']==1 else 1]:
            raise ValueError('turn_only')
        if s['confirm'] is not None:raise ValueError('confirm_first')
        square = int(value)
        if not 0 <= square < 64:raise ValueError('illegal')
        moves = legal(s)
        chosen = next((m for m in moves if m[0]==s['selected'] and m[1]==square),None)
        if chosen is None:
            if not any(m[0]==square for m in moves):raise ValueError('illegal')
            s['selected']=square
        else:
            src,dst,mid=chosen
            piece=s['board'][src]
            s['board'][src]=0
            s['board'][dst]=piece
            if mid is not None:s['board'][mid]=0
            crowned=abs(piece)==1 and dst//8==(0 if piece>0 else 7)
            if crowned:s['board'][dst]=2 if piece>0 else -2
            s['quiet']=0 if mid is not None or crowned else s['quiet']+1
            s['offer']=None
            if mid is not None and not crowned and candidates(s['board'],dst,True):
                s['chain']=s['selected']=dst
                # Same turn deadline: selection/jump chains cannot stall forever.
            else:
                s['turn'] *= -1
                s.update(chain=None, selected=None, deadline=now+s['turn_seconds'])
                s['history']=(s['history']+[position(s)])[-81:]
                if not legal(s):finish(s,'win',-s['turn'])
                elif s['quiet']>=80 or s['history'].count(position(s))>=3:finish(s,'draw')
    else:
        raise ValueError('expired')
    s['revision']+=1
    return s
