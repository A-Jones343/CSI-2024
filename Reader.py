import json
import pandas as pd
import math
import datetime


class Obj:
    machine = ""
    id = 0
    pullrate = None
    plies = None
    grade = None
    scrapFactor = 0
    po = None
    quantity = 0
    conversion = 0
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


class Avail:
    machine = ""
    po = ""

    startIPO = None
    endIPO = None
    startReserve = None
    endReserve = None

    start = 0
    end = 0

    weekTotal = 0
    id = 0
    quantity = 0
    grade = ""
    asset = 0

    def __init__(self, asset, machine):
        self.asset = asset
        self.machine = machine


class Quantity:
    quantity = 0
    id = 0
    loc = 0
    machine = ""

    def __init__(self, quantity, id, loc, machine):
        self.quantity = quantity
        self.id = id
        self.loc = loc
        self.machine = machine


class DemandTm:
    grade = ""
    id = 0
    demand = 0
    time = 0

    ppm = 0


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

    columnName = ["Machine", "ID", "PullRate", "Plies", "Grade", "ScrapFactor", "ProductPerMinute", "FeetPerLog", "RollPerLog", "SheetWidth", "Length", "Weight"]

    if(displayMax):
        pd.set_option('display.max_rows', None)
    
    df = pd.DataFrame(columns=columnName)

    for obj in list:
        if(math.isnan(obj.pullrate) == False and obj.rate != 0):
            df = pd.concat([pd.DataFrame([[obj.machine, obj.id, obj.pullrate, obj.plies, obj.grade, 
                                           obj.scrapFactor, obj.rate, obj.feetPerLog, 
                                           obj.rollPerLog, obj.sheetWidth, obj.length, obj.weight]], columns=columnName), df], ignore_index=True)
            

    df = df.where(pd.notnull(df), None)
    df = df.drop((df[(~df["Machine"].isin(["BI4 Machine", "TM3 Machine"])) & (df["FeetPerLog"].isin([None])) & (df["RollPerLog"].isin([None])) & (df["SheetWidth"].isin([None]))]).index)
    return df


def Available(Foldername):
    list = []
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\initialPOs.json", 'r') as f:
        data = json.load(f)

    for field, attribute in data.items():
        if(field == "ProductionUnit"):
            for asset, machine in attribute.items():
                obj = Avail(asset, machine)
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




    columnName = ["Machine", "ID", "Start of Initial PO", "End of Initial PO", "Process Order", "Grade", "Quantity", "Start of Reserve Time", "End of Reserve Time"]


    df = pd.DataFrame(columns=columnName)
    
    for obj in list:
        df = pd.concat([pd.DataFrame([[obj.machine, obj.id, obj.startIPO, obj.endIPO, obj.po, obj.grade, obj.quantity, obj.startReserve, obj.endReserve]], columns=columnName), df], ignore_index=True)
    
    rt = []

    
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\reservedTimes.json", 'r') as f:
        data = json.load(f)

        for field, attribute in data.items():
            if(field == "ProductionUnit"):
                for asset, machine in attribute.items():
                    for dfMachine in df["Machine"]:
                        search = df['Machine'].str.contains(machine)
                        if(machine == dfMachine):
                            rt.append(df[search].index)

            if(field != "ProductionUnit"):
                for key, val in attribute.items():
                    
                    for i in range(len(rt)):
                        if(field == "ForecastStartTime"):
                            df.at[rt[i][0], "Start of Reserve Time"] = val
                        else:
                            df.at[rt[i][0], "End of Reserve Time"] = val
    return df
    

# Total time should be in minutes
def getQuantity(totalTime, id, Foldername):
    q = []
    df = Reader(Foldername, False)

    search = df['ID'].str.contains(id)
    values = df[search].index
    for i in range(len(values)):
        ForcastQ = df.loc[values[i], "ProductPerMinute"] * totalTime

        machine = df.loc[values[i], "Machine"]
        q.append(Quantity(ForcastQ, id, values[i], machine))
    return tuple(q)


