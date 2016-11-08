import numpy as np
import subprocess
import os
from shutil import copyfile
import struct
from sklearn.utils.extmath import cartesian
import random
import re

PROJECT_DIR = "../" #ror-dam-simulation directory
CE_QUAL_W2_EXE = "../../bin/w2_ivf32_v372.exe"
CONTROL_DIR = PROJECT_DIR + "model-control-chain/"
TOKENIZED_CON_FILE = "w2_con_tokenized.npt"
CON_FILE = "w2_con.npt"
TEMPERATURE_FILE = "spr.opt"
QWO_FILE = "qwo_34.opt"
QOUT_FILE = "qot_br1.npt"
RSI_FILE = "rso%STEP%.opt"
CHAINING_FILE = CONTROL_DIR + "scripts/propagate.flow.sh"
ELEVATION_FILE = "wl.opt"

# Hyperparameters
EPSILON_GREEDY = 0.2 # TODO: Should start high & decrease over time
FUTURE_DISCOUNT = 0.95
STEP_SIZE = 0.01

# Actions
SPILLWAY_OUTFLOWS = [0, 500]
POWERHOUSE_OUTFLOWS = [0, 600, 1200]
HYPOLIMNAL_OUTFLOWS = [0, 500]

# Reward parameters
MIN_ELEVATION = 200
MAX_ELEVATION = 225

def modifyControlFile(fileDir, timeStart, timeEnd, year):
    with open(fileDir + CON_FILE, "w") as fout:
        with open(fileDir + "inputs/control/" + TOKENIZED_CON_FILE, "r") as fin:
            for line in fin:
                line = line.replace("%RSIFN%", RSI_FILE.replace("%STEP%", str(timeStart)))
                line = line.replace("%TMSTRT%", str(timeStart).rjust(8))
                line = line.replace("%TMEND_%", str(timeStart + timeStep).rjust(8))
                line = line.replace("%YEAR__%", str(year).rjust(8))
                fout.write(line)

def setAction(fileDir, timeStart, action, wb):
    line = str(timeStart+1).rjust(8)
    line += str(action[0]).rjust(8)
    line += str(action[1]).rjust(8)
    line += str(action[2]).rjust(8)
    line += "\n"
    with open(fileDir + QOUT_FILE, "a") as f:
        f.write(line)

def getReward(numDams):
    for i in range(1, numDams+1):
        wlFile = CONTROL_DIR + "wb" + str(i) + "/" + ELEVATION_FILE
        elevations = np.genfromtxt(wlFile, delimiter=",")
        elevation = np.mean(elevations[-1,1:-1])
        if elevation < MIN_ELEVATION or elevation > MAX_ELEVATION:
            return -1
    return 0

'''
    temps = np.genfromtxt(fileDir + TEMPERATURE_FILE, delimiter=",", skip_header=1, usecols = 4)
    # TODO: This is for one dam, do the same for other dams
    if gatesOn[0,1]:
        powerStr = int(np.sum(gatesOn[0,:2]))
        print powerStr
        qPowerGate = np.genfromtxt(fileDir + QWO_FILE, delimiter=",", skip_header=3, usecols=(1+powerStr))
    else:
        qPowerGate = 0
    print temps
    print qPowerGate
    return qPowerGate - np.mean(temps) #TODO: Calculate a reward
'''

def copyInYearFiles(year, numDams):
    copyfile( CONTROL_DIR + "wb1/inputs/QIN" + str(year) +".npt", CONTROL_DIR + "wb1/qin.npt")
    copyfile( CONTROL_DIR + "wb1/inputs/TIN" + str(year) +".npt", CONTROL_DIR + "wb1/tin.npt")
    for wb in range(1, numDams + 1):
        copyfile( CONTROL_DIR + "wb" + str(wb) + "/inputs/met" + str(year) +".npt", CONTROL_DIR + "wb" + str(wb) + "/met.npt")
        spinupDir =  CONTROL_DIR + "wb" + str(wb) + "/inputs/spinup/" + str(year)
        for f in os.listdir(spinupDir):
            filename = spinupDir + "/" + f
            if os.path.isfile(filename):
                copyfile( filename , CONTROL_DIR + "wb" + str(wb) + "/" + f)

def calculatePossibleActions():
    return cartesian((SPILLWAY_OUTFLOWS, POWERHOUSE_OUTFLOWS, HYPOLIMNAL_OUTFLOWS))

# TODO: Real state function here
def getState(timeStart, year):
    # Get QIN/TIN for today on Dam 1
    fieldwidths = (8, 8)  


    # Read last QIN/TIN for each of Dams 2-4
    # Weather Judgement
    # Water Level
    # Output Structure +/- 65 F / 16 C
    return np.random.randint(2, size=25)

def getAction(state, weights, possibleActions):
    if random.random() < EPSILON_GREEDY:
        return random.randrange(possibleActions.shape[0])
    else:
        [bestActionInd, Vopt] = getBestAction(state, weights, possibleActions)
        return bestActionInd

def getBestAction(state, weights, possibleActions):
    Qopts = np.empty(possibleActions.shape[0])
    for actionInd in range(possibleActions.shape[0]):
        Qopts[actionInd] = calculateQopt(state, actionInd, weights)
    bestActionIndices = np.argwhere(Qopts == np.max(Qopts))
    bestActionInd = random.choice(bestActionIndices)[0] # Make sure not always choosing first action if all valued same
    return bestActionInd, Qopts[bestActionInd]

def getFeatures(state, actionInd, shape):
    features = np.zeros(shape)
    features[:, actionInd] = state # TODO: Add a bias term?
    return features

def calculateQopt(state, actionInd, weights):
    features = getFeatures(state, actionInd, weights.shape)
    return weights.flatten().dot(features.flatten())

# TODO: Add regularization?
def updateWeights(state, actionInd, reward, nextState, weights, possibleActions):
    features = getFeatures(state, actionInd, weights.shape)
    [nextAction, Vopt] = getBestAction(nextState, weights, possibleActions)
    error = calculateQopt(state, actionInd, weights) - (reward + FUTURE_DISCOUNT * Vopt)
    return weights - STEP_SIZE * error * features


timeStart = 60
timeStep = 1
year = 2015

numDams = 4
numGates = 3 # per dam

copyInYearFiles(year, numDams)
for i in range(3):
    actionInd = getAction(state, weights, possibleActions)
    action = possibleActions[actionInd]

    for wb in range(numDams):
        wbDir = CONTROL_DIR + "wb" + str(wb + 1) + "/"
        modifyControlFile(wbDir, timeStart, timeStart + timeStep, year)
        setAction(wbDir, timeStart, action, wb) # TODO: Different actions for different dams
        path = os.getcwd()
        os.chdir(wbDir)
        subprocess.check_call(['wine', CE_QUAL_W2_EXE])
        os.chdir(path)
        if wb != (numDams - 1):
            subprocess.check_call([CHAINING_FILE, "wb" + str(wb+1), "wb" + str(wb+2)])

    reward = getReward(numDams)
    nextState = getState(timeStart + timeStep, year)
    weights = updateWeights(state, actionInd, reward, nextState, weights, possibleActions)

    timeStart = timeStart + timeStep
    state = nextState
