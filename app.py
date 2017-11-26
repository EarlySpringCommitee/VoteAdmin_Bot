# -*- coding: utf-8 -*-
import configparser
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, Bot
import time, datetime, calendar
import math
import threading
import queue
import uuid

config = configparser.SafeConfigParser()
config.read('config.ini', encoding="utf8")
token = config.get('General', 'Token')

vote_queue = queue.Queue()

if config.has_section('General'):
    if config.has_option('General', 'Token') and config.has_option('General', 'Lang'):
        token = config.get('General', 'Token')
    else:
        config.set('General', 'Token', 'REPLACE_THIS_WITH_TOKEN')
        config.set('General', 'Lang', 'REPLACE_THIS_WITH_YOUR_LANG_INI')
        with open('config.ini','w') as configfile:
            config.write(configfile)
        print("Please fill out the config file")
        exit()
else:
    config.add_section('General')
    config.set('General', 'Token', 'REPLACE_THIS_WITH_TOKEN')
    config.set('General', 'Lang', 'REPLACE_THIS_WITH_YOUR_LANG_INI')
    with open('config.ini','w') as configfile:
        config.write(configfile)
    print("Please fill out the config file")
    exit()

def getValue(dest, section, title, defaultValue):
    if dest.has_option(section, title):
        return dest.get(section, title)
    else:
        dest.set(section, title, defaultValue)
        return defaultValue

# 讀入語言字串
strings = configparser.SafeConfigParser()
strings.read(config.get('General', 'Lang'), encoding="utf8")

#讀入群組規則
group = configparser.SafeConfigParser()
group.read('groupPolicy.ini')

#keyboards

createButton = lambda x: [createButton(i) for i in x] if isinstance(x[0], list) else InlineKeyboardButton(x[0], callback_data=x[1])
createKeyboard = lambda x: InlineKeyboardMarkup([createButton(i) for i in x])

vote_keyboard = createKeyboard([
                                    [
                                        [strings.get('Boolean', 'Agree'), '1'],
                                        [strings.get('Boolean', 'DisAgree'), '0'],
                                        [strings.get('Boolean', 'NoComment'), '2']
                                    ],
                                    [
                                        [strings.get('Boolean', 'Cancel'), 'cancel']\
                                    ]
                                ])
    

restrict_keyboard = createKeyboard([
                                        [
                                            [strings.get('Restriction', 'SendMessage'), 'sendMessage'],
                                            [strings.get('Restriction', 'SendMedia'), 'sendMedia'],
                                            [strings.get('Restriction', 'SendOther'), 'sendOther'],
                                            [strings.get('Restriction', 'WebPreview'), 'webPreview']
                                        ],
                                        [
                                            [strings.get('Boolean', 'Cancel'), 'cancel']
                                        ]
                                    ])
                                    
admin_keyboard = createKeyboard([
                                        [
                                            [strings.get('Admin', 'CanChangeInfo'), 'canChangeInfo'],
                                            [strings.get('Admin', 'CanDeleteMessages'), 'canDeleteMessages'],
                                            [strings.get('Admin', 'CanInviteUsers'), 'canInviteUsers']

                                        ],
                                        [
                                            [strings.get('Admin', 'CanRestrictMembers'), 'canRestrictMembers'],
                                            [strings.get('Admin', 'CanPinMessages'), 'canPinMessages'],
                                            [strings.get('Admin', 'CanPromoteMembers'), 'canPromoteMembers']
                                        ],
                                        [
                                            [strings.get('Boolean', 'Cancel'), 'cancel']
                                        ]
                                    ])
                                            
# logging
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

@run_async
def start(bot, update):
    update.message.reply_text('Hi!')

@run_async
def help(bot, update):
    update.message.reply_text(strings.get('Help','Help').replace('\\n', '\n').replace('^', ' '))

chat_member = {}

def checkmember(chatid,userid):
    chatid=str(chatid)
    userid=str(userid)
    if chatid not in chat_member:
        chat_member[chatid] = {}
    if userid not in chat_member[chatid]:
        try:
            tgbot.get_chat_member(chatid,userid)    
            chat_member[chatid][userid] = True
        except:
            chat_member[chatid][userid] = False
    return(chat_member[chatid][userid])
    
