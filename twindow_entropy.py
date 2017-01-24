from sets import *
import csv
import pickle
import numpy
import os
import operator
from string import Template
import collections
from scipy.cluster.vq import *
import scipy.stats
import midi
from imghdr import what

#Data cleaning and local keyfinding/transposition for the YJaMP tracks

#path = 'C:/Users/Andrew/Documents/DissNOTCORRUPT/MIDIunquant/' #local
path = '/lustre/scratch/client/fas/quinn/adj24/JazzMIDI/' #cluster
listing = os.listdir(path)
#testFile = 'C:/Users/Andrew/Documents/DissNOTCORRUPT/MIDIQuantized/Alex_1_1.mid'
#testFile = 'C:/Users/Andrew/Documents/DissNOTCORRUPT/MIDIQuantized/Julian_5_6.mid'

"""
OK, things to do:
1. Strip out tracks which contain no notes (DONE)
2. From the remaining tracks, determine the number of milli(micro?)secs per tick (DONE)
3. Get a list of the note events in absolute ticks (DONE)
4. Translate those absolute ticks into elapsed milli/microseconds (DONE)
5. Figure out the distribution of note lengths; choose a good one for windowing (SKIPPED)
6. Make a list of time slices in which we can look for notes (DONE)
7. Export time slices as a csv.  Mimic ycac? (DONE)
8. Now, go back and figure out how to make the windows overlapping. (DONE)
9. Weight the pc vectors from the time slices by duration (DONE)
10. Transpose all the things to local C (DONE)
"""


def midiTimeWindows(windowWidth,incUnit,solos=all,transpose=True):
    #Cleans raw midi data, producing binned windows of duration windowWidth sliding by step incUnit
    #If transpose = True, yields pitch class sets in each durational window, else MIDI note names
    
    #data we'll output: [millisecs at end of window, music21 chord, set of midi numbers,  pcs in order, file name]
    msandmidi = []
    #Load the pickled slices that have not been bass-normalized into types
    if transpose==True:
        openCSV = open('solokeys.csv','rb')
        allSlices = csv.reader(openCSV)
    for n, testFile in enumerate(listing):
        if solos != all:
            if testFile != solos:
                continue
        print path + testFile
        #If transpose, 
        if transpose==True:
            for slice in allSlices:
                if slice[0] == testFile:
                    theTonic = int(slice[1]) 
                    #print theTonic   
        #for use with import midi
        pattern = midi.read_midifile(path + testFile)
        #this line makes each tick count cumulative
        pattern.make_ticks_abs()
        #print pattern.resolution, testFile
        #print len(pattern)
        for i,track in enumerate(pattern):
            #numTracks += 1
            if len(track) < 50:
                #numShortTracks += 1
                continue
            #how many tempo events?
            tempEvents = 0
            noteEvents = 0
            for thing in track:
                #print thing
                if thing.__class__ == midi.events.NoteOnEvent:
                    noteEvents += 1
                if thing.__class__ == midi.events.SetTempoEvent:
                    microspt = thing.get_mpqn() / pattern.resolution
                    #print microspt
                    tempEvents +=1
            if noteEvents == 0:
                #numShortTracks += 1
                continue
            if tempEvents == 0:
                microspt = 500000 / pattern.resolution
            if tempEvents > 1:
                print 'hey, extra tempo event?'
                break
            #windowWidth = 100 #number of milliseconds wide each bin will be
            windows = []
            #Generate a window starting at each incUnit until last window exceeds track end
            startTime = 0
            #print track[-1]
            while startTime + windowWidth < track[-1].tick* microspt/1000:
                windows.append(collections.Counter())
                startTime += incUnit
            for m, thing in enumerate(track):
                #Now put each event into all the right windows
                absTicks = thing.tick * microspt/1000
                if thing.__class__ == midi.events.NoteOnEvent and thing.get_velocity() != 0:
                    #figure out how long it is by looking for off event
                    for s in range(m,len(track)):
                        if track[s].__class__ == midi.events.NoteOnEvent and track[s].get_velocity() == 0 and track[s].get_pitch() == thing.get_pitch():
                            endTick = track[s].tick* microspt/1000
                            diffTicks = endTick - absTicks
                            break
                        if track[s].__class__ == midi.events.NoteOffEvent and track[s].get_pitch() == thing.get_pitch():
                            endTick = track[s].tick* microspt/1000
                            diffTicks = endTick - absTicks
                            break
                        if s == len(track):
                            print 'No note end!',testFile
                    for j in range(len(windows)):
                        #weight considering four cases.  First, if the note off starts and ends inside the first window
                        if j*incUnit < absTicks < j*incUnit + windowWidth:
                            if endTick < j*incUnit + windowWidth:
                                windows[j][thing.get_pitch()] += int(round(diffTicks))
                            #next, if it starts in one and stretches to some future window
                            if endTick > j*incUnit + windowWidth:
                                windows[j][thing.get_pitch()] += int(round(j*incUnit + windowWidth - absTicks))
                        if j*incUnit > absTicks:
                            #if it started in some past window and ends in some future one
                            if endTick > j*incUnit + windowWidth:
                                windows[j][thing.get_pitch()] += windowWidth
                            #and last: if it started in some past window and ends in this one
                            if j*incUnit < endTick < j*incUnit + windowWidth:
                                windows[j][thing.get_pitch()] += int(round(endTick - j*incUnit))
                        #Once the note has ended, stop looking for places to stick it
                        if j*incUnit > endTick:
                            break
            for j in range(len(windows)):
                if sum(windows[j].values()) == 0:#skip the empty windows
                    continue
                if transpose==True:
                    #count up the transposed pitch vector
                    pitchClasses = collections.Counter()
                    for mid in windows[j]:
                        if windows[j][mid] == 0:
                            continue
                        pitchClasses[str((mid%12 - theTonic)%12)] +=  windows[j][mid]
                        msandmidi.append([(j)*incUnit,pitchClasses])
                elif transpose != True:
                    msandmidi.append([(j)*incUnit,windows[j]])
    #print msandmidi
    #package up a csv
    #print msandmidi
    '''
    #package up a csv
    fieldnames = ['ms window end','weighted MIDI','ordered PCs','file']
    fileName = Template('$siz $inc ms inc 1122.csv')
    csvName = fileName.substitute(siz = str(windowWidth), inc = str(incUnit))
    file = open(csvName, 'wb')
    lw = csv.writer(file)
    lw.writerow(fieldnames)
    for row in msandmidi:
        lw.writerow(row)
    '''
    #pickle
    if transpose==True:
        fpPickle = Template('$win ms pcCount trans.pkl')
    elif transpose != True:
        fpPickle = Template('$win ms midcount overlap.pkl')
    pickleName = fpPickle.substitute(win = windowWidth)
    pickle.dump(msandmidi, open(pickleName, "wb"))
    #return msandmidi

