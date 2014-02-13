#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division
try:
    import builtins as py
except ImportError:
    import __builtin__ as py

import os
import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import tables as ts
import sys
import re
import time
import multiprocessing
from mpl_toolkits.mplot3d import Axes3D
from commentedfile import *
from importLooper import *
from dataSampler import *
from itertools import izip_longest

def dataset(path, 
            commentstring=None, 
            colnames=None, 
            delimiter='[\s\t]+', 
            start=-float('inf'), 
            stop=float('inf'), 
            colid=None, 
            ext=None, 
            every=None, 
            numfiles=None, 
            hdf5=None):
    """
    Return a pytsa DataObject object from a set of time series.

    Arguments:

    path string : where the folder is located, in the form '/myworkingdir/tsfolder' (required)

    Keyword arguments:
    
    commentstring string (default None) : the symbol that indicates a comment line like '#' or '//'
    colnames array-like (default None) : columns names, in the form ['t', 'col1', 'col2']. If not set the name will be X1, X2 and so on, excluding time axis.
    delimiter string (default [\s\\t]+) : a regex. Default is whitespace.
    start float : first row to import based on time axis
    stop float : last row to import based on time axis
    colid array-like (default None) : columns to import. Must have same length of colnames. First column has to be included. 
    ext string (default None) : extension of the files to be imported, like data or .txt
    every float range 0-1 (default None) : percentage of rows to be loaded, equally distributed over the entire file. 0 is no rows, 1 is the entire file. If Default every row will be loaded
    numfiles int (default None) : in a folder you can load only numfiles files. Files are chosen randomly.
    """

    # check if pathname is correct
    if not path.endswith('/'):
        path = path + '/'


    #times check
    if start > stop:
        raise ValueError('start > stop... Somethings wrong here?\n')


    # check if len(colnames) and len(colis) are = 
    if colnames and colid:
        if len(colnames) != len(colid):
            raise ValueError('colid and colnames must have same length!')
    if colnames is None:
        col_pref = 'Y'
    else:
        col_pref = None


    # check if delimiter is ok
    convert_comma = None
    if colid and delimiter != ',':
        convert_comma = True
        delimiter = ','
        #raise ValueError('column selection work only with delimiter = \',\' (yet)')

    # if hdf5 create a HDFStore object in 'w' mode
    if hdf5 is None:
        datadict = {}
        hdf5name = None
        r = None
    else:
        name = hdf5 + '.h5'
        datadict =  pd.HDFStore(name, 'w')  
        r = re.compile(r'[\W]+')
        hdf5name = name 

    # other usefull infos
    timemin = 0.0
    timemax = 0.0
    

    # Only not ending with
    files = [f for f in os.listdir(path) if (os.path.isfile(path + f) )]
    if ext:
        #badfiles = [f for f in os.listdir(path) if (ext not in f and os.path.isfile(path + f))]
        files = [x for x in files if ext in x]
    if numfiles:
        files = files[:numfiles]


    # progressbar
    numberoffile = len(files)
    size = sum([os.path.getsize(path + f) for f in files]) / (1024**2)
    print ('Files to load: ', numberoffile, ' - Size: {:0.3f}'.format(size), 'Mb')
    progressbarlen = 50
    atraitevery = numberoffile / float(progressbarlen)
    counter = 0.0
    stepcounter = atraitevery
    traitcounter = 0
    if numberoffile >= progressbarlen:
        biggerthanone = True
    else:
        biggerthanone = False

    sys.stdout.write("[%s]" % (" " * progressbarlen))
    sys.stdout.flush()
    sys.stdout.write("\b" * (progressbarlen+1)) # return to start of line, after '['


    # skip dir, parse all file matching ext

    queueIN = multiprocessing.Queue()
    queueOUT = multiprocessing.Queue()
    process = multiprocessing.cpu_count()
    for f in files:
        queueIN.put(f)

    proc = []

    tstart = time.time()

    for _ in range(process):
        looper = ImportLooper(path, queueIN, queueOUT, r, every, start, stop, \
            commentstring, delimiter, colnames, colid, col_pref, convert_comma)
        looper.start()
        proc.append(looper)
   

    fileindex = []

    for _ in files:
        k, w = queueOUT.get()
        datadict[k] = w

        # range limit check
        thismin = w.index.values.min()
        thismax = w.index.values.max()
        if thismin < timemin:
            timemin = thismin
        if thismax > timemax:
            timemax = thismax

        fileindex.append(k)

        # progress bar

        counter += 1
        if biggerthanone:
            if counter > stepcounter:
                sys.stdout.write("=")
                sys.stdout.flush()
                stepcounter += atraitevery
                traitcounter += 1
        else:
            while stepcounter < int(counter):
                sys.stdout.write("=")
                sys.stdout.flush()
                stepcounter += atraitevery
                traitcounter += 1

    for p in proc:
        p.terminate()

    for p in proc:
        p.join()
    

    # always progress bar
    if counter == stepcounter:
        sys.stdout.write("=")
        sys.stdout.flush()
        traitcounter += 1
    if traitcounter < progressbarlen:
        sys.stdout.write("=")
        sys.stdout.flush()
    sys.stdout.write("\n")

    tstop = time.time()
    t = tstop - tstart

    return DataObject(datadict, True, timemin, timemax, fileindex, hdf5name, t = t)

def timeseries(path, 
               commentstring=None, 
               colnames=None, 
               delimiter='[\s\t]+', 
               start=-float('inf'), 
               stop=float('inf'), 
               colid=None, 
               every=None):
    """
    Return a pytsa DataObject object from a single timeseries.

    Arguments:

    path string : where the file is located, in the form '/myworkingdir/timeseries.ext' (required)

    Keyword Arguments:

    commentstring string (default None) : the symbol that indicates a comment line like '#' or '//'
    colnames array-like (default None) : columns names, in the forma ['t', 'col1', 'col2']. If not set the name will be X1, X2 and so on, excluding time axis.
    delimiter string (default [\s\\t]+) : a regex. Default is whitespace.
    start float : first row to import based on time axis
    stop float : last row to import based on time axis
    """
    
    # microvalidation
    if start > stop:
        print('maybe start > stop ?\n')
    if colnames and colid:
        if len(colnames) != len(colid):
            print('colid and colnames must have same length!')
    if not colnames:
        col_pref = 'Y'
    else:
        col_pref = None

    if colid and delimiter != ',':
        print('column selection work only with delimiter = \',\' (yet)')

    source = CommentedFile(open(path, 'rb'), \
        commentstring=commentstring, low_limit=start, high_limit=stop, every=every)
    timedata = pd.read_csv(source, sep=delimiter, index_col=0, \
        header=None, names=colnames, usecols=colid, prefix=col_pref)
    source.close()

    # return DataObject Obj (isset = False)
    return DataObject(timedata, False, timedata.index.values.min(), timedata.index.values.max())