def getGroupPolicyCount(chat_id, command):
    temp = False
    if group.has_option(chat_id, command):
        if '%' in group.get(chat_id, command, raw=True): #百分比投票制
            notNum = True
            temp = group.get(chat_id, command)
        else: #固定人數投票制
            return int(group.get(chat_id, command))
    if not temp: #查無群組資料
        try:
            temp = group.get('Universal', command, raw=True) #採用預設值
        except configparser.NoOptionError:
            temp = group.get('Universal', 'default', raw=True) #採用預設值的預設值(X
        try:
            return int(temp)
        except ValueError:
            notNum = True
    if notNum:
        global tgbot
        return int(math.ceil(float(temp.replace('%',''))*tgbot.getChatMembersCount(chat_id)/100)) 


group_vote = {}

@run_async
def vote(chat_id, title, command, commandArgs, status='voting', proposer=None): #command = 'ban', #commandArgs = {'userId':123456, 'until_date':140632804545}
    chatid = str(chat_id)
    group_vote[chatid] = {}
    nowTime = time.time()
    voteuuid = str(uuid.uuid1())
    
    global vote_keyboard, restrict_keyboard, admin_keyboard

    if command in ['ban', 'unban', 'setDesc', 'setPolicy', 'setTitle']:
        keyboard = vote_keyboard
    else:
        keyboard = {'restrict': restrict_keyboard,
                    'admin': admin_keyboard
                    }[command]
    
    global tgbot
    deadlineTime = nowTime + int(getGroupPolicyCount(chatid, 'expire'))
    msgid = str(tgbot.sendMessage(
        chatid,
        parse_mode='Markdown',
        text="{}\n\n{} : 0\n{}: 0\n{}: 0\n\nUUID: {}\n{}: {}".format(
            title,
            strings.get('Boolean', 'Agree'), 
            strings.get('Boolean', 'Disagree'), 
            strings.get('Boolean', 'NoComment'),
            voteuuid,
            strings.get('Vote', 'ExpireTime'),
            datetime.datetime.fromtimestamp(deadlineTime).strftime('%Y/%m/%d %H:%M:%S')),
        reply_markup=keyboard).message_id)
    group_vote[chatid][msgid] = {}
    group_vote[chatid][msgid]['title'] = title
    group_vote[chatid][msgid]['message'] = title
    group_vote[chatid][msgid]['command'] = command #command == 'ban' or sth else
    group_vote[chatid][msgid]['commandArgs'] = commandArgs #commandArgs = {'userId':123456, 'until_date':140632804545}
    group_vote[chatid][msgid]['time'] = nowTime #投票建立時間
    group_vote[chatid][msgid]['status'] = status #直接進入投票主題!!!!!!!!!!
    group_vote[chatid][msgid]['proposer'] = proposer #發起者 user_id
    group_vote[chatid][msgid]['voted'] = False #False 表未有任何人參與過投票
    group_vote[chatid][msgid]['deadline'] = datetime.datetime.fromtimestamp(deadlineTime).strftime('%Y/%m/%d %H:%M:%S')
    group_vote[chatid][msgid]['uuid'] = voteuuid

    if command in ['ban', 'unban', 'setDesc', 'setPolicy', 'setTitle']:
        group_vote[chatid][msgid]['y'] = 0
        group_vote[chatid][msgid]['n'] = 0
        group_vote[chatid][msgid]['u'] = 0
    elif command == 'restrict':
        group_vote[chatid][msgid]['sendMessage'] = [0,0,0] #[y,n,u]
        group_vote[chatid][msgid]['sendMedia'] = [0,0,0]
        group_vote[chatid][msgid]['sendOther'] = [0,0,0]
        group_vote[chatid][msgid]['webPreview'] = [0,0,0]
    elif command == 'admin':
        group_vote[chatid][msgid]['canChangeInfo'] = [0,0,0]
        group_vote[chatid][msgid]['canDeleteMessages'] = [0,0,0]
        group_vote[chatid][msgid]['canInviteUsers'] = [0,0,0]
        group_vote[chatid][msgid]['canRestrictMembers'] = [0,0,0]
        group_vote[chatid][msgid]['canPinMessages'] = [0,0,0]
        group_vote[chatid][msgid]['canPromoteMembers'] = [0,0,0]
    
    vote_queue.put_nowait({ "chat_id" : chatid , "message_id" : msgid })
    return(msgid)

