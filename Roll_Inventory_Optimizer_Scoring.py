#import pymssql
import pandas as pd
import numpy as np
import json
#import pickle
import copy
#from requests.auth import HTTPBasicAuth
import os
from datetime import timedelta
from datetime import datetime
import pytz

import warnings
warnings.filterwarnings("ignore")

pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)

importAdditionalLibraries=True
if importAdditionalLibraries: #These libraries arent necessary for scoring but are valuable for visualization
    import plotly.express as px
    from matplotlib import pyplot as plt
    

def importSituation(situationPath): #Imports the Situation from each Week's Directory and properly formats the data to be able to be run through the scorer. 
    planningSchedule=pd.read_json(situationPath+r'\planningSchedule.json')
    planningSchedule[['ForecastStartTime','ForecastEndTime']]=planningSchedule[['ForecastStartTime','ForecastEndTime']].astype('datetime64[ms]')
    initialPOs=pd.read_json(situationPath+r'\initialPOs.json')
    initialPOs[['ForecastStartTime','ForecastEndTime']]=initialPOs[['ForecastStartTime','ForecastEndTime']].astype('datetime64[ms]')
    reservedTimes=pd.read_json(situationPath+r'\reservedTimes.json')
    reservedTimes[['ForecastStartTime','ForecastEndTime']]=reservedTimes[['ForecastStartTime','ForecastEndTime']].astype('datetime64[ms]')
    plannedDemandConverting=pd.read_json(situationPath+r'\plannedDemandConverting.json',typ='series')
    plannedDemandConverting.index=plannedDemandConverting.index.astype('int')
    plannedDemandTM=pd.read_json(situationPath+r'\plannedDemandTM.json',typ='series')
    plannedDemandTM.index=plannedDemandTM.index.astype('int')
    inventoryGradeCount=pd.read_json(situationPath+r'\inventoryGradeCount.json',typ='series')

    with open(situationPath+r'\planningRateDict.json','rb') as fp:
        planningRateDict = json.load(fp)
    with open(situationPath+r'\SKU_Pull_Rate_Dict.json','rb') as fp:
        SKU_Pull_Rate_Dict = json.load(fp)
    with open(situationPath+r'\SKU_Converting_Specs_Dict.json','rb') as fp:
        SKU_Converting_Specs_Dict = json.load(fp)
    planningRate={}
    for asset in planningRateDict:
        planningRate[asset]=pd.Series(planningRateDict[asset])
        planningRate[asset].index=planningRate[asset].index.astype('int')
    SKU_Pull_Rate={}
    for asset in SKU_Pull_Rate_Dict:
        SKU_Pull_Rate[asset]=pd.DataFrame(SKU_Pull_Rate_Dict[asset]).T
        SKU_Pull_Rate[asset].index=SKU_Pull_Rate[asset].index.astype('int')
    SKU_Converting_Specs={}
    for asset in SKU_Converting_Specs_Dict:
        SKU_Converting_Specs[asset]=pd.DataFrame(SKU_Converting_Specs_Dict[asset]).T
        SKU_Converting_Specs[asset].index=SKU_Converting_Specs[asset].index.astype('int')
        
        
    SKU_TM_Specs=pd.read_json(situationPath+r'\SKU_TM_Specs.json')
    scrapFactor=pd.read_json(situationPath+r'\scrapFactor.json',typ='series')
    currentTimeUTC=pd.read_json(situationPath+r'\currentTimeUTC.json',typ='series')
    currentTimeUTC=currentTimeUTC['currentTimeUTC'].to_pydatetime().replace(tzinfo=pytz.utc)
    #print('Data Imported and Formatted')
    
    return (planningSchedule,initialPOs,reservedTimes,plannedDemandConverting,plannedDemandTM,inventoryGradeCount,planningRate,SKU_Pull_Rate,SKU_Converting_Specs,SKU_TM_Specs,scrapFactor,currentTimeUTC)

def find_overlaps(df,startCol, endCol, thresh=1): #A threshold of 1 identifies 1 single overlap of 2 POs. A threshold of 2 identifies an overlap of 3 POs
    forecastRanges=pd.concat([df[startCol],df[endCol]])
    forecastRanges=forecastRanges.sort_values()
    forecastRanges=forecastRanges.drop_duplicates()
    overlaps = []
    for i, rangeStart in enumerate(forecastRanges):
        hitTimes=(df[startCol]<=rangeStart) & (rangeStart<df[endCol]) #No additional checks are necessary because it is impossible for an SKU to start or end in between the Forecast Ranges
        if hitTimes.sum()>thresh: #All ranges hit the original PO starttime so a overlap occurs with 2 hits or more
            overlaps.append({"Start": forecastRanges.iloc[i], "End": forecastRanges.iloc[i+1], "Overlaps": hitTimes.sum()-1, "Raw": df[hitTimes]}) #Don't need to worry about overflow because time at i+1 cannot be the start of the last interval with a valid hit.
    return overlaps

