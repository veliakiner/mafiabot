
#! /usr/bin/env python
# version 4.26

from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr
from random import randint, shuffle
from threading import Timer
from copy import copy
from collections import defaultdict

# mafia - work in a team, they can kill somebody or corrupt the narrator
# inspector - asks to discover the identity of a player (and on which side he is), gets wrong clues if the narrator was corrupted
# hooker - sleeps with somebody, that person cannot do anything during the night, if the mafia kills the client the hooker dies too, one turn after the act the client has AIDS and dies a turn later if he is not cured
# doctor - cures AIDS
# bodyguard - protects somebody during the night
# joker - wins if he gets lynched with a strict majority vote (50%+1)
# wanderer - every night, he is informed of the actions of a player
# opportunist - can ask to know who has a given role and can switch sides anytime
# vigilante - gets the inspector's information and can kill somebody during the night


# things to do list: ghost, joker, twins, !kill hooker instead of regular, lovers, martyr, assassin. maybe: cab driver, party dude, fallguy, mole.
# ghost: villager becomes randomly. immune to killing and votes. acts as hooker at night. mindfuck role DONE.
# joker: same villager becomes randomly. lone psychopath. DONE
# twins: seperate faction. one dies by mafia, other becomes vigilante. one dies by lynch, becomes lone psychopath. DONE
# !kill hooker means to change to respond only to guy who does !kill DONE.
# lovers is just a team change for two people randomly. old powers remain, just on a different side.
# martyr is weak hooker. when fucks someone, becomes their target. DONE.
# assassin is a good vigilante. when mayor dies becomes loner/mafia.
# cab driver switches around two peoples results. switches what happens to them not what they do.
# party dude throws party
# mole/fallguy obv.
# johnny tightlips: silencer. DONE





class Player:
    def __init__(self,nick):
#         self.role = None
        self.group = None
        self.nick = nick
        self.dead = 0
        self.team = None
        self.reset()

    def reset(self):
        self.vote = None
        if self.group:
            self.group.do(None,None)
        self.hooked = 0
        self.protected = 0

class Group:
    def __init__(self,**k):
        self.__dict__ = k
        k['members'] = []
        self.do(None,None)

    def accept(self,nick,player,irc):
        self.members.append(player)
        player.group = self
        player.team = player.group.team

    def do(self,action,target):
        self.action = action
        self.target = target

    def redirect(self,target):
        self.target = target

    def execute(self,game,irc):
        if self.members and len(filter(lambda p:not p.dead, self.members)) != 0 and self.action:
            if self.action != 'idle':
                getattr(self,'execute_'+self.action)(game,self.target,irc)
            self.do(None,None)

    def check_idle(self,game,nick,args,irc):
        self.do('idle',None)
        for player in self.members:
            irc.notice(player.nick,"You have chosen to idle.")

    def check_hooked(self,irc):
        hooked = 0
        for player in self.members:
            if not player.dead and player.hooked:
                hooked = 1
        if hooked:
            for player in self.members:
                if player.hooked:
                    if player.hooked.role == 'ghost':
                        for player2 in self.members:
                            irc.notice(player2.nick,"The ghost came and spooked you into hiding under your bed last night.")
                    elif player.hooked.role == 'martyr':
                        if player.group.role == 'inspector':
                            player.group.falsename == player.group.target.nick
                        self.redirect(player.hooked.members[0])
                        return 0
                    else:
                        for player2 in self.members:
                            irc.notice(player2.nick,"You were too busy fucking the hooker to do anything.")
            return 1
        return 0