@run_async
def vote_callback(bot, update):
    query = update.callback_query
    chat_id = str(query.message.chat.id)
    message_id = str(query.message.message_id)
    user_id = str(query.from_user.id)
    command = group_vote[chat_id][message_id]['command']
    status = group_vote[chat_id][message_id]['status']
    #print(query)
    if status == "selecting_rest":
        pass
    elif status == "voting":
        try:
            group_vote[chat_id][message_id][user_id]
        except KeyError:
            if command in ['ban', 'unban', 'setDesc', 'setPolicy', 'setTitle']:
                group_vote[chat_id][message_id][user_id] = -1
            elif command == 'restrict':
                group_vote[chat_id][message_id][user_id] = {
                    'sendMessage': -1,
                    'sendMedia': -1,
                    'sendOther': -1,
                    'webPreview': -1
                }
            elif command == 'admin':
                group_vote[chat_id][message_id][user_id] = {
                    'canChangeInfo': -1,
                    'canDeleteMessages': -1,
                    'canInviteUsers': -1,
                    'canRestrictMembers': -1,
                    'canPinMessages': -1,
                    'canPromoteMembers': -1
                }
        
        if query.data == "cancel":
            if not group_vote[chat_id][message_id]['voted']:
                group_vote[chat_id][message_id]['time'] = -48794878740 #立即過期
            else:
                alert= "Cancel vote."
    
        if command in ['ban', 'unban', 'setDesc', 'setPolicy', 'setTitle']:
            if query.data == "0" :
                group_vote[chat_id][message_id]['voted'] = True
                if group_vote[chat_id][message_id][user_id] == 0:
                    group_vote[chat_id][message_id][user_id] = -1
                    group_vote[chat_id][message_id]['n'] -= 1
                    alert=strings.get('Vote', "Undo")
                else:
                    group_vote[chat_id][message_id][user_id] = 0
                    group_vote[chat_id][message_id]['n'] += 1
                    alert=strings.get('Vote', "Disagree")
            elif query.data == "1":
                group_vote[chat_id][message_id]['voted'] = True
                if group_vote[chat_id][message_id][user_id] == 1:
                    group_vote[chat_id][message_id][user_id] = -1
                    group_vote[chat_id][message_id]['y'] -= 1
                    alert=strings.get('Vote', "Undo")
                else:
                    group_vote[chat_id][message_id][user_id] = 1
                    group_vote[chat_id][message_id]['y'] += 1
                    alert=strings.get('Vote', "Agree")
            elif query.data == "2" :
                group_vote[chat_id][message_id]['voted'] = True
                if group_vote[chat_id][message_id][user_id] == 2:
                    group_vote[chat_id][message_id][user_id] = -1
                    group_vote[chat_id][message_id]['u'] -=1
                    alert=strings.get('Vote', "Undo")
                else:
                    group_vote[chat_id][message_id][user_id] = 2
                    group_vote[chat_id][message_id]['u'] += 1
                    alert=strings.get('Vote', "NoComment")
            global vote_keyboard
            keyboard = vote_keyboard
            msg = "{}\n\n{} : {}\n{}: {}\n{}: {}".format(
                    group_vote[chat_id][message_id]['title'],
                    strings.get('Boolean', 'Agree'),
                    str(group_vote[chat_id][message_id]['y']),
                    strings.get('Boolean', 'Disagree'),
                    str(group_vote[chat_id][message_id]['n']),
                    strings.get('Boolean', 'NoComment'),
                    str(group_vote[chat_id][message_id]['u']))
            
        elif command in ['restrict', 'admin']:
            group_vote[chat_id][message_id]['voted'] = True
            if group_vote[chat_id][message_id][user_id][query.data] == -1: #對 query.data 的投票為 -1,1,0,2 之一
                group_vote[chat_id][message_id][user_id][query.data] = 1
                group_vote[chat_id][message_id][query.data][0] +=1
                alert=strings.get('Vote', "Agree")
            elif group_vote[chat_id][message_id][user_id][query.data] == 1:
                group_vote[chat_id][message_id][user_id][query.data] = 0
                group_vote[chat_id][message_id][query.data][0] -=1
                group_vote[chat_id][message_id][query.data][1] +=1
                alert=strings.get('Vote', "Disagree")
            elif group_vote[chat_id][message_id][user_id][query.data] == 0:
                group_vote[chat_id][message_id][user_id][query.data] = 2
                group_vote[chat_id][message_id][query.data][1] -=1
                group_vote[chat_id][message_id][query.data][2] +=1
                alert=strings.get('Vote', "NoComment")
            elif group_vote[chat_id][message_id][user_id][query.data] == 2:
                group_vote[chat_id][message_id][user_id][query.data] = 1
                group_vote[chat_id][message_id][query.data][2] -=1
                group_vote[chat_id][message_id][query.data][0] +=1
                alert=strings.get('Vote', "Agree")
                
            global restrict_keyboard, admin_keyboard
            keyboard = {'restrict': restrict_keyboard,
                            'admin': admin_keyboard
                            }[command]
                            
            if command == 'restrict':
                msg = "{}\n\n{} : {}\n{}: {}\n{}: {}\n{} : {}".format(
                    group_vote[chat_id][message_id]['title'],
                    strings.get('Restriction', 'SendMessage'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['sendMessage']]),
                    strings.get('Restriction', 'SendMedia'), 
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['sendMedia']]),
                    strings.get('Restriction', 'SendOther'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['sendOther']]),
                    strings.get('Restriction', 'WebPreview'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['webPreview']])
                    )
            elif command == 'admin':
                msg = "{}\n\n{} : {}\n{}: {}\n{}: {}\n{} : {}\n{} : {}\n{} : {}".format(
                    group_vote[chat_id][message_id]['title'],
                    strings.get('Admin', 'CanChangeInfo'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canChangeInfo']]),
                    strings.get('Admin', 'CanDeleteMessages'), 
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canDeleteMessages']]),
                    strings.get('Admin', 'CanInviteUsers'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canInviteUsers']]),
                    strings.get('Admin', 'CanRestrictMembers'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canRestrictMembers']]),
                    strings.get('Admin', 'CanPinMessages'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canPinMessages']]),
                    strings.get('Admin', 'CanPromoteMembers'),
                    '/'.join([str(i) for i in group_vote[chat_id][message_id]['canPromoteMembers']])
                    )
        
        group_vote[chat_id][message_id]['message'] = msg
        msg += '\n\nUUID: ' + group_vote[chat_id][message_id]['uuid']
        msg += '\n' + strings.get('Vote', 'ExpireTime') + ': '+ group_vote[chat_id][message_id]['deadline']

        
        bot.edit_message_text(text=msg,
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id,
                              reply_markup=keyboard,
                              parse_mode='Markdown')
    
        bot.answer_callback_query(query.id,text=alert)
                    

def checkVoteExpired():
    while True:
        global tgbot
        item = vote_queue.get()
        chat_id = str(item['chat_id'])
        message_id = str(item['message_id'])
        vote = group_vote[str(chat_id)][str(message_id)]
        command = vote['command']
        #print("林北這個Thread 在 checking Chat id" + chat_id + " Message ID " + message_id + " 的la Time : "+str(time.time()) +" Expire Time : " + str(group_vote[chat_id][message_id]['time'] + getGroupPolicyCount(chat_id, 'expire')) + " eXPIRE : " +  str(getGroupPolicyCount(chat_id, 'expire')))
        
        if int(time.time()) > (group_vote[chat_id][message_id]['time'] + getGroupPolicyCount(chat_id, 'expire')):
            if command in ['ban', 'unban', 'setDesc', 'setPolicy', 'setTitle']: 
                if vote['y'] > vote['n'] and (vote['y'] + vote['n'] + vote['u']) >= getGroupPolicyCount(chat_id, command):
                    tgbot.edit_message_text(
                        parse_mode='Markdown',
                        text='{}\n\n{}'.format(
                            group_vote[chat_id][message_id]['message'],
                            strings.get('Vote', "Pass")),
                        chat_id=chat_id,
                        message_id=message_id)
                        
                    tgbot.sendMessage(chat_id, quote=True, reply_to_message_id=int(message_id), text=strings.get('Vote', "PassMessage"))
                    if command == 'setPolicy':
                        try:
                            group.set(chat_id, vote['commandArgs']['command'], vote['commandArgs']['value'])
                        except configparser.NoSectionError:
                            group.add_section(chat_id)
                            group.set(chat_id, vote['commandArgs']['command'], vote['commandArgs']['value'])
                        with open('groupPolicy.ini', 'w') as configfile:
                            group.write(configfile)
                        pass
                    else:
                        {
                            'ban': tgbot.kickChatMember,
                            'unban': tgbot.unbanChatMember,
                            'setDesc': tgbot.setChatDescription,
                            'setTitle': tgbot.setChatTitle
                        }[command](chat_id=chat_id, **vote['commandArgs'])
                        pass
                else: #投票不通過
                    tgbot.edit_message_text(
                        parse_mode='Markdown',
                        text='{}\n\n{}'.format(
                            group_vote[chat_id][message_id]['message'],
                            strings.get('Vote', "Fail")),
                        chat_id=chat_id,
                        message_id=message_id)
                        
                    tgbot.sendMessage(chat_id, quote=True, reply_to_message_id=int(message_id), text=strings.get('Vote', "FailMessage"))
                    pass
            
            elif command in ['restrict', 'admin']:
                tempResult = {}
                tempResultText = {}
                resultToCommand = {
                    'restrict':{
                        'sendMessage': 'can_send_messages',
                        'sendMedia': 'can_send_media_messages',
                        'sendOther': 'can_send_other_messages',
                        'webPreview': 'can_add_web_page_previews'
                    },
                    'admin':{
                        'canChangeInfo': 'can_change_info',
                        'canDeleteMessages': 'can_delete_messages',
                        'canInviteUsers': 'can_invite_users',
                        'canRestrictMembers': 'can_restrict_members',
                        'canPinMessages': 'can_pin_messages',
                        'canPromoteMembers': 'can_promote_members'
                    }
                }[command]
                for key, value in group_vote[chat_id][message_id].items():
                    if isinstance(value, list):
                        if len(value) == 3:
                            if value[0] > value[1] and sum(value) >= getGroupPolicyCount(chat_id, command):
                                if command == 'restrict':
                                    tempResult.update({resultToCommand[key]:False})
                                    tempResultText.update({key:'False'})
                                elif command == 'admin':
                                    tempResult.update({resultToCommand[key]:True})
                                    tempResultText.update({key:'True'})                                    
                            elif value[0] < value[1] and sum(value) >= getGroupPolicyCount(chat_id, command):
                                if command == 'restrict':
                                    tempResult.update({resultToCommand[key]:True})
                                    tempResultText.update({key:'True'})
                                elif command == 'admin':
                                    tempResult.update({resultToCommand[key]:False})
                                    tempResultText.update({key:'False'})                                    
                            else:
                                tempResultText.update({key:'Maintain'})
                                
                if command == 'restrict':
                    resultText = '{}\n\n{}:\n{}:{}\n{}:{}\n{}:{}\n{}:{}\n'.format(
                                    group_vote[chat_id][message_id]['message'],
                                    strings.get('Vote', 'VoteResult'),
                                    strings.get('Restriction', 'SendMessage'),
                                    strings.get('Boolean', tempResultText['sendMessage']),
                                    strings.get('Restriction', 'SendMedia'),
                                    strings.get('Boolean', tempResultText['sendMedia']),
                                    strings.get('Restriction', 'SendOther'),
                                    strings.get('Boolean', tempResultText['sendOther']),
                                    strings.get('Restriction', 'WebPreview'),
                                    strings.get('Boolean', tempResultText['webPreview'])
                                    )
                elif command == 'admin':
                    resultText = '{}\n\n{}:\n{}:{}\n{}:{}\n{}:{}\n{}:{}\n{}:{}\n{}:{}'.format(
                                    group_vote[chat_id][message_id]['message'],
                                    strings.get('Vote', 'VoteResult'),
                                    strings.get('Admin', 'CanChangeInfo'),
                                    strings.get('Boolean', tempResultText['canChangeInfo']),
                                    strings.get('Admin', 'CanDeleteMessages'),
                                    strings.get('Boolean', tempResultText['canDeleteMessages']),
                                    strings.get('Admin', 'CanInviteUsers'),
                                    strings.get('Boolean', tempResultText['canInviteUsers']),
                                    strings.get('Admin', 'CanRestrictMembers'),
                                    strings.get('Boolean', tempResultText['canRestrictMembers']),
                                    strings.get('Admin', 'CanPinMessages'),
                                    strings.get('Boolean', tempResultText['canPinMessages']),
                                    strings.get('Admin', 'CanPromoteMembers'),
                                    strings.get('Boolean', tempResultText['canPromoteMembers'])
                                    )

                tgbot.edit_message_text(chat_id=chat_id, message_id=message_id, text=resultText, parse_mode='Markdown')
                tgbot.sendMessage(chat_id, quote=True, reply_to_message_id=int(message_id), text=strings.get('Vote', "OtherMessage"))
                {'restrict': tgbot.restrictChatMember,
                 'admin': tgbot.promoteChatMember}[command](chat_id=chat_id, **vote['commandArgs'], **tempResult)
                pass
                
        else:
            vote_queue.put_nowait({ "chat_id" : chat_id , "message_id" : message_id })
        time.sleep(int(config.get('General', 'checkInterval')))

def timeConvert(timeText): # timeText -> int (second)
    if '/' in timeText:
      return calendar.timegm(datetime.datetime.strptime(timeText, '%Y/%m/%d-%H:%M:%S').utctimetuple()) - \
        3600*int(config.get('General', 'userUTC'))  
    elif any(i in timeText for i in ['y', 'M', 'd', 'h', 'm', 's']):
        timeArray, timeVar = ['0'], 0
        for i in timeText:
            if i.isdigit():
                if timeArray[-1].isnumeric():
                    timeArray[-1] += i
                else:
                    timeArray.append(i)
            elif i in ['y', 'M', 'd', 'h', 'm', 's']:
                timeArray.append(i)
        for i in list(range(len(timeArray))):
            if timeArray[i].isalpha():
                timeVar += {'y':31556926, 'M':2592000, 'd':86400, 'h':3600, 'm':60, 's':1}.get(timeArray[i], 0)*int(timeArray[i-1])
        return timeVar
    else:
        raise TypeError('{} is not a timetext.'.format(timeText))
    
isTimeText = lambda x: any(i in x for i in ['y', 'M', 'd', 'h', 'm', '/', 's'])
isTimeTextArray = lambda x: any(isTimeText(i) for i in x)

def getTimeText(array):
    for i in array:
        if isTimeText(i):
            return i
    return False
@run_async
def voteLoader(bot, update, args, command):
    chat_id = update.message.chat_id
    user_id, userName, userFirstName = None, None, None
        
    try:
        timeVar = timeConvert(getTimeText(args))
    except(TypeError, IndexError):
        timeVar = 0
                    
    if update.message.reply_to_message is not None: # 有回覆訊息
        user_id = getUser(update.message.reply_to_message.from_user).getId()
        userName = getUser(update.message.reply_to_message.from_user).getUsername()
        userFirstName = getUser(update.message.reply_to_message.from_user).getFirstname()
    else:
        try:
            if not args[0].isnumeric: # 第一個參數不是 userId 且沒有回覆訊息
                update.message.reply_text(strings.get('Error', 'ArgumentError'))
                return
        except IndexError: # 奇怪的錯誤之類的
            update.message.reply_text(strings.get('Error', 'ArgumentError'))
            return
        
    if not (user_id and userName):
        userName = bot.getChatMember(chat_id=chat_id, user_id=int(args[0]))['user']['username']
        user_id = args[0]

    if not userFirstName:
         userFirstName = bot.getChatMember(chat_id=chat_id, user_id=user_id)['user']['first_name']
    
    askString = {'ban':strings.get('Ask', 'AgreedToBan'),
                 'restrict':strings.get('Ask', 'AgreedToRestrict'),
                 'admin':strings.get('Ask', 'AgreedToAdmin'),
                 'unban':strings.get('Ask','AgreedToUnban')}[command].format(
                     '[{}](tg://user?id={})'.format(userFirstName, user_id))
    
    if timeVar:
        askString += strings.get('Ask', 'until') + datetime.datetime.fromtimestamp(untilTime).strftime('%Y/%m/%d %H:%M:%S') + '?'

        vote(chat_id,
            '{}{}{} ?'.format(
                askString,
                command,
                {'user_id':user_id, 'until_date':int(time.time()+timeVar)}))
    else:
        askString += '?'

        vote(chat_id,
        askString,
        command,
        {'user_id':user_id})
    return

@run_async
def voteban(bot, update, args=[]):
    return voteLoader(bot=bot, update=update, args=args, command='ban')

@run_async
def voterest(bot, update, args=[]):
    return voteLoader(bot=bot, update=update, args=args, command='restrict')
    
@run_async
def voteadmin(bot, update, args=[]):
    return voteLoader(bot=bot, update=update, args=args, command='admin')

@run_async
def voteunban(bot, update, args=[]):
    return voteLoader(bot=bot, update=update, args=args, command='unban')

@run_async
def votedesc(bot, update, args=['']):
    chat_id = update.message.chat_id
    if update.message.reply_to_message is not None and args != ['']: # 有回覆訊息且沒有參數
        text = update.message.reply_to_message.text
    else:
        text = args[0]
    text = text.replace('^', ' ').replace('\\n', '\n')
    askString = strings.get('Ask', 'AgreedToSetDesc').replace('\\n','\n').format(text)

    vote(chat_id,
        askString,
        'setDesc',
        {'description':text})
    return
@run_async
def votetitle(bot, update, args=['']):
    chat_id = update.message.chat_id
    if update.message.reply_to_message is not None and args != ['']: # 有回覆訊息且沒有參數
        text = update.message.reply_to_message.text
    else:
        text = args[0]
    askString = strings.get('Ask', 'AgreedToSetTitle').replace('\\n','\n').format(text)

    vote(chat_id,
        askString,
        'setTitle',
        {'title':text})
    return

@run_async
def voteset(bot, update, args):
    chat_id = update.message.chat_id
    message_id = update.message.message_id

    #Error
    if len(args) < 2:
        bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'NotEnoughArguments'))
        return
    if len(args) > 2:
        bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'TooMuchArguments'))
        return
    if not args[0] in ['ban', 'restrict', 'admin', 'unban', 'expire']:
        return
    if args[0] == 'expire':
        if not args[1].isnumeric():
            try:
                args[1] = str(timeConvert(args[1]))
            except TypeError:
                bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'ArgumentError'))
                return
        askString = strings.get('Ask', 'AgreedToSetExpire').format(str(datetime.timedelta(seconds=int(args[1]))))
    elif args[0] in ['ban', 'restrict', 'admin', 'unban']:
        if not args[1].isnumeric():
            if not args[1][-1] == '%':
                bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'ArgumentError'))
                return
            elif not args[1][:-1].isnumeric:
                bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'ArgumentError'))
                return
            elif not 0 < float(args[1][:-1]) < 100:
                bot.sendMessage(chat_id, reply_to_message_id=message_id, text=strings.get('Error', 'ArgumentError'))
                return
        askString = strings.get('Ask', 'AgreedToSetMinimumCount').format(
                strings.get('Command', args[0].capitalize()),
                args[1])
    askStrint += '?'
    vote(chat_id,
        askString,
        'setPolicy',
        {'command': args[0],
         'value': args[1]       
        })