def officialScorer(situationDate, convertGrade, scheduleOver, simulate, plot):
    situationRoot='C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations'
    situationPath=situationRoot+'\\'+situationDate
    #Key Point 1
    (planningSchedule,
    initialPOs,
    reservedTimes,
    plannedDemandConverting,
    plannedDemandTM,
    inventoryGradeCount,
    planningRate,
    SKU_Pull_Rate,
    SKU_Converting_Specs,
    SKU_TM_Specs,
    scrapFactor,
    currentTimeUTC) = importSituation(situationPath)

    currentMinuteUTC=currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None)
    currentFiveMinutesUTC=currentTimeUTC.replace(minute=5*(currentTimeUTC.minute//5),second=0,microsecond=0,tzinfo=None)#round down to nearest 5 minute interval
    inventoryTotalLength=inventoryGradeCount*SKU_TM_Specs['Inv_Length']
    
    #Key Point 2
    planningSchedule['Grade']=planningSchedule[['ProductionUnit','Prod_Id']].apply(lambda x: SKU_Pull_Rate[x[0]].loc[x[1]]['Grade'],axis=1) #Get the Parent Roll Grade Type for each SKU using a ProductionUnit+Prod_Id lookup from the SKU_Pull_Rate
    planningSchedule['ProcessOrder']="PO-"+planningSchedule.reset_index().index.astype(str) #The proposed schedule will have Process Orders with unique identifiers based on the order they are entered. Only affects visualization
    planningSchedule['ProductionPlanStatus']='Proposed Schedule'
    planningSchedule['PredictedRemainingDuration']=(planningSchedule['ForecastEndTime']-planningSchedule['ForecastStartTime']).dt.total_seconds()/60 #Convert Start and End time to duration in minutes
    planningSchedule['PlanningRate']=planningSchedule.apply(lambda x: planningRate[x['ProductionUnit']].get(x['Prod_Id']),axis=1)
    planningSchedule['PlannedQuantity']=planningSchedule['ForecastQuantity'] #Unused. Storage of Manually labeled quantity. Overwriten by Duration*PlanningRate
    planningSchedule['ForecastQuantity']=planningSchedule['PredictedRemainingDuration']*planningSchedule['PlanningRate']
    
    #Downtime is treated like normal PO's but with no quantity, grade, or assigned Product Id
    reservedTimes['Prod_Id']=0 
    reservedTimes['ForecastQuantity']=0
    reservedTimes['Grade']='Downtime'
    reservedTimes['ProcessOrder']='Downtime'
    reservedTimes['ProductionPlanStatus']='Downtime'

    #Key Point 3
    SKU_Forecasting=pd.concat([initialPOs,planningSchedule,reservedTimes]) #Combine the proposed schedule, initial schedule, and downtimes together to form a combined schedule to simulate
    SKU_Forecasting=SKU_Forecasting.sort_values(['ProductionUnit','ForecastStartTime']) #Effectively groups the schedule by Asset then sorts the PO's in that Asset by Start Time
    SKU_Forecasting=SKU_Forecasting.reset_index()
    SKU_Forecasting['PredictedRemainingQuantity']=SKU_Forecasting['ForecastQuantity'] #For the proposed schedule, PredictedRemainingQuantity is the same as the Forecasted Quantity
    SKU_Forecasting['PredictedRemainingDuration']=(SKU_Forecasting['ForecastEndTime']-SKU_Forecasting['ForecastStartTime']).dt.total_seconds()/60 #Convert Start and End time to duration in minutes
    SKU_Forecasting.loc[:,['PullRate', 'InfrequentDelay']]=SKU_Forecasting.apply(lambda x: pd.Series([SKU_Pull_Rate[x['ProductionUnit']]['PullRate'].get(x['Prod_Id']), SKU_Pull_Rate[x['ProductionUnit']]['InfrequentDelay'].get(x['Prod_Id'])], index=['PullRate', 'InfrequentDelay']), axis=1)

    productionUnitWinders=[
        'PB1 Winder',
        'PB2 Winder',
        'PB3 Winder',
        'PB4 Winder',
        'PB5 Winder',
        'PB6 Winder',
        'L07 Winder',
        'L08 Winder',
        'L09 Winder',
        'L10 Winder',
        'L11 Winder', 
        'CFR1 Parent Rolls', 
    ]

    productionUnitConvertingLines=[
        'PB1 Winder',
        'PB2 Winder',
        'PB3 Winder',
        'PB4 Winder',
        'PB5 Winder',
        'PB6 Winder',
        'L07 Winder',
        'L08 Winder',
        'L09 Winder',
        'L10 Winder',
        'L11 Winder',
    ]

    productionUnitTMs=[
        'TM3 Machine',
        'BI4 Machine',
    ]

    #Key Point 4
    for winder in productionUnitWinders:
        specData=SKU_Converting_Specs[winder]
        isCurrentWinder=SKU_Forecasting['ProductionUnit']==winder
        if winder == 'CFR1 Parent Rolls':
            sheetWidths=SKU_Forecasting.loc[isCurrentWinder,'Prod_Id'].map(specData['CFR1 Sheet Width'])/36 #Sheet Width originally in inches: 36 inches in a yard
            SKU_Forecasting.loc[isCurrentWinder,'ForecastYardage']=SKU_Forecasting.loc[isCurrentWinder,'ForecastQuantity']*1000/sheetWidths #QuantityMSY*1000=QuantityY^2 -> QuantityY^2/WidthY=LengthY    (MSY=1000 sqr yards)
            SKU_Forecasting.loc[isCurrentWinder,'ForecastRemainingYardage']=SKU_Forecasting.loc[isCurrentWinder,'PredictedRemainingQuantity']*1000/sheetWidths #QuantityMSY*1000=QuantityY^2 -> QuantityY^2/WidthY=LengthY    (MSY=1000 sqr yards)
        else:
            pliesPerLog=SKU_Forecasting.loc[isCurrentWinder,'Prod_Id'].map(SKU_Pull_Rate[winder]['Plies'])
            yardsPerLog=SKU_Forecasting.loc[isCurrentWinder,'Prod_Id'].map(specData['Feet/Log'])*pliesPerLog/3 #Conversion: 3 Feet in a Yard    #If the roll is 2 ply, twice the number of yards are needed
            rollsPerLog=SKU_Forecasting.loc[isCurrentWinder,'Prod_Id'].map(specData['Rolls/Log'])
            SKU_Forecasting.loc[isCurrentWinder,'ForecastYardage']=SKU_Forecasting.loc[isCurrentWinder,'ForecastQuantity']*yardsPerLog/rollsPerLog #Quantity in rolls -> Quantity in Yards. 
            SKU_Forecasting.loc[isCurrentWinder,'ForecastRemainingYardage']=SKU_Forecasting.loc[isCurrentWinder,'PredictedRemainingQuantity']*yardsPerLog/rollsPerLog #Quantity in rolls -> Quantity in Yards. 

    isTM=SKU_Forecasting['ProductionUnit'].isin(productionUnitTMs)
    yardsPerRoll=SKU_Forecasting.loc[isTM,'Grade'].map(SKU_TM_Specs['Inv_Length'])
    weightPerRoll=SKU_Forecasting.loc[isTM,'Grade'].map(SKU_TM_Specs['Inv_Weight']) #Lbs
    SKU_Forecasting.loc[isTM,'ForecastYardage']=SKU_Forecasting.loc[isTM,'ForecastQuantity']*2204.62/weightPerRoll*yardsPerRoll*-1 #Schedule -> Metric Tons -> Lbs (1T=2204.62Lbs)-> Rolls -> Yardage   Assuming the Forecasted quantity is Inventory Rolls and not Reel Rolls and therefore do not need to multiply this by 2
    SKU_Forecasting.loc[isTM,'ForecastRemainingYardage']=SKU_Forecasting.loc[isTM,'PredictedRemainingQuantity']*2204.62/weightPerRoll*yardsPerRoll*-1
    SKU_Forecasting['PercentRemaining']=SKU_Forecasting['PredictedRemainingQuantity']/SKU_Forecasting['ForecastQuantity']
    SKU_Forecasting.loc[SKU_Forecasting['PercentRemaining']<0,'PercentRemaining']=0

    #Key Point 5
    SKU_Forecasting['ForecastDuration']=SKU_Forecasting['ForecastYardage']/SKU_Forecasting['PullRate']#+SKU_Forecasting['InfrequentDelay']
    SKU_Forecasting['ForecastRemainingDuration']=SKU_Forecasting['ForecastRemainingYardage']/SKU_Forecasting['PullRate']
    SKU_Forecasting.loc[SKU_Forecasting['ForecastRemainingDuration']<0,'ForecastRemainingDuration']=0 #Zero out if negative
    SKU_Forecasting.loc[SKU_Forecasting['ForecastRemainingDuration'].isna(),'ForecastRemainingDuration']=SKU_Forecasting.loc[SKU_Forecasting['ForecastRemainingDuration'].isna(),'PredictedRemainingDuration']
    SKU_Forecasting['ForecastRemainingDuration']=SKU_Forecasting['ForecastRemainingDuration']#+SKU_Forecasting['InfrequentDelay'] #How do you add Infrequent Delay to a partial run?

    #SKU_Forecasting['ProductionPlanStatusPriority']=SKU_Forecasting['ProductionPlanStatus'].map(ProductionPlanStatusPriorityMapping)
    SKU_Forecasting['PlannedSwitchoverTime']=SKU_Forecasting['ForecastStartTime'].shift(-1)-SKU_Forecasting['ForecastEndTime']#Estimates the planned downtime between Forecasted Production Starts. Should show future large downs
    SKU_Forecasting.loc[SKU_Forecasting['PlannedSwitchoverTime']<timedelta(0),'PlannedSwitchoverTime']=timedelta(0)
    SKU_Forecasting.loc[SKU_Forecasting.groupby('ProductionUnit').tail(1).index,'PlannedSwitchoverTime']=timedelta(0)


    SKU_Forecasting['TotalForecastedDuration']=pd.to_timedelta(SKU_Forecasting['ForecastRemainingDuration'],unit='m')+SKU_Forecasting['PlannedSwitchoverTime']
    SKU_Forecasting['TotalForecastedDurationCumSum']=SKU_Forecasting.groupby('ProductionUnit')['TotalForecastedDuration'].cumsum()

    forecastStarts=SKU_Forecasting.groupby('ProductionUnit').head(1)
    forecastStarts['ActiveTime']=forecastStarts['ForecastStartTime']
    forecastStarts.loc[(forecastStarts['ForecastStartTime']<=(currentTimeUTC-timedelta(days=0)).replace(tzinfo=None)) | (forecastStarts['ProductionPlanStatus']=='Active'),'ActiveTime']=currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None) #If a PO has already started or has been scheduled to have started, set the active time to the current time.

    #Key Point 6
    SKU_Forecasting['ActiveTime']=SKU_Forecasting['ProductionUnit'].map(forecastStarts.set_index('ProductionUnit')['ActiveTime'])
    SKU_Forecasting['ModelStartTime']=np.NaN
    SKU_Forecasting['ModelEndTime']=np.NaN
    SKU_Forecasting['ModelSwitchoverTime']=SKU_Forecasting['ActiveTime']+SKU_Forecasting['TotalForecastedDurationCumSum']
    startTimeLoyalists=productionUnitConvertingLines
    SKU_Forecasting.loc[SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists),'ModelStartTime']=SKU_Forecasting.loc[SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists),'ForecastStartTime']
    SKU_Forecasting.loc[forecastStarts[forecastStarts['ProductionUnit'].isin(startTimeLoyalists)].index,'ModelStartTime']=SKU_Forecasting.loc[forecastStarts[forecastStarts['ProductionUnit'].isin(startTimeLoyalists)].index,'ActiveTime']
    startTimeLoyalistsDF=SKU_Forecasting[SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists)]
    SKU_Forecasting.loc[startTimeLoyalistsDF[startTimeLoyalistsDF['ModelStartTime']<startTimeLoyalistsDF['ActiveTime']].index,'ModelStartTime']=SKU_Forecasting.loc[startTimeLoyalistsDF[startTimeLoyalistsDF['ModelStartTime']<startTimeLoyalistsDF['ActiveTime']].index,'ActiveTime'] #There was a rare condition where both the active PO as well as the next PO would overlap at the beginning of the week such that both had start times before the current times. Resolved by starting both at the active time and allowing overlap.
    SKU_Forecasting.loc[~SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists),'ModelStartTime']=SKU_Forecasting.loc[~SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists),'ModelSwitchoverTime']-SKU_Forecasting.loc[~SKU_Forecasting['ProductionUnit'].isin(startTimeLoyalists),'TotalForecastedDuration']
    SKU_Forecasting['ModelEndTime']=SKU_Forecasting['ModelStartTime']+pd.to_timedelta(SKU_Forecasting['ForecastRemainingDuration'],unit='m')

    activeTMTimeRemaining=SKU_Forecasting[SKU_Forecasting['ProductionUnit'].isin(productionUnitTMs) & (SKU_Forecasting['ProductionPlanStatus']=='Active')].drop_duplicates('ProductionUnit',keep='last').set_index('ProductionUnit')['PredictedRemainingDuration']
    activeTMTimeRemaining=pd.Series(index=productionUnitTMs,data=activeTMTimeRemaining) #Fill In Missing TMs
    activeTMTimeRemaining=activeTMTimeRemaining/60
    activeTMTimeRemaining=activeTMTimeRemaining.fillna(0)

    timeToNextTMPO=SKU_Forecasting[SKU_Forecasting['ProductionUnit'].isin(productionUnitTMs) & (SKU_Forecasting['ProductionPlanStatus']!='Active')].drop_duplicates('ProductionUnit',keep='first').set_index('ProductionUnit')['ForecastStartTime']
    timeToNextTMPO=pd.Series(index=productionUnitTMs,data=timeToNextTMPO) #Fill In Missing TMs
    timeToNextTMPO=(timeToNextTMPO-currentMinuteUTC).dt.total_seconds()/(60*60)
    timeToNextTMPO=timeToNextTMPO.fillna(0)


    forecastRanges=pd.concat([SKU_Forecasting['ModelStartTime'],SKU_Forecasting['ModelEndTime']])
    forecastRanges=forecastRanges.sort_values()
    forecastRanges=forecastRanges.drop_duplicates()
    forecastPairs=list(zip(forecastRanges[::1],forecastRanges[1::1]))
    forecastTimes=pd.Series(data = forecastRanges.index, index = forecastRanges.values)
    #for periodStart,periodEnd in forecastPairs:
    # forecastAssetGrades=pd.DataFrame(columns=productionUnitWinders+productionUnitTMs)
    # forecastAssetRates=pd.DataFrame(columns=productionUnitWinders+productionUnitTMs)
    forecastGradeRates=pd.DataFrame(columns=SKU_Forecasting['Grade'].unique())
    runoutGradeRates=pd.DataFrame(columns=SKU_Forecasting['Grade'].unique())
    
    #Key Point 7
    #print("Calculate Intervals")
    for rangeStart in forecastRanges:
        hitTimes=(SKU_Forecasting['ModelStartTime']<=rangeStart) & (rangeStart<SKU_Forecasting['ModelEndTime']) #No additional checks are necessary because it is impossible for an SKU to start or end in between the Forecast Ranges
        # forecastAssetGrades.loc[rangeStart]=SKU_Forecasting[hitTimes].drop_duplicates('ProductionUnit').set_index('ProductionUnit')['Grade'] #There will sometimes be overlap in the run schedules for a single line. We are currently assuming that the first PO has priority over the second PO but the opposite may be true as well. *ASSUMPTION* #Re-evaluate at a later date
        # forecastAssetRates.loc[rangeStart]=SKU_Forecasting[hitTimes].drop_duplicates('ProductionUnit').set_index('ProductionUnit')['PullRate']
        #forecastGradeRates.loc[rangeStart]=SKU_Forecasting[hitTimes].drop_duplicates('ProductionUnit').groupby('Grade')['PullRate'].sum() 
        #runoutGradeRates.loc[rangeStart]=SKU_Forecasting[hitTimes][SKU_Forecasting[hitTimes]['ProductionUnit'].isin(productionUnitWinders)].drop_duplicates('ProductionUnit').groupby('Grade')['PullRate'].sum() #Includes drop_duplicates. See next line vvv for explaination for why this was removed.
        forecastGradeRates.loc[rangeStart]=SKU_Forecasting[hitTimes].groupby('Grade')['PullRate'].sum() #Unlike with forecastAssetRates, forecastGradeRates does not drop duplicates because that will cut off the next PO if there is overlap. We assume for the sake of calculation, that multiple PO's can run on the same Line even though this is impossible. *ASSUMPTION* #Re-evaluate at a later date
        runoutGradeRates.loc[rangeStart]=SKU_Forecasting[hitTimes][SKU_Forecasting[hitTimes]['ProductionUnit'].isin(productionUnitWinders)].groupby('Grade')['PullRate'].sum()
    #print("Calculate Intervals Finished")
    runoutGradeEndtimes=SKU_Forecasting[SKU_Forecasting['ProductionUnit'].isin(productionUnitWinders)].sort_values('ModelEndTime').groupby('Grade').tail(1)
    runoutGradeEndtimesLookup=runoutGradeEndtimes.set_index('Grade')['ModelEndTime']

    runoutGradeSampled=runoutGradeRates.resample('S').ffill()[::60] #Resample forecasted time-ranges to minutes
    runoutGradeSampled.index=runoutGradeSampled.index.floor('min')
    runoutGradeSampledOriginal=runoutGradeSampled.copy()

    #Extend the Domain for the consumption by adding an "Average PO" at the end of each grade's last PO
    extendedDomain=pd.DataFrame(index=pd.date_range(runoutGradeSampled.index[-1]+timedelta(minutes=1),runoutGradeSampled.index[0]+timedelta(days=14),freq='min'),columns=runoutGradeSampled.columns)
    runoutGradeSampled=pd.concat([runoutGradeSampled,extendedDomain])
    for grade in runoutGradeEndtimesLookup.index:
        runoutGradeSampled.loc[runoutGradeEndtimesLookup[grade]:,grade]=runoutGradeRates.fillna(0).mean()[grade]

    runoutGradeYardageConsumed=runoutGradeSampled.fillna(0).cumsum()
    # runoutGradeYardageRemaining=inventoryTotalLength-runoutGradeYardageConsumed*(1+scrapFactor) #Multiply one of these by the scrap percentage to get total Usable Yards
    # runoutGradeRollsRemaining=runoutGradeYardageRemaining/SKU_TM_Specs['Inv_Length'] #When inventory is less then 20, replace this with the average of the other roll sizes or some other fallback
    # #print(runoutGradeRollsRemaining)
    # gradeHasUpcomingPOs=(runoutGradeRollsRemaining.iloc[0]-runoutGradeRollsRemaining.iloc[-1])>0
    # runoutTime=runoutGradeRollsRemaining.apply(lambda x: x[x<0].head(1).index,axis=0)
    # runoutTime.loc[runoutTime.apply(len)==0]=[[None]]*len(runoutTime[runoutTime.apply(len)==0])
    # runoutTime=runoutTime.apply(lambda x: x[0])
    # remainingTime=runoutTime-currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None)
    # remainingTimeHours=remainingTime.dt.total_seconds()/3600
    # remainingTimeHours[remainingTimeHours<0]=0
    # remainingTimeHours=remainingTimeHours.fillna(gradeHasUpcomingPOs.map({True:-1,False:-2})) #If no runout expected, remaining time is NA. If grade has upcoming PO, fill NA with -1, if No PO, fill with -2 
    # runoutGradeRollsResampled=runoutGradeRollsRemaining.resample('H').bfill()
    # runoutGradeRollsResampled.index=runoutGradeRollsResampled.index-timedelta(days=7)
    # runoutGradeRollsSevenDay=runoutGradeRollsResampled.loc[currentFiveMinutesUTC-timedelta(days=7):currentFiveMinutesUTC] #Changed the slice from referencing the 1 hour UTC time to 5 minute UTC time. This prevents the program for overwriting historical datapoints and prevents it from being an hour delayed

    #Key Point 8
    forecastGradeSampled=forecastGradeRates.resample('S').ffill()[::60] #Resample forecasted time-ranges to minutes
    forecastGradeSampled.index=forecastGradeSampled.index.floor('min')
    forecastGradeYardageConsumed=forecastGradeSampled.fillna(0).cumsum()
    forecastGradeYardageRemaining=inventoryTotalLength-forecastGradeYardageConsumed*(1+scrapFactor) #Multiply one of these by the scrap percentage to get total Usable Yards. Maybe apply the scrap percentage only to the converting component of the forecastGradeYardageConsumed which is comprised of a TM and Converting component
    #Key Point 9
    forecastGradeRollsRemaining=forecastGradeYardageRemaining/SKU_TM_Specs['Inv_Length'] #When inventory is less then 20, replace this with the average of the other roll sizes or some other fallback
    #print(forecastGradeRollsRemaining)
    forecastTime=forecastGradeRollsRemaining.apply(lambda x: x[x<0].head(1).index,axis=0)
    forecastTime.loc[forecastTime.apply(len)==0]=[[None]]*len(forecastTime[forecastTime.apply(len)==0])
    forecastTime=forecastTime.apply(lambda x: x[0])
    if len(forecastTime)==0:
        forecastTime=pd.Series(index=forecastTime.columns,data=pd.NaT)
    OOPTimeGrade=forecastTime-currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None)
    OOPTimeGradeHours=OOPTimeGrade.dt.total_seconds()/3600
    OOPTimeGradeHours[OOPTimeGradeHours<0]=0
    OOPTimeGradeHours=OOPTimeGradeHours.fillna(-1)
    forecastGradeRollsResampled=forecastGradeRollsRemaining.resample('H').bfill()
    forecastGradeRollsResampledCopy=forecastGradeRollsResampled.copy()
    forecastGradeYardageResampled=forecastGradeRollsResampled*SKU_TM_Specs['Inv_Length']
    forecastGradeRollsResampled.index=forecastGradeRollsResampled.index-timedelta(days=7)
    forecastGradeRollsSevenDay=forecastGradeRollsResampled.loc[currentFiveMinutesUTC-timedelta(days=7):currentFiveMinutesUTC] #Changed the slice from referencing the 1 hour UTC time to 5 minute UTC time. This prevents the program for overwriting historical datapoints and prevents it from being an hour delayed

    #forecastGradeRollsRemaining and runoutGradeSampled
    #runoutRatesFillNA=runoutGradeSampled.fillna(0)
    #runoutGradeYardageConsumed

    inventoryRollsLimitMax=pd.Series({
        'Grade1':120,
        'Grade2':145,
    })
    inventoryRollsLimitMin=pd.Series({
        'Grade1':0,
        'Grade2':25,
    })
    runoutTimeLimitMax=pd.Series({
        'Grade3':96,
        'Grade4':72,
        'Grade5':60,
        'Grade6':72,
    })
    runoutTimeLimitMin=pd.Series({
        'Grade3':24,
        'Grade4':24,
        'Grade5':24,
        'Grade6':24,
    })

    gradeAssignments={
        'Grade1':   'Grade1',
        'Grade2':   'Grade2',
        'Grade3':   'Grade3',
        'Grade4':   'Grade4',
        'Grade5':   'Grade5',
        'Grade6':   'Grade6',
        }
    gradeNAs=pd.Series(index=gradeAssignments.keys(),dtype='object')

    forecastGradeYardageResampled[inventoryRollsLimitMax.add_suffix('_Max').keys()]=inventoryRollsLimitMax*SKU_TM_Specs['Inv_Length'][inventoryRollsLimitMax.keys()]
    forecastGradeYardageResampled[inventoryRollsLimitMin.add_suffix('_Min').keys()]=inventoryRollsLimitMin*SKU_TM_Specs['Inv_Length'][inventoryRollsLimitMin.keys()]       

    runoutGradeYardageConsumedResampled=runoutGradeYardageConsumed.resample('H').bfill() #Takes the consumed yardage since the current time (assuming the TM's arent running) calculated using a cumsum from an earlier step and resampled for every hour...
    runoutGradeYardageConsumedResampled[gradeNAs.add_suffix('_Max').keys()]=runoutGradeYardageConsumedResampled[gradeNAs.keys()]
    runoutGradeYardageConsumedResampled[gradeNAs.add_suffix('_Min').keys()]=runoutGradeYardageConsumedResampled[gradeNAs.keys()]
    
    #Key Point 10
    #print("Calculate Time Domain")
    forecastTimeRemaining=pd.DataFrame(columns=forecastGradeYardageResampled.columns)
    for i,t in enumerate(forecastGradeYardageResampled.index):  #...Then it recalculates that cumsum at every future inventory level by simply subtracting out the sum of the preceeding consumption rates for the timestamp being calculated for. This makes it more efficient then recalculating the cumsum on the entire slice.
        if i==0:
            tempYardage=forecastGradeYardageResampled.loc[t]-(runoutGradeYardageConsumedResampled[t:])
        else:
            tempYardage=forecastGradeYardageResampled.loc[t]-(runoutGradeYardageConsumedResampled[t:]-runoutGradeYardageConsumedResampled.loc[t-timedelta(hours=1)])
        runoutTime=tempYardage.apply(lambda x: x[x<0].head(1).index,axis=0)
        runoutTime.loc[runoutTime.apply(len)==0]=[[None]]*len(runoutTime[runoutTime.apply(len)==0])
        runoutTime=runoutTime.apply(lambda x: x[0])
        forecastRemainingTime=runoutTime-t
        if len(forecastRemainingTime)==0:
            forecastRemainingTimeHours=-1
        else:
            forecastRemainingTimeHours=forecastRemainingTime.dt.total_seconds()/3600
            forecastRemainingTimeHours[forecastRemainingTimeHours<0]=0
            forecastRemainingTimeHours=forecastRemainingTimeHours.fillna(-1)
        forecastTimeRemaining.loc[t]=forecastRemainingTimeHours
        # if (t-currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None))>timedelta(days=2): Test the run out calculation in the middle of the week
        #     0/0
    #print("Calculate Time Domain Finished")
    # runoutGradeTimeToEndtime=runoutGradeEndtimesLookup.apply(lambda x: list((x-forecastTimeRemaining.index).total_seconds()/3600))
    # runoutGradeTimeToEndtime=pd.DataFrame(runoutGradeTimeToEndtime.values.tolist(), index=runoutGradeTimeToEndtime.index, columns=forecastTimeRemaining.index).T
    # runoutGradeTimeToEndtime[gradeNAs.keys()[~gradeNAs.keys().isin(runoutGradeTimeToEndtime.columns)]]=None #Add missing grades

    SKU_TM_Specs_Full=SKU_TM_Specs.T.copy()
    SKU_TM_Specs_Full.loc[:,SKU_TM_Specs['Inv_Length'].add_suffix('_Max').keys()]=SKU_TM_Specs.T.values
    SKU_TM_Specs_Full.loc[:,SKU_TM_Specs['Inv_Length'].add_suffix('_Min').keys()]=SKU_TM_Specs.T.values
    SKU_TM_Specs_Full=SKU_TM_Specs_Full.T

    #Key Point 11
    forecastTimeRemainingFull=forecastTimeRemaining.copy()
    forecastTimeRemainingFull[runoutTimeLimitMax.add_suffix('_Max').keys()]=runoutTimeLimitMax
    forecastTimeRemainingFull[runoutTimeLimitMin.add_suffix('_Min').keys()]=runoutTimeLimitMin
    forecastTimeRemainingFullSevenDay=forecastTimeRemainingFull.copy()
    forecastTimeRemainingFullSevenDay.index=forecastTimeRemainingFullSevenDay.index-timedelta(days=7)
    forecastTimeRemainingFullSevenDay=forecastTimeRemainingFullSevenDay.loc[currentFiveMinutesUTC-timedelta(days=7):currentFiveMinutesUTC]
    forecastTimeRemainingFull[forecastTimeRemainingFull==-1]=pd.NaT
    forecastTimeRemainingFullCopy=forecastTimeRemainingFull.copy()
    #forecastTimeRemainingFull=forecastTimeRemainingFull.astype('timedelta64[h]')
    forecastTimeRemainingFull=forecastTimeRemainingFull.apply(pd.to_timedelta,unit='hours', errors='raise')
    #print("Recalculate Inventory Domain")
    forecastGradeYardageRemainingFull=pd.DataFrame(columns=runoutGradeYardageConsumedResampled.columns)
    for i,t in enumerate(runoutGradeYardageConsumedResampled.index): 
        if (forecastTimeRemainingFull.index!=t).all(): #If t exceeds the timeIndexes of forecastTimeRemainingFull, break out of the loop
            break
        runoutTime=t+forecastTimeRemainingFull.loc[t]
        for grade in runoutGradeYardageConsumedResampled.columns:
            if pd.isnull(runoutTime[grade]) or not runoutGradeYardageConsumedResampled.index.isin([runoutTime[grade]]).any(): #Sometimes the runout time is beyond the indexes of the runoutGradeYardageConsumedResampled dataframe which needs to be handled. Replaces the runoutYardage with NA 
                #print(runoutGradeYardageConsumedResampled.index.isin([runoutTime[grade]]).any())
                runoutYardage=np.NaN
            else:
                runoutYardage=runoutGradeYardageConsumedResampled.loc[runoutTime[grade],grade]
            yardsConsumed=runoutYardage-runoutGradeYardageConsumedResampled.loc[t,grade]#-runoutGradeYardageConsumedResampled.loc[t-timedelta(hours=0)]
            forecastGradeYardageRemainingFull.loc[t,grade]=yardsConsumed
    #print("Recalculate Inventory Domain Finished")
    forecastGradeRollsRemainingFull=forecastGradeYardageRemainingFull/SKU_TM_Specs_Full['Inv_Length']
    forecastGradeRollsRemainingFullSevenDay=forecastGradeRollsRemainingFull.copy()
    forecastGradeRollsRemainingFullSevenDay.index=forecastGradeRollsRemainingFullSevenDay.index-timedelta(days=7)
    forecastGradeRollsRemainingFullSevenDay=forecastGradeRollsRemainingFullSevenDay.loc[currentFiveMinutesUTC-timedelta(days=7):currentFiveMinutesUTC]        
    forecastGradeRollsRemainingFullSevenDay['TOTAL_Min']=forecastGradeRollsRemainingFullSevenDay[gradeNAs.add_suffix('_Min').keys()].sum(axis=1)
    forecastGradeRollsRemainingFullSevenDay['TOTAL_Max']=forecastGradeRollsRemainingFullSevenDay[gradeNAs.add_suffix('_Max').keys()].sum(axis=1)
    forecastGradeRollsRemainingFullSevenDay.loc[forecastGradeRollsRemainingFullSevenDay['Grade3_Max']>250,'Grade3_Max']=250 #Temp Fix to add a cap to Grade3 until Jeff can decide a better Stored Runtime value then 4 Days for Grade3
    forecastGradeRollsRemainingFullSevenDay=forecastGradeRollsRemainingFullSevenDay.fillna(-1)
    forecastGradeRollsRemainingFullSevenDay[inventoryRollsLimitMin.keys()+'_Min']=inventoryRollsLimitMin
    forecastGradeRollsRemainingFullSevenDay[inventoryRollsLimitMin.keys()+'_Max']=inventoryRollsLimitMax

    pullRateTrendData=runoutGradeSampled.resample('H').bfill()

    # forecastAssetGrades=forecastAssetGrades.resample('S').ffill()[::60]
    # forecastAssetGrades.index=forecastAssetGrades.index.floor('min')
    # print('Computationally Expensive Remapping')
    # forecastAssetGradeYardage=forecastAssetGrades.apply(lambda x: x.map(forecastGradeYardageRemaining.loc[x.name]),axis=1)
    # print('Computationally Expensive Remapping Finished')
    # #forecastAssetTimes=forecastAssetGradeYardage.apply(lambda x: x[x<0].head(1).index)
    # print("Calculate OOP Times")
    # forecastAssetTimes=pd.Series() #Old code would break if all lines had OOP expected. Required a full rewrite
    # for asset in forecastAssetGradeYardage:
    #     assetTime=forecastAssetGradeYardage[asset][forecastAssetGradeYardage[asset]<0].head(1).index
    #     if len(assetTime)==0:
    #         assetTime=pd.NaT
    #     else:
    #         assetTime=assetTime[0]
    #     forecastAssetTimes[asset]=assetTime
    # print("Calculate OOP Times Finished")
    # #forecastAssetTimes.loc[forecastAssetTimes.apply(len)==0]=[[None]]*len(forecastAssetTimes[forecastAssetTimes.apply(len)==0])
    # #forecastAssetTimes=forecastAssetTimes.apply(lambda x: x[0])
    # if len(forecastAssetTimes)==0:
    #     forecastAssetTimes=pd.Series(index=forecastAssetTimes.columns,data=pd.NaT)
    # forecastAssetTimesGrades=pd.DataFrame(forecastAssetTimes).apply(lambda x: '' if x[0] is pd.NaT else forecastAssetGrades.loc[x[0],x.name], axis=1)
    # OOPTime=forecastAssetTimes-currentTimeUTC.replace(second=0,microsecond=0,tzinfo=None)
    # OOPTimeHours=OOPTime.dt.total_seconds()/3600
    # OOPTimeHours[OOPTimeHours<0]=0
    # OOPTimeHours=OOPTimeHours.fillna(-1)
    # print("Calculate OOP Grades")
    # OOPAssetGrade=pd.Series()
    # for asset in forecastAssetTimes.index:
    #     if pd.isnull(forecastAssetTimes[asset]):
    #         OOPAssetGrade[asset]=None
    #     else:
    #         OOPAssetGrade[asset]=forecastAssetGrades.loc[forecastAssetTimes[asset],asset]
    # print("Calculate OOP Grades Finished")

    #Key Point 12
    #print("Calculate Score")
    proposedSchedule=SKU_Forecasting[SKU_Forecasting['ProductionPlanStatus']=='Proposed Schedule']
    TMPOMinimumRuntime2hr=2*60
    HoursBelowTMPOMinimumRuntime2hr=(TMPOMinimumRuntime2hr-proposedSchedule[(proposedSchedule['PredictedRemainingDuration']<TMPOMinimumRuntime2hr) & proposedSchedule['ProductionUnit'].isin(productionUnitTMs)]['PredictedRemainingDuration']).sum()/60
    TMPOMinimumRuntime8hr=8*60
    HoursBelowTMPOMinimumRuntime8hr=(TMPOMinimumRuntime8hr-proposedSchedule[(proposedSchedule['PredictedRemainingDuration']<TMPOMinimumRuntime8hr) & proposedSchedule['ProductionUnit'].isin(productionUnitTMs)]['PredictedRemainingDuration']).sum()/60
    ConvertingPOMinimumRuntime8hr=8*60
    HoursBelowConvertingPOMinimumRuntime8hr=(ConvertingPOMinimumRuntime8hr-proposedSchedule[(proposedSchedule['PredictedRemainingDuration']<ConvertingPOMinimumRuntime8hr) & proposedSchedule['ProductionUnit'].isin(productionUnitWinders)]['PredictedRemainingDuration']).sum()/60

    SKU_Forecasting_Group=SKU_Forecasting.groupby('ProductionUnit')

    overlaps={}
    overlapDF=pd.DataFrame()
    overlapHours={}
    totalOverlapHours=0
    for asset, group in SKU_Forecasting_Group:
        overlaps[asset]=find_overlaps(group,'ForecastStartTime', 'ForecastEndTime', thresh=1)
        overlapHours[asset]=0
        for i in overlaps[asset]:
            overlapHours[asset]=overlapHours[asset]+(i['End']-i['Start']).total_seconds()*i['Overlaps']/3600 #Convert seconds of overlap to hours of overlap. Higher penalty for concurrent overlaps
            overlapDF=overlapDF.append({'ProductionUnit':asset,'ForecastStartTime':i['Start'],'ForecastEndTime':i['End']},ignore_index=True)

        totalOverlapHours=totalOverlapHours+overlapHours[asset]

    gradeChangesConverting=pd.DataFrame()
    gradeChangesConverting[['ProductionUnit','Grade','GradeChangeStart']]=SKU_Forecasting[SKU_Forecasting['ProductionUnit'].isin(productionUnitConvertingLines)][['ProductionUnit','Grade','ForecastEndTime']]
    gradeChangesConverting['GradeChangeEnd']=gradeChangesConverting['GradeChangeStart']+timedelta(hours=3)
    gradeChangesConvertingOverlaps=find_overlaps(gradeChangesConverting,'GradeChangeStart','GradeChangeEnd', thresh=2) #Get overlaps of 3 or more concurrent PO grade changes
    gradeChangesConvertingOverlapsDF=pd.DataFrame()
    for overlap in gradeChangesConvertingOverlaps:
        gradeChangesConvertingOverlapsDF=gradeChangesConvertingOverlapsDF.append({'GradeChangeStart':overlap['Start'],'GradeChangeEnd':overlap['End'],"Overlaps":overlap['Overlaps']},ignore_index=True)
    gradeChangesConvertingOverlapsDF['Duration']=gradeChangesConvertingOverlapsDF['GradeChangeEnd']-gradeChangesConvertingOverlapsDF['GradeChangeStart']
    #Grade Change Score is A*B   A: Hours of overlapping converting Grade Changes   B: # Overlapping Converting Grade Changes. You can’t grade change within 3 hours of all converting lines (No manpower). You can Grade Change 2 at a time but will penalize 3 or above
    gradeChangesConvertingHours=(gradeChangesConvertingOverlapsDF['Duration']*(gradeChangesConvertingOverlapsDF['Overlaps']-1)).sum().total_seconds()/3600

    #forecastGradeRollsRemainingFullSevenDay has the min/max info, however the roll counts should be reverted back to the original by pulling them from forecastGradeRollsSevenDay
    rollForecast7Day=forecastGradeRollsRemainingFullSevenDay.copy()
    rollForecast7Day.index=rollForecast7Day.index+timedelta(days=7)

    forecastGradeRollsSevenDayNoLimits=forecastGradeRollsSevenDay.copy()
    forecastGradeRollsSevenDayNoLimits.index=forecastGradeRollsSevenDayNoLimits.index+timedelta(days=7)

    gradeList=list(gradeAssignments.keys())
    rollForecast7Day[gradeList]=forecastGradeRollsSevenDayNoLimits[gradeList]

    gradeMinViolationHours={}
    gradeMaxViolationHours={}
    gradeOOPViolationHours={}
    gradeMinViolationHoursTotal=0
    gradeMaxViolationHoursTotal=0
    gradeOOPViolationHoursTotal=0
    for grade in gradeList:
        gradeMinViolationHours[grade]=(rollForecast7Day[grade]<rollForecast7Day[grade+'_Min']).sum()
        gradeMaxViolationHours[grade]=(rollForecast7Day[grade]>rollForecast7Day[grade+'_Max']).sum()
        gradeOOPViolationHours[grade]=(rollForecast7Day[grade]<0).sum()
        gradeMinViolationHoursTotal=gradeMinViolationHoursTotal+gradeMinViolationHours[grade]
        gradeMaxViolationHoursTotal=gradeMaxViolationHoursTotal+gradeMaxViolationHours[grade]
        gradeOOPViolationHoursTotal=gradeOOPViolationHoursTotal+gradeOOPViolationHours[grade]

    GradeChangeOrderViolations={
        ('Grade 1', 'Grade2'): True,
        ('Grade 3', 'Grade2'): True,
        ('Grade 2', 'Grade1'): True,
        ('Grade 4', 'Grade1'): True,
    }

    TM4GradeChanges=SKU_Forecasting[SKU_Forecasting['ProductionUnit']=='BI4 Machine'][['ProductionUnit','ProcessOrder','ProductionPlanStatus','Prod_Id','ForecastStartTime','ForecastEndTime','ForecastQuantity','Grade']]
    TM4GradeChanges['NextGrade']=SKU_Forecasting[SKU_Forecasting['ProductionUnit']=='BI4 Machine']['Grade'].shift(-1)
    TM4GradeChanges['GradeChanges']=list(zip(TM4GradeChanges['Grade'],TM4GradeChanges['NextGrade']))
    TM4GradeChanges['GradeChangeViolation']=TM4GradeChanges['GradeChanges'].map(GradeChangeOrderViolations)
    TM4GradeChanges['GradeChangeViolation']=TM4GradeChanges['GradeChangeViolation'].fillna(False)
    TM4GradeChangeOrderViolations=TM4GradeChanges['GradeChangeViolation'].sum()

    GradeChangeCountTM=planningSchedule['ProductionUnit'].isin(productionUnitTMs).sum()
    GradeChangeCountConverting=planningSchedule['ProductionUnit'].isin(productionUnitWinders).sum()

    #7 Days for Converting #9 Days for TM because the TM PO's duration can shrink significantly below 7 days
    SKU_Forecasting['EndtimeToCurrent']=SKU_Forecasting['ForecastEndTime']-currentMinuteUTC
    SKU_Forecasting.loc[SKU_Forecasting['ProductionUnit'].isin(productionUnitTMs),'BoundaryEndDelta']=timedelta(days=9)
    SKU_Forecasting.loc[~SKU_Forecasting['ProductionUnit'].isin(productionUnitTMs),'BoundaryEndDelta']=timedelta(days=7)
    SKU_Forecasting['BoundaryEndViolation']=SKU_Forecasting['EndtimeToCurrent']-SKU_Forecasting['BoundaryEndDelta']
    
    #hoursPerWeek=168
    #hoursOver1Week=((SKU_Forecasting['ForecastEndTime'].max()-SKU_Forecasting['ForecastStartTime'].min())-timedelta(hours=hoursPerWeek)).total_seconds()/3600
    #hoursOver1Week=((SKU_Forecasting[SKU_Forecasting['ProductionPlanStatus']=='Proposed Schedule']['ForecastEndTime'].max()-currentMinuteUTC)-timedelta(hours=hoursPerWeek)).total_seconds()/3600 #Don't include downtime or initial POs in the calculation for going over 168 hours / 1 week
    
    hoursBeyondEndBoundary=SKU_Forecasting[(SKU_Forecasting['BoundaryEndViolation']>timedelta(days=0)) & (SKU_Forecasting['ProductionPlanStatus']=='Proposed Schedule')]['BoundaryEndViolation'].sum().total_seconds()/3600 #Don't include downtime or initial POs in the calculation for going over 168 hours / 1 week

    proposedDemand=planningSchedule[~planningSchedule['ProductionUnit'].isin(productionUnitTMs)].groupby('Prod_Id')['ForecastQuantity'].sum() #The demand penalty only applies to converting demand. TM demand included solely as reference
    proposedDemandViolationPercentage=abs(1-proposedDemand/plannedDemandConverting)
    proposedDemandViolationPenalty=proposedDemandViolationPercentage.copy()
    proposedDemandViolationPenalty[proposedDemandViolationPercentage>0]=proposedDemandViolationPercentage[proposedDemandViolationPercentage>0]*100*0
    proposedDemandViolationPenalty[proposedDemandViolationPercentage>.02]=(proposedDemandViolationPercentage[proposedDemandViolationPercentage>.02]-.02)*100*50
    proposedDemandViolationPenalty[proposedDemandViolationPercentage>.05]=(proposedDemandViolationPercentage[proposedDemandViolationPercentage>.05]-.05)*100*2000+.05*100*50 #Adds the error from the 2% violation to make the transition smooth
    proposedDemandViolationPenaltyTotal=proposedDemandViolationPenalty.sum() #Already implements the multiplier. This is the score for demand

    GradePriorityRanking={ #The Higher the Priority, the Lower the number
        'Grade1':6,
        'Grade2':1,
        'Grade3':5,
        'Grade4':4,
        'Grade5':3,
        'Grade6':2,
    }

    rollsBelowMaxInventory=pd.DataFrame()
    for grade in gradeList:
        rollsBelowMaxInventory[grade]=rollForecast7Day[grade+'_Max']-rollForecast7Day[grade]
        rollsBelowMaxInventory.loc[rollsBelowMaxInventory[grade]<0,grade]=0
    rollsBelowMaxInventoryCount=rollsBelowMaxInventory.mean()
    rollsBelowMaxInventoryScore=0.1*rollsBelowMaxInventoryCount*1/pd.Series(GradePriorityRanking) #Already implements the multiplier. This is the score for Grade Priority Ranking
    rollsBelowMaxInventoryScoreTotal=rollsBelowMaxInventoryScore.sum()

    scoringBreakdown={
        'HoursBelowTMPOMinimumRuntime2hr':-10000*HoursBelowTMPOMinimumRuntime2hr,
        'totalOverlapHours':-10000*totalOverlapHours,
        'gradeOOPViolationHoursTotal':-1000*gradeOOPViolationHoursTotal,
        'gradeChangesConvertingHours':-1000*gradeChangesConvertingHours,
        'hoursBeyondEndBoundary':-1000*hoursBeyondEndBoundary,
        'gradeMinViolationHoursTotal':-250*gradeMinViolationHoursTotal,
        'proposedDemandViolationPenaltyTotal':-1*proposedDemandViolationPenaltyTotal, #Score Built In
        'HoursBelowTMPOMinimumRuntime8hr':-100*HoursBelowTMPOMinimumRuntime8hr,
        'HoursBelowConvertingPOMinimumRuntime8hr':-100*HoursBelowConvertingPOMinimumRuntime8hr,
        'TM4GradeChangeOrderViolations':-500*TM4GradeChangeOrderViolations,
        'gradeMaxViolationHoursTotal':-50*gradeMaxViolationHoursTotal,
        'GradeChangeCountTM':-1*GradeChangeCountTM,
        'GradeChangeCountConverting':-1*GradeChangeCountConverting,
        'rollsBelowMaxInventoryScoreTotal':-1*rollsBelowMaxInventoryScoreTotal, #Score Built In
    }
    totalScore=0
    for criteria in scoringBreakdown:
        totalScore=totalScore+scoringBreakdown[criteria]
    

    #print(pd.Series(scoringBreakdown))
    #print(totalScore)

    # import pickle
    # forecastRoot='d:\\otapps\\inventory_dev\\root\\DataCache\\HistoricalForecasts'
    # oldForecastPath=forecastRoot+'\\'+situationDate
    # with open(oldForecastPath+r'\forecastGradeRollsSevenDay.p','rb') as fp:
    #     comparisonForecastGradeRollsSevenDay = pickle.load(fp)
    # comparisonForecastGradeRollsSevenDay.index=comparisonForecastGradeRollsSevenDay.index+timedelta(days=7)
    # with open(oldForecastPath+r'\SKU_Forecasting.p','rb') as fp:
    #     oldForecast = pickle.load(fp)

    #Enable for converting grade change overlap visualization
    def ConvertingGradeChangeOverlapVisualizer():
        gradeChangesConverting['Color']='Schedule'
        gradeChangesConvertingOverlapsDF['Color']='Overlaps'
        gradeChangesConvertingOverlapsDF['ProductionUnit']='Overlaps'
        gradeChangesConvertingOverlapVisual=pd.concat([gradeChangesConverting,gradeChangesConvertingOverlapsDF])
        px.timeline(gradeChangesConvertingOverlapVisual, x_start="GradeChangeStart", x_end="GradeChangeEnd", y="ProductionUnit", color='Color').show()
        return
    
    def ScheduleOverlapVisualizer(mode='Overlay'):
        SKU_Forecasting_Schedule_Visual=SKU_Forecasting.copy()
        SKU_Forecasting_Schedule_Visual['Color']='Schedule'
        overlapDF['Color']='Overlap'
        SKU_Forecasting_Schedule_Visual=pd.concat([SKU_Forecasting_Schedule_Visual,overlapDF])
        #mode='Overlay'
        #mode='Group'
        if mode=='Group':
            px.timeline(SKU_Forecasting_Schedule_Visual, x_start="ForecastStartTime", x_end="ForecastEndTime", y="ProductionUnit", color='Color', hover_data=['ProcessOrder']).update_layout(barmode='group').show()
        else: #Overlay Mode
            px.timeline(SKU_Forecasting_Schedule_Visual, x_start="ForecastStartTime", x_end="ForecastEndTime", y="ProductionUnit", color='Color', hover_data=['ProcessOrder']).show()
        return
    def scheduleSimulationVisualizer():
        originalSchedule=pd.DataFrame()
        originalSchedule[['StartTime','EndTime','ProductionUnit','ProcessOrder']]=SKU_Forecasting[['ForecastStartTime','ForecastEndTime','ProductionUnit','ProcessOrder']]
        originalSchedule['Color']='Original Schedule'
        simulatedSchedule=pd.DataFrame()
        simulatedSchedule[['StartTime','EndTime','ProductionUnit','ProcessOrder']]=SKU_Forecasting[['ModelStartTime','ModelEndTime','ProductionUnit','ProcessOrder']]
        simulatedSchedule['Color']='Simulated Schedule'
        px.timeline(pd.concat([originalSchedule,simulatedSchedule]), x_start="StartTime", x_end="EndTime", y="ProductionUnit", color='Color', hover_data=['ProcessOrder']).update_layout(barmode='group').show()
        return
    
    def SKU_Forecasting_Visualizer():    
        px.timeline(SKU_Forecasting.sort_values(['ProductionPlanStatus','ProductionUnit']), x_start="ForecastStartTime", x_end="ForecastEndTime", y="ProductionUnit", color='ProductionPlanStatus', hover_data=['ProcessOrder']).show()
        return


    def plotInventory(gradeSelection='All'):
        if gradeSelection=='All':
            fig, ax = plt.subplots(3, 2)
            #((ax1, ax2), (ax3, ax4), (ax5, ax6))=ax
            fig.suptitle('Forecasted Inventory Levels and Limits by Grade')
            
            for i, grade in enumerate(gradeList):
                axis=fig.get_axes()[i]
                axis.set_title(grade)
                axis.set_ylabel('Rolls')
                axis.plot(rollForecast7Day[[grade,grade+'_Min',grade+'_Max']],label=['Predicted','Min','Max'])
                axis.legend(loc='upper right')
            plt.show()
            
        else:
            grade=gradeSelection
            plt.title(grade)
            plt.ylabel('Rolls')
            plt.plot(rollForecast7Day[[grade,grade+'_Min',grade+'_Max']],label=['Predicted','Min','Max'])
            plt.legend(loc='upper right')
        return

    # I changed this
    if(convertGrade == True):
        ConvertingGradeChangeOverlapVisualizer();
    if(scheduleOver):
        ScheduleOverlapVisualizer();
    if(simulate):
        scheduleSimulationVisualizer();
    if(plot):
        plotInventory();

    #print("Finished")
    return (totalScore, scoringBreakdown)
    
#situationDate='2024-09-06 Week 1'
#situationDate='2024-10-09'

#totalScore, scoringBreakdown = officialScorer(situationDate, False, False, False, False)
#print("Finished")