def entrop(solo=all):
    #go from 50ms to 60*1000 ms by doubling
    windowSize = 25
    EntropyatSize = []
    while windowSize < 60000:
        windowSize = windowSize*2
        print windowSize
        if windowSize <= 1000:
            incUnit = 25
        elif 1000 < windowSize < 10000:
            incUnit = 250
        else:
            incUnit = 1000
        if solo != all:
            msandmidi = midiTimeWindows(windowSize, incUnit, solos=solo)
        else:
            msandmidi = midiTimeWindows(windowSize,incUnit)
        entropies = []
        for i, row in enumerate(msandmidi):
            if i == 0:
                continue
            pcVector = []
            for j in range(12):
                pcVector.append(0.1)
            for mid, counts in row[1].iteritems():
                pcVector[mid%12] += counts
            #print pcVector, scipy.exp2(scipy.stats.entropy(pcVector,base=2))
            entropies.append(scipy.exp2(scipy.stats.entropy(pcVector,base=2)))
            #print windowSize,pcVector, entropies[-1]
        EntropyatSize.append([windowSize,scipy.average(entropies)])
        #now write the body of the table
    if solo != all:
        fileName = Template('$sol overlap window pc avg perp.csv')
        csvName =fileName.substitute(sol = solo.split('.')[0])
    else:
        csvName ='overlap window pc avg perp.csv'
    file = open(csvName, 'wb')
    lw = csv.writer(file)
    for row in EntropyatSize:
        lw.writerow(row)
        
def clusterPCVecs(windowWidth,clusters):
    fpPickle = Template('$win ms midcount overlap.pkl')
    pickleName = fpPickle.substitute(win = str(windowWidth))
    msandmidi = pickle.load( open (pickleName, 'rb') )
    pcVectors = []
    for i, row in enumerate(msandmidi):
        if i == 0:
            continue
        pcVector = []
        for j in range(12):
            pcVector.append(0.1)
        for mid, counts in row[1].iteritems():
            pcVector[mid%12] += counts
        pcVectors.append(pcVector)
    whitened = whiten(pcVectors)
    clustered = kmeans(whitened,clusters)
    print clustered
    csvTemp = str(windowWidth) + Template('ms $clus-kclusters.csv')
    csvName = csvTemp.substitute(clus = str(clusters))
    file = open(csvName, 'wb')
    lw = csv.writer(file)
    row1 = ['C','C#/Db','D','D#/Eb','E','F','F#/Gb','G','G#/Ab','A','Bb','B']
    lw.writerow(row1)
    for row in clustered[0]:
        lw.writerow(row)
    lw.writerow(clustered[1])
           

midiTimeWindows(400,25)
midiTimeWindows(800,25)
midiTimeWindows(1600,50)
midiTimeWindows(3200,50)
midiTimeWindows(6400,50)
midiTimeWindows(12800,250)
midiTimeWindows(25600,250)
midiTimeWindows(51200,250)
#entrop()
#clusterPCVecs(800,7)
#slidingEntropy('Alex_6_6_blueingreen.mid', 1000, 25)