@run_async
def getUserId(chat_id):
    global tgbot
    chatMember = tgbot.getChat(chat_id)
    print(chatMember)
    
class User(object):
    def __init__(self, name=None, first_name=None, last_name=None, username=None, id=None):
        self.__name = name
        self.__first_name = first_name
        self.__last_name = last_name
        self.__username = username
        self.__id = id
        
    def getId(self):
        return self.__id
    def setId(self, id=None):
        self.__id=id
        return self.__id
    
    def getUsername(self):
        return self.__username
    def setUsername(self, username=None):
        self.__username=username
        return self.__username
    
    def getLastname(self):
        return self.__last_name
    def setLastname(self, last_name=None):
        self.__last_name = last_name
        return self.__last_name
    
    def getFirstname(self):
        return self.__first_name
    def setFirstname(self, first_name=None):
        self.__first_name = first_name
        return self.__first_name
    
    def getName(self):
        return self.__name
    def setName(self, name=None):
        self.__name=name
        return self.__name
    
def getUser(from_user=None): #input update.message.from_user, return an User object.
    if from_user:
        item = User(name=from_user.first_name, first_name=from_user.first_name)
        if not from_user.username:
            item.setId(from_user.id)
        else:
            item.setUsername(from_user.username)
            item.setId(from_user.id)
        if from_user.last_name:
            item.setLastname(from_user.last_name)
            item.setName(item.getName() + item.getLastname())
    else:
        item = User(name="NoUser")
    return(item)

def main():
    updater = Updater(token)
    global tgbot
    tgbot = Bot(token)
    
    for i in range(1,21):
        t = threading.Thread(target=checkVoteExpired, daemon=True).start()
        print("checkVoteExpired(" + str(i) + ") has launched !")
    
    updater.dispatcher.add_handler(CommandHandler('voteban', voteban, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('voterest', voterest, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('voteadmin', voteadmin, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('voteunban', voteunban, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('votedesc', votedesc, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('votetitle', votetitle, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('voteset', voteset, pass_args=True))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(vote_callback))
    updater.start_polling()
    updater.idle()
    
if __name__ == '__main__':
    main()