class Mafia(Group):
    def __init__(self,gang):
        Group.__init__(self, role='mafia',
                             description='Kill a person during the night.',
                             night='Please type /msg %s kill <player> to kill a player.',
                             priority = 7)
        if gang:
            self.name = gang
        else:
            self.name = 'mafia'
        self.team = self.name
        self.killer = None

    def check_kill(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please kill someone.")
        elif game.players.has_key(args[0]):
            self.do('kill',game.players[args[0]])
            self.killer=nick
            for player in self.members:
                irc.notice(player.nick,"You have chosen to kill " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_kill(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            if target.protected:
                for player in self.members:
                    irc.notice(player.nick,"Your target was protected.")
                return
            if target.group.role == 'bpv' or target.group.name == 'ghost':
                for player in self.members:
                    irc.notice(player.nick,"Your target was protected.")		
                return
            if target.group.role == 'rogue':
#if target.group.stalked == self.killer:
                for player in self.members:
                    if player.nick == target.group.stalked:
                        irc.notice(target.nick,"Looks like you stalked the right person!! Type !resurrect to come alive again at any point in the game!!")
                        target.group.correct = 1
            game.kill_player(target.nick,irc)

class Werewolf(Group):
    def __init__(self):
        Group.__init__(self, name='werewolf',
                             team='werewolf',
                             role='werewolf',
                             description='Kill a person during the night.',
                             night='Please type /msg %s kill <player> to kill a player.',
                             priority = 5)

    def check_kill(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please kill someone.")
        elif game.players.has_key(args[0]):
            self.do('kill',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to kill " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def check_hooked(self,game,irc):
        hooked = 0
        for player in self.members:
            if player.hooked:
                hooked = player.hooked
        if hooked:
            for player in self.members:
                if player.hooked.name == 'ghost':
                    irc.notice(player.nick,"The ghost came and spooked you into hiding under your bed last night.")
                    return 1
                else:
                    if player.hooked.role == 'hooker':
                        irc.notice(player.nick,"The hooker came to see you and you savagely raped and murdered her (not necessarily in that order).")
                    if hooked.members[0].protected:
                        for player in self.members:
                            irc.notice(player.nick,"Your target was protected.")
                        return 1
                    else:
                        game.kill_player(hooked.members[0].nick,irc)
                        return 1
        return 0

    def execute_kill(self,game,target,irc):
        if not self.check_hooked(game, irc):
            if target.protected:
                for player in self.members:
                    irc.notice(player.nick,"Your target was protected.")
                return
            if target.group.role == 'bpv' or target.group.name == 'ghost':
                for player in self.members:
                    irc.notice(player.nick,"Your target was protected.")		
                return
            if target.group.role == 'rogue':
                for player in self.members:
                    if player.nick == target.group.stalked:
                        irc.notice(target.nick,"Looks like you stalked the right person!! Type !resurrect to come alive again at any point in the game!!")
                        target.group.correct = 1
            game.kill_player(target.nick,irc)



class Bodyguard(Group):
    def __init__(self):
        Group.__init__(self, name='bodyguard',
                             team='good people',
                             role='bodyguard',
                             description='Protect a person during the night to prevent him or her from being killed.',
                             night='Please type /msg %s protect <player> to prevent that player from getting killed.',
                             priority = 3)

    def check_protect(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please protect someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot protect yourself.")
        elif game.players.has_key(args[0]):
            self.do('protect',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to protect " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_protect(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            target.protected = self

class Hooker(Group):
    def __init__(self):
        Group.__init__(self, name='hooker',
                             team='good people',
                             role='hooker',
                             description='Fuck a person during the night so he or she cannot do anything this night.',
                             night='Please type /msg %s fuck <player> to prevent that player from doing anything this night.',
                             priority = 2)
        self.last_target = None


    def check_fuck(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please fuck someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot fuck yourself.")
        elif args[0] == self.last_target:
            irc.notice(nick,"You fucked this person last time. Please pick another target.")
        elif game.players.has_key(args[0]):
            self.do('fuck',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to fuck " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_fuck(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            self.last_target = target.nick
            target.hooked = self

class Martyr(Group):
    def __init__(self):
        Group.__init__(self, name='martyr',
                             team='good people',
                             role='martyr',
                             description='You are the ultimate sacrifice. Distract one person each night so that they target you for their action instead of whoever they were initially targetting.',
                             night='Please type /msg %s distract <player> to prevent that player from doing anything this night.',
                             priority = 2)
        self.last_target = None


    def check_distract(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please distract someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot distract yourself.")
        elif args[0] == self.last_target:
            irc.notice(nick,"You distract this person last time. Please pick another target.")
        elif game.players.has_key(args[0]):
            self.do('distract',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to distract " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_distract(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            self.last_target = target.nick
            target.hooked = self

    def check_idle(self,game,nick,args,irc):
        self.do('idle',None)
        self.last_target = None
        for player in self.members:
            irc.notice(player.nick,"You have chosen to idle.")
			
class Ghost(Group):
    def __init__(self):
        Group.__init__(self, name='villager',
                             team='good people',
                             role='ghost',
                             description='Vote to lynch people during the day.',
                             night=None,
                             priority = 1)
        self.last_target = None
        self.activated = 0

    def activate(self,game,irc):
        self.activated = 1
        self.name = 'ghost'
        self.team = 'neutral'
        self.description = 'You can spook a person at night so they cant do anything that night. however, you cannot vote and cannot be killed or lynched.'
        self.night = 'Please type /msg %s spook <player> to prevent that player from doing anything this night.'
        for player in self.members:
            player.team = 'neutral'
            irc.notice(player.nick,"You have become: " + player.group.name + ". " + player.group.description)

    def check_spook(self,game,nick,args,irc):
        if self.activated == 1:
            if len(args) == 0:
                irc.notice(nick,"Please spook someone.")
            elif args[0] in map(lambda x:x.nick, self.members):
                irc.notice(nick,"You cannot spook yourself.")
            elif args[0] == self.last_target:
                irc.notice(nick,"You spooked this person last time. Please pick another target.")
            elif game.players.has_key(args[0]):
                self.do('spook',game.players[args[0]])
                for player in self.members:
                    irc.notice(player.nick,"You have chosen to spook " + args[0] + ".")
            else:
                irc.notice(nick,args[0] + " is not playing or has been killed.")
        else:
            for player in self.members:
                irc.notice(player.nick, "You cannot do anything this night because you are sleeping.")
            return

    def execute_spook(self,game,target,irc):
        self.last_target = target.nick
        target.hooked = self

class Inspector(Group):
    def __init__(self):
        Group.__init__(self, name='inspector',
                             team='good people',
                             role='inspector',
                             description='Inspect a person during the night to know what role he or she has.',
                             night='Please type /msg %s inspect <player> to see who that player is.',
                             priority = 9)
        self.falsename = None

    def check_inspect(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please inspect someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot inspect yourself.")
        elif game.players.has_key(args[0]):
            self.do('inspect',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to inspect " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_inspect(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            for player in self.members:
                if self.falsename:
                    irc.notice(player.nick,self.falsename + " is: " + target.group.name + ".")
                    self.falsename = None
                else:
                    irc.notice(player.nick,target.nick + " is: " + target.group.name + ".")

class Sheriff(Group):
    def __init__(self):
        Group.__init__(self, name='sheriff',
                             team='good people',
                             role='sheriff',
                             description='Check a person during the night to know if they are a villager or not.',
                             night='Please type /msg %s check <player> to see if that player is a villager or not.',
                             priority = 9)

    def check_check(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please check someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot check yourself.")
        elif game.players.has_key(args[0]):
            self.do('check',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to check " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_check(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            for player in self.members:
                if target.group.name == 'villager':
                    irc.notice(player.nick,target.nick + " is: villager.")
                else:
                    irc.notice(player.nick,target.nick + " is: non-villager.")

class Rogue(Group):
    def __init__(self):
        Group.__init__(self, name='rogue',
                             team='good people',
                             role='rogue',
                             description='Stalk a person during the night. If that person kills you then you are given a secret "second" life.',
                             night='Please type /msg %s stalk <player> to stalk a player during the night. If that player kills you, you will be able to resurrect!',
                             priority = 4)
        self.stalked = None
        self.correct = 0
        self.activated = 0

    def activate(self,game,irc):
        self.activated = 1
        self.name = 'rogue'
        self.team = 'good people'
        self.description = 'You have been resurrected from the dead but you have lost all your powers in the process. Now, all you can do is vote to lynch people during the day!'
        self.night = None

    def check_stalk(self,game,nick,args,irc):
        if self.activated == 0:
            if len(args) == 0:
                irc.notice(nick,"Please stalk someone.")
            elif args[0] in map(lambda x:x.nick, self.members):
                irc.notice(nick,"You cannot stalk yourself.")
            elif game.players.has_key(args[0]):
                self.do('stalk',game.players[args[0]])
                for player in self.members:
                    irc.notice(player.nick,"You have chosen to stalk " + args[0] + ".")
            else:
                irc.notice(nick,args[0] + " is not playing or has been killed.")
        else:
            for player in self.members:
                irc.notice(player.nick, "You cannot do anything this night because you are sleeping.")
            return

    def execute_stalk(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            self.stalked = target.nick

class Twin(Mafia):
    def __init__(self):
        Group.__init__(self, name='twin',
                             team='good people',
                             role='twin',
                             description='As of now you are allied with the good people and you know that your brother is also on their side.',
                             night=None,
                             priority = 6)
        self.activated = 0

    def activate_lynch(self,game,irc):
        self.activated = 1
        self.name = 'twin'
        self.team = 'twins'
        self.description = 'You are a lone psychopath struggling to be the last one alive.'
        self.night = 'Please type /msg %s kill <player> to kill a player.'
        for player in self.members:
            player.team = 'twins'
            irc.notice(player.nick,"You have become: " + player.group.name + ". " + player.group.description)

    def activate_kill(self,game,irc):
        self.activated = 1
        self.name = 'twin'
        self.team = 'good people'
        self.description = 'You are vigilante on the side of the good people. You can kill at night.'
        self.night = 'Please type /msg %s kill <player> to kill a player.'
        for player in self.members:
            player.team = 'good people'
            irc.notice(player.nick,"You have become: " + player.group.name + ". " + player.group.description)


    def check_kill(self,game,nick,args,irc):
        if self.activated == 1:
            return Mafia.check_kill(self,game,nick,args,irc)
        else:
            for player in self.members:
                irc.notice(player.nick, "Your twin is still alive so you cannot kill.")
            return

    def execute_kill(self,game,target,irc):
        Mafia.execute_kill(self,game,target,irc)			

class Joker(Mafia):
    def __init__(self):
        Group.__init__(self, name='villager',
                             team='good people',
                             role='joker',
                             description='Vote to lynch people during the day.',
                             night=None,
                             priority = 5)
        self.activated = 0

    def activate(self,game,irc):
        self.activated = 1
        self.name = 'joker'
        self.team = 'joker'
        self.description = 'You fell into a chemical vat and have now turned against everyone.'
        self.night = 'Please type /msg %s kill <player> to kill a player.'
        for player in self.members:
            player.team = 'joker'
            irc.notice(player.nick,"You have become: " + player.group.name + ". " + player.group.description)

    def check_kill(self,game,nick,args,irc):
        if self.activated == 1:
            return Mafia.check_kill(self,game,nick,args,irc)
        else:
            for player in self.members:
                irc.notice(player.nick, "You cannot do anything this night because you are sleeping.")
            return

    def execute_kill(self,game,target,irc):
        Mafia.execute_kill(self,game,target,irc)			

class Silencer(Group):
    def __init__(self,gang):
        Group.__init__(self, name=gang + ' silencer',
                             team=gang,
                             role='silencer',
                             description='You are working with the ' + gang + '. Silence a person during the night to prevent him or her from talking during the day. If he or she talks, they get auto-killed.',
                             night='Please type /msg %s silence <player> to silence that player.',
                             priority = 8)

    def check_silence(self,game,nick,args,irc):
        if len(args) == 0:
            irc.notice(nick,"Please silence someone.")
        elif args[0] in map(lambda x:x.nick, self.members):
            irc.notice(nick,"You cannot silence yourself.")
        elif game.players.has_key(args[0]):
            self.do('protect',game.players[args[0]])
            for player in self.members:
                irc.notice(player.nick,"You have chosen to silence " + args[0] + ".")
        else:
            irc.notice(nick,args[0] + " is not playing or has been killed.")

    def execute_protect(self,game,target,irc):
        if not self.check_hooked(irc):
            target = self.target
            game.silenced = target
            game.silence = 0
            irc.notice(target.nick, "You have been silenced for this day. If you speak up during the day you will be autokilled.")

def Villager():
    return Group(name='villager',
                 team='good people',
                 role='villager',
                 description='Vote to lynch people during the day.',
                 night=None,
                 priority = 9)

def Drogue():
    return Group(name='rogue',
                 team='good people',
                 role='drogue',
                 description='You have been resurrected from the dead but you have lost all your powers in the process. Now, all you can do is vote to lynch people during the day!',
                 night=None,
                 priority = 9)

def Mayor():
    return Group(name='mayor',
                 team='good people',
                 role='mayor',
                 description='vote counts double!',
                 night=None,
                 priority = 9)

def bpv():
    return Group(name='bulletproof vest',
                 team='good people',
                 role='bpv',
                 description='immune to night kills!!',
                 night=None,
                 priority = 9)

def devil():
    return Group(name='devil',
                 team='devil',
                 role='devil',
                 description='you know everybody\'s roles and your vote counts double, but you are on your own',
                 night=None,
                 priority = 9)

class O:
    def __init__(self,**k):
        self.__dict__ = k

def bind(f,arg):
    def f2():
        f(arg)
    return f2

class TestBot(SingleServerIRCBot):
    def __init__(self, channel, nickname, server, port=6667):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel

        self.time_join =60
        self.time_night = 45
        self.time_talk = 3
        self.time_silence = 27
        self.time_vote = 30
        self.timer = None
        self.begin_idle(None)
        self.nightno = 0
        self.specialrole = 0
        self.silencer = 0
        self.silenced = 0
        self.silence = 0

    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
		
    def on_welcome(self, c, e):
        c.privmsg("nickserv", "identify bigcornichon")
        c.join(self.channel)

    def on_pubmsg(self, c, e):
        if self.silence == 1:
            nick = nm_to_n(e.source()).lower()
            if nick == self.silenced.nick and nick in self.players and not self.players[nick].dead:
                self.say(c, self.silenced.nick + " had been silenced but decided to try and talk. " + self.silenced.nick + " will now be auto-killed.")
                if self.players[nick].group.name == 'ghost':
                    self.say(c,nick + " (ghost) was killed!")
                    self.say(c,"But Uh-oh, a ghost is already dead. Looks like " + nick + " shall exist among us forever.")
                elif self.players[nick].group.role == 'twin':
                    self.deadplayers[nick] = self.players[nick]
                    self.players[nick].dead = 1
                    name = self.players[nick].group.name
                    self.say(c,nick + " (" + name + ")" + " was killed!")
                    if self.players[nick].group.activated == 0:
                        someonealive = False
                        for player in self.players[nick].group.members:
                            if not player.dead:
                                someonealive = True
                        if someonealive:
                            getattr(self.players[nick].group,"activate_kill")(self,c)
                            self.say(c,"Cool! " + nick + "'s brother has turned into a vigilante on the side of the good people!")
                    del self.players[nick]
                else:
                    self.kill_player(self.silenced.nick, c)
                self.silence = 0
                self.silenced = 0
                if self.state == 'vote':
                    self.say(c,"Voting will now restart.")
                    self.timer.cancel()
                    self.begin_vote(c)
        try:
            if e.arguments()[0][0] == '!':
                self.on_privmsg(c, e)
        except IndexError:
            return

    def on_pubnotice(self, c, e):
        if self.silence == 1:
            nick = nm_to_n(e.source()).lower()
            if nick == self.silenced.nick and nick in self.players and not self.players[nick].dead:
                self.say(c, self.silenced.nick + " had been silenced but decided to try and talk. " + self.silenced.nick + " will now be auto-killed.")
                if self.players[nick].group.name == 'ghost':
                    self.say(c,nick + " (ghost) was killed!")
                    self.say(c,"But Uh-oh, a ghost is already dead. Looks like " + nick + " shall exist among us forever.")
                elif self.players[nick].group.role == 'twin':
                    self.deadplayers[nick] = self.players[nick]
                    self.players[nick].dead = 1
                    name = self.players[nick].group.name
                    self.say(c,nick + " (" + name + ")" + " was killed!")
                    if self.players[nick].group.activated == 0:
                        someonealive = False
                        for player in self.players[nick].group.members:
                            if not player.dead:
                                someonealive = True
                        if someonealive:
                            getattr(self.players[nick].group,"activate_kill")(self,c)
                            self.say(c,"Cool! " + nick + "'s brother has turned into a vigilante on the side of the good people!")
                    del self.players[nick]
                else:
                    self.kill_player(self.silenced.nick, c)
                self.silence = 0
                self.silenced = 0
                if self.state == 'vote':
                    self.say(c,"Voting will now restart.")
                    self.timer.cancel()
                    self.begin_vote(c)
        try:
            if e.arguments()[0][0] == '!':
                self.on_privmsg(c, e)
        except IndexError:
            return

    def on_privmsg(self, c, e):
        try:
            nick = nm_to_n(e.source()).lower()
            if not self.channels[self.channel].has_user(nick):
                for key in self.channels[self.channel].userdict.keys():
                    if key[0] in ["%","+","~","@","&"]:
                        key = key[1:]
                    key = key.lower()
                    self.channels[self.channel].userdict[key]=1
            line = e.arguments()[0].lower().split(" ")
            line[0] = line[0].replace('!','')
            print "calling: ", nick, " -- ", line[0], " -- ", line[1:]
            # print (self.channels[self.channel].userdict, nick, self.channels[self.channel].has_user(nick))
            if not self.channels[self.channel].has_user(nick):
                c.notice(nick,"Please join the channel, THEN try pm'ing the bot. If you are just trying to fuck around, then suck my balls.")
                self.begin_idle(c)
            elif line[0] == 'reset':
                if self.channels[self.channel].is_oper(nick):
                   self.say(c, "The game has been reset.")
                   self.begin_idle(c)
                else:
                   c.kick(self.channel, nick, "faggot")  # self.begin_idle(c)
            elif line[0] == 'help':
                c.notice(nick,"\002\037For mafiabot:\037\002")
                c.notice(nick,"To start a game type \037!mafia\037. To join a game type \037!join\037.")
                c.notice(nick,"For the various commands, either type '!command target' in main chat or pm the bot with 'command target' where command can be either: \037vote\037 / \037kill\037 / \037fuck\037 / \037protect\037 / \037inspect\037 / \037check\037 / \037distract\037 / \037stalk\037 / \037spook\037 / \037silence\037 and target is the person it is directed towards.")
                c.notice(nick,"\037!reset\037 to reset the mafia game!")
            else:
                getattr(self, 'do_' + self.state)(nick,line[0],line[1:],c)
        except IndexError:
            return


    def say(self,irc,text):
        irc.privmsg(self.channel,"\00312"+self.highlight_players(text))

    def highlight_players(self,text):
        for nick in self.players.keys():
            text = text.replace(nick,"\002\037" + nick + "\037\002")
        return text

    def schedule(self,time,f):
        if self.timer:
            self.timer.cancel()
        if f:
            self.timer = Timer(time,f)
            self.timer.start()

    def invalid_command(self, nick, cmd, args, irc):
        irc.notice(nick, "This command is invalid, or cannot be issued at this point of the game.")

    def begin_idle(self,irc):
        self.state = 'idle'
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.players = {}
        self.deadplayers = {}
        self.order = []
        self.nightno = 0
        self.specialrole = 0
        self.silencer = 0
        self.silenced = 0
        self.silence = 0
        return

    def do_idle(self,nick,cmd,args,irc):
        if cmd == 'mafia':
            self.begin_registering(irc)
            self.do_registering(nick, 'join', [], irc)
        elif cmd == 'version':
            irc.notice(nick,"mafiabot. current version: 4.2")
        elif cmd == 'roles':
            roles = []
            order = []
            roles = self.setup1(10)
            order = copy(roles)
            order.sort(lambda x, y: x.priority.__cmp__(y.priority))
            x = [x.role for x in order]
            self.say(irc, "The roles are: " + ', '.join(x))
        elif cmd != 'witty' and cmd != 'next' and cmd != 'poker' and cmd != 'pokerstop':
            irc.notice(nick,"There is no active game. Type '/msg " + irc.get_nickname() + " mafia or !mafia to start a game.")

    def begin_registering(self,irc):
        self.state = 'registering'
        self.say(irc, "A new game was started! Type '/msg " + irc.get_nickname() + " join' or !join to join! You have " + str(self.time_join) + " seconds to join.")
        irc.notice(self.channel, "Join!")
        self.schedule(self.time_join,bind(self.initialize_game,irc))
#         self.timer = Timer(self.time_join,bind(self.initialize_game,irc))
#         self.timer.start()

    def do_registering(self,nick,cmd,args,irc):
        if cmd == 'join':
            if self.players.has_key(nick):
                irc.notice(nick, "You already joined!")
            else:
                self.players[nick] = Player(nick)
                self.say(irc, nick + " has joined the game!")
        elif cmd == 'mafia':
            if self.players.has_key(nick):
                irc.notice(nick, "The game has already been started and looks like you are already in it!")
            else:
                irc.notice(nick, "The game has already been started.")
                self.players[nick] = Player(nick)
                self.say(irc, nick + " has joined the game!")  
        elif cmd == 'version':
            irc.notice(nick,"mafiabot. current version: 4.2")				
        elif cmd != 'witty' and cmd != 'next' and cmd != 'poker' and cmd != 'pokerstop':
            irc.notice(nick,"You cannot do that now. Type '/msg " + irc.get_nickname() + " join or !join to join the game.")

    def initialize_game(self,irc):
        players = self.players
        roles = self.make_roles(len(players))
        self.order = copy(roles)
        if roles == None:
            self.say(irc, "There are not enough players to play.")
            self.begin_idle(None)
            return

        for nick,player in players.items():
            r = randint(0,len(roles)-1)
            role = roles[r]
            role.accept(nick,player,irc)
            if player.group.role == 'ghost' or player.group.role == 'joker':
                self.specialrole = player
            if player.group.role == 'silencer':
                self.silencer = player
            del roles[r]

        villagers = map(lambda x:x[0], filter(lambda x:x[1].group.role == 'villager', self.players.items()))
        for nick,player in players.items():
            if len(player.group.members) > 1:
                irc.notice(nick,"You are: " + player.group.name + ". " + player.group.description +
                                " Your partner(s) is/are: " + ' '.join(filter(lambda x:x!=nick,map(lambda x:x.nick, player.group.members))))
                if self.silencer and self.silencer.team == player.group.team:
                    irc.notice(nick,"You also have a silencer working with your team, he is: " + self.silencer.nick)
            elif player.group.role == 'silencer':
                for nick2,player2 in players.items():
                    if player2.group.team == player.group.team and player != player2:
                        irc.notice(nick, "You are: " + player.group.name + ". " + player.group.description + " Your partners are: "  + ' '.join(filter(lambda x:x!=nick,map(lambda x:x.nick, player2.group.members))))
                        break
            elif player.group.role == 'devil':
                irc.notice(nick,"You are: " + player.group.name + ", " + player.group.description +
                                " Here are the roles of everyone: " + ' '.join(map(lambda x:"(" + x[0] + " is " + x[1].group.role + ")", players.items())))
            elif False: # player.group.role == 'villager' and len(villagers) > 1:
                v2 = copy(villagers)
                v2.remove(nick)
                r = randint(0,len(v2)-1)
                friend = v2[r]
                irc.notice(nick,"You are: " + player.group.name + ". " + player.group.description + ". You know that " + friend + " is also a villager.")
            else:
                irc.notice(nick,"You are: " + player.group.name + ". " + player.group.description)
        self.order.sort(lambda x, y: x.priority.__cmp__(y.priority))
        x = [x.name for x in self.order]
        x.sort()
        self.say(irc, "The roles are: " + ', '.join(x))
       # self.say(irc, "The roles are: " + ', '.join(map(lambda x:x.name, self.order)))

        self.begin_night(irc)

    def setup1(self, nplayers):
        if nplayers < 7 or nplayers > 10: return None
        roles = []
        roles += {4: [Joker()], 2: [Ghost()]}.get(randint(0, 15), [])
        roles += [Hooker() if randint(0, 1) else Martyr()]
        roles += [Bodyguard()]
        roles += [Werewolf()]
        roles += [Mafia(None)]*2
        if nplayers == 10:
            roles += [Inspector() if randint(0, 1) else Sheriff()]
        else:
            roles += [Inspector()]
        if nplayers > 7:
            roles += [Mayor()]
        tempplayers = len(roles)
        roles += [Villager() for x in xrange(0,nplayers-tempplayers)]
        return roles

    def setup2(self, nplayers):
        if nplayers < 10 or nplayers > 13: return None
        roles = []
        roles += {4: [Ghost()], 2: [Joker()]}.get(randint(0, 15), [])
#        possible = [Martyr(), Hooker(), Bodyguard(), Inspector(), Sheriff(), Rogue(), Silencer()]
#       for i in xrange(3): idx = randint(0, len(possible)-1); possible[idx:idx+1] = []
#        roles += possible
        roles += [Hooker() if randint(0, 1) else Martyr()]
        roles += [Rogue()]
        roles += [Inspector() if randint(0, 1) else Sheriff()]
        roles += [Bodyguard()]
        roles += [Mafia('italian mafia')]*2
        roles += [Mafia('french canadian mafia')]*2
        roles += [Mayor()]
        tempplayers = len(roles)
        roles += [Villager() for x in xrange(0,nplayers-tempplayers)]
        return roles

    def setup3(self, nplayers):
        if nplayers < 12 or nplayers > 15: return None
        roles = []
        roles += {4: [Ghost()], 2: [Joker()]}.get(randint(0, 15), [])
#        possible = [Rogue(), Silencer(), Mayor()]
#        for i in xrange(1): idx = randint(0, len(possible)-1); possible[idx:idx+1] = []
#        roles += possible
        roles += [Rogue()]
        roles += [Mayor()]
        roles += [Hooker() if randint(0, 1) else Martyr()]
        roles += [Inspector() if randint(0, 1) else Sheriff()]
        roles += [Bodyguard()]
        roles += [Mafia('russian mafia')]*2
        roles += [Silencer('russian mafia')]
        roles += [Twin()]*2
        roles += [Werewolf()]
        tempplayers = len(roles)
        roles += [Villager() for x in xrange(0,nplayers-tempplayers)]
        return roles

    def setup4(self, nplayers):
        if nplayers < 14 or nplayers > 20: return None
        roles = []
        roles += {4: [Ghost()], 2: [Joker()]}.get(randint(0, 15), [])
        possible = [Inspector(), Sheriff(), Hooker(), Martyr()]
        for i in xrange(1): idx = randint(0, len(possible)-1); possible[idx:idx+1] = []
        roles += possible
        roles += [Rogue()]
        roles += [Mayor()]
        roles += [Bodyguard()]
        roles += [Mafia('italian mafia')]*3
        roles += [Mafia('french canadian mafia')]*3
        tempplayers = len(roles)
        roles += [Villager() for x in xrange(0,nplayers-tempplayers)]
        return roles
		
    def make_roles(self, nplayers):
        setups = [getattr(self, attr) for attr in dir(self) if attr.startswith('setup')]
        choice = randint(0, len(setups)-1)
        shuffle(setups)
        for setup in setups:
            result = setup(nplayers)
            if result: return result
        return None

    def begin_night(self,irc):
        self.state = 'night'
        self.say(irc,"The night starts! The players still alive are: " + ', '.join(self.players.keys()) +
                     ". The night will end in " + str(self.time_night) + " seconds.")
        self.nightno += 1
        if self.nightno == 2:
            if self.specialrole and not self.specialrole.dead:
                self.say(irc,"Oh! Looks like one of the villagers has become a " + self.specialrole.group.role + ".")
                getattr(self.specialrole.group,"activate")(self,irc)
        for nick,player in self.players.items():
            if player.group.night:
                irc.notice(nick, player.group.night % irc.get_nickname())
        self.schedule(self.time_night,bind(self.end_night,irc))
#         self.timer = Timer(self.time_night,bind(self.end_night,irc))
#         self.timer.start()

    def do_night(self,nick,cmd,args,irc):
        try:
            player = self.players[nick]
            if player.group.night:
                try:
                    getattr(player.group,"check_" + cmd)(self,nick,args,irc)
                except AttributeError:
                    irc.notice(nick,"You cannot issue this command.")
            else:
                irc.notice(nick,"You cannot do anything this night because you are sleeping.")
            if self.all_moved():
                try:
                    self.timer.cancel()
                    self.end_night(irc)
                except AssertionError:
                    return
        except KeyError:
            if cmd == 'resurrect':
                if nick in self.deadplayers and self.deadplayers[nick].group.role == 'rogue' and self.deadplayers[nick].group.correct == 1:
                    self.players[nick] = self.deadplayers[nick]
                    del self.deadplayers[nick]
                    Rogue().accept(nick, self.players[nick], irc)
                    getattr(self.players[nick].group,"activate")(self,irc)
                    self.say(irc, nick + " has been resurrected!")
            else:
                irc.notice(nick, "You are not playing.")

    def all_moved(self):
        for nick,player in self.players.items():
            if player.group.night and not player.group.action:
                if player.group.role == 'twin':
                    if player.group.activated == 1:
                        return 0
                else:
                    return 0
        return 1

    def end_night(self,irc):
        before = len(self.players)
        for group in self.order:
            group.execute(self,irc)
        after = len(self.players)
        if before == after:
            self.say(irc, "Nobody was killed.")
        winner_team, winners = self.winner()
        if winner_team:
            self.say(irc, "Game over! " + " ".join(winners) + " (the " + winner_team + ") won!")
            self.begin_idle(irc)
        elif len(self.players)==0:
            self.say(irc, "The game ended in a tie.")
        else:
            self.begin_talk(irc)

#     def begin_deliberate(self,irc):
#         self.state = 'deliberate'
#         self.say(irc,"The day starts! The players still alive are: " +
#                      ', '.join(self.players.keys()) + '. You can deliberate during the day. Type !accuse <player> to accuse that ' +
#                      'player, or !nolynch to suggest that nobody is lynched today. After ' + str(self.time_deliberate) ' seconds, if ' +
#                      'nobody was lynched, the night will start nonetheless.')
#         self.deliberate = 1
#         self.deliberate_timer = Timer(self.time_deliberate,bind(self.end_deliberate,irc))
#         self.deliberate_timer.start()
# 
#     def end_deliberate(self,irc):
#         if self.state == 'deliberate':
#             try:
#                 self.deliberate_timer.cancel()
#             except:
#                 pass
#         else:
#             self.deliberate = 0
# 
#     def revert_deliberate(self,irc):
#         self.state = 'deliberate'
#         if self.deliberate == 0:
#             self.end_deliberate(irc)
# 
#     def do_deliberate(self,irc):
#         try:
#             if cmd == 'accuse':
#                 if len(args) == 0:
#                     irc.notice(nick, "Please accuse someone.")
#                 elif self.players.has_key(args[0]):
#                     self.players[nick].vote = args[0]
#                     self.say(irc, nick + " is accusing " + args[0] + "! " + args[0] + ", you have " + self.time_defend + " seconds to defend yourself.")
#                 else:
#                     irc.notice(nick, args[0] + " is not playing or has been killed.")
#             else:
#                 irc.notice(nick,"You cannot do that now. Type '/msg " + irc.get_nickname() + " accuse <player> or !accuse <player> to accuse that player.")
#         except KeyError:
#             irc.notice(nick, "You are not playing or you have been killed.")

    def begin_talk(self,irc):
        self.state = 'talk'
        self.say(irc,"The day starts! The players still alive are: " +
                     ', '.join(self.players.keys()) + '. You can deliberate for the next ' + str(self.time_talk + self.time_silence) + ' seconds.')
        self.timer = Timer(self.time_talk,bind(self.begin_silence,irc))
        self.timer.start()

    def do_talk(self,nick,cmd,args,irc):
        if cmd == 'resurrect':
            if nick in self.deadplayers and self.deadplayers[nick].group.role == 'rogue' and self.deadplayers[nick].group.correct == 1:
                   self.players[nick] = self.deadplayers[nick]
                   del self.deadplayers[nick]
                   Rogue().accept(nick, self.players[nick], irc)
                   getattr(self.players[nick].group,"activate")(self,irc)
                   self.say(irc, nick + " has been resurrected!")
	    if cmd == 'version':
                   irc.notice(nick,"mafiabot. current version: 4.2")
	    elif cmd != 'witty' and cmd != 'next' and cmd != 'poker' and cmd != 'pokerstop':
                   irc.notice(nick,"You cannot issue a command right now.")

    def begin_silence(self,irc):
        self.state = 'silence'
        if self.silenced:
            self.silence = 1
        self.timer = Timer(self.time_silence,bind(self.begin_vote,irc))
        self.timer.start()

    def do_silence(self,nick,cmd,args,irc):
        if cmd == 'resurrect':
            if nick in self.deadplayers and self.deadplayers[nick].group.role == 'rogue' and self.deadplayers[nick].group.correct == 1:
                   self.players[nick] = self.deadplayers[nick]
                   del self.deadplayers[nick]
                   Rogue().accept(nick, self.players[nick], irc)
                   getattr(self.players[nick].group,"activate")(self,irc)
                   self.say(irc, nick + " has been resurrected!")
	    if cmd == 'version':
                   irc.notice(nick,"mafiabot. current version: 4.2")
	    elif cmd != 'witty' and cmd != 'next' and cmd != 'poker' and cmd != 'pokerstop':
                   irc.notice(nick,"You cannot issue a command right now.")

    def begin_vote(self,irc):
        self.state = 'vote'
        self.say(irc,"Deliberations are over. You have " + str(self.time_vote) + ' seconds to vote for the person you want to lynch.' +
                     " To vote, type: /msg " + irc.get_nickname() + " vote <player>")
        for nick,player in self.players.items():
            player.reset()
        self.timer = Timer(self.time_vote,bind(self.end_vote,irc))
        self.timer.start()

    def do_vote(self,nick,cmd,args,irc):
        try:
            if cmd == 'vote':
                if self.players[nick].vote:
                    irc.notice(nick, "You have already voted!")
                elif len(args) == 0:
                    irc.notice(nick, "Please vote for someone.")
                elif self.players[nick].group.name == 'ghost':
                    irc.notice(nick, "Sorry, the ghost cannot vote.")
                elif self.silence == 1:
                    if self.players[nick] == self.silenced:
                        irc.notice(nick, "Sorry, you have been silenced and cannot vote.")
                    elif self.players.has_key(args[0]):
                        self.players[nick].vote = args[0]
                        self.say(irc, nick + " has voted for " + args[0])
                    else:
                        irc.notice(nick, args[0] + " is not playing or has been killed.")
                elif self.players.has_key(args[0]):
                    self.players[nick].vote = args[0]
                    self.say(irc, nick + " has voted for " + args[0])
                else:
                    irc.notice(nick, args[0] + " is not playing or has been killed.")
            else:
                if cmd == 'resurrect':
                    if nick in self.deadplayers and self.deadplayers[nick].group.role == 'rogue' and self.deadplayers[nick].group.correct == 1:
                        self.players[nick] = self.deadplayers[nick]
                        del self.deadplayers[nick]
                        Rogue().accept(nick, self.players[nick], irc)
                        getattr(self.players[nick].group,"activate")(self,irc)
                        self.say(irc, nick + " has been resurrected!")
                else:
                        irc.notice(nick,"You cannot do that now. Type '/msg " + irc.get_nickname() + " vote <player> to vote to lynch that player.")
            if self.all_voted():
                try:
                    self.timer.cancel()
                    self.say(irc,"Everybody has voted.")
                    self.end_vote(irc)
                except AssertionError:
                    return
        except KeyError:
            if cmd == 'resurrect':
                if nick in self.deadplayers and self.deadplayers[nick].group.role == 'rogue' and self.deadplayers[nick].group.correct == 1:
                    self.players[nick] = self.deadplayers[nick]
                    del self.deadplayers[nick]
                    Rogue().accept(nick, self.players[nick], irc)
                    getattr(self.players[nick].group,"activate")(self,irc)
                    self.say(irc, nick + " has been resurrected!")
            else:
                irc.notice(nick, "You are not playing or you have been killed.")

    def end_vote(self,irc):
        tally = {}
        self.silence = 0
        self.silenced = 0
        tally = defaultdict(lambda: 0)
        for nick,player in self.players.items():
            if player.vote:
                if player.group.role == 'mayor' or player.group.role == 'devil':
                    tally[player.vote] += 2
                else:
                    tally[player.vote] += 1
            player.reset()
        max = 0
        for nick,votes in tally.items():
            if max < votes:
                max = votes
        tally = filter(lambda x:x[1]==max,tally.items())
        if len(tally) == 1:
            victim = tally[0][0]
            if self.players[victim].group.name == 'ghost':
                self.say(irc,victim + " (ghost) was killed!")
                self.say(irc,"But Uh-oh, a ghost is already dead. " + victim + " shall exist among us forever.")
            else:
                if victim in self.players and not self.players[victim].dead:
                    self.lynch_player(victim,irc)
                else:
                    if self.players[victim].group.role == 'drogue' or self.players[victim].group.role == 'rogue':
                        self.lynch_player(victim,irc)
                    else:
                        self.say(irc,"Looks like " + victim + " is already dead!")
        else:
            self.say(irc, "There is a tie between: " + ", ".join(map(lambda x:x[0],tally)) + ". Nobody is going to be lynched.")
#             r = randint(0,len(tally)-1)
#             victim = tally[r][0]
#         self.kill_player(victim,irc)
        winner_team, winners = self.winner()
        if winner_team:
            self.say(irc, "Game over! " + " ".join(winners) + " (the " + winner_team + ") won!")
            self.begin_idle(irc)
        else:
            self.begin_night(irc)

    def all_voted(self):
        for nick,player in self.players.items():
            if not player.vote:
                return 0
        return 1

    def winner(self):
        remaining = {}
        neutral = []
        for nick,player in self.players.items():
            if player.team != 'neutral':
                try:
                    remaining[player.team].append(nick)
                except KeyError:
                    remaining[player.team] = [nick]
            else:
                neutral.append(nick)
        if len(remaining) == 1:
            winning_team, winners = remaining.items()[0]
            winners = winners + neutral
            return winning_team, winners
        else:
            return [None,None]

    def kill_player(self,nick,irc):
        try:
            if self.players[nick].group.role == 'twin':
                self.deadplayers[nick] = self.players[nick]
                self.players[nick].dead = 1
                name = self.players[nick].group.name
                self.say(irc,nick + " (" + name + ")" + " was killed!")
                if self.players[nick].group.activated == 0:
                    someonealive = False
                    for player in self.players[nick].group.members:
                        if not player.dead:
                            someonealive = True
                    if someonealive:
                        getattr(self.players[nick].group,"activate_kill")(self,irc)
                        self.say(irc,"Cool! " + nick + "'s brother has turned into a vigilante on the side of the good people!")
                del self.players[nick]

            else:
                self.deadplayers[nick] = self.players[nick]
                self.players[nick].dead = 1
                name = self.players[nick].group.name
                self.say(irc,nick + " (" + name + ")" + " was killed!")
                del self.players[nick]
        except KeyError:
            return

    def akill_player(self,nick,irc):
        try:
            self.deadplayers[nick] = self.players[nick]
            self.players[nick].dead = 1
            name = self.players[nick].group.name
            self.say(irc,nick + " (" + name + ")" + " was godkilled!")
            del self.players[nick]
        except KeyError:
            return

    def lynch_player(self,nick,irc):
        try:
            if self.players[nick].group.role == 'twin':
                self.deadplayers[nick] = self.players[nick]
                self.players[nick].dead = 1
                name = self.players[nick].group.name
                self.say(irc,nick + " (" + name + ")" + " was lynched!")
                if self.players[nick].group.activated == 0:
                    someonealive = False
                    for player in self.players[nick].group.members:
                        if not player.dead:
                            someonealive = True
                    if someonealive:
                        getattr(self.players[nick].group,"activate_lynch")(self,irc)
                        self.say(irc,"Uh-Oh, " + nick + "'s brother has turned into a lone psychopath caring for nobody except himself...")
                del self.players[nick]
            else:
                self.deadplayers[nick] = self.players[nick]
                self.players[nick].dead = 1
                name = self.players[nick].group.name
                self.say(irc,nick + " (" + name + ")" + " was lynched!")
                del self.players[nick]
        except KeyError:
            return

def main():

    import sys

    if len(sys.argv) != 4:
        print "Usage: mafiabot <server[:port]> <channel> <nickname>"
        sys.exit(1)

    s = sys.argv[1].split(":", 1)
    server = s[0]
    if len(s) == 2:
        try:
            port = int(s[1])
        except ValueError:
            print "Error: Erroneous port."
            sys.exit(1)
    else:
        port = 6667
    channel = sys.argv[2]
    nickname = sys.argv[3]
    bot = TestBot(channel, nickname, server, port)
    bot.start()

if __name__ == "__main__":
    main()
