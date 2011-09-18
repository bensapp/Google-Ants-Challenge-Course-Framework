#!/usr/bin/env python
# Created: September 2011
# Author: Jennifer Gillenwater
#
# An example deterministic finite automaton (DFA) bot.

import sys
import time
import random
from antsbot import AntsBot
from greedybot import GreedyBot
from worldstate import AIM, AntStatus, AntWorld, LAND, FOOD, WATER, MY_ANT
import json

class JSONParseError(Exception):
    def __init__(self, caller, json_txt, fieldname):
        self.json_txt = json_txt
        self.fieldname = fieldname
        self.caller = str(caller.__class__)
    def __str__(self):
        return "Error parsing %s:\nJSON txt = '%s'\nBad field '%s'" %  \
            (self.caller, self.json_txt, self.fieldname)

class Feature:
    @classmethod
    def get_feature_class(cls, name):
        if name == 'SquareFeature':
            return SquareFeature
        else:
            raise Exception("Invalid feature class") 
        
class SquareFeature: 
    def __init__(self, offset):
        self.offset = offset
        
    def __str__(self):
        return "square[%d,%d]" % (self.offset[0], self.offset[1])

    def to_dict(self):
        return {'_type': 'SquareFeature', 'offset': self.offset}
    
    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, x):
        if not x['_type'] == 'SquareFeature':
            raise JSONParseError(self, json.dumps(x), '_type')
        return SquareFeature(x['offset'])

    def get_value(self, world, state, loc):
        row = loc[0] + self.offset[0]
        col = loc[1] + self.offset[1]
        if row < 0: 
            row = row + world.height
        elif row >= world.height:
            row = world.height - row
            
        if col < 0:
            col = col + world.width
        elif col >= world.width:
            col = world.width - col
            
        value = world.map[row][col]    
        if value == WATER:
            return 0
        if value == FOOD:
            return 1
        if value == MY_ANT:
            return 2
        if value == LAND:
            return 3
        if value > MY_ANT:
            return 4
        return 5
    
    def get_range(self):
        return range(0, 6)
    
class DecisionNode:
    def __init__(self, feature, leaves, is_terminal):
        self.feature = feature
        self.leaves = leaves
        self.is_terminal = is_terminal
            
class DecisionTree:
    def __init__(self, world, depth_limit):
        self.world = world
        self.offset_range = [-8, -4, -2, -1, 1, 2, 4, 8]
        self.root = self.build_random_tree(depth_limit=depth_limit)
               
    def get_decision(self, loc, state):
        node = self.root

        # recursively traverse tree until terminal node is reached
        while not node.is_terminal:
            value = node.feature.get_value(self.world, state, loc)
            self.world.L.debug("feature: %s at pos %s = %d" % (str(node.feature), str(loc), value))
            node = node.leaves[value]

        # get final value         
        value = node.feature.get_value(self.world, state, loc)
        self.world.L.debug("feature: %s at pos %s = %d --> %s" % (str(node.feature), str(loc), value, node.leaves[value]))   
        return node.leaves[value]
    
    def build_random_tree(self, depth=0, depth_limit=3):
        # get random offset
        offset = list()
        
        offset.append(random.choice(self.offset_range))
        offset.append(random.choice(self.offset_range))
        feature = SquareFeature(offset)
        leaves = []
        for value in feature.get_range():
            if depth < depth_limit:
                leaves.append(self.build_random_tree(depth+1, depth_limit))
            else:
                leaves.append(random.choice(['n','s','e','w']))
        return DecisionNode(feature, leaves, depth == depth_limit)
            
    def to_dict(self, node=None):
        if node == None:
            node = self.root

        x = {}
        x['_type'] = 'DecisionNode'
        x['is_terminal'] = node.is_terminal
        x['feature'] = node.feature.to_dict()
        if node.is_terminal:
            x['leaves'] = node.leaves
        else:
            x['leaves'] = [self.to_dict(leaf) for leaf in node.leaves]

        return x
    
    def from_dict(self, input):     
    
        assert(input['_type'] == 'DecisionNode')
        
        # Get feature
        feature_class = Feature.get_feature_class(input['feature']['_type'])
        feature = feature_class.from_dict(input['feature'])
        
        # Get leaves
        if input['is_terminal']:
            leaves = input['leaves']
        else:
            leaves = [self.from_dict(leaf) for leaf in input['leaves']]
            
        return DecisionNode(feature, leaves, input['is_terminal'])
                                    
