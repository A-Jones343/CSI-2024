import json
import pandas as pd
import math
import datetime


class Obj:
    asset = 0
    machine = ""
    id = 0
    pullrate = None
    plies = None
    grade = None
    scrapFactor = 0

    quantity = 0
    demand = 0
    rate = 0
    
    feetPerLog = None
    rollPerLog = None
    sheetWidth = None

    length = None
    weight = None


    def __init__(self, machine, id):
        self.machine = machine
        self.id = id


class Schedule:
    machine = ""

    startIPO = None
    endIPO = None
    startReserve = None
    endReserve = None

    start = 0
    end = 0
    schedule = 0
    totalTime = 0
    id = 0
    quantity = 0
    grade = ""

    def __init__(self, asset, machine):
        self.asset = asset
        self.machine = machine


def demandReader(Foldername):

    id = []
    demand = []
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\plannedDemandConverting.json", 'r') as f:
        data = json.load(f)

    for key, val in data.items():
        id.append(key)
        demand.append(val)

    return (id, demand)


def Reader(Foldername, displayMax):
    list = []

    def getTMSpecs(Grade, obj):
        with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\SKU_TM_Specs.json", 'r') as f:
            data = json.load(f)

        for field, attribute in data.items():
            if(field == "Inv_Length"):
                for key, val in attribute.items():
                    if(key == Grade):
                        obj.length = val


            elif(field == "Inv_Weight"):
                for key, val in attribute.items():
                    if(key == Grade):
                        obj.weight = val


    # Reads in SKU_Pull_Rate_Dict
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\SKU_Pull_Rate_Dict.json", 'r') as f:
        data = json.load(f)

    for machine, attribute in data.items():
        for id, field in attribute.items():
            obj = Obj(machine, id)
            for key, val in field.items():
                if(key == "PullRate"):
                    obj.pullrate = val

                if(key == "Plies"):
                    obj.plies = val

                if(key == "Grade"):
                    obj.grade = val
                    getTMSpecs(val, obj)

            list.append(obj)
    f.close()

    # Reads in scrapFactor
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\scrapFactor.json", 'r') as f:
        data = json.load(f)
    
    for attribute in list:
        for key, val in data.items():
            if(attribute.grade == key):
                attribute.scrapFactor = val              
    f.close()

    # Reads in planningRateDict
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\planningRateDict.json", 'r') as f:
        data = json.load(f)
    
    for machine, val in data.items():
        for attribute, field in val.items():
            for obj in list:
                if(obj.id == attribute and obj.machine == machine):
                    obj.rate = field
    f.close()


# Reads in SKU_Converting_Specs_Dict
    with open("C:\\Users\\ajone\\OneDrive\\Documents\\GitHub\\CSI-2024\\DataCache\\OptimizerSituations\\" + Foldername + "\\SKU_Converting_Specs_Dict.json", 'r') as f:
        data = json.load(f)

    for machine, attribute in data.items():
        for id, field in attribute.items():
            for obj in list:
                if(obj.id == id and obj.machine == machine):
                    for key, val in field.items():
                        if(key == "Feet/Log"):
                            obj.feetPerLog = val
                        elif(key == "Rolls/Log"):
                            obj.rollPerLog = val
                        elif(key == "CFR1 Sheet Width"):
                            obj.sheetWidth = val

    columnName = ["Asset", "Machine", "ID", "PullRate", "Plies", "Grade", "ScrapFactor", "ProductPerMinute", "FeetPerLog", "RollPerLog", "SheetWidth", "Length", "Weight", "Demand", "Time"]

    if(displayMax):
        pd.set_option('display.max_rows', None)
    
    df = pd.DataFrame(columns=columnName)
    TM = ["5914", "1252", "10520", "1251", "1713", "391"]

    Asset = 10000

    for obj in list:
        if(math.isnan(obj.pullrate) == False and obj.rate != 0):
            df = pd.concat([pd.DataFrame([[Asset, obj.machine, obj.id, obj.pullrate, obj.plies, obj.grade, 
                                           obj.scrapFactor, obj.rate, obj.feetPerLog, 
                                           obj.rollPerLog, obj.sheetWidth, obj.length, obj.weight, 0, 0]], columns=columnName), df], ignore_index=True)
        Asset += 10
            

    df = df.where(pd.notnull(df), None)
    df = df.drop((df[(~df["Machine"].isin(["BI4 Machine", "TM3 Machine"])) & (df["FeetPerLog"].isin([None])) & (df["RollPerLog"].isin([None])) & (df["SheetWidth"].isin([None]))]).index)

    TM = df.drop(df[(df['Machine'] != 'TM3 Machine') & (df["Machine"] != 'BI4 Machine')].index)


    id, demand = demandReader(week)
    df = df.drop(df[(~df["ID"].isin(id))].index)

    for index, row in df.iterrows():
        ID = row["ID"]
        for i,d in zip(id, demand):
            if(i == ID):
                df.at[index, "Demand"] = d
                df.at[index, "Time"] = d / row["ProductPerMinute"]

    ref = df.drop_duplicates("ID")

    grades = getTMTime(ref, TM)

    for index, row in TM.iterrows():
        grade = row["Grade"]

        if(grade == "Grade1"):
            TM.at[index, "Time"] = grades[0]
        
        if(grade == "Grade2"):
            TM.at[index, "Time"] = grades[1]
        
        if(grade == "Grade3"):
            TM.at[index, "Time"] = grades[2]
        
        if(grade == "Grade4"):
            TM.at[index, "Time"] = grades[3]
        
        if(grade == "Grade5"):
            TM.at[index, "Time"] = grades[4]   
        
        if(grade == "Grade6"):
            TM.at[index, "Time"] = grades[5]



    for index, row in TM.iterrows():
        TM.at[index, "Demand"] = row["Time"] * row["ProductPerMinute"]

    df = pd.concat([TM, df])
    return df


