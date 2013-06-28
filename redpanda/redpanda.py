# -*- coding: utf-8 -*-

import os
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d
from dataset import *

def dataset(path, commentstring=None, colnames=None, delimiter='[\s\t]+', start=-float('inf'), stop=float('inf'), \
    colid=None, ext=None):
    '''more than one file'''
    
    #microvalidation
    if start > stop:
        print 'maybe start > stop ? \n'
    if colnames and colid:
        if len(colnames) != len(colid):
            print 'colid and colnames must have same length!'
    if not colnames:
        col_pref = 'Y'
    else:
        col_pref = None

    if ext and not ext.startswith('.'):
        ext = ''.join(('.', ext))

    if colid and delimiter != ',':
        print 'column selection work only with delimiter = \',\' (yet)'


    dataset = {}

    # skip dir, parse all file matching ext
    for x in os.listdir(path):
        actualfile = os.path.join(path, x)

        # check if isdir
        if os.path.isdir(actualfile):
            continue
        _, actualext = os.path.splitext(actualfile)

        # check if ext match
        if ext and ext != actualext:
            continue

        # import
        source = CommentedFile(open(actualfile, 'rb'), \
            commentstring=commentstring, low_limit=start, high_limit=stop)
        dataset[x] = pd.read_csv(source, sep=delimiter, index_col=0, \
            header=None, names=colnames, usecols=colid, prefix=col_pref)
        source.close()

    # return RedPanda Obj (isset = True)
    return RedPanda(dataset, True)

def timeseries(path, commentstring=None, colnames=None, delimiter='[\s\t]+', start=-float('inf'), stop=float('inf'), \
    colid=None):
    '''just one file'''
    
    # microvalidation
    if start > stop:
        print 'maybe start > stop ? \n'
    if colnames and colid:
        if len(colnames) != len(colid):
            print 'colid and colnames must have same length!'
    if not colnames:
        col_pref = 'Y'
    else:
        col_pref = None

    if colid and delimiter != ',':
        print 'column selection work only with delimiter = \',\' (yet)' 

    source = CommentedFile(open(path, 'rb'), \
        commentstring=commentstring, low_limit=start, high_limit=stop)
    timeseries = pd.read_csv(source, sep=delimiter, index_col=0, \
        header=None, names=colnames, usecols=colid, prefix=col_pref)
    source.close()

    # return RedPanda Obj (isset = False)
    return RedPanda(timeseries, None)

class RedPanda:
    def __init__(self, data, isSet):
        # dataset or timeseries
        self.data = data
        # what's the type
        self.isSet = isSet
        # start with default terminal
        self.output = ['view']
        # range -> label:data (pandas df with index)
        self.range = {}

    def createrange(self, label, colname, start, stop, step):
        """Select 1 column and create a range from start to stop"""
        if not self.isSet:
            print 'createrange works only on dataset'
            return
        index = np.arange(start, stop, step)
        mean_df = pd.DataFrame(index=index)
        for k,v in self.data.iteritems():
            mean_df.insert(0, k, self.get(v[colname], start, stop, step))
        self.range[label] = mean_df

    @staticmethod
    def get(df, l_limit, h_limit, step):
        start = float(l_limit)
        now = float(start + step)
        to_return = []
        try:
            last_value = df.truncate(after=start).tail(1).values[0]
        except:
            last_value = 0
        to_return.append(last_value)
        while now < h_limit:
            try:
                last_value = df.truncate(before=start, after=now).tail(1).values[0]
            except:
                pass
            to_return.append(last_value)
            start = start + step
            now = now + step
        return to_return



def meq_relfreq(df_dict, colname, l_limit, h_limit, step, numbins=10):
    range_df = create_range(df_dict, colname, l_limit, h_limit, step)
    rangeX = np.arange(l_limit, h_limit, step)
    X = np.zeros((len(rangeX),numbins))
    for x in range(len(rangeX)):
        X[x] = rangeX[x]
    Y = []
    Z = []
    for x in rangeX: 
        relfreq, startpoint, binsize, extrap = stats.relfreq(range_df.loc[x].values, numbins=numbins, \
                defaultreallimits=(min(range_df.loc[x]),max(range_df.loc[x])))
        Yline = [startpoint]
        Z.append(list(relfreq))
        for _ in range(1, len(relfreq)):
            next_y = Yline[-1] + binsize
            Yline.append(next_y)
        Y.append(Yline)
    Y = np.array(Y)
    Z = np.array(Z)
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    cset = ax.contourf(X, Y, Z, alpha=0.5)
    #ax.clabel(cset, fontsize=9, inline=1)
    ax.set_zlim3d(0, 1)
    plt.show()
    return (X, Y, Z)

def meq_itemfreq(df_dict, colname, l_limit, h_limit, step):
    range_df = create_range(df_dict, colname, l_limit, h_limit, step)
    rangeX = np.arange(l_limit, h_limit, step)
    X = np.zeros((len(rangeX),len(rangeX)))
    for x in range(len(rangeX)):
        X[x] = rangeX[x]
    Y = []
    Z = []
    for x in rangeX: 
        itemfreq = stats.itemfreq(range_df.loc[x].values)
        return itemfreq
        Y.append([y[0] for y in itemfreq])
        Z.append([z[1] for z in itemfreq])
    return (X, Y, Z)
    Y = np.array(Y)
    Z = np.array(Z)
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    cset = ax.contourf(X, Y, Z, cmap=cm.coolwarm)
    ax.clabel(cset, fontsize=9, inline=1)

def rel_pdf(self, df_dict, numbins=10):
    to_return = np.array([])
    for k,v in df_dict.iteritems():
        to_return = np.append(to_return, [k].append(stats.relfreq(v, numbins=numbins)))
    #plt.ion()
    #fig = plt.figure()
    #ax = fig.add_subplot(111, projection='3d')
    #X, Y, Z = axes3d.get_test_data(0.1)
    #ax.plot_wireframe(X, Y, Z, rstride=5, cstride=5)
#
#        #for angle in range(0, 360):
#        #    ax.view_init(30, angle)
    #plt.draw()
    return to_return