class EvoBot(AntsBot):
    def __init__(self, world):
        self.world = world
        self.tree = DecisionTree(self.world, depth_limit=2)
        #tree2 = DecisionTree(self.world, depth_limit=1)
        #tree2.from_json(self.tree.to_json())
        #print json.dumps(self.tree.to_dict())
        x = json.loads(json.dumps(self.tree.to_dict()))
        self.tree.root = self.tree.from_dict(x)
        print self.tree.to_dict() 
        
    # Main logic
    def do_turn(self):
        # Run the routine for each living ant independently.
        for ant in self.world.ants:
            if ant.status == AntStatus.ALIVE:
                ant.direction = self.tree.get_decision(ant.location, None)

def EvaluateTrees(engine, evo_bot, trees, num_games):
    played_games = 0
    start_time = time.time()
    bot_wins = [ 0 for i in range(0, pop_size)]
    bot_scores = [ 0 for i in range(0, pop_size)]
    for i in range(0, num_games):
        random_map = SymmetricMap(min_dim=30, max_dim=30)
        random_map.random_walk_map()                
        
        for b in range(0, pop_size):
            evo_bot.tree = trees[b]
            engine.game.Reset(random_map.map_text())
            engine.Run()
            if engine.game.score[0] > engine.game.score[1]: 
                bot_wins[b] += 1
            bot_scores[b] += engine.game.score[0]
            played_games += 1
        print "map", i, ": bot_scores", str([float(s) for s in bot_scores])
        
    elapsed = time.time() - start_time
    sum_bots = 0
    print "bot_wins,", bot_wins
    print "Time summary: %.2f s total elapsed = %.2f s/game " % (elapsed, elapsed/played_games)
    for b,bot in engine.bots:
        sum_bots += engine.bot_time[b]
        print "\tbot %d %s: %.5f s = %.2f%%" % (b, str(bot.__class__), engine.bot_time[b], engine.bot_time[b]/elapsed*100)     
    print "\tengine: %.5f s = %.2f%%" % (elapsed-sum_bots, (elapsed-sum_bots)/elapsed*100)
    
    return bot_scores
        
# Main section allowing for dual use either with the standard engine
# or the LocalEngine. If no arguments are given, it calls
# AntsBot.Run() to run as a stand alone process, communicating via
# stdin/stdout. However, if arguments are given, it passes them to
# LocalEngine and creates an instance of DFABot and an instance of
# GreedyBot to play against one another.
if __name__ == '__main__':

    # From Ants distribution: use psyco to speed up all code.
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    try:
        if len(sys.argv) > 1: # Run LocalEngine version
            
            batchMode = False            
            if batchMode:                
                from batchlocalengine import BatchLocalEngine
                from mapgen import SymmetricMap
                engine = BatchLocalEngine()    
                evo_bot = EvoBot(engine.GetWorld())            

                # generate 10 random trees
                pop_size = 10
                trees = []
                for i in range(0, pop_size):
                    trees.append(DecisionTree(evo_bot.world, 3))
                    
                engine.AddBot(evo_bot)
                engine.AddBot(GreedyBot(engine.GetWorld()))
                engine.PrepareGame(sys.argv + ["-t", "100"])
                engine.game.efficient_update = True
                
                # How many rounds of evolution?
                for rounds in range(0, 10):
                    EvaluateTrees(engine, evo_bot, trees, 10)             
                
            else:
                from localengine import LocalEngine
                engine = LocalEngine()
                engine.AddBot(EvoBot(engine.GetWorld()))
                engine.AddBot(GreedyBot(engine.GetWorld()))
                engine.Run(sys.argv)
            
            
        else: # Run as stand-alone process
            bot = EvoBot(AntWorld())
            bot._run()

    except KeyboardInterrupt:
        print('ctrl-c, leaving ...')