def Available(Foldername):
    list = []
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\initialPOs.json", 'r') as f:
        data = json.load(f)

    for field, attribute in data.items():
        if(field == "ProductionUnit"):
            for asset, machine in attribute.items():
                obj = Schedule(asset, machine)
                list.append(obj)

        if(field == "ProcessOrder"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.po = val

        if(field == "Prod_Id"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.id = val

        if(field == "ForecastStartTime"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.startIPO = val

        if(field == "ForecastEndTime"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.endIPO = val
        
        if(field == "ForecastQuantity"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.quantity = val

        if(field == "Grade"):
            for asset, val in attribute.items():
                for obj in list:
                    if(obj.asset == asset):
                        obj.grade = val

    f.close()

    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\reservedTimes.json", 'r') as f:
        data = json.load(f)
    
    rt = []

    for field, attribute in data.items():
        for asset, machine in attribute.items():
            if(field == "ProductionUnit"):
                obj = Schedule(asset, machine)
                rt.append(obj)
        
        
        for asset, val in zip(attribute.items(), rt):
            if(field == "ForecastStartTime"):
                val.startReserve = asset[1]

            if(field == "ForecastEndTime"):
                val.endReserve = asset[1]
        
    for obj in range(0, (len(rt) - 1)):
        if(rt[obj].machine == rt[obj + 1].machine):
            rt[obj].startReserve = (rt[obj].startReserve, rt[obj + 1].startReserve)
            rt[obj].endReserve = (rt[obj].endReserve, rt[obj + 1].endReserve)
            rt.pop(obj + 1)
            break

    for i in list:
        for j in rt:
            if(i.machine == j.machine):
                i.startReserve = j.startReserve
                i.endReserve = j.endReserve

    for obj in list:
        if(obj.startIPO == None and obj.startReserve == None):
            obj.schedule = (obj.start, obj.end)

        elif(obj.startIPO != None and obj.startReserve == None):
            obj.schedule = (obj.endIPO, obj.end)
        
        elif(obj.startIPO != None and obj.startReserve != None and type(obj.startReserve) != tuple):
            obj.schedule = ((obj.endIPO, obj.startReserve), (obj.endReserve, obj.end))

        elif(obj.startIPO != None and obj.startReserve != None and type(obj.startReserve) == tuple):
            obj.schedule = ((obj.endIPO, obj.startReserve[0]), (obj.endReserve[0], obj.startReserve[1]), (obj.endReserve[1], obj. end))


    columnName = ["Machine", "ID", "Start of Initial PO", "End of Initial PO", "Process Order", "Grade", "Quantity", "Start of Reserve Time", "End of Reserve Time", "Schedule"]



    df = pd.DataFrame(columns=columnName)
    
    for obj in list:
        #print(obj.startReserve, obj.endReserve)
        df = pd.concat([pd.DataFrame([[obj.machine, obj.id, obj.startIPO, obj.endIPO, obj.po, obj.grade, obj.quantity, obj.startReserve, obj.endReserve, obj.schedule]], columns=columnName), df], ignore_index=True)
    

    return df


def getTimeDifference(start, end):
    start = datetime.datetime.fromtimestamp(start/1000)
    end = datetime.datetime.fromtimestamp(end/1000)

    return (end - start).seconds / 60
    

def Availibility(Foldername, machine):
    df = Available(Foldername)

    search = df['Machine'].str.contains(machine)
    values = df[search].index
    
    for i in range(len(values)):
        obj = Schedule(None, machine)
        #if(df.loc[values[i], "Start of Reserve Time"] != None):
        obj.startReserve = 0 if df.loc[values[i], "Start of Reserve Time"] == None else df.loc[values[i], "Start of Reserve Time"]

        obj.endReserve = 0 if df.loc[values[i], "End of Reserve Time"] == None else df.loc[values[i], "End of Reserve Time"]

        #if(df.loc[values[i], "Start of Initial PO"] != None):
        obj.startIPO = 0 if df.loc[values[i], "Start of Initial PO"] == None else df.loc[values[i], "Start of Initial PO"]
    
        obj.start = obj.startIPO
        machine = df.loc[values[i], "Machine"]

        if(machine == "TM3 Machine" or machine == "BI4 Machine"):
            obj.end = obj.startIPO + 777600000 
        else:
            obj.end = obj.startIPO + 604800000

        obj.endIPO = df.loc[values[i], "End of Initial PO"]

    return obj
        

def search(df, col, key, returnCell):
    index = df.loc[df[col] == key].index[0]
    return df.at[index, returnCell]


def getTMTime(ref, TM):
    def getIt(ref, ppm):
        
        if(ref["Machine"] == "CFR1 Parent Rolls"):
            return ((ref["Weight"] * ref["Demand"] * 36000) / (ref["SheetWidth"] * ppm * 2204.62 * ref["Length"]))
    
        elif(ref["Machine"] != "TM3 Machine" and ref["Machine"] !=  "BI4 Machine" and ref["Machine"] != "CFR1 Parent Rolls"):
            return ((ref["Weight"] * ref["Demand"] * ref["FeetPerLog"] * ref["Plies"]) / (3 * ref["RollPerLog"] * ppm * 2204.62 * ref["Length"]))
        
    g1 = g2 = g3 = g4 = g5 = g6 = 0

    for index, row in ref.iterrows():
        grade = row["Grade"]

        if(grade == "Grade1"):
            g1 += getIt(row, TM["ProductPerMinute"][2])
        
        if(grade == "Grade2"):
            g2 += getIt(row, TM["ProductPerMinute"][0])
        
        if(grade == "Grade3"):
            g3 += getIt(row, TM["ProductPerMinute"][3])
        
        if(grade == "Grade4"):
            g4 += getIt(row, TM["ProductPerMinute"][1])
        
        if(grade == "Grade5"):
            g5 += getIt(row, TM["ProductPerMinute"][5])
        
        if(grade == "Grade6"):
            g6 += getIt(row, TM["ProductPerMinute"][4])

    return (g1,g2,g3,g4,g5,g6)
    

week = "2024-09-06 Week 1"

def Scheduler(Foldername):
    rd = Reader(Foldername, False)
    av = Available(Foldername)

    
    startGrade = search(av, "Machine", "BI4 Machine", "Grade")
    
    for i in range(1):
        if(startGrade == "Grade1"):
            grade = rd.loc[rd["Grade"] == "Grade4"]
            print(grade)


            startGrade = "Grade4"
    
        if(startGrade == "Grade2"):
            grade = rd.loc[rd["Grade"] == "Grade3"]
            print(grade)


            startGrade = "Grade3"

        if(startGrade == "Grade3"):
            grade = rd.loc[rd["Grade"] == "Grade1"]

            startGrade = "Grade1"

        if(startGrade == "Grade4"):
            grade = rd.loc[rd["Grade"] == "Grade2"]


            TM = av.loc[av["Machine"] == "BI4 Machine"]
            machine = tuple(TM["Schedule"])

            WI = av.loc[(av["Grade"] == "Grade2") & (av["Machine"] != "BI4 Machine")]
            winder = tuple(WI["Schedule"])[0]

            
            for index, row in rd.itterows():
                Build(row, winder, row["Machine"])



            startGrade = "Grade2"

        
        
def toMilli(int):
    return int * 60000

def timeDifference(start, end):
    return end - start

def Build(df, schedule, machine):
    if(len(schedule) == 1):
        sect1 = timeDifference(schedule[0][0], schedule[0][1])
        timeReq = toMilli(search(df, "Machine", machine, "Time"))
        print(timeReq)

    elif(len(schedule) == 2):
        sect1 = timeDifference(schedule[0][0], schedule[0][1])
        sect2 = timeDifference(schedule[1][0], schedule[1][1])
        timeReq = toMilli(search(df, "Machine", machine, "Time"))
        print(timeReq)

    elif(len(schedule) == 3):
        sect1 = timeDifference(schedule[0][0], schedule[0][1])
        sect2 = timeDifference(schedule[1][0], schedule[1][1])
        sect3 = timeDifference(schedule[2][0], schedule[2][1])
        timeReq = toMilli(search(df, "Machine", machine, "Time"))

Scheduler(week)