def loadHdf5(path):
    store = ts.openFile(path, 'r')
    table = store.root.info.desc
    isSet = table.attrs.isSet
    timemin = table.attrs.timemin
    timemax = table.attrs.timemax
    fileindex = list(table.attrs.fileindex)

    return DataObject(store, isSet, timemin, timemax, fileindex, path, newRp = None)

def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def grouper(n, iterable):
    "grouper(3, 'abcdefg') --> ('a','b','c'), ('d','e','f'), ('g', None, None)"
    return izip_longest(*[iter(iterable)]*n)



class DataObject:
    def __init__(self, 
                 data, 
                 isSet, 
                 timemin, 
                 timemax, 
                 fileindex=None, 
                 hdf5name = None, 
                 newRp = True,
                 t = None):

        # dataset or timeseries
        self.__data = data
        # what's the type
        self.__isSet = isSet
        # start with default terminal (supported type are png, pdf, ps, eps and svg)
        self.__outputs = set()
        self.__outputs.add('view')
        # range -> label:data (pandas df with index)
        self.__range = {}
        self.__row = {}
        self.__timemin = timemin
        self.__timemax = timemax
        self.__hdf5 = hdf5name
        self.__fpath = ''

        if fileindex is not None:
            self.__fileindex = fileindex

        if isSet:
            self.__columns = self.__data[self.__fileindex[0]].columns.values.tolist()
        else:
            self.__columns = self.__data.columns.values.tolist()
        
        if t:
            print('loaded ', len(self.__fileindex), ' files in ', round(t, 2), ' s')
        print('pyTSA data object successfully created, use function \'help()\' \nto see a list of functions that you can call on this object.\n')
        print('Default start value: ', round(self.__timemin, 6))
        print('Default stop value:  ', round(self.__timemax, 6))
        if(self.__isSet):
            print('\nComplete details for each column loaded:')
            for col in self.__columns:
                vmin = []
                vmax = []
                vmed = []
                vstd = []
                for ds in self.__fileindex:
                    vmin.append(self.__data[ds][col].min())
                    vmax.append(self.__data[ds][col].max())
                    vmed.append(self.__data[ds][col].mean())
                    vstd.append(self.__data[ds][col].std())
                print('\nColumn: ', col)
                print('min:  ', round(min(vmin), 6))
                print('max:  ', round(max(vmax), 6))
                print('mean: ', round(np.mean(vmed), 6))
                print('std:  ', round(np.mean(vstd), 6))

        if hdf5name and newRp:
            self.__data.close()
            store = ts.openFile(hdf5name, 'a')
            group = store.createGroup('/', 'info')
            table = store.createTable(group, 'desc', RedPandaInfo)
            table.attrs.isSet = self.__isSet
            table.attrs.timemin = self.__isSet = self.__timemin
            table.attrs.timemax = self.__isSet = self.__timemax
            table.attrs.fileindex =  self.__fileindex
            table.flush()
            store.close()
            

    def getTimemin(self):
        """
        Get current start time.

        To get this information you have to do this:

        >>> dataset.getTimemin()
        0.0"""
        return self.__timemin

    def getTimemax(self):
        """
        Get current stop time.

         To get this information you have to do this:

        >>> dataset.getTimemax()
        55.0"""
        return self.__timemax

    def getIndex(self):
        """
        Names of the files. 

        To get this information you have to do this:
        
        >>> timeseries.getIndex()
        [’timeS-1.data’,
        ’timeS-2.data’,
        ’timeS-3.data’]"""
        return self.__fileindex

    def getOutputs(self):
        """List of Active Outputs

        To get information about active outputs you have to do this:

        >>> dataset.getOutputs()
        [’view’, ’pdf’]"""
        return list(self.__outputs)

    def getColumns(self):
        """
        Names of the columns. 

        To get information about the names of the columns you have to do this:
        
        >>> timeseries.getColumns()
        [’X1’, ’X2’]"""
        return self.__columns

    def setTimemin(self, timemin):
        """
        Set new start time.

        Arguments:

        timemin int: 
        
        Usage:
        
        >>> dataset.setTimemax(15.0)"""
        self.__timemin = timemin

    def setTimemax(self, timemax):
        """
        Set new start time.

        Arguments:

        timemax int: 
        
        Usage:
        
        >>> dataset.setTimemax(55.0)"""
        self.__timemax = timemax

    
    def createrange(self, label, colname, start, stop, step):
        """
        Select a column and create a range from start to stop.

        Arguments:

        label string : name of the range. It will be used as key in a dictionary
        colname string : name of the column
        start float: the initial time
        stop float: the final time
        step float: This parameter indicates the discretization factor to be used to generate the graph"""
        if not self.__isSet:
            print('createrange works only on dataset')
            return
        index = np.arange(start, stop, step)
        mean_df = pd.DataFrame(index=index)

        queueIN = multiprocessing.Queue()
        queueOUT = multiprocessing.Queue()
        process = multiprocessing.cpu_count()
        
        for k,v in self.__data.iteritems():
            queueIN.put((k, v))

        proc = []

        for _ in range(process):
            sampler = DataSampler(queueIN, queueOUT, start, stop, step, colname)
            sampler.start()
            proc.append(sampler)

        for _ in self.__data.iteritems():
            k, v = queueOUT.get()
            mean_df.insert(0, k, v)

        for p in proc:
            p.terminate()

        for p in proc:
            p.join()

        self.__range[label] = mean_df

    def addoutput(self, out):
        """
        Add a new output type.

        Arguments:
        out string: select outputs from png, pdf, ps, eps and svg

        To add a new output to the output list you have to do this:

        >>> dataset.addOutput('eps')"""
        if out in ['png', 'pdf', 'ps', 'eps', 'svg', 'view', 'txt']:
            self.__outputs.add(out)
        else:
            print(out, 'not in outputs')

    def deloutput(self, out):
        """
        Delete an output from output list.

        Arguments:
        out string: select outputs from png, pdf, ps, eps and svg

        To remove an output from the output list you have to do this:

        >>> dataset.delOutput('svg')"""
        if out in ['png', 'pdf', 'ps', 'eps', 'svg', 'view']:
            try:
                self.__outputs.remove(out)
            except:
                print(out, 'not in outputs')
        else:
            print(out, 'not in outputs')

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

    def getarow(self, index, col):
        value = float(index)
        to_return = np.array([])
        label = '_'.join((str(value), str(col)))
        for k, ts in self.__data.iteritems():
            try:
                fromthists = ts[col].truncate(after=value).tail(1).values[0]
            except:
                fromthists = 0.0
            to_return = np.append(to_return, fromthists)
        self.__row[label] = pd.Series(to_return)

    def getacolumn(self, col, start, stop, step, filename = None):
        '''
        filename  -> dataset
        !filename -> timeseries
        '''
        start = float(start)
        stop = float(stop)
        step = float(step)
        if filename:
            pass
        else:
            to_return = np.array([])
            while start < stop:
                try:
                    value = self.__data[col].truncate(after=start).tail().values[0]
                except:
                    value = 0.0
                to_return = np.append(to_return, value)
                start += step
        print(to_return)
        return to_return


    def splot(self, 
              start=None, 
              stop=None, 
              columns=None, 
              merge=None, 
              xkcd=None,
              numfiles=None,
              layout=None,
              hsize = 4,
              wsize = 8,
              xlabel = 'time',
              ylabel = 'value'):

        """
        Print a single time series or a set of time series.

        Keyword arguments:

        start float (default Timemin) : The initial time 
        stop float (default Timemax) : The final time
        columns array-like : columns names, in the form ['X1', 'X2']. If not set all the columns will be considered
        merge boolean (default None) : If default one column per axis, if True overlaps the axes
        numfiles int (default None) : Display only first numfiles file
        xkcd boolean (default None) : If you want xkcd-style

        The following code is an example of splot():

        >>> timeseries.splot(stop = 50, merge = True)

        >>> dataset.splot(stop = 100)"""
        if self.__hdf5:
            self.__data = pd.HDFStore(self.__hdf5, 'r')
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        if layout and merge:
            raise ValueError('Layout and merge is not a good idea')
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        start = float(start)
        stop = float(stop)
        if len(columns) == 1:
            merge = True

        def internalSplot():
            figname = 'Simple Plot'
            if self.__isSet:
                figname = figname + ' ' + ' '.join(columns)
                if merge:
                    fig = plt.figure()
                    ax = fig.add_subplot(111) 
                    filename = '_'.join(('ds_merge', columns[0], columns[-1], str(start), str(stop)))
                    for i, col in enumerate(columns):
                        drawn = 0
                        for ds in self.__fileindex:
                            data = self.__data[ds][col].truncate(before=start, after=stop)
                            data.plot(ax=ax, color=np.random.rand(3,1))
                            drawn += 1
                            if numfiles and drawn == numfiles:
                                break
                    ax.set_xlabel(xlabel)
                    ax.set_ylabel(ylabel)
                else:

                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)
                    filename = '_'.join(('ds', columns[0], columns[-1], str(start), str(stop)))

                    actualCol = 0
                    for i in range(r):
                        if actualCol >= len(columns):
                            break
                        for j in range(c):
                            if actualCol >= len(columns):
                                break
                            drawn = 0
                            for ds in self.__fileindex:
                                data = self.__data[ds][columns[actualCol]].truncate(before=start, after=stop)
                                data.plot(ax=axes[i][j], color=np.random.rand(3,1))
                                axes[i][j].set_xlabel('') 
                                drawn += 1
                                if numfiles and drawn == numfiles:
                                    break
                            actualCol += 1
                    fig.tight_layout(rect = [0, 0, 1, 0.95])
                    ax = fig.add_subplot(111, frame_on=False, visible=False)
                    ax.set_xticks([]) 
                    ax.set_yticks([]) 
                    ax.set_xlabel(xlabel, labelpad=20)
                    ax.set_ylabel(ylabel, labelpad=50)

            else:
                figname = figname + ' ' + ' '.join(columns)
                if merge:
                    fig = plt.figure()
                    ax = fig.add_subplot(111) 
                    filename = '_'.join(('ts_merge', columns[0], columns[-1], str(start), str(stop)))
                    for col in columns:
                        data = self.__data[col].truncate(before=start, after=stop)
                        data.plot(ax=ax, label=col)
                    plt.legend(loc='best')
                    ax.set_xlabel(xlabel)
                    ax.set_ylabel(ylabel)
                else: 
                    filename = '_'.join(('ts', columns[0], columns[-1], str(start), str(stop)))
                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)
                    actualCol = 0
                    for i in range(r):
                        if actualCol >= len(columns):
                            break
                        for j in range(c):
                            if actualCol >= len(columns):
                                break
                            data = self.__data[columns[actualCol]].truncate(before=start, after=stop)
                            data.plot(ax=axes[i][j], label=columns[actualCol])
                            axes[i][j].legend(loc='best')
                            axes[i][j].set_xlabel('')
                            actualCol += 1

                    fig.tight_layout(rect = [0.05, 0.05, 1, 0.95])
                    ax = fig.add_subplot(111, frame_on=False)
                    ax.set_xticks([]) 
                    ax.set_yticks([]) 
                    ax.set_xlabel(xlabel, labelpad=20)
                    ax.set_ylabel(ylabel, labelpad=50)
                    
            self.printto(filename, figname, 'traces/')
        
        if (xkcd):
            with plt.xkcd():
                internalSplot()
        else:
            internalSplot()

        
        plt.close()
        if self.__hdf5:
            self.__data.close()
        

    def phspace(self,
                columns,
                start=None, 
                stop=None,
                step=1,
                xkcd=None,
                numfiles=None,
                layout=None,
                hsize = 4,
                wsize = 8,
                xlabel = '',
                ylabel = ''):

        """
        Print the phase space of 2 columns

        Keyword arguments:

        columns array-like : columns names, in the form ['X1', 'X2']. If not set all the columns will be considered
        start float (default Timemin) : The initial time 
        stop float (default Timemax) : The final time
        numfiles int (default None) : Display only first numfiles file
        xkcd boolean (default None) : If you want xkcd-style

        The following code is an example of splot():

        >>> timeseries.phspace(['X1', 'X2'], stop = 50)

        >>> dataset.phspace(['X3', 'X5'], stop = 100)"""
        if self.__hdf5:
            self.__data = pd.HDFStore(self.__hdf5, 'r')
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        if layout and merge:
            raise ValueError('Layout and merge is not a good idea')
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (1, 1)
            if len(columns) != 2:
                raise ValueError('Columns must have length = 2')
        start = float(start)
        stop = float(stop)
        step = float(step)

        def internalPhspace():
            figname = 'Phase Space'
            if self.__isSet:

                raise Exception('These aren\'t the droids you\'re looking for...')

                figname = figname + ' ' + ' '.join(columns)

                r, c = layout
                if (r * c) < len(columns):
                    raise ValueError('too columns to represent')
                fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                h = (hsize * r) +1
                w = (wsize * c)
                fig.set_size_inches(w, h)
                filename = '_'.join(('ds', columns[0], columns[-1], str(start), str(stop)))

                actualCol = 0
                for i in range(r):
                    if actualCol >= len(columns):
                        break
                    for j in range(c):
                        if actualCol >= len(columns):
                            break
                        drawn = 0
                        for ds in self.__fileindex:
                            data = self.__data[ds][columns[actualCol]].truncate(before=start, after=stop)
                            data.plot(ax=axes[i][j], color=np.random.rand(3,1))
                            axes[i][j].set_xlabel('') 
                            drawn += 1
                            if numfiles and drawn == numfiles:
                                break
                        actualCol += 1
                fig.tight_layout(rect = [0, 0, 1, 0.95])
                ax = fig.add_subplot(111, frame_on=False, visible=False)
                ax.set_xticks([]) 
                ax.set_yticks([]) 
                ax.set_xlabel(xlabel, labelpad=20)
                ax.set_ylabel(ylabel, labelpad=50)

            else:
                # dev version
                figname = figname + ' ' + ' '.join(columns)
                col = [columns]                
                filename = '_'.join(('ts', columns[0], columns[-1], str(start), str(stop)))
                r, c = layout
                if (r * c) < len(col):
                    raise ValueError('too phase space to represent')
                fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                h = (hsize * r) +1
                w = (wsize * c)
                fig.set_size_inches(w, h)
                actualCol = 0
                for i in range(r):
                    if actualCol >= len(col):
                        break
                    for j in range(c):
                        if actualCol >= len(col):
                            break
                        c = col[actualCol]
                        x = self.getacolumn(c[0], start, stop, step)
                        y = self.getacolumn(c[1], start, stop, step)
                        label = c[0] + ' ' + c[1]
                        plt.plot(x, y, color=np.random.rand(3,1), axes=axes[i][j], label = label)
                        axes[i][j].legend(loc='best')
                        actualCol += 1

                fig.tight_layout(rect = [0.05, 0.05, 1, 0.95])
                ax = fig.add_subplot(111, frame_on=False)
                ax.set_xticks([]) 
                ax.set_yticks([]) 
                ax.set_xlabel(xlabel, labelpad=20)
                ax.set_ylabel(ylabel, labelpad=50)
                    
            self.printto(filename, figname, 'traces/')
        
        if (xkcd):
            with plt.xkcd():
                internalPhspace()
        else:
            internalPhspace()

        
        plt.close()
        if self.__hdf5:
            self.__data.close()

    def mplot(self):
        """
        Just to prevent error...
        """
        raise NameError('Sorry sir, no more mplot(). Try use aplot()!')

    def aplot(self, 
              start=None, 
              stop=None, 
              columns=None, 
              step=1, 
              merge=None, 
              xkcd=None,
              layout=None,
              hsize = 4,
              wsize = 8):

        """
        Average of a dataset.

        aplot() is used to plot the average of a set of time series. You can select a single
        column or a set of columns and also merge them. It does not work (obviously) on single time series. 
        Picks an observation from start to stop every step elements.

        Keyword arguments:

        start number (default Timemin) : The initial time
        stop number (default Timemax) : The final time
        step number (default 1) : Used in createRange()
        columns array-like (default None) : columns names, in the form ['X1', 'X2']. If not set all the columns will be considered
        merge boolean (default None) : If default one column per axis, if True overlaps the axes
        xkcd boolean (default None) : If you want xkcd-style

        The following code is an example of mplot():

        >>> dataset.aplot(start = 0, stop = 80)
        >>> dataset.aplot(start = 0, stop = 80, merge = True)"""
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        if layout and merge:
            raise ValueError('Layout and merge is not a good idea')
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        start = float(start)
        stop = float(stop)
        step = float(step)
        if len(columns) == 1:
            merge = True

        def internalMplot():
            if self.__isSet:
                figname = 'mean'
                if merge:
                    plt.figure()
                    filename = '_'.join(('mean_merge', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join(columns)
                        filetitle = '# mean al columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))
                    for col in columns:
                        thisrange = '_'.join((str(start), str(stop), str(step), str(col)))
                        if thisrange not in self.__range:
                            self.createrange(thisrange, col, start, stop, step)
                        if 'txt' in self.__outputs:
                            filedata.append(self.__range[thisrange].mean(1).values)
                        self.__range[thisrange].mean(1).plot(label=col)
                    plt.legend(loc='best')
                else:
                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)
                    filename = '_'.join(('mean', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join(columns)
                        filetitle = '# mean al columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))

                    # plot block
                    actualCol = 0
                    for i in range(r):
                        if actualCol >= len(columns):
                            break
                        for j in range(c):
                            if actualCol >= len(columns):
                                break
                            thisrange = '_'.join((str(start), str(stop), str(step), str(columns[actualCol])))
                            if thisrange not in self.__range:
                                self.createrange(thisrange, columns[actualCol], start, stop, step)
                            if 'txt' in self.__outputs:
                                filedata.append(self.__range[thisrange].mean(1).values)
                            self.__range[thisrange].mean(1).plot(label=columns[actualCol], ax=axes[i][j])
                            axes[i][j].legend(loc='best')
                            actualCol += 1
                    fig.tight_layout(rect = [0, 0, 1, 0.95])





                if 'txt' in self.__outputs:
                    self.printFromSeries(filename, filetitle, filedata)
                self.printto(filename, figname, 'averages/')

        if (xkcd):
            with plt.xkcd():
                internalMplot()
        else:
            internalMplot()

        plt.clf()
        plt.close()

    def sdplot(self, 
               start=None, 
               stop=None, 
               columns=None, 
               step=1, 
               merge=None, 
               xkcd=None,
               layout=None,
               hsize = 4,
               wsize = 8):

        """
        Standard Deviation of a dataset.

        sdplot() is used to plot the standard deviation of a set of time series. 
        You can select a single column or a set of columns and also merge them. 
        It does not work (obviously) on single time series.
        Picks an observation from start to stop every step elements.

        Keyword arguments:

        start number (default Timemin) : The initial time
        stop number (default Timemax) : The final time
        step number (default 1) : Used in createRange()
        columns array-like (default None) : columns names, in the form ['X1', 'X2']. If not set all the columns will be considered
        merge boolean (default None) : If default one column per axis, if True overlaps the axes
        xkcd boolean (default None) : If you want xkcd-style

        The following code is an example of sdplot():

        >>> dataset.sdplot(stop = 50)
        
        >>> dataset.sdplot(stop = 90, merge = True)"""
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        if layout and merge:
            raise ValueError('Layout and merge is not a good idea')
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        start = float(start)
        stop = float(stop)
        step = float(step)
        if len(columns) == 1:
            merge = True

        def internalSdplot():    
            if self.__isSet:
                figname = 'standard deviation'
                if merge:
                    plt.figure()
                    filename = '_'.join(('std_merge', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join([c + '_mean ' + c + '_std' for c in columns])
                        filetitle = '# mean al columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))
                    for col in columns:
                        thisrange = '_'.join((str(start), str(stop), str(step), str(col)))
                        if thisrange not in self.__range:
                            self.createrange(thisrange, col, start, stop, step)
                        if 'txt' in self.__outputs:
                            filedata.append(self.__range[thisrange].mean(1).values)
                            filedata.append(self.__range[thisrange].std(1).values)
                        self.__range[thisrange].std(1).plot(label=col)
                    plt.legend(loc='best')
                else:
                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)
                    filename = '_'.join(('std', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join([cl + '_mean ' + cl + '_std' for cl in columns])
                        filetitle = '# mean al columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))

                    # graphics block
                    actualCol = 0
                    for i in range(r):
                        if actualCol >= len(columns):
                            break
                        for j in range(c):
                            if actualCol >= len(columns):
                                break
                            thisrange = '_'.join((str(start), str(stop), str(step), str(columns[actualCol])))
                            if thisrange not in self.__range:
                                self.createrange(thisrange, columns[actualCol], start, stop, step)
                            if 'txt' in self.__outputs:
                                filedata.append(self.__range[thisrange].mean(1).values)
                                filedata.append(self.__range[thisrange].std(1).values)
                            self.__range[thisrange].std(1).plot(label=columns[actualCol], ax=axes[i][j])
                            axes[i][j].legend(loc='best')
                            actualCol += 1

                    fig.tight_layout(rect = [0, 0, 1, 0.95])

                if 'txt' in self.__outputs:
                    self.printFromSeries(filename, filetitle, filedata)
                self.printto(filename, figname, 'averages/')

        if (xkcd):
            with plt.xkcd():
                internalSdplot()
        else:
            internalSdplot()

        plt.close()


    def msdplot(self, 
                start=None, 
                stop=None, 
                columns=None, 
                step=1, 
                merge=None, 
                errorbar=None, 
                bardist=5, 
                xkcd=None,
                layout=None,
                hsize = 4,
                wsize = 8):

        """
        Mean with Standard Deviation.

        msdplot() is used to plot the mean and the standard deviation of a set of time series on the same image. 
        You can select a single column or a set of columns and also merge them. It doen not work (obviously) on single time series.
        Picks an observation from start to stop every step elements.

        start number (default Timemin) : The initial time
        stop number (default Timemax) : The final time
        step number (default 1) : Used in createRange()
        columns array-like (defaul None): columns names, in the form ['X1', 'X2']. If not set all the columns will be considered
        merge boolean (defaul None) : If default one column per axis, if True overlaps the axes
        xkcd boolean (default None) : If you want xkcd-style

        The following code is an example of msdplot() :

        >>> dataset.msdplot(stop = 90, errorbar = True, bardist = 15)

        >>> dataset.msdplot(stop = 110, merge = True)"""
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        if layout and merge:
            raise ValueError('Layout and merge is not a good idea')
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        start = float(start)
        stop = float(stop)
        step = float(step)
        if len(columns) == 1:
            merge = True

        def internalMsdplot():    
            if self.__isSet:
                figname = 'mean and standard deviation'
                if merge:
                    fig = plt.figure()
                    filename = '_'.join(('mean_std_merge', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join(columns)
                        filetitle = '# mean std all columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))
                    for col in columns:
                        thisrange = '_'.join((str(start), str(stop), str(step), str(col)))
                        if thisrange not in self.__range:
                            self.createrange(thisrange, col, start, stop, step)
                        if 'txt' in self.__outputs:
                            filedata.append(self.__range[thisrange].mean(1).values)
                            filedata.append(self.__range[thisrange].std(1).values)
                        mean = self.__range[thisrange].mean(1)
                        std = self.__range[thisrange].std(1)
                        mean.plot(label=col)
                        if errorbar:
                            xind = [t for i, t in enumerate(mean.index.values) if (i % bardist) == 0]
                            yval = [t for i, t in enumerate(mean.values) if (i % bardist) == 0]
                            yerr = [t for i, t in enumerate(std.values) if (i % bardist) == 0]
                            plt.errorbar(xind, yval, yerr=yerr, fmt=None)
                        else:
                            upper = mean + std
                            lower = mean - std
                            upper.plot(style='k--', legend=False)
                            lower.plot(style='k--', legend=False)
                    patches, labels = fig.get_axes()[0].get_legend_handles_labels()
                    fig.get_axes()[0].legend(patches[::3], labels[::3], loc='best')
                else:
                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)
                    filename = '_'.join(('mean_std', str(columns[0]), str(columns[-1]), str(start), str(stop)))
                    if 'txt' in self.__outputs:
                        filecolumns = ' '.join([cl + '_mean ' + cl + '_std' for cl in columns])
                        filetitle = '# mean std all columns \n# time ' + filecolumns
                        filedata = []
                        filedata.append(np.arange(start, stop, step))

                    # graphics block    
                    actualCol = 0
                    for i in range(r):
                        if actualCol >= len(columns):
                            break
                        for j in range(c):
                            if actualCol >= len(columns):
                                break
                            thisrange = '_'.join((str(start), str(stop), str(step), str(columns[actualCol])))
                            if thisrange not in self.__range:
                                self.createrange(thisrange, columns[actualCol], start, stop, step)
                            mean = self.__range[thisrange].mean(1)
                            std = self.__range[thisrange].std(1)
                            if 'txt' in self.__outputs:
                                filedata.append(mean.values)
                                filedata.append(std.values)
                            mean.plot(label=columns[actualCol], ax=axes[i][j])
                            if errorbar:
                                xind = [t for j, t in enumerate(mean.index.values) if (j % bardist) == 0]
                                yval = [t for j, t in enumerate(mean.values) if (j % bardist) == 0]
                                yerr = [t for j, t in enumerate(std.values) if (j % bardist) == 0]
                                axes[i][j].errorbar(xind, yval, yerr=yerr, fmt=None)
                            else:
                                upper = mean + std
                                lower = mean - std
                                upper.plot(style='k--', ax=axes[i][j], legend=False)
                                lower.plot(style='k--', ax=axes[i][j], legend=False)
                            handles, labels = axes[i][j].get_legend_handles_labels()
                            axes[i][j].legend([handles[0]], [labels[0]], loc='best')
                            actualCol += 1

                    fig.tight_layout(rect = [0, 0, 1, 0.95])
                if 'txt' in self.__outputs:
                    self.printFromSeries(filename, filetitle, filedata)
                self.printto(filename, figname, 'averages/')

        if (xkcd):
            with plt.xkcd():
                internalMsdplot()
        else:
            internalMsdplot()

        plt.clf()
        plt.close()

    def pdf(self, 
            time, 
            columns=None, 
            merge=None, 
            binsize=None, 
            numbins=None, 
            normed=False, 
            fit=False, 
            range=None, 
            xkcd=None,
            layout=None,
            hsize = 4,
            wsize = 8):

        """
        Probability Density Function (PDF).

        pdf() is used to plot the PDF histogram of a set of time series. 
        pdf() calculates the probability density function of a set of time series in a precise time instant.

        Arguments:

        time number : The time instant

        Keyword arguments:

        columns array-like (default None) : columns names, in the form [’X1’, ’X2’]. If not set all the columns will be considered
        merge boolean (default None) : If default one column per axis, if True overlaps the axes
        binsize number (default None) : Size of bins
        numbins number (default 1) : Number of bins, works if binsize not set.
        normed boolean (defaul None) : If True histogram will be scaled in range 0.0 - 1.0
        fit boolean (defaul None) : If True fits the histrogram with a gaussian, works if normed
        xkcd boolean (defaul None) : If you want xkcd-style"""
        time = float(time)
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        value = float(time)
        if len(columns) == 1:
            merge = True

        if numbins is None:
            numbins = 10

        def internalPdf(nbins):    
            if self.__isSet:
                figname = 'probability density function'
                if merge:
                    filename = '_'.join(('pdf_merge', str(columns[0]), str(columns[-1]), str(time)))
                    plt.figure()
                    minrange = None
                    maxrange = None
                    for col in columns:
                        thisrow = '_'.join((str(value), str(col)))
                        if thisrow not in self.__row:
                            self.getarow(value, col)
                        if not minrange or self.__row[thisrow].min() < minrange:
                            minrange = self.__row[thisrow].min()
                        if not maxrange or self.__row[thisrow].max() > maxrange:
                            maxrange = self.__row[thisrow].max()
                    print('range: ', minrange, ' - ', maxrange)
                    
                    if binsize:
                        nbins = int((maxrange - minrange) / binsize)

                    for col in columns:  
                        thisrow = '_'.join((str(value), str(col)))       
                        n, bins, patches = plt.hist(self.__row[thisrow].values, range=[minrange, maxrange], bins=nbins, \
                            normed=normed, alpha=0.5, label=col)
                        if fit:
                            if not normed:
                                raise ValueError('Fit only if normed')
                            else:
                                (mu, sigma) = stats.norm.fit(self.__row[thisrow].values)
                                x = np.arange(minrange, maxrange, ((maxrange-minrange) / 100))
                                y = mlab.normpdf(x, mu, sigma)
                                plt.plot(x, y, 'r--', linewidth=2)

                    plt.legend(loc='best')
                else:
                    filename = '_'.join(('pdf', str(columns[0]), str(columns[-1]), str(time)))
                    r, c = layout
                    if (r * c) < len(columns):
                        raise ValueError('too columns to represent')
                    fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
                    h = (hsize * r) +1
                    w = (wsize * c)
                    fig.set_size_inches(w, h)

                    # graphics block    
                    actualCol = 0
                    for i in py.range(r):
                        if actualCol >= len(columns):
                            break
                        for j in py.range(c):
                            if actualCol >= len(columns):
                                break
                            thisrow = '_'.join((str(value), str(columns[actualCol])))
                            if thisrow not in self.__row:
                                self.getarow(value, columns[actualCol])
                            minrange = self.__row[thisrow].min()
                            maxrange = self.__row[thisrow].max()
                            if binsize:
                                nbins = int((self.__row[thisrow].max() - self.__row[thisrow].min()) / binsize)
                            n, bins, patches = axes[i][j].hist(self.__row[thisrow].values, bins=nbins, range=range,\
                                normed=normed, alpha=0.75, label=columns[actualCol])
                            
                            if fit:
                                if not normed:
                                    raise ValueError('Fit only if normed')
                                else:
                                    (mu, sigma) = stats.norm.fit(self.__row[thisrow].values)
                                    x = np.arange(minrange, maxrange, ((maxrange-minrange) / 100))
                                    y = mlab.normpdf(x, mu, sigma)
                                    axes[i][j].plot(x, y, 'r--', linewidth = 2)

                            axes[i][j].legend(loc='best')
                            actualCol += 1

                    fig.tight_layout(rect = [0, 0, 1, 0.95])
                self.printto(filename, figname, 'p-density/')

        if (xkcd):
            with plt.xkcd():
                internalPdf(numbins)
        else:
            internalPdf(numbins)                
        
        plt.clf()
        plt.close()

    def pdf3d(self, 
              column, 
              moments, 
              binsize=None, 
              numbins=None, 
              normed=False, 
              fit=False, 
              vmax=None):

        """
        Probability Density Function 3D.

        Calculates the probability density function of a set of time series in an array of time instants

        Arguments:

        column string : column name, in the form 'X1'.
        time  array-like : The time instants in the form ['10', '22.5', '50']

        Keyword arguments:

        binsize number (default None) : Size of bins
        numbins number (default 10) : Number of bins, works if binsize not set
        normed boolean (default None) : If True histogram will be scaled in range 0.0 - 1.0
        fit boolean (default None) : If True fits the histrogram with a gaussian, works if normed
        vmax float (default None) : Cuts the upper part of the drawing area at vmax on the Z-axis

        The following code is an example of pdf3d():

        >>> dataset.pdf3d('X1', [10, 20, 30])"""
        moments = [float(x) for x in moments]
        moments.sort()
        figname = 'probability density function'
        filename = '_'.join(('pdf_3d', column, str(moments[0]), str(moments[-1])))
        if self.__isSet:
            minrange = None
            maxrange = None
            for moment in moments:
                thisrow = '_'.join((str(moment), str(column)))
                if thisrow not in self.__row:
                    self.getarow(moment, column)
                if not minrange or self.__row[thisrow].min() < minrange:
                    minrange = self.__row[thisrow].min()
                if not maxrange or self.__row[thisrow].max() > maxrange:
                    maxrange = self.__row[thisrow].max()
            print('range: ', minrange, ' - ', maxrange)
            if binsize:
                numbins = int((maxrange - minrange) / binsize)
            if not numbins:
                numbins = 10

            fig = plt.figure()
            ax = Axes3D(fig)

            for i, moment in enumerate(moments):
                thisrow = '_'.join((str(moment), str(column)))
                histogram, low_range, binsize, extrapoints = stats.histogram(self.__row[thisrow].values, \
                    numbins=numbins, defaultlimits=(minrange, maxrange))
                newx = np.array([low_range + (binsize * 0.5)])
                for index in py.range(1, len(histogram)):
                    newx = np.append(newx, newx[index-1] + binsize)
                

                if normed:
                    histogram = histogram / sum(histogram)

                ax.bar(newx, histogram, zs=i, zdir='y', alpha=0.5, width=binsize, label='A')

                if fit:
                    if not normed:
                        print ('Fit only if normed')
                        fit = False
                    else:
                        (mu, sigma) = stats.norm.fit(self.__row[thisrow].values)
                        gauss = mlab.normpdf(newx, mu, sigma)
                        ax.plot(newx, gauss, zs=i, zdir='y', c='r', ls='--', lw=2)

            if vmax:
                ax.set_zlim3d(0, vmax)

            ax.set_xlabel(column)
            ax.set_ylabel('moments')
            ax.set_ylim3d(-1, len(moments))
            yticks = [-1] + py.range(len(moments)) + [len(moments)]
            ytick_labels = [''] + moments + ['']
            ax.set_yticks(yticks)
            ax.set_yticklabels(ytick_labels)

            self.printto(filename, figname, 'p-density/')
            plt.clf()
            plt.close()

    def meq2d(self, 
              start=None, 
              stop=None, 
              columns=None, 
              step=1.0, 
              binsize=None, 
              numbins=None, 
              normed=True, 
              vmax=None,
              hsize = 4,
              wsize = 8):

        """
        Master Equation 2D.

        Keyword arguments:

        start number (default Timemin) : The initial time
        stop number (default Timemax) : The final time
        step numebr (default 1) : Used in createRange().
        columns array-like (default None) : columns names, in the form ['X1', 'X2']. If not set all the columns will be considered.
        binsize number (default None) : Size of bins
        numbins number (default 10) : Number of bins, works if binsize not set
        normed boolean (default None) : If True histogram will be scaled in range 0.0 - 1.0
        vmax number (default None) : Max value displayed on color bar

        The following code is an example of meq2d():

        >>> dataset.meq2d(stop=150)

        >>> dataset.meq2d(columns=['X2'], stop=200, numbins=30)"""

        # layour has been removed from parameters
        layout = None

        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        columns = self.columnsCheck(columns)
        if layout is None:
            layout = (len(columns), 1)
        step = float(step)
        moments = np.arange(start, stop, step)
        
        figname = 'Heatmap' + ' ' + ' '.join(columns)
        filename = '_'.join(('heatmap', columns[0], columns[-1], str(start), str(stop)))
        if self.__isSet:
            r, c = layout
            if (r * c) < len(columns):
                raise ValueError('too columns to represent')
            fig, axes = plt.subplots(nrows=r, ncols=c, squeeze=False)
            h = (hsize * r) +1
            w = (wsize * c)
            fig.set_size_inches(w, h)

            # graphics block    
            actualCol = 0
            for q in py.range(r):
                if actualCol >= len(columns):
                    break
                for j in py.range(c):
                    if actualCol >= len(columns):
                        break
                minrange = None
                maxrange = None
                newindex = np.array([])
                thesemoments = []
                for moment in moments:
                    thisrow = '_'.join((str(moment), str(columns[actualCol])))
                    if thisrow not in self.__row:
                        self.getarow(moment, columns[actualCol])
                    thesemoments.append(self.__row[thisrow])
                    if not minrange or self.__row[thisrow].min() < minrange:
                        minrange = self.__row[thisrow].min()
                    if not maxrange or self.__row[thisrow].max() > maxrange:
                        maxrange = self.__row[thisrow].max()
                    newindex = np.append(newindex, self.__row[thisrow].index.values)
                
                newindex = np.unique(np.append(newindex, np.arange(newindex.min(), newindex.max())))
                newindex.sort()
                
                if binsize:
                    numbins = int((maxrange - minrange) / binsize)
                if not numbins:
                    numbins = 10

                histogram, low_range, intbinsize, extrapoints = stats.histogram(thesemoments[0], numbins=numbins, \
                    defaultlimits=(minrange, maxrange))
                if normed:
                    histogram = histogram / sum(histogram)
                
                I = np.array(histogram)
                for k in py.range(1, len(thesemoments)):
                    histogram, low_range, intbinsize, extrapoints = stats.histogram(thesemoments[k], numbins=numbins, \
                        defaultlimits=(minrange, maxrange))
                    if normed:
                        histogram = histogram / sum(histogram)
                    I = np.vstack([I, histogram])

                value = np.array([low_range + (intbinsize * 0.5)])
                for index in py.range(1, len(histogram)):
                    value = np.append(value, value[index-1] + intbinsize)


                im = axes[q][j].imshow(I.T, aspect='auto', interpolation='nearest', \
                    extent=[moments[0], moments[-1], value[0], value[-1]],origin='lower', vmax=vmax)
                cbar = fig.colorbar(im, ax=axes[q][j])
                cbar.set_label('probability')
                actualCol += 1

            fig.tight_layout(rect = [0, 0, 1, 0.95])

            self.printto(filename, figname, 'm-equation/')
            plt.clf()
            plt.close()



    def meq3d(self, 
              column, 
              start=None, 
              stop=None, 
              step=1.0, 
              binsize=None, 
              numbins=None, 
              normed=True, 
              vmax=None):

        """
        Master Equation 3D.

        Calculates the Master Equation. Uses a 3D surface to display it.

        Arguments:

        column string : column name, in the form 'X1'

        Keyword arguments:

        start number (default Timemin) : The initial time
        stop number (default Timemax) : The final time
        step number (default 1) : Used in createRange()
        binsize number (default None) : Size of bins
        numbins number (default 10) : Number of bins, works if binsize not set
        normed boolean (default None) : If True histogram will be scaled in range 0.0 - 1.0

        The following code is an example of meq2d():

        >>> dataset.meq3d('X1', stop = 50)

        >>> dataset.meq3d('X1', start = 10, stop = 100, numbins = 30)"""
        if start is None:
            start = self.__timemin
        if stop is None:
            stop = self.__timemax
        step = float(step)
        moments = np.arange(start, stop, step)
        figname = 'Surface ' + column 
        filename = '_'.join(('surface', column, str(start), str(stop)))
        if self.__isSet:
            fig = plt.figure()
            ax = Axes3D(fig)
            
            minrange = None
            maxrange = None
            newindex = np.array([])
            thesemoments = []
            for moment in moments:
                thisrow = '_'.join((str(moment), str(column)))
                if thisrow not in self.__row:
                    self.getarow(moment, column)
                thesemoments.append(self.__row[thisrow])
                if not minrange or self.__row[thisrow].min() < minrange:
                    minrange = self.__row[thisrow].min()
                if not maxrange or self.__row[thisrow].max() > maxrange:
                    maxrange = self.__row[thisrow].max()
                newindex = np.append(newindex, self.__row[thisrow].index.values)
            
            newindex = np.unique(np.append(newindex, np.arange(newindex.min(), newindex.max())))
            newindex.sort()
            
            if binsize:
                numbins = int((maxrange - minrange) / binsize)
            if not numbins:
                numbins = 10

            #14 coherenche check
            numbins += 1

            histogram, low_range, intbinsize, extrapoints = stats.histogram(thesemoments[0], numbins=numbins, \
                defaultlimits=(minrange, maxrange))
            if normed:
                histogram = histogram / sum(histogram)
            
            I = np.array(histogram)
            for j in py.range(1, len(thesemoments)):
                histogram, low_range, intbinsize, extrapoints = stats.histogram(thesemoments[j], numbins=numbins, \
                    defaultlimits=(minrange, maxrange))
                if normed:
                    histogram = histogram / sum(histogram)
                I = np.vstack([I, histogram])

            value = np.array([low_range + (intbinsize * 0.5)])
            for index in py.range(1, len(histogram)):
                value = np.append(value, value[index-1] + intbinsize)

            X, Y = np.meshgrid(moments, value)
            surf = ax.plot_surface(X, Y, I.T, rstride=1, cstride=1, cmap=plt.cm.jet, \
                linewidth=0, antialiased=False)
            cbar = fig.colorbar(surf, shrink=0.5, aspect=5)
            cbar.set_label('probability')

            ax.set_xlabel('time')
            ax.set_ylabel(column)
            

        self.printto(filename, figname, 'm-equation/')
        plt.clf()
        plt.close()


    def printto(self, filename, figname = None, path = ''):
        if figname:
            plt.suptitle(figname)
        for out in self.__outputs:
            if out == 'view':
                plt.show()
            elif out == 'txt':
                pass
            else:
                fig = '.'.join((filename, out))
                if not os.path.isdir(path):
                    os.makedirs(path)
                fname = path + fig
                plt.savefig(fname)

    @staticmethod
    def printFromSeries(name, title, data):
        filename = name + '.data'
        with open(filename, 'w') as f:
            f.write(title)
            f.write('\n')
            for row in zip(*data):
                cols = [c for c in row]
                for col in cols:
                    f.write(str(col))
                    f.write('\t')
                f.write('\n')

    def columnsCheck(self, col):
        if col is None:
            return self.__columns
        if isinstance(col, str):
            col = col.split()
        for c in col:
            if c not in self.__columns:
                error = 'Column ' + c + ' not in columns'
                raise ValueError(error)
        return col


class RedPandaInfo(ts.IsDescription):
    pass