def getTimeDifference(start, end):
    start = datetime.datetime.fromtimestamp(start/1000)
    end = datetime.datetime.fromtimestamp(end/1000)

    return (end - start)
    

def demandReader(Foldername):
    d = []
    with open("C:\\Users\\ajone\\OneDrive\\Desktop\\HackathonPackageV2\\HackathonPackageV2\\DataCache\\OptimizerSituations\\" + Foldername + "\\plannedDemandConverting.json", 'r') as f:
        data = json.load(f)
    for key, val in data.items():
        d.append((key, val))

    return tuple(d)


def Availibility(Foldername, machine):
    df = Available(Foldername)

    search = df['Machine'].str.contains(machine)
    values = df[search].index
    
    for i in range(len(values)):
        obj = Avail(None, machine)
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
        

def getMachine(df, id):
        search = df['ID'].str.contains(id)
        val = df[search].index

        for i in range(len(val)):
            r = df.loc[val[i], "Machine"]

        return r


def getTotalTime(obj):
    total = getTimeDifference(obj.start, obj.end)
    i = getTimeDifference(obj.startIPO, obj.endIPO)
    
    r = getTimeDifference(obj.startReserve, obj.endReserve)
    return (total - (r + i)).seconds /60


def search(Foldername, col, key, returnCell):
    df = Reader(Foldername, False)
    index = df.loc[df[col] == key].index[0]

    return df.at[index, returnCell]


def getTmDemand(Foldername, id, list, time):
    machine = search(Foldername, "ID", id, "Machine")
    grade = search(Foldername, "ID", id, "Grade")
    Mppm = search(Foldername, "Grade", grade, "ProductPerMinute")

    sw = search(Foldername, "ID", id, "SheetWidth")

    weight = search(Foldername, "ID", id, "Weight")
    length = search(Foldername, "ID", id, "Length")

    plies = search(Foldername, "ID", id, "Plies")
    fpl = search(Foldername, "ID", id, "FeetPerLog")
    rpl = search(Foldername, "ID", id, "RollPerLog")

    ppm = search(Foldername, "ID", id, "ProductPerMinute")

    if(machine == "CFR1 Parent Rolls"):
        yardage = time * ppm * 36000 / 102.2
    
    elif(machine != "TM3 Machine" and machine != "BI4 Machine" and machine != "CFR1 Parent Rolls"):
        yardage = time * ppm * fpl * plies / 3 / rpl

    
    # get Time Amnt:
    time = yardage / (Mppm * 2204.62 / weight * length)


    grade = search(Foldername, "ID", id, "Grade")
    print("MPPM", Mppm, "TIME", time , "DEMAND", Mppm * time, "GRADE", grade)
    
    if(grade == "Grade1"):
        list[0].demand = list[0].demand + (Mppm * time)
        list[0].grade = "Grade1"
        list[0].time = time

    if(grade == "Grade2"):
        list[1].demand = list[1].demand + (Mppm * time)
        list[1].grade = "Grade2"
        list[1].time = time

    if(grade == "Grade3"):
        list[2].demand = list[2].demand + (Mppm * time)
        list[2].grade = "Grade3"
        list[2].time = time

    if(grade == "Grade4"):
        list[3].demand = list[3].demand + (Mppm * time)
        list[3].grade = "Grade4"
        list[3].time = time

    if(grade == "Grade5"):
        list[4].demand = list[4].demand + (Mppm * time)
        list[4].grade = "Grade5"
        list[4].time = time

    if(grade == "Grade6"):
        list[5].demand = list[5].demand + (Mppm * time)
        list[5].grade = "Grade6"
        list[5].time = time


    for obj in list:
        print("TIME", obj.time, "DEMAND", obj.demand, "GRADE", obj.grade)
    return tuple(list)


week = "2024-09-06 Week 1"
TmDemand = []

for i in range(6):
    TmDemand.append(DemandTm())

for id, demand in demandReader("2024-09-06 Week 1"):
    time = demand / search(week, "ID", id, "ProductPerMinute")
    print(time, search(week, "ID", id, "Machine"), id, search(week, "ID", id, "Grade") , search(week, "ID", id, "Plies"))